import unittest
import importlib.util

class RecipeTests(unittest.TestCase):
    def test_finite_cli_is_available(self):
        from pathlib import Path
        import subprocess,sys
        p=subprocess.run([sys.executable,'-m','tools.qdrant_knowledge','--help'],capture_output=True,text=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('import',p.stdout)
        p=subprocess.run([sys.executable,'-m','tools.qdrant_knowledge.migrate','--help'],capture_output=True,text=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('--executable',p.stdout)

    def test_native_bm25_recipe_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.qdrant_knowledge'), 'Qdrant full-text runtime missing')
        from tools.qdrant_knowledge.core import BM25
        r=BM25.fit(['alpha alpha beta', 'beta gamma'])
        self.assertEqual(r.state['vocabulary'], {'alpha':0,'beta':1,'gamma':2})
        self.assertGreater(r.query('alpha')['values'][0],r.query('beta')['values'][0])
        self.assertEqual(r.document('alpha alpha beta')['indices'],[0,1])
        import math
        doc=r.document('alpha alpha beta');query=r.query('alpha alpha')
        score=sum(weight*dict(zip(query['indices'],query['values'])).get(index,0) for index,weight in zip(doc['indices'],doc['values']))
        expected=math.log1p((2-1+.5)/(1+.5))*2*2.2/(2+1.2*(.25+.75*3/2.5))
        self.assertAlmostEqual(score,expected,places=12)
        self.assertEqual(r.query('alpha'),query)
        self.assertEqual(len(set(r.state['vocabulary'].values())),len(r.state['vocabulary']))

class IntegrationTests(unittest.TestCase):
    def test_full_text_native_service_and_archive_independent_reads(self):
        from pathlib import Path
        import json, sqlite3, tempfile, uuid, sys
        from unittest.mock import patch
        from tools.agent_knowledge_runtime import digest
        from tools.qdrant_knowledge import core
        self.assertTrue(hasattr(core,'Store'), 'full-text Store missing')
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
        from tools.server_benchmark import Server
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo/'artifacts/qdrant-text') as folder:
            out=Path(folder);root=out/'root';root.mkdir(); archive=out/'archive.sqlite'
            db=sqlite3.connect(archive)
            db.executescript('CREATE TABLE sources(path,revision,sha,size,status,metadata); CREATE TABLE revisions(path,revision,sha,size,status,original); CREATE TABLE chunks(id,path,revision,sha,start,stop,text,heading,active);')
            for i in range(40):
                name=f'notes/n{i}.md';p=root/name;p.parent.mkdir(exist_ok=True)
                text=('# Café mémoire\n'+('local sparse search confidentialité alpha ' if i==0 else 'semantic dense retrieval beta ')* (2400 if i==0 else 2))+'\n \t\n'
                data=text.encode('utf-8-sig');p.write_bytes(data);sha=digest(data)
                db.execute('insert into sources values(?,1,?,?,\'active\',\'{}\')',(name,sha,len(data)))
                db.execute('insert into revisions values(?,1,?,?,\'active\',?)',(name,sha,len(data),data))
                for start in range(0,len(text),400):
                    chunk=text[start:start+400];db.execute('insert into chunks values(?,?,1,?,?,?,?,\'Café\',1)',(str(uuid.uuid4()),name,sha,start,start+len(chunk),chunk))
            db.commit();db.close()
            server=Server(out);server.start()
            try:
                state=out/'registry.json';s=core.Store(state=state,root=root,model=repo/'artifacts/models/minilm',qdrant_url=f'http://127.0.0.1:{server.port}',collection='akr_'+uuid.uuid4().hex,create=True)
                result=s.import_archive(archive)
                self.assertEqual(result['source'],40)
                self.assertGreater(result['chunk'],40)
                self.assertEqual(s.verify_archive(archive)['sources_verified'],40)
                # Actual write succeeds, acknowledgment lost: durable pending + replay.
                request=s.remote.request;lost=[False]
                def lost_ack(method,path='',body=None):
                    value=request(method,path,body)
                    if method=='PUT' and path=='/points?wait=true' and not lost[0]:
                        lost[0]=True;raise RuntimeError('lost successful acknowledgment')
                    return value
                s.registry['completed']=[];s.remote.request=lost_ack
                with self.assertRaisesRegex(RuntimeError,'lost successful'):s.import_archive(archive)
                s=core.Store(state=state)
                with self.assertRaises(ValueError):s.search('alpha')
                self.assertEqual(s.import_archive(archive)['source'],40)
                hit=s.search('alpha',mode='bm25')[0]
                vectorpoint=s.remote.request('POST','/points',dict(ids=[hit['id']],with_payload=True,with_vector=True))[0]
                vectorpoint['vector']['sparse']={'indices':[0],'values':[999.]}
                s.remote.request('PUT','/points?wait=true',dict(points=[{k:vectorpoint[k] for k in ('id','vector','payload')}]))
                with self.assertRaisesRegex(ValueError,'vector'):s.verify_archive(archive)
                s.import_archive(archive)
                self.assertEqual(s.verify_archive(archive)['sources_verified'],40)
                archive.rename(out/'unavailable.sqlite')
                with patch('sqlite3.connect',side_effect=AssertionError('SQLite forbidden on read')):
                    s=core.Store(state=state)
                    hits=s.search('confidentialité alpha',mode='hybrid')
                    self.assertTrue(hits)
                    point=s.get(hits[0]['id']);self.assertIn('text',point)
                    source=s.get(point['source_id']);self.assertGreater(len(source['text']),65536)
                    self.assertEqual(source['encoding'],'utf-8-sig')
                p=root/point['path'];before=p.read_bytes();p.write_bytes(before+b'changed')
                self.assertIsNone(s.get(point['id']))
                p.write_bytes(before)
                self.assertEqual(s.stats()['source'],40)
                # Another writer's pending checkpoint must invalidate an older resident reader.
                from tools.qdrant_knowledge.core import save
                saved=json.loads(state.read_bytes());pending=dict(saved,status='importing');save(state,pending)
                with self.assertRaises(ValueError):s.search('alpha')
                save(state,saved)
                with self.assertRaises(ValueError):core.Store(state=out/'foreign.json',root=root,model=repo/'artifacts/models/minilm',qdrant_url=f'http://127.0.0.1:{server.port}',collection=s.config['collection'],create=True)
                # Snapshot update + deletion, including lost ack and fresh reopen.
                old_source=source['id'];old_chunk=point['id']
                archive=out/'unavailable.sqlite'
                newtext='# Updated\narchival refreshed alpha canonical.';newdata=newtext.encode('utf-8-sig');newsha=digest(newdata)
                p.write_bytes(newdata);(root/'notes/n1.md').unlink()
                self.assertIsNone(s.get(old_chunk))
                with self.assertRaisesRegex(ValueError,'archive/current source hash mismatch'):s.import_archive(archive)
                self.assertFalse(any(h['path']==point['path'] for h in s.search('alpha',scope='all')))
                db=sqlite3.connect(archive)
                db.execute('update chunks set active=0 where path in (?,?)',(point['path'],'notes/n1.md'))
                db.execute('update sources set revision=2,sha=?,size=? where path=?',(newsha,len(newdata),point['path']))
                db.execute('insert into revisions values(?,2,?,?,\'active\',?)',(point['path'],newsha,len(newdata),newdata))
                db.execute('insert into chunks values(?,?,2,?,0,?,?,\'Updated\',1)',(str(uuid.uuid4()),point['path'],newsha,len(newtext),newtext))
                db.execute("update sources set status='deleted',revision=2 where path='notes/n1.md'")
                db.commit();db.close()
                request=s.remote.request;lost=[False];s.remote.request=lost_ack
                with self.assertRaisesRegex(RuntimeError,'lost successful'):s.import_archive(archive)
                s=core.Store(state=state)
                with self.assertRaises(ValueError):s.get(old_source)
                self.assertEqual(s.import_archive(archive)['source'],39)
                self.assertIsNone(s.get(old_source));self.assertIsNone(s.get(old_chunk))
                self.assertTrue(s.search('archival refreshed',mode='bm25'))
                self.assertEqual(s.verify_archive(archive)['sources_verified'],39)
                trace=[json.loads(line) for line in (out/'network.jsonl').read_text().splitlines()]
                fused=[row for row in trace if 'prefetch' in row['request']]
                self.assertTrue(fused)
                self.assertEqual(fused[0]['request']['query'],{'rrf':{'k':60}})
                self.assertEqual({b['using'] for b in fused[0]['request']['prefetch']},{'dense','sparse'})
            finally:
                cleanup=server.close()
                self.assertTrue(cleanup['process_exited']);self.assertTrue(cleanup['port_closed'])

if __name__=='__main__':unittest.main()
