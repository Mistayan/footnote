"""Real local-model/Qdrant acceptance. Never connects to an incumbent server."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
from server_benchmark import Server, save

RUN = Path(os.environ.get('AKR_EVIDENCE', str(REPO / 'artifacts/agent-knowledge-runtime' / uuid.uuid4().hex)))
RUN.mkdir(parents=True, exist_ok=True)
SCRATCH = Path('C:/Users/johan/AppData/Local/hermes/cache/scratch')


class RuntimeAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server(RUN)
        try:
            cls.server.start()
        except Exception:
            cls.server.close()
            raise
        cls.events = []
        cls.roots = []

    @classmethod
    def tearDownClass(cls):
        save(RUN / 'events.json', cls.events)
        result = cls.server.close()
        scratch = {str(path): not path.exists() for path in cls.roots}
        save(RUN / 'scratch-cleanup.json', scratch)
        assert all(scratch.values()), scratch
        assert result['process_exited'] and result['port_closed'], result

    def setUp(self):
        path = REPO / 'tools/agent_knowledge_runtime.py'
        self.assertTrue(path.is_file(), 'opt-in runtime does not exist yet')
        spec = importlib.util.spec_from_file_location('agent_knowledge_runtime', path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.root = Path(tempfile.mkdtemp(prefix='akr-', dir=SCRATCH))
        self.roots.append(self.root)
        self.addCleanup(shutil.rmtree, self.root)
        self.source = self.root / 'sources'
        self.source.mkdir()
        self.file = self.source / 'fixture.md'
        self.file.write_text('Comet release supports atomic SQLite backups.\n', encoding='utf-8')
        self.config = dict(db=self.root / 'authority.sqlite', model=REPO / 'artifacts/models/minilm',
                           qdrant_url=f'http://127.0.0.1:{self.server.port}',
                           collection='akr_' + uuid.uuid4().hex, allow_root=self.source,
                           allow_files=['fixture.md'], write=True, create=True)
        self.runtime = self.mod.Runtime(**self.config)
        self.addCleanup(self.runtime.close)

    def call(self, request):
        event = {'test': self.id(), 'request': request}
        try:
            response = self.runtime.handle(request)
            event['response'] = response
            return response
        except Exception as error:
            event['error'] = {'type': type(error).__name__, 'message': str(error)}
            raise
        finally:
            self.events.append(event)

    def scan(self):
        value = hashlib.sha256(self.file.read_bytes()).hexdigest() if self.file.exists() else None
        return self.call({'op': 'ingest', 'expected': {'fixture.md': value}})

    def test_01_ingest_actual_resident_search_and_get(self):
        self.assertEqual(self.scan()['changed'], 1)
        self.assertEqual(self.call({'op': 'sync'})['pending'], 0)
        for _ in range(2):
            found = self.call({'op': 'search', 'query': 'atomic SQLite backups'})['hits']
            self.assertEqual(len(found), 1)
            hit = found[0]
            got = self.call({'op': 'get', 'id': hit['id'], 'revision': hit['revision'], 'sha256': hit['sha256']})
            self.assertEqual(got['text'], hit['text'])
            self.assertEqual(got['trust'], 'untrusted_source_data')
            self.assertTrue(got['usable'])
        stats = self.call({'op': 'stats'})
        self.assertEqual(stats['encoder_loads'], 1)
        self.assertEqual(stats['current_chunks'], 1)
        self.assertEqual(stats['pending'], 0)
        self.assertEqual(stats['qdrant_points'], 1)

    def test_03_bounds_permissions_and_explicit_lexical(self):
        self.scan()
        lexical = self.call({'op': 'search', 'query': 'SQLite', 'mode': 'lexical'})
        self.assertEqual(lexical['mode'], 'lexical')
        self.assertEqual(len(lexical['hits']), 1)
        for request in (
            {'op': 'get', 'id': '../../private.md', 'revision': 1, 'sha256': '0' * 64},
            {'op': 'get', 'path': 'C:/Users/johan/private.md'},
            {'op': 'ingest', 'expected': {'../private.md': '0' * 64}},
            {'op': 'search', 'query': 'x' * 1025},
            {'op': 'search', 'query': 'x', 'limit': 9},
            {'op': 'stats', 'request_id': 'x' * 65},
            {'op': 'sync', 'path': 'fixture.md'},
        ):
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    self.call(request)
        with self.assertRaisesRegex(ValueError, 'hash drift'):
            self.call({'op': 'ingest', 'expected': {'fixture.md': '0' * 64}})
        self.runtime.write = False
        with self.assertRaisesRegex(ValueError, 'not authorized'):
            self.scan()
        with self.assertRaisesRegex(ValueError, 'not authorized'):
            self.call({'op': 'sync'})
        self.assertEqual(self.file.read_text(encoding='utf-8'), 'Comet release supports atomic SQLite backups.\n')
        self.assertEqual(self.runtime.read_source('fixture.md'), self.file.read_bytes())
        with self.assertRaisesRegex(ValueError, 'nonallowlisted'):
            self.runtime.read_source('../private.md')
        self.runtime.write = True
        self.file.write_bytes(b'x' * 65537)
        with self.assertRaisesRegex(ValueError, '65536'):
            self.scan()

    def test_04_coverage_rejects_tampered_remote_payload(self):
        self.scan()
        self.call({'op': 'sync'})
        hit = self.call({'op': 'search', 'query': 'SQLite'})['hits'][0]
        self.runtime.remote.request('POST', '/points/payload?wait=true',
                                    {'points': [hit['id']], 'payload': {'sha256': '0' * 64}})
        readback = self.runtime.remote.request('POST', '/points', {'ids': [hit['id']], 'with_payload': True})
        self.assertEqual(readback[0]['payload']['sha256'], '0' * 64)
        self.assertEqual(self.call({'op': 'search', 'query': 'SQLite'})['hits'], [])
        stats = self.call({'op': 'stats'})
        self.assertEqual(stats['valid_vectors'], 0)
        self.assertEqual(stats['invalid_or_orphan_points'], 1)
        self.file.unlink()
        self.assertEqual(self.call({'op': 'stats'})['stale_sources'], 1)

    def test_05_missing_dependencies_and_ownership_refuse(self):
        for changes, message in (
            ({'db': self.root / 'missing-model.sqlite', 'model': self.root / 'no-model',
              'collection': 'akr_' + uuid.uuid4().hex}, 'manifest'),
            ({'db': self.root / 'missing-server.sqlite', 'qdrant_url': 'http://127.0.0.1:1',
              'collection': 'akr_' + uuid.uuid4().hex}, 'Qdrant unavailable'),
            ({'db': self.root / 'forbidden.sqlite', 'collection': 'borg_vault'}, 'owned collection'),
            ({'db': self.root / 'existing-collection.sqlite'}, 'takeover'),
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex((ValueError, RuntimeError, FileNotFoundError), message):
                    self.mod.Runtime(**dict(self.config, **changes))
                self.assertFalse(changes['db'].exists())
        with self.assertRaises((OSError, RuntimeError)):
            self.mod.Runtime(**dict(self.config, create=False))

    def test_06_derived_recovery_from_authority_backup(self):
        import sqlite3
        from contextlib import closing
        self.scan()
        self.call({'op': 'sync'})
        hit = self.call({'op': 'search', 'query': 'SQLite'})['hits'][0]
        backup = self.root / 'backup.sqlite'
        with closing(sqlite3.connect(backup)) as target:
            self.runtime.db.backup(target)
        self.runtime.remote.request('DELETE')
        with self.assertRaisesRegex(RuntimeError, '404'):
            self.runtime.remote.request('GET')
        self.runtime.close()
        shutil.copyfile(backup, self.config['db'])
        self.runtime = self.mod.Runtime(**dict(self.config, create=False, recover_index=True))
        self.addCleanup(self.runtime.close)
        self.assertEqual(self.call({'op': 'sync'})['pending'], 0)
        got = self.call({'op': 'get', 'id': hit['id'], 'revision': 1, 'sha256': hit['sha256']})
        self.assertEqual(got['text'], hit['text'])
        self.assertEqual(self.call({'op': 'stats'})['valid_vectors'], 1)
        self.assertEqual(len(self.call({'op': 'search', 'query': 'SQLite'})['hits']), 1)

    def test_07_jsonl_resident_process_journey(self):
        import queue
        import subprocess
        import threading
        import time
        self.runtime.close()
        argv = [sys.executable, str(REPO / 'tools/agent_knowledge_runtime.py'),
                '--db', str(self.config['db']), '--model', str(self.config['model']),
                '--qdrant-url', self.config['qdrant_url'], '--collection', self.config['collection'],
                '--allow-root', str(self.source), '--allow-file', 'fixture.md', '--write']
        transcript = []
        processes = []
        def spawn():
            log = (RUN / ('jsonl-stderr-' + str(len(processes)) + '.log')).open('w')
            cold_started = time.perf_counter()
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                       text=True, encoding='utf-8', bufsize=1)
            processes.append(process)
            lines = queue.Queue()
            def reader():
                for line in process.stdout:
                    lines.put(line)
            thread = threading.Thread(target=reader, daemon=True)
            thread.start()
            def read():
                line = lines.get(timeout=20)
                transcript.append({'stdout': line, 'pid': process.pid})
                self.assertLessEqual(len(line.encode()), 65536)
                return json.loads(line)
            ready = read()
            transcript[-1]['cold_start_to_ready_ms'] = (time.perf_counter() - cold_started) * 1000
            self.assertTrue(ready['ready'], ready)
            self.assertEqual(ready['encoder_loads'], 1)
            def send(request):
                line = json.dumps(request) + '\n' if not isinstance(request, str) else request
                transcript.append({'stdin': line, 'pid': process.pid})
                started = time.perf_counter()
                process.stdin.write(line)
                process.stdin.flush()
                response = read()
                transcript[-1]['client_roundtrip_ms'] = (time.perf_counter() - started) * 1000
                return response
            def stop():
                if process.poll() is None:
                    process.stdin.close()
                    process.wait(timeout=10)
                thread.join(timeout=5)
                process.stdout.close()
                log.close()
            self.addCleanup(stop)
            return process, send, stop
        self.addCleanup(lambda: save(RUN / 'jsonl-transcript.json', {'argv': argv, 'events': transcript,
                        'processes': [{'pid': p.pid, 'returncode': p.poll()} for p in processes]}))
        process, send, stop = spawn()
        sha = hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.assertTrue(send({'op': 'ingest', 'expected': {'fixture.md': sha}})['ok'])
        self.assertTrue(send({'op': 'sync'})['ok'])
        for index in range(3):
            response = send({'op': 'search', 'query': 'atomic backups', 'request_id': str(index)})
            self.assertEqual(response['request_id'], str(index))
            hit = response['result']['hits'][0]
            self.assertTrue(send({'op': 'get', 'id': hit['id'], 'revision': 1, 'sha256': sha})['ok'])
        self.file.write_text('Neptune revision stores PostgreSQL snapshots.\n', encoding='utf-8')
        self.assertFalse(send({'op': 'get', 'id': hit['id'], 'revision': 1, 'sha256': sha})['ok'])
        self.assertEqual(send({'op': 'search', 'query': 'atomic'})['result']['hits'], [])
        self.assertFalse(send({'op': 'sync'})['ok'])
        sha = hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.assertTrue(send({'op': 'ingest', 'expected': {'fixture.md': sha}})['ok'])
        self.assertTrue(send({'op': 'sync'})['ok'])
        current = send({'op': 'search', 'query': 'Neptune'})['result']['hits'][0]
        self.assertEqual(current['revision'], 2)
        self.assertFalse(send('{broken JSON\n')['ok'])
        self.assertFalse(send({'op': 'get', 'path': '../denied.md'})['ok'])
        self.assertEqual(send({'op': 'stats'})['result']['encoder_loads'], 1)
        stop()
        self.assertEqual(process.returncode, 0)
        process, send, stop = spawn()
        restored = send({'op': 'get', 'id': current['id'], 'revision': 2, 'sha256': sha})
        self.assertTrue(restored['ok'])
        self.file.unlink()
        self.assertTrue(send({'op': 'ingest', 'expected': {'fixture.md': None}})['ok'])
        self.assertTrue(send({'op': 'sync'})['ok'])
        self.assertEqual(send({'op': 'search', 'query': 'Neptune'})['result']['hits'], [])
        self.assertFalse(send('x' * 16385 + '\n')['ok'])
        stop()
        self.assertEqual(process.returncode, 2)

    def test_08_pending_upsert_becomes_tombstone_before_restart(self):
        self.scan()
        remote = self.runtime.remote.request
        def interrupted(method, path='', body=None):
            result = remote(method, path, body)
            if method == 'PUT' and path.startswith('/points'):
                raise RuntimeError('lost ack after actual upsert')
            return result
        self.runtime.remote.request = interrupted
        with self.assertRaisesRegex(RuntimeError, 'lost ack'):
            self.call({'op': 'sync'})
        self.runtime.remote.request = remote
        self.assertEqual(self.call({'op': 'stats'})['qdrant_points'], 1)
        self.assertEqual(self.runtime.pending(), 1)
        self.file.unlink()
        self.scan()
        self.runtime.close()
        self.runtime = self.mod.Runtime(**dict(self.config, create=False))
        self.addCleanup(self.runtime.close)
        self.call({'op': 'sync'})
        self.assertEqual(self.call({'op': 'stats'})['qdrant_points'], 0)
        self.assertEqual(self.call({'op': 'search', 'query': 'SQLite'})['hits'], [])

    def test_09_resident_vector_parity_and_config_binding(self):
        import numpy as np
        from embed import encode
        session = self.runtime.encoder.session
        texts = ['SQLite atomic backup', 'PostgreSQL snapshot isolation']
        resident = self.runtime.encoder.encode(texts, 'query')
        baseline = encode(self.config['model'], {'texts': texts, 'kind': 'query'})
        self.assertEqual(baseline['model_sha256'], self.runtime.encoder.identity)
        self.assertLessEqual(float(np.max(np.abs(np.array(resident) - np.array(baseline['vectors'])))), 1e-6)
        self.runtime.encoder.encode(texts, 'passage')
        self.assertIs(self.runtime.encoder.session, session)
        self.runtime.close()
        with self.assertRaisesRegex(ValueError, 'config/model/schema mismatch'):
            self.mod.Runtime(**dict(self.config, create=False, allow_files=['other.md']))
        self.runtime = self.mod.Runtime(**dict(self.config, create=False))
        self.addCleanup(self.runtime.close)

    def test_10_jsonl_startup_failures_and_incumbent_denial(self):
        import sqlite3
        import subprocess
        from contextlib import closing
        for kind in ('model', 'server'):
            db = self.root / (kind + '-failure.sqlite')
            argv = [sys.executable, str(REPO / 'tools/agent_knowledge_runtime.py'),
                    '--db', str(db), '--model', str(self.root / 'absent' if kind == 'model' else self.config['model']),
                    '--qdrant-url', 'http://127.0.0.1:1' if kind == 'server' else self.config['qdrant_url'],
                    '--collection', 'akr_' + uuid.uuid4().hex, '--allow-root', str(self.source),
                    '--allow-file', 'fixture.md', '--write', '--create']
            result = subprocess.run(argv, input='', text=True, encoding='utf-8', capture_output=True, timeout=20)
            self.events.append({'test': self.id(), 'argv': argv, 'stdout': result.stdout,
                                'stderr': result.stderr, 'exit_code': result.returncode})
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ready'])
            self.assertIn('manifest' if kind == 'model' else 'Qdrant unavailable', json.loads(result.stdout)['error'])
            self.assertFalse(db.exists())
        incumbent = self.root / 'not-runtime.sqlite'
        with closing(sqlite3.connect(incumbent)) as connection:
            connection.execute('CREATE TABLE records(id INTEGER)')
            connection.execute('INSERT INTO records VALUES(123)')
            connection.commit()
        before = hashlib.sha256(incumbent.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'incumbent DB denied'):
            self.mod.Runtime(**dict(self.config, db=incumbent, create=False))
        self.assertEqual(hashlib.sha256(incumbent.read_bytes()).hexdigest(), before)

    def test_02_revision_lifecycle_replay_and_restart(self):
        self.scan()
        self.call({'op': 'sync'})
        old = self.call({'op': 'search', 'query': 'SQLite'})['hits'][0]
        original = self.file.read_bytes()
        self.file.write_text('Nebula revision supports PostgreSQL snapshots.\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.call({'op': 'get', 'id': old['id'], 'revision': 1, 'sha256': old['sha256']})
        self.assertEqual(self.call({'op': 'search', 'query': 'SQLite'})['hits'], [])
        with self.assertRaisesRegex(ValueError, 'hash drift'):
            self.call({'op': 'sync'})
        self.assertEqual(self.scan()['changed'], 1)
        self.assertEqual(self.call({'op': 'stats'})['pending'], 2)
        with self.assertRaisesRegex(ValueError, 'obsolete'):
            self.call({'op': 'get', 'id': old['id'], 'revision': 1, 'sha256': old['sha256']})
        self.assertEqual(self.call({'op': 'search', 'query': 'Nebula'})['hits'], [])
        # Real remote mutation succeeds, then simulated transport loss prevents SQLite acknowledgement.
        remote = self.runtime.remote.request
        fired = []
        def interrupted(method, path='', body=None):
            value = remote(method, path, body)
            if method == 'PUT' and path.startswith('/points') and not fired:
                fired.append(True)
                raise RuntimeError('simulated loss after actual remote upsert')
            return value
        self.runtime.remote.request = interrupted
        with self.assertRaisesRegex(RuntimeError, 'simulated loss'):
            self.call({'op': 'sync'})
        self.runtime.remote.request = remote
        self.runtime.close()
        config = dict(self.config, create=False)
        self.runtime = self.mod.Runtime(**config)
        self.addCleanup(self.runtime.close)
        self.assertEqual(self.call({'op': 'sync'})['pending'], 0)
        current = self.call({'op': 'search', 'query': 'PostgreSQL'})['hits'][0]
        self.assertEqual(current['revision'], 2)
        self.assertNotEqual(current['id'], old['id'])
        snapshot = self.runtime.db.execute('SELECT original FROM revisions WHERE revision=1').fetchone()[0]
        self.assertEqual(snapshot, original)
        self.file.unlink()
        self.assertEqual(self.call({'op': 'search', 'query': 'PostgreSQL'})['hits'], [])
        self.assertEqual(self.scan()['changed'], 1)
        # Old pending upsert must never resurrect a tombstone on replay.
        self.assertEqual(self.call({'op': 'sync'})['pending'], 0)
        self.runtime.close()
        self.runtime = self.mod.Runtime(**config)
        self.addCleanup(self.runtime.close)
        self.assertEqual(self.call({'op': 'search', 'query': 'PostgreSQL'})['hits'], [])
        self.assertEqual(self.call({'op': 'stats'})['qdrant_points'], 0)
        self.assertEqual(self.runtime.db.execute('SELECT count(*) FROM revisions').fetchone()[0], 3)
        with self.assertRaisesRegex(ValueError, 'obsolete'):
            self.call({'op': 'get', 'id': current['id'], 'revision': 2, 'sha256': current['sha256']})


if __name__ == '__main__':
    print('EVIDENCE=' + str(RUN), flush=True)
    unittest.main(verbosity=2)
