"""Real offline resident JSONL/Qdrant lifecycle, not a relevance benchmark."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

from test_knowledge_runtime_acceptance import REPO, SCRATCH, Server
from test_knowledge_runtime_rerank import MODEL


class RerankTransport(unittest.TestCase):
    def test_loaded_rerank_preserves_pending_outbox_and_lost_ack_replay(self):
        from unittest.mock import patch
        from tools.knowledge_runtime import KnowledgeRuntime, Runtime
        run = REPO/'artifacts/knowledge-rerank'/uuid.uuid4().hex
        run.mkdir(parents=True)
        root = Path(tempfile.mkdtemp(prefix='rerank-replay-',dir=SCRATCH))
        server_root = root/'server'
        server_root.mkdir()
        source = root/'sources'
        source.mkdir()
        fixture = source/'fixture.md'
        fixture.write_text('SQLite backup original evidence.')
        server, runtime, events = Server(server_root), None, []
        try:
            server.start()
            config = dict(db=root/'authority.sqlite',model=REPO/'artifacts/models/minilm',
                          qdrant_url=f'http://127.0.0.1:{server.port}',collection='akr_'+uuid.uuid4().hex,
                          allow_root=source,allow_files=['fixture.md'],write=True)
            runtime = KnowledgeRuntime(Runtime(**config,create=True),reranker_model=MODEL)
            runtime.handle({'op':'sync'})
            request = {'op':'search','mode':'hybrid_rrf','query':'SQLite backup','rerank_budget':'budget5'}
            old = runtime.handle(request)['hits'][0]
            fixture.write_text('SQLite backup updated evidence.')
            with patch.object(runtime.authority.encoder,'encode',side_effect=RuntimeError('injected inference failure')):
                with self.assertRaisesRegex(RuntimeError,'inference failure'):
                    runtime.handle({'op':'sync'})
            current = runtime.handle(request)
            self.assertGreater(current['pending'],0)
            self.assertEqual(current['hits'][0]['revision'],2)
            self.assertNotEqual(current['hits'][0]['id'],old['id'])
            events.append({'pending_rerank':current})
            original = runtime.authority.remote.request
            def lose_ack(method,path='',body=None):
                result = original(method,path,body)
                if method=='PUT' and path=='/points?wait=true':
                    raise RuntimeError('lost acknowledgement after real upsert')
                return result
            with patch.object(runtime.authority.remote,'request',side_effect=lose_ack):
                with self.assertRaisesRegex(RuntimeError,'lost acknowledgement'):
                    runtime.handle({'op':'sync'})
            self.assertGreater(runtime.authority.pending(),0)
            runtime.close()
            runtime = KnowledgeRuntime(Runtime(**config),reranker_model=MODEL)
            self.assertEqual(runtime.handle({'op':'sync'})['pending'],0)
            self.assertEqual(runtime.handle(request)['hits'][0]['revision'],2)
            fixture.write_text('SQLite backup pending revision three.')
            with patch.object(runtime.authority.encoder,'encode',side_effect=RuntimeError('injected failure')):
                with self.assertRaises(RuntimeError):
                    runtime.handle({'op':'sync'})
            fixture.unlink()
            self.assertEqual(runtime.handle(request)['hits'],[])
            self.assertEqual(runtime.handle({'op':'sync'})['pending'],0)
            self.assertEqual(runtime.handle({'op':'stats'})['qdrant_points'],0)
            events.append({'lost_ack_replayed':True,'tombstone_superseded_pending_upsert':True})
        finally:
            if runtime:
                runtime.close()
            cleanup = server.close()
            for name in ('server.yaml','server.log'):
                if (server_root/name).exists():
                    shutil.copyfile(server_root/name,run/name)
            shutil.rmtree(root)
            cleanup['scratch_removed'] = not root.exists()
            for name,value in [('events.json',events),('cleanup.json',cleanup)]:
                (run/name).write_text(json.dumps(value,indent=2))
            print('RERANK_REPLAY_EVIDENCE='+str(run))
            self.assertTrue(cleanup['process_exited'] and cleanup['port_closed'] and cleanup['scratch_removed'])

    def test_real_resident_budget_lifecycle_and_unloaded_default(self):
        run = REPO/'artifacts/knowledge-rerank'/uuid.uuid4().hex
        run.mkdir(parents=True)
        root = Path(tempfile.mkdtemp(prefix='knowledge-rerank-', dir=SCRATCH))
        source = root/'sources'
        source.mkdir()
        fixtures = {f'n{n:02}.md': f'SQLite backup database note {n:02}. Preserve original bytes and immutable revision evidence.' for n in range(25)}
        for name, text in fixtures.items():
            (source/name).write_text(text,encoding='utf-8')
        (source/'sentinel.md').write_text('Unallowlisted sentinel.',encoding='utf-8')
        def save(name, data):
            (run/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
        save('freeze.json', {'fixtures':fixtures,'query':'SQLite backup database','budgets':['budget5','budget10','budget20'],
                             'scope':'mechanical lifecycle, no relevance labels/gains','model':str(MODEL)})
        server_root = root/'server'
        server_root.mkdir()
        server = Server(server_root)
        workers, logs, threads, transcript, rows, cold = [], [], [], [], [], []
        argv = []
        def spawn(create=False, loaded=True, invalid=False):
            command = argv + (['--create'] if create else [])
            if loaded:
                command += ['--reranker-model',str(root/'missing-model' if invalid else MODEL)]
            log = (run/f'worker-{len(workers)}.stderr').open('w')
            logs.append(log)
            start = time.perf_counter()
            proc = subprocess.Popen(command,cwd=REPO,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',bufsize=1)
            workers.append(proc)
            lines = queue.Queue()
            def reader():
                for line in proc.stdout:
                    lines.put(line)
                lines.put(None)
            thread = threading.Thread(target=reader,daemon=True)
            threads.append(thread)
            thread.start()
            def receive():
                try:
                    line = lines.get(timeout=60)
                except queue.Empty:
                    self.fail('JSONL timeout')
                self.assertIsNotNone(line,'worker exited without JSON response')
                value = json.loads(line)
                transcript.append({'pid':proc.pid,'response':value})
                return value
            ready = receive()
            cold.append({'loaded':loaded,'invalid':invalid,'wall_ms':(time.perf_counter()-start)*1000})
            transcript.append({'argv':command,'cold':cold[-1]})
            self.assertEqual(ready['ready'],not invalid,ready)
            def call(request, ok=True):
                request = dict(request,request_id=str(len(transcript)))
                transcript.append({'pid':proc.pid,'request':request})
                started = time.perf_counter()
                proc.stdin.write(json.dumps(request)+'\n')
                proc.stdin.flush()
                response = receive()
                transcript[-1]['wall_ms'] = (time.perf_counter()-started)*1000
                self.assertEqual(response['ok'],ok,response)
                self.assertEqual(response['request_id'],request['request_id'])
                return response.get('result',response)
            def stop(expected=0):
                proc.stdin.close()
                proc.wait(timeout=20)
                thread.join(timeout=3)
                proc.stdout.close()
                self.assertFalse(thread.is_alive())
                self.assertEqual(proc.returncode,expected)
            return ready,call,stop
        def search(call,budget='budget5'):
            return call({'op':'search','mode':'hybrid_rrf','query':'SQLite backup database','limit':5,'rerank_budget':budget})
        def get(call,hit,ok=True):
            return call({'op':'get',**{k:hit[k] for k in ('id','revision','sha256')}},ok=ok)
        try:
            server.start()
            argv.extend([sys.executable,'-m','tools.knowledge_runtime','--db',str(root/'authority.sqlite'),
                         '--model',str(REPO/'artifacts/models/minilm'),'--qdrant-url',f'http://127.0.0.1:{server.port}',
                         '--collection','akr_'+uuid.uuid4().hex,'--allow-root',str(source),'--write'])
            for name in fixtures:
                argv.extend(['--allow-file',name])
            # Invalid optional model must fail bounded, before creation of authority.
            _,_,stop = spawn(create=True,invalid=True)
            stop(expected=1)
            self.assertFalse((root/'authority.sqlite').exists())
            ready,call,stop = spawn(create=True)
            self.assertEqual(ready['reranker_loads'],1)
            self.assertEqual(call({'op':'sync'}),{'changed':25,'pending':0})
            plain = call({'op':'search','mode':'hybrid_rrf','query':'SQLite backup database','limit':5})
            self.assertNotIn('reranking',plain)
            self.assertNotIn('rerank_logit',plain['hits'][0])
            # Alternating requests freshly execute every stage; no shared timing sums.
            for budget in ('budget5','budget20','budget10','budget20','budget5'):
                result = search(call,budget)
                self.assertEqual(result['reranking']['candidate_count'],int(budget[6:]))
                self.assertEqual(result['reranking']['eligible_pool_count'],20)
                self.assertEqual(len(result['hits']),5)
                self.assertTrue(all(h['applicability']=='not_estimated' for h in result['hits']))
                self.assertEqual(result['answerability'],'not_estimated')
                rows.append(result)
            old = rows[-1]['hits'][0]
            self.assertEqual(get(call,old)['text'],old['text'])
            stats = call({'op':'stats'})
            self.assertEqual((stats['encoder_loads'],stats['reranker_loads'],stats['selected_rerank_budget']),(1,1,'budget5'))
            for bad in ('budget0',5,None,True):
                call({'op':'search','mode':'hybrid_rrf','query':'backup','rerank_budget':bad},ok=False)
            # External edit before sync withholds stale signatures even when reranked.
            changed = source/old['path']
            changed.write_text('SQLite backup updated revision preserves immutable evidence.',encoding='utf-8')
            self.assertNotIn(old['id'],[h['id'] for h in search(call,'budget20')['hits']])
            get(call,old,ok=False)
            self.assertEqual(call({'op':'sync'}),{'changed':1,'pending':0})
            current = call({'op':'search','mode':'bm25_or','query':'updated'})['hits'][0]
            self.assertEqual(current['revision'],2)
            get(call,current)
            self.assertNotIn(old['id'],[h['id'] for h in search(call,'budget20')['hits']])
            unchanged = call({'op':'search','mode':'hybrid_rrf','query':'SQLite backup database'})
            stop()
            ready,call,stop = spawn(loaded=False)
            self.assertEqual(ready['reranker_loads'],0)
            self.assertEqual(call({'op':'search','mode':'hybrid_rrf','query':'SQLite backup database'}),unchanged)
            default = call({'op':'search','query':'SQLite backup database'})
            self.assertEqual(default['mode'],'semantic')
            self.assertEqual(len(default['hits']),5)
            self.assertNotIn('reranking',default)
            stop()
            _,call,stop = spawn()
            self.assertEqual(get(call,current)['revision'],2)
            search(call,'budget20')
            changed.unlink()
            self.assertNotIn(current['id'],[h['id'] for h in search(call,'budget20')['hits']])
            get(call,current,ok=False)
            self.assertEqual(call({'op':'sync'}),{'changed':1,'pending':0})
            for name in fixtures:
                (source/name).unlink(missing_ok=True)
            self.assertEqual(search(call,'budget20')['hits'],[])
            self.assertEqual(call({'op':'sync'}),{'changed':24,'pending':0})
            self.assertEqual(call({'op':'stats'})['qdrant_points'],0)
            stop()
            _,call,stop = spawn()
            self.assertEqual(search(call,'budget20')['reranking']['candidate_count'],0)
            get(call,current,ok=False)
            stop()
            # The unloaded worker starts with no ranker and inherited defaults.
            ready,call,stop = spawn(loaded=False)
            self.assertEqual(ready['reranker_loads'],0)
            self.assertEqual(call({'op':'stats'})['reranker_loads'],0)
            error = call({'op':'search','mode':'hybrid_rrf','query':'backup','rerank_budget':'budget5'},ok=False)
            self.assertIn('reranker not loaded',error['error'])
            default = call({'op':'search','query':'backup'})
            self.assertEqual(default['mode'],'semantic')
            self.assertNotIn('reranking',default)
            self.assertEqual(default['hits'],[])
            stop()
            self.assertEqual((source/'sentinel.md').read_text(),'Unallowlisted sentinel.')
            with closing(sqlite3.connect(root/'authority.sqlite')) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM jobs WHERE pending=1').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM chunks WHERE active=1').fetchone()[0],0)
                save('revision-history.json',db.execute('SELECT path,revision,sha,status FROM revisions ORDER BY path,revision').fetchall())
            save('measurements.json',{'requests':rows,'cold':cold,'quality':'not measured; no relevance fixture gains asserted'})
        finally:
            for proc in workers:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=20)
                for stream in (proc.stdin,proc.stdout):
                    if stream and not stream.closed:
                        stream.close()
            for thread in threads:
                thread.join(timeout=3)
            for log in logs:
                log.close()
            cleanup = server.close()
            for name in ('server.yaml','server.log'):
                if (server_root/name).exists():
                    shutil.copyfile(server_root/name,run/name)
            cleanup['worker_exit_codes'] = [p.returncode for p in workers]
            shutil.rmtree(root)
            cleanup['scratch_removed'] = not root.exists()
            save('transcript.json',transcript)
            save('cleanup.json',cleanup)
            save('manifest-sha256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in run.iterdir() if p.is_file() and p.name!='manifest-sha256.json'})
            print('RERANK_EVIDENCE='+str(run))
            self.assertTrue(cleanup['process_exited'] and cleanup['port_closed'] and cleanup['scratch_removed'])


if __name__ == '__main__':
    unittest.main()