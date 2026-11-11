"""Independent BM25 arithmetic and actual native Qdrant fusion scores.

The interrupted TextVault contract is consolidated onto the existing Store;
lifecycle/update/delete/lost-ack coverage lives in test_qdrant_knowledge.
"""
import unittest
import math

class SparseContract(unittest.TestCase):
    def test_bm25_document_frequency_and_restart_vocabulary(self):
        from tools.qdrant_knowledge.core import BM25
        s=BM25.fit(['alpha alpha beta','beta gamma'])
        self.assertEqual(s.state['df'][s.state['vocabulary']['beta']],2)
        self.assertEqual(s.state['df'][s.state['vocabulary']['alpha']],1)
        d=s.document('alpha alpha beta');q=s.query('alpha')
        score=sum(v*dict(zip(q['indices'],q['values'])).get(i,0) for i,v in zip(d['indices'],d['values']))
        expected=math.log1p((2-1+.5)/(1+.5))*2*2.2/(2+1.2*(.25+.75*3/2.5))
        self.assertAlmostEqual(score,expected)
        self.assertEqual(BM25(s.state).query('alpha gamma absent'),s.query('alpha gamma absent'))
        self.assertEqual(s.query('absent'),dict(indices=[],values=[]))

class EngineContract(unittest.TestCase):
    def test_native_sparse_and_rrf_match_independent_arithmetic(self):
        import json,sqlite3,sys,tempfile,uuid
        from pathlib import Path
        from tools.qdrant_knowledge.core import Store,digest
        repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'tools'))
        from tools.server_benchmark import Server
        with tempfile.TemporaryDirectory(dir=repo/'artifacts/qdrant-text') as folder:
            out=Path(folder);root=out/'root';root.mkdir();archive=out/'archive.sqlite'
            db=sqlite3.connect(archive)
            db.executescript('CREATE TABLE sources(path,revision,sha,size,status,metadata); CREATE TABLE revisions(path,revision,sha,size,status,original); CREATE TABLE chunks(id,path,revision,sha,start,stop,text,heading,active);')
            for i,text in enumerate(['alpha alpha beta','beta gamma']):
                name=f'n{i}.md';data=text.encode();(root/name).write_bytes(data);sha=digest(data)
                db.execute("insert into sources values(?,1,?,?,'active','{}')",(name,sha,len(data)))
                db.execute("insert into revisions values(?,1,?,?,'active',?)",(name,sha,len(data),data))
                db.execute("insert into chunks values(?,?,1,?,0,?,?,'',1)",(str(uuid.uuid4()),name,sha,len(text),text))
            db.commit();db.close();server=Server(out)
            try:
                server.start();s=Store(state=out/'registry.json',root=root,model=repo/'artifacts/models/minilm',qdrant_url=f'http://127.0.0.1:{server.port}',collection='akr_'+uuid.uuid4().hex,create=True)
                s.import_archive(archive)
                hits=s.search('alpha',mode='bm25',dedup=False)
                expected=math.log1p((2-1+.5)/(1+.5))*2*2.2/(2+1.2*(.25+.75*3/2.5))
                self.assertEqual(len(hits),1);self.assertAlmostEqual(hits[0]['score'],expected,places=6)
                s.search('beta',mode='hybrid',dedup=False)
                trace=[json.loads(line) for line in (out/'network.jsonl').read_text().splitlines()]
                fused=trace[-1];self.assertEqual(fused['request']['query'],{'rrf':{'k':60}})
                contributions={}
                for branch in fused['request']['prefetch']:
                    points=s.remote.request('POST','/points/query',dict(branch,with_payload=False))['points']
                    # Qdrant 1.19.2 RrfQuery uses zero-based rank in k+rank.
                    for rank,point in enumerate(points):contributions[point['id']]=contributions.get(point['id'],0)+1/(60+rank)
                for point in fused['response']['result']['points']:
                    self.assertAlmostEqual(point['score'],contributions[point['id']],places=7)
            finally:
                cleanup=server.close();self.assertTrue(cleanup['process_exited']);self.assertTrue(cleanup['port_closed'])

if __name__=='__main__':unittest.main()
