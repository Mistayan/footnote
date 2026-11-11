"""Pinned resident reranker contracts; mechanical, not relevance qualification."""
import json
import hashlib
import sqlite3
from pathlib import Path
import tempfile
import unittest

from tools import knowledge_runtime

REPO = Path(__file__).resolve().parents[1]
MODEL = REPO / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model'
SCRATCH = Path('C:/Users/johan/AppData/Local/hermes/cache/scratch')


class PinnedModel(unittest.TestCase):
    def test_real_pinned_model_resident_parity_and_receipt_tamper_rejection(self):
        self.assertTrue(hasattr(knowledge_runtime, 'ResidentReranker'), 'optional resident reranker missing')
        from tools.retrieval_ablation import CrossEncoder
        reranker = knowledge_runtime.ResidentReranker(MODEL)
        incumbent = CrossEncoder(MODEL)
        documents = [{'id': 'a', 'text': 'SQLite backups preserve the database.'},
                     {'id': 'b', 'text': 'A comet orbits the Sun.'}]
        for _ in range(2):
            self.assertEqual(reranker.rank('SQLite backup', documents), incumbent.rank('SQLite backup', documents))
        self.assertEqual(reranker.loads, 1)
        self.assertEqual(reranker.session.get_providers(), ['CPUExecutionProvider'])
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            root = Path(folder)
            receipt = json.loads((MODEL/'receipt.json').read_bytes())
            receipt['revision'] = '0'*40
            (root/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'pinned'):
                knowledge_runtime.ResidentReranker(root)
            # An unchanged receipt must not allow modified local artifact bytes.
            (root/'receipt.json').write_bytes((MODEL/'receipt.json').read_bytes())
            (root/'README.md').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                knowledge_runtime.ResidentReranker(root)


class RequestContract(unittest.TestCase):
    def test_budget_requires_explicit_loaded_ranker_before_sources_are_read(self):
        class NoReads:
            def handle(self, request):
                raise AssertionError('invalid rerank request reached authority')
        runtime = knowledge_runtime.KnowledgeRuntime(NoReads())
        with self.assertRaisesRegex(ValueError, 'reranker'):
            runtime.handle({'op':'search', 'mode':'hybrid_rrf', 'query':'backup', 'rerank_budget':'budget5'})

    def test_eligible_budget_and_post_inference_source_recheck(self):
        from tools.agent_knowledge_runtime import Runtime
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            root = Path(folder)
            authority = Runtime.__new__(Runtime)
            authority.path, authority.root = root/'authority.sqlite', root
            authority.allowed = [f'd{n:02}.md' for n in range(25)]
            authority.write, authority.generation, authority.lock = True, 'fixture', None
            authority.encoder = type('Encoder', (), {'identity':'fixture', 'encode':lambda *args:[[1.0]]})()
            authority.db = sqlite3.connect(authority.path)
            authority.db.row_factory = sqlite3.Row
            authority.db.executescript('CREATE TABLE chunks(id TEXT PRIMARY KEY,path TEXT,revision INTEGER,sha TEXT,start INTEGER,stop INTEGER,text TEXT,active INTEGER); CREATE TABLE jobs(id TEXT,pending INTEGER);')
            for n, path in enumerate(authority.allowed):
                text = f'backup database fixture {n:02}'
                (root/path).write_text(text)
                authority.db.execute('INSERT INTO chunks VALUES(?,?,1,?,0,?,?,1)', (str(n),path,hashlib.sha256(text.encode()).hexdigest(),len(text),text))
            authority.db.commit()
            points = [{'id':row['id'],'score':1.0,'payload':authority.signature(row)} for row in authority.db.execute('SELECT * FROM chunks')]
            authority.remote = type('Remote', (), {'request':lambda *args: {'points':points}})()
            # One stale high-rank candidate must never consume an inference pair.
            (root/'d00.md').unlink()
            runtime = knowledge_runtime.KnowledgeRuntime(authority)
            class Ranker:
                loads, identity, recipe, at_limit = 1, 'test', 'test', 0
                mutate = False
                def rank(self, query, docs):
                    self.docs = docs
                    if self.mutate:
                        (root/docs[-1]['path']).write_text('edited during inference')
                    return [d['id'] for d in reversed(docs)], {d['id']:float(n) for n,d in enumerate(docs)}
            ranker = Ranker()
            runtime.reranker = ranker
            try:
                for budget in (5,10,20):
                    result = runtime.handle({'op':'search','mode':'hybrid_rrf','query':'backup','limit':8,'rerank_budget':f'budget{budget}'})
                    self.assertEqual(result['reranking']['candidate_count'], budget)
                    self.assertEqual(len(ranker.docs),budget)
                    self.assertNotIn('0',[d['id'] for d in ranker.docs])
                    self.assertEqual([h['id'] for h in result['hits']], [d['id'] for d in reversed(ranker.docs)][:8])
                    self.assertTrue(all(h['applicability']=='not_estimated' for h in result['hits']))
                ranker.mutate = True
                result = runtime.handle({'op':'search','mode':'hybrid_rrf','query':'backup','rerank_budget':'budget5'})
                self.assertNotIn(ranker.docs[-1]['id'],[h['id'] for h in result['hits']])
                for budget in ('budget0',5,None,True):
                    with self.assertRaisesRegex(ValueError,'budget'):
                        runtime.handle({'op':'search','mode':'hybrid_rrf','query':'backup','rerank_budget':budget})
                for mode in ('semantic','lexical','bm25_or'):
                    with self.assertRaisesRegex(ValueError,'hybrid_rrf'):
                        runtime.handle({'op':'search','mode':mode,'query':'backup','rerank_budget':'budget5'})
                ranker.rank = lambda *args: (['out-of-pool'], {'out-of-pool': 42.0})
                with self.assertRaisesRegex(ValueError,'permutation'):
                    runtime.handle({'op':'search','mode':'hybrid_rrf','query':'backup','rerank_budget':'budget5'})
            finally:
                runtime.close()


if __name__ == '__main__':
    unittest.main()