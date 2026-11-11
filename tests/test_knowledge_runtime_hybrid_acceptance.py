"""Real isolated JSONL hybrid parity/lifecycle; mechanical fixtures, no quality claim."""
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


class HybridTransport(unittest.TestCase):
    def test_real_jsonl_hybrid_parity_lifecycle_and_compact(self):
        run = REPO/'artifacts/knowledge-hybrid'/uuid.uuid4().hex
        run.mkdir(parents=True)
        root = Path(tempfile.mkdtemp(prefix='knowledge-hybrid-', dir=SCRATCH))
        source = root/'sources'
        source.mkdir()
        fixtures = {'alpha.md':'TaskGroup task_group Python3.11 C++ ->> atomic SQLite backup.',
                    'beta.txt':'Task group Python3.12 C -> PostgreSQL replication.',
                    'gamma.md':'Qdrant vector search reconciles immutable revision signatures.'}
        queries = ['task_group absent', 'Python3.11', '->>', 'immutable revision', 'SQLite backup']
        freeze = {'fixtures':fixtures, 'queries':queries,
                  'expected_lexical_paths':[['alpha.md'],['alpha.md'],['alpha.md'],['gamma.md'],['alpha.md']],
                  'dense_budget':60,'lexical_budget':20,'rrf_k':60,
                  'rank_origin':1,'tie':'id ascending', 'quality':'not assessed'}
        (run/'freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
        for name,text in fixtures.items():
            (source/name).write_text(text,encoding='utf-8')
        (source/'sentinel.md').write_text('Unallowlisted sentinel.',encoding='utf-8')
        server_root = root/'server'
        server_root.mkdir()
        server = Server(server_root)
        workers, transcript, logs = [], [], []
        dbpath = root/'authority.sqlite'
        collection = 'akr_'+uuid.uuid4().hex
        argv = []
        def spawn(create=False):
            log = (run/f'worker-{len(workers)}.stderr').open('w')
            logs.append(log)
            command = argv + (['--create'] if create else [])
            started = time.perf_counter()
            proc = subprocess.Popen(command,cwd=REPO,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',bufsize=1)
            workers.append(proc)
            lines = queue.Queue()
            def reader():
                for line in proc.stdout:
                    lines.put(line)
            thread = threading.Thread(target=reader,daemon=True)
            thread.start()
            def receive():
                try:
                    value = json.loads(lines.get(timeout=40))
                except queue.Empty:
                    self.fail('JSONL worker timeout')
                transcript.append({'response':value})
                return value
            ready = receive()
            transcript.append({'argv':command,'cold_wall_ms':(time.perf_counter()-started)*1000})
            self.assertTrue(ready['ready'],ready)
            def call(req,ok=True):
                req = dict(req,request_id=str(len(transcript)))
                transcript.append({'request':req})
                start = time.perf_counter()
                proc.stdin.write(json.dumps(req)+'\n')
                proc.stdin.flush()
                value = receive()
                transcript[-1]['wall_ms'] = (time.perf_counter()-start)*1000
                self.assertEqual(value['ok'],ok,value)
                self.assertEqual(value['request_id'],req['request_id'])
                return value.get('result',value)
            def stop():
                proc.stdin.close()
                proc.wait(timeout=15)
                thread.join(timeout=3)
                proc.stdout.close()
                self.assertFalse(thread.is_alive())
                self.assertEqual(proc.returncode,0)
            return call,stop
        try:
            server.start()
            argv.extend([sys.executable,'-m','tools.knowledge_runtime','--db',str(dbpath),'--model',str(REPO/'artifacts/models/minilm'),'--qdrant-url',f'http://127.0.0.1:{server.port}','--collection',collection,'--allow-root',str(source),'--write'])
            for name in fixtures:
                argv.extend(['--allow-file',name])
            call,stop = spawn(True)
            self.assertEqual(call({'op':'sync'})['changed'],3)
            first = call({'op':'search','mode':'hybrid_rrf','query':queries[0],'limit':8})
            self.assertEqual(first['mode'],'hybrid_rrf')
            # Independent test-side encoder and SQLite FTS construction, frozen before queries.
            from tools.agent_knowledge_runtime import Encoder, Qdrant
            encoder = Encoder(REPO/'artifacts/models/minilm')
            remote = Qdrant(f'http://127.0.0.1:{server.port}',collection)
            import re
            pattern = re.compile(r'->>|->|#>>|#>|::|\w+(?:[._:/-]\w+)*(?:\+\+|#)?')
            def terms(text):
                return ['x'+t.casefold().encode().hex() for t in pattern.findall(text)]
            parity = []
            with closing(sqlite3.connect(dbpath)) as db, closing(sqlite3.connect(':memory:')) as independent:
                chunks = db.execute('SELECT id,path,text FROM chunks WHERE active=1 ORDER BY id').fetchall()
                independent.execute('CREATE VIRTUAL TABLE expected USING fts5(id UNINDEXED,body)')
                independent.executemany('INSERT INTO expected VALUES(?,?)',[(i,' '.join(terms(t))) for i,p,t in chunks])
                for query in queries:
                    vector = encoder.encode([query],'query')[0]
                    raw = remote.request('POST','/points/query',{'query':vector,'limit':60,'with_payload':True,'with_vector':False})['points']
                    ids = {i for i,p,t in chunks}
                    dense = [p['id'] for p in sorted(raw,key=lambda p:(-p['score'],p['id'])) if p['id'] in ids]
                    expression = ' OR '.join('"'+t+'"' for t in sorted(set(terms(query))))
                    lexical_rows = independent.execute('SELECT id,bm25(expected) FROM expected WHERE expected MATCH ? ORDER BY bm25(expected),id LIMIT 20',(expression,)).fetchall()
                    lexical = [r[0] for r in lexical_rows]
                    paths = {i:p for i,p,t in chunks}
                    self.assertEqual([paths[i] for i in lexical],freeze['expected_lexical_paths'][queries.index(query)])
                    with closing(sqlite3.connect(str(dbpath)+'.lexical.sqlite')) as actual_index:
                        actual_sql = []
                        actual_index.set_trace_callback(actual_sql.append)
                        actual_rows = actual_index.execute('SELECT id,bm25(lexical) FROM lexical WHERE lexical MATCH ? ORDER BY bm25(lexical),id LIMIT 20',(expression,)).fetchall()
                        self.assertEqual(actual_rows,lexical_rows)
                    candidates = set(dense)|set(lexical)
                    expected = sorted(candidates,key=lambda i:(-sum(1/(61+b.index(i)) for b in [dense,lexical] if i in b),i))
                    result = call({'op':'search','mode':'hybrid_rrf','query':query,'limit':8})
                    self.assertEqual([h['id'] for h in result['hits']],expected)
                    bm25 = call({'op':'search','mode':'bm25_or','query':query,'limit':8})
                    self.assertEqual([h['id'] for h in bm25['hits']],lexical)
                    for hit in result['hits']:
                        wanted = sum(1/(61+b.index(hit['id'])) for b in [dense,lexical] if hit['id'] in b)
                        self.assertAlmostEqual(hit['score'],wanted,places=15)
                    packed = call({'op':'search','mode':'hybrid_rrf','query':query,'limit':8,'response_format':'compact_v2'})
                    expanded = {k:v for k,v in packed.items() if k not in ('contract_version','evidence_format','shared')}
                    expanded['hits'] = [{**packed['shared'],**hit} for hit in packed['hits']]
                    self.assertEqual(expanded,result)
                    self.assertLess(len(json.dumps(packed).encode()),len(json.dumps(result).encode()))
                    parity.append({'query':query,'dense':dense,'lexical_sql':lexical_rows,'actual_sql_trace':actual_sql,'expected':expected,'actual':result,'compact':packed,
                                   'full_bytes':len(json.dumps(result).encode()),'compact_bytes':len(json.dumps(packed).encode())})
            old = first['hits'][0]
            get = {'op':'get','id':old['id'],'revision':old['revision'],'sha256':old['sha256']}
            full_get = call(get)
            self.assertEqual(full_get['text'],old['text'])
            self.assertEqual(call(dict(get,response_format='compact_v2'))['evidence'],full_get)
            for invalid in [{'op':'search','mode':'hybrid_rrf','query':'x','limit':True},
                            {'op':'search','mode':'hybrid_rrf','query':'x','limit':9},
                            {'op':'search','mode':'bm25_or','query':'x'*1025},
                            {'op':'search','mode':'bm25_or','query':'x','path':'sentinel.md'},
                            {'op':'search','mode':'bm25_or','query':'x','response_format':'unknown'},
                            {'op':'sync','response_format':'compact_v2'},
                            {'op':'get','path':'../sentinel.md','response_format':'compact_v2'}]:
                call(invalid,False)
            self.assertEqual(call({'op':'stats'})['encoder_loads'],1)
            # Legacy defaults unchanged, no added envelope fields without opt-in.
            self.assertEqual(call({'op':'search','query':'backup'})['mode'],'semantic')
            self.assertEqual(call({'op':'search','mode':'lexical','query':'backup'})['mode'],'lexical')
            (source/old['path']).write_text('Replacement unique_new_identifier immutable revision.',encoding='utf-8')
            for mode in ['bm25_or','hybrid_rrf']:
                self.assertNotIn(old['id'],[h['id'] for h in call({'op':'search','mode':mode,'query':'task_group backup','limit':8})['hits']])
            call(get,False)
            call({'op':'sync'})
            with closing(sqlite3.connect(str(dbpath)+'.lexical.sqlite')) as lexical_db:
                self.assertNotIn(old['id'],[r[0] for r in lexical_db.execute('SELECT id FROM lexical')],
                                 'sync must reconcile an activated lexical index')
            fresh = call({'op':'search','mode':'bm25_or','query':'unique_new_identifier'})['hits'][0]
            self.assertEqual(fresh['revision'],2)
            stop()
            call,stop = spawn()
            self.assertEqual(call({'op':'search','mode':'hybrid_rrf','query':'unique_new_identifier'})['hits'][0]['id'],fresh['id'])
            (source/fresh['path']).unlink()
            self.assertEqual(call({'op':'search','mode':'bm25_or','query':'unique_new_identifier'})['hits'],[])
            call({'op':'get','id':fresh['id'],'revision':2,'sha256':fresh['sha256']},False)
            call({'op':'sync'})
            stop()
            call,stop = spawn()
            self.assertEqual(call({'op':'search','mode':'bm25_or','query':'unique_new_identifier'})['hits'],[])
            self.assertEqual(call({'op':'stats'})['revision_snapshots'],5)
            stop()
            self.assertEqual((source/'sentinel.md').read_text(),'Unallowlisted sentinel.')
            (run/'per-query-parity.json').write_text(json.dumps(parity,indent=2),encoding='utf-8')
            (run/'result.json').write_text(json.dumps({'passed':True,'queries':len(parity),'sessions':3}),encoding='utf-8')
        finally:
            for proc in workers:
                if proc.poll() is None:
                    proc.terminate(); proc.wait(timeout=15)
                for stream in [proc.stdin,proc.stdout]:
                    if not stream.closed:
                        stream.close()
            for log in logs:
                log.close()
            cleanup = server.close()
            for name in ['server.yaml','server.log']:
                if (server_root/name).exists():
                    shutil.copyfile(server_root/name,run/name)
            shutil.rmtree(root)
            cleanup.update(scratch_removed=not root.exists(),worker_exit_codes=[p.returncode for p in workers])
            (run/'transcript.json').write_text(json.dumps(transcript,indent=2),encoding='utf-8')
            (run/'cleanup.json').write_text(json.dumps(cleanup,indent=2),encoding='utf-8')
            self.assertTrue(cleanup['process_exited'] and cleanup['port_closed'] and cleanup['scratch_removed'])
            print('HYBRID_EVIDENCE='+str(run))


if __name__ == '__main__':
    unittest.main()
