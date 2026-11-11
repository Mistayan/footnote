"""Real metadata JSONL lifecycle and remote lost-ack replay in owned scratch."""
import hashlib
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from test_knowledge_runtime_acceptance import REPO, SCRATCH, Server


class MetadataLifecycle(unittest.TestCase):
    def test_jsonl_metadata_sync_restart_and_remote_replay(self):
        from tools.knowledge_runtime import KnowledgeRuntime, Runtime
        run = REPO/'artifacts/knowledge-metadata'/uuid.uuid4().hex
        run.mkdir(parents=True)
        root = Path(tempfile.mkdtemp(prefix='knowledge-metadata-', dir=SCRATCH))
        server_root = root/'server'
        server_root.mkdir()
        server = Server(server_root)
        source = root/'sources'
        source.mkdir()
        fixture = source/'one.md'
        fixture.write_bytes(b'Python task_group preserves structured concurrency.')
        manifest = root/'manifest.json'
        def metadata(version):
            manifest.write_text(json.dumps({'schema_version':1,'sources':{'one.md':{'technology':'python','documented_version':version}}}))
        metadata('3.11')
        original = hashlib.sha256(fixture.read_bytes()).hexdigest()
        config = dict(db=root/'authority.sqlite', model=REPO/'artifacts/models/minilm',
            collection='akr_'+uuid.uuid4().hex, allow_root=source, allow_files=['one.md'], write=True)
        processes, transcript, logs = [], [], []
        runtime = None
        try:
            server.start()
            config['qdrant_url'] = f'http://127.0.0.1:{server.port}'
            def spawn(create=False, write=True):
                argv = [sys.executable,'-m','tools.knowledge_runtime','--source-manifest',str(manifest)]
                for key in ('db','model','collection','allow_root','qdrant_url'):
                    argv += ['--'+key.replace('_','-'),str(config[key])]
                argv += ['--allow-file','one.md'] + (['--write'] if write else []) + (['--create'] if create else [])
                log = (run/f'worker-{len(processes)}.stderr').open('w')
                logs.append(log)
                proc = subprocess.Popen(argv,cwd=REPO,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',bufsize=1)
                processes.append(proc)
                lines = queue.Queue()
                def reader():
                    for line in proc.stdout:
                        lines.put(line)
                thread = threading.Thread(target=reader,daemon=True)
                thread.start()
                def receive():
                    value = json.loads(lines.get(timeout=40))
                    transcript.append({'response':value})
                    return value
                transcript.append({'argv':argv})
                self.assertTrue(receive()['ready'])
                def call(request, ok=True):
                    transcript.append({'request':request})
                    proc.stdin.write(json.dumps(request)+'\n')
                    proc.stdin.flush()
                    result = receive()
                    self.assertEqual(result['ok'],ok,result)
                    return result.get('result',result)
                def stop():
                    proc.stdin.close()
                    proc.wait(timeout=15)
                    thread.join(timeout=3)
                    proc.stdout.close()
                    self.assertEqual(proc.returncode,0)
                return call, stop
            def search(call, version, mode='hybrid_rrf', ok=True):
                return call({'op':'search','mode':mode,'query':'Python task_group','constraints':{'documented_version':version}},ok)
            call,stop = spawn(create=True)
            call({'op':'sync'})
            hit = search(call,'3.11')['hits'][0]
            get = {'op':'get','id':hit['id'],'revision':hit['revision'],'sha256':hit['sha256'],'constraints':{'documented_version':'3.11'}}
            call(get)
            self.assertEqual(search(call,'3.12')['hits'],[])
            metadata('3.12')
            search(call,'3.11',ok=False)
            call(get,False)
            self.assertEqual(call({'op':'sync'})['changed'],0)
            self.assertEqual(search(call,'3.11')['hits'],[])
            call(get,False)
            self.assertEqual(search(call,'3.12')['hits'][0]['id'],hit['id'])
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),original)
            stop()
            call,stop = spawn(write=False)
            for mode in ('semantic','bm25_or','hybrid_rrf'):
                self.assertEqual(search(call,'3.12',mode)['hits'][0]['id'],hit['id'])
            stop()
            runtime = KnowledgeRuntime(Runtime(**config),source_manifest=manifest)
            fixture.write_bytes(b'Python task_group updated revision evidence.')
            with patch.object(runtime.authority.encoder,'encode',side_effect=RuntimeError('injected encoder failure')):
                with self.assertRaises(RuntimeError):
                    runtime.handle({'op':'sync'})
            current = runtime.handle({'op':'search','mode':'bm25_or','query':'Python','constraints':{'documented_version':'3.12'}})['hits'][0]
            self.assertEqual(current['revision'],2)
            request = runtime.authority.remote.request
            def lost_ack(method,path='',body=None):
                result = request(method,path,body)
                if method == 'PUT' and path == '/points?wait=true':
                    raise RuntimeError('lost acknowledgement after actual upsert')
                return result
            with patch.object(runtime.authority.remote,'request',side_effect=lost_ack):
                with self.assertRaisesRegex(RuntimeError,'lost acknowledgement'):
                    runtime.handle({'op':'sync'})
            self.assertGreater(runtime.authority.pending(),0)
            runtime.close()
            runtime = KnowledgeRuntime(Runtime(**config),source_manifest=manifest)
            self.assertEqual(runtime.handle({'op':'sync'})['pending'],0)
            fixture.unlink()
            self.assertEqual(runtime.handle({'op':'search','mode':'hybrid_rrf','query':'Python','constraints':{'documented_version':'3.12'}})['hits'],[])
            runtime.handle({'op':'sync'})
            runtime.close()
            runtime = None
            call,stop = spawn(write=False)
            self.assertEqual(search(call,'3.12')['hits'],[])
            call(dict(get,constraints={'documented_version':'3.12'}),False)
            stop()
            (run/'result.json').write_text(json.dumps({'passed':True,'source_unchanged_metadata_sync':True,'actual_lost_ack_replayed':True}))
        finally:
            if runtime:
                runtime.close()
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=15)
                for stream in (proc.stdin,proc.stdout):
                    if not stream.closed:
                        stream.close()
            for log in logs:
                log.close()
            cleanup = server.close()
            for name in ('server.yaml','server.log'):
                if (server_root/name).exists():
                    shutil.copyfile(server_root/name,run/name)
            shutil.rmtree(root)
            cleanup.update(scratch_removed=not root.exists(),worker_exit_codes=[p.returncode for p in processes])
            (run/'transcript.json').write_text(json.dumps(transcript,indent=2))
            (run/'cleanup.json').write_text(json.dumps(cleanup,indent=2))
            self.assertTrue(cleanup['process_exited'] and cleanup['port_closed'] and cleanup['scratch_removed'])
