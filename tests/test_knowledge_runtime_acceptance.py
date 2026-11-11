"""Actual resident JSONL + isolated Qdrant/model lifecycle, no private sources."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
from server_benchmark import Server

SCRATCH = Path('C:/Users/johan/AppData/Local/hermes/cache/scratch')
RUN = REPO / 'artifacts/knowledge-runtime' / uuid.uuid4().hex


class ResidentLifecycle(unittest.TestCase):
    def test_actual_agent_fresh_process_lifecycle(self):
        self.assertTrue((REPO / 'tools/knowledge_runtime/__main__.py').is_file(),
                        'runnable resident package is missing')
        RUN.mkdir(parents=True)
        root = Path(tempfile.mkdtemp(prefix='knowledge-runtime-', dir=SCRATCH))
        server_root = root / 'server'
        server_root.mkdir()
        server = Server(server_root)
        source = root / 'sources'
        source.mkdir()
        fixture = source / 'fixture.md'
        fixture.write_bytes(b'# Comet\nAtomic SQLite backup preserves the release database.\n')
        (source / 'not-allowed.md').write_text('Never ingest this sentinel.', encoding='utf-8')
        collection = 'akr_' + uuid.uuid4().hex
        transcript, processes, logs = [], [], []
        cleanup = {}
        argv = []
        def save(name, data):
            (RUN / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        def spawn(create=False):
            command = argv + (['--create'] if create else [])
            log = (RUN / f'worker-{len(processes)}.stderr').open('w')
            logs.append(log)
            start = time.perf_counter()
            proc = subprocess.Popen(command, cwd=REPO, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=log, text=True, encoding='utf-8', bufsize=1)
            processes.append(proc)
            lines = queue.Queue()
            def reader():
                for line in proc.stdout:
                    lines.put(line)
            thread = threading.Thread(target=reader, daemon=True)
            thread.start()
            def receive():
                try:
                    raw = lines.get(timeout=40)
                except queue.Empty:
                    self.fail(f'worker response timeout; exit={proc.poll()}')
                response = json.loads(raw)
                transcript.append({'pid': proc.pid, 'response': response})
                return response
            ready = receive()
            transcript.append({'argv': command, 'cold_wall_ms': (time.perf_counter()-start)*1000})
            self.assertTrue(ready['ready'], ready)
            def call(request, ok=True):
                request = dict(request, request_id=str(len(transcript)))
                transcript.append({'pid': proc.pid, 'request': request})
                proc.stdin.write(json.dumps(request) + '\n')
                proc.stdin.flush()
                response = receive()
                self.assertEqual(response['ok'], ok, response)
                self.assertEqual(response['request_id'], request['request_id'])
                return response.get('result', response)
            def stop():
                proc.stdin.close()
                proc.wait(timeout=15)
                thread.join(timeout=3)
                proc.stdout.close()
                self.assertFalse(thread.is_alive())
                self.assertEqual(proc.returncode, 0)
            return ready, call, stop
        try:
            server.start()
            argv.extend([sys.executable, '-m', 'tools.knowledge_runtime', '--db', str(root/'authority.sqlite'),
                         '--model', str(REPO/'artifacts/models/minilm'), '--qdrant-url', f'http://127.0.0.1:{server.port}',
                         '--collection', collection, '--allow-root', str(source), '--allow-file', 'fixture.md', '--write'])
            ready, call, stop = spawn(create=True)
            self.assertEqual(call({'op': 'sync'}), {'changed': 1, 'pending': 0})
            self.assertEqual(call({'op': 'sync'}), {'changed': 0, 'pending': 0})
            old = None
            for _ in range(3):
                hits = call({'op': 'search', 'query': 'How do atomic SQLite backups work?'})['hits']
                self.assertEqual(len(hits), 1)
                old = hits[0]
                self.assertEqual(old['sha256'], hashlib.sha256(fixture.read_bytes()).hexdigest())
                self.assertEqual(call({'op': 'get', 'id': old['id'], 'revision': 1, 'sha256': old['sha256']})['text'], old['text'])
            self.assertEqual(call({'op': 'stats'})['encoder_loads'], 1)
            self.assertEqual(old['trust'], 'untrusted_source_data')
            for invalid in ({'op': 'get', 'path': '../not-allowed.md'},
                            {'op': 'sync', 'path': 'not-allowed.md'},
                            {'op': 'search', 'query': 'x', 'limit': 9},
                            {'op': 'search', 'query': 'x' * 1025},
                            {'op': 'ingest', 'expected': {'not-allowed.md': '0' * 64}}):
                call(invalid, ok=False)
            fixture.write_bytes(b'# Comet revision\nIncremental Qdrant reconciliation preserves revision signatures.\n')
            self.assertEqual(call({'op': 'search', 'query': 'SQLite backup'})['hits'], [])
            call({'op': 'get', 'id': old['id'], 'revision': 1, 'sha256': old['sha256']}, ok=False)
            self.assertEqual(call({'op': 'sync'}), {'changed': 1, 'pending': 0})
            updated = call({'op': 'search', 'query': 'revision signatures'})['hits'][0]
            self.assertEqual(updated['revision'], 2)
            self.assertNotEqual(updated['id'], old['id'])
            self.assertNotIn('SQLite', updated['text'])
            stop()
            _, call, stop = spawn()
            self.assertEqual(call({'op': 'search', 'query': 'revision signatures'})['hits'][0]['id'], updated['id'])
            fixture.unlink()
            self.assertEqual(call({'op': 'search', 'query': 'revision signatures'})['hits'], [])
            self.assertEqual(call({'op': 'sync'}), {'changed': 1, 'pending': 0})
            call({'op': 'get', 'id': updated['id'], 'revision': 2, 'sha256': updated['sha256']}, ok=False)
            stats = call({'op': 'stats'})
            self.assertEqual((stats['current_sources'], stats['current_chunks'], stats['qdrant_points'], stats['revision_snapshots']), (0, 0, 0, 3))
            stop()
            _, call, stop = spawn()
            self.assertEqual(call({'op': 'search', 'query': 'SQLite backup'})['hits'], [])
            self.assertEqual(call({'op': 'stats'})['revision_snapshots'], 3)
            stop()
            with closing(sqlite3.connect(root/'authority.sqlite')) as db:
                revisions = db.execute('SELECT revision,sha,status,hex(original) FROM revisions ORDER BY revision').fetchall()
                self.assertEqual([row[2] for row in revisions], ['current', 'current', 'deleted'])
                self.assertEqual(db.execute('SELECT path FROM sources').fetchall(), [('fixture.md',)])
                save('revision-history.json', revisions)
            self.assertEqual((source/'not-allowed.md').read_text(encoding='utf-8'), 'Never ingest this sentinel.')
            save('result.json', {'passed': True, 'collection': collection, 'storage': str(server_root/'storage'),
                                 'sessions': len(processes), 'encoder_loads_per_session': 1,
                                 'model': ready['model'], 'scope': 'synthetic lifecycle, not relevance acceptance'})
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=15)
                for stream in (proc.stdin, proc.stdout):
                    if stream and not stream.closed:
                        stream.close()
            for log in logs:
                log.close()
            cleanup.update(server.close())
            if server_root.exists():
                for name in ('server.yaml', 'server.log', 'cleanup.json'):
                    if (server_root/name).exists():
                        shutil.copyfile(server_root/name, RUN/name)
            cleanup['worker_exit_codes'] = [p.returncode for p in processes]
            shutil.rmtree(root)
            cleanup['scratch_removed'] = not root.exists()
            save('transcript.json', transcript)
            save('cleanup.json', cleanup)
            self.assertTrue(cleanup['process_exited'] and cleanup['port_closed'] and cleanup['scratch_removed'])

    def test_failed_encoding_and_lost_ack_replay_from_authority(self):
        from unittest.mock import patch
        from tools.knowledge_runtime import KnowledgeRuntime, Runtime
        run = RUN / 'failure-replay'
        run.mkdir(parents=True)
        root = Path(tempfile.mkdtemp(prefix='knowledge-replay-', dir=SCRATCH))
        server_root = root / 'server'
        server_root.mkdir()
        sources = root / 'sources'
        sources.mkdir()
        fixture = sources / 'fixture.txt'
        fixture.write_bytes(b'Original SQLite backup evidence.')
        server = Server(server_root)
        runtime = None
        events = []
        try:
            server.start()
            config = dict(db=root/'authority.sqlite', model=REPO/'artifacts/models/minilm',
                          qdrant_url=f'http://127.0.0.1:{server.port}', collection='akr_'+uuid.uuid4().hex,
                          allow_root=sources, allow_files=['fixture.txt'], write=True)
            runtime = KnowledgeRuntime(Runtime(**config, create=True))
            runtime.handle({'op': 'sync'})
            old = runtime.handle({'op': 'search', 'query': 'backup'})['hits'][0]
            self.assertEqual(runtime.handle({'op': 'search', 'query': 'backup', 'mode': 'bm25_or'})['hits'][0]['id'], old['id'])
            fixture.write_bytes(b'New revision uses Qdrant reconciliation.')
            with patch.object(runtime.authority.encoder, 'encode', side_effect=RuntimeError('injected encoder failure')):
                with self.assertRaisesRegex(RuntimeError, 'encoder failure'):
                    runtime.handle({'op': 'sync'})
            stats = runtime.handle({'op': 'stats'})
            self.assertGreater(stats['pending'], 0)
            self.assertEqual(stats['valid_vectors'], 0)
            for mode in ('bm25_or', 'hybrid_rrf'):
                current = runtime.handle({'op': 'search', 'query': 'reconciliation', 'mode': mode})
                self.assertGreater(current['pending'], 0)
                self.assertEqual(current['hits'][0]['revision'], 2)
                self.assertNotIn(old['id'], [hit['id'] for hit in current['hits']])
            self.assertEqual(runtime.handle({'op': 'search', 'query': 'backup'})['hits'], [])
            with self.assertRaises(ValueError):
                runtime.handle({'op': 'get', 'id': old['id'], 'revision': 1, 'sha256': old['sha256']})
            events.append({'injected_encoder_failure': 'pending retained, old evidence excluded', 'stats': stats})
            remote = runtime.authority.remote
            original_request = remote.request
            def lose_ack(method, path='', body=None):
                result = original_request(method, path, body)
                if method == 'PUT' and path == '/points?wait=true':
                    raise RuntimeError('injected lost acknowledgement after actual upsert')
                return result
            with patch.object(remote, 'request', side_effect=lose_ack):
                with self.assertRaisesRegex(RuntimeError, 'lost acknowledgement'):
                    runtime.handle({'op': 'sync'})
            self.assertGreater(runtime.authority.pending(), 0)
            runtime.close()
            runtime = KnowledgeRuntime(Runtime(**config))
            self.assertEqual(runtime.handle({'op': 'sync'}), {'changed': 0, 'pending': 0})
            self.assertEqual(runtime.handle({'op': 'search', 'query': 'reconciliation'})['hits'][0]['revision'], 2)
            events.append({'lost_ack_restart_replayed': True, 'stats': runtime.handle({'op': 'stats'})})
            # A deletion must supersede a durable upsert that never got acknowledged.
            fixture.write_bytes(b'Third revision is pending when deleted.')
            with patch.object(runtime.authority.encoder, 'encode', side_effect=RuntimeError('injected failure')):
                with self.assertRaises(RuntimeError):
                    runtime.handle({'op': 'sync'})
            fixture.unlink()
            self.assertEqual(runtime.handle({'op': 'sync'})['pending'], 0)
            self.assertEqual(runtime.handle({'op': 'search', 'query': 'revision'})['hits'], [])
            self.assertEqual(runtime.handle({'op': 'stats'})['qdrant_points'], 0)
            events.append({'tombstone_supersedes_pending_upsert': True})
        finally:
            if runtime:
                runtime.close()
            cleanup = server.close()
            for name in ('server.yaml', 'server.log'):
                if (server_root/name).exists():
                    shutil.copyfile(server_root/name, run/name)
            shutil.rmtree(root)
            cleanup['scratch_removed'] = not root.exists()
            (run/'events.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
            (run/'cleanup.json').write_text(json.dumps(cleanup, indent=2), encoding='utf-8')
            self.assertTrue(cleanup['process_exited'] and cleanup['port_closed'] and cleanup['scratch_removed'])


if __name__ == '__main__':
    unittest.main()
