"""Regression tests for instruction routing and bounded citation-safe reads."""
import unittest

class RoutingTests(unittest.TestCase):
    def test_auto_scope_routes_instructions_without_hiding_mixed_questions(self):
        from tools.qdrant_knowledge.core import route_scope
        cases=[('What does the UI skill require?','instruction'),
               ('Quelles références avant une refonte UI/UX ?','instruction'),
               ('Compare UI acceptance method with BP process baseline','all'),
               ('Comment présenter des statistiques sans inventer de scores ?','all'),
               ('Le circuit BP commence-t-il par DEMPART ?','knowledge'),
               ('Next.js refresh URL filters','knowledge')]
        for query,expected in cases:
            with self.subTest(query=query):self.assertEqual(route_scope(query),expected)

class TransportDefaultsTests(unittest.TestCase):
    def test_default_transport_routes_auto_and_keeps_explicit_scope(self):
        from tools.qdrant_knowledge.__main__ import operation
        class Recorder:
            def search(self,*args,**kwargs):return kwargs
        self.assertEqual(operation(Recorder(),{'op':'search','query':'UI skill'})['scope'],'auto')
        self.assertEqual(operation(Recorder(),{'op':'search','query':'UI skill','scope':'knowledge'})['scope'],'knowledge')

class TiePresentationTests(unittest.TestCase):
    def test_equal_native_scores_have_stable_source_and_chunk_presentation(self):
        from tools.qdrant_knowledge.core import Store,BM25
        class Remote:
            def __init__(self,points):self.points=points
            def request(self,*args):return {'points':self.points}
        points=[dict(id='b',score=.02,payload=dict(path='same.md',metadata={},scope='knowledge')),
                dict(id='a',score=.02,payload=dict(path='same.md',metadata={},scope='knowledge')),
                dict(id='c',score=.01,payload=dict(path='other.md',metadata={},scope='knowledge'))]
        s=Store.__new__(Store);s.registry={'owner':'test','bm25':BM25.fit(['alpha']).state};s.ready=lambda:None
        s._present=lambda p,cache:dict(id=p['id'],**p['payload'])
        acquired=[]
        for order in [points,list(reversed(points))]:
            s.remote=Remote(order)
            acquired.append([h['id'] for h in s.search('alpha',mode='bm25',limit=2)])
        self.assertEqual(acquired,[['a','c'],['a','c']])

class LivePresentationTests(unittest.TestCase):
    def test_auto_prefilter_and_bounded_source_window_on_native_service(self):
        import json,sqlite3,sys,tempfile,uuid
        from pathlib import Path
        from tools.qdrant_knowledge.core import Store,digest
        repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'tools'))
        from tools.server_benchmark import Server
        with tempfile.TemporaryDirectory(dir=repo/'artifacts/qdrant-quality') as folder:
            out=Path(folder);root=out/'root';root.mkdir();archive=out/'archive.sqlite'
            db=sqlite3.connect(archive)
            db.executescript('CREATE TABLE sources(path,revision,sha,size,status,metadata); CREATE TABLE revisions(path,revision,sha,size,status,original); CREATE TABLE chunks(id,path,revision,sha,start,stop,text,heading,active);')
            for name,text in [('notes/ui.md','UI skills ordinary note'),('skills/demo/SKILL.md','prefix '*40+'UI skill dark theme proof '+'suffix '*40)]:
                data=text.encode();p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);sha=digest(data)
                db.execute("insert into sources values(?,1,?,?,'active','{}')",(name,sha,len(data)))
                db.execute("insert into revisions values(?,1,?,?,'active',?)",(name,sha,len(data),data))
                db.execute("insert into chunks values(?,?,1,?,0,?,?,'',1)",(str(uuid.uuid4()),name,sha,len(text),text))
            db.commit();db.close();server=Server(out)
            try:
                server.start();s=Store(state=out/'registry.json',root=root,model=repo/'artifacts/models/minilm',qdrant_url=f'http://127.0.0.1:{server.port}',collection='akr_'+uuid.uuid4().hex,create=True)
                s.import_archive(archive)
                hits=s.search('UI skill dark theme',limit=1)
                self.assertEqual(hits[0]['scope'],'instruction')
                trace=json.loads((out/'network.jsonl').read_text().splitlines()[-1])
                for branch in trace['request']['prefetch']:
                    self.assertIn({'key':'scope','match':{'value':'instruction'}},branch['filter']['must'])
                source=s.get(hits[0]['source_id'])
                view=s.get(source['id'],start=280,max_chars=24)
                self.assertEqual(view['text'],source['text'][280:304])
                self.assertEqual(view['view'],dict(start=280,stop=304,total_characters=len(source['text']),truncated=True,text_sha=digest(view['text'].encode())))
                self.assertEqual(view['text_sha'],source['text_sha'])
                self.assertEqual(view['sha'],source['sha'])
                for invalid in [dict(start=-1),dict(max_chars=0),dict(max_chars=65537),dict(start=True)]:
                    with self.assertRaises(ValueError):s.get(source['id'],**invalid)
                p=root/source['path'];p.write_bytes(p.read_bytes()+b'changed')
                self.assertIsNone(s.get(source['id'],start=280,max_chars=24))
            finally:
                cleanup=server.close();self.assertTrue(cleanup['process_exited']);self.assertTrue(cleanup['port_closed'])

if __name__=='__main__':unittest.main()
