"""Frozen mechanical ranking contracts; not semantic relevance judgments."""
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools.agent_knowledge_runtime import Runtime
from tools.knowledge_runtime import KnowledgeRuntime

SCRATCH = Path('C:/Users/johan/AppData/Local/hermes/cache/scratch')


class LexicalContract(unittest.TestCase):
    def test_real_bm25_or_preserves_identifiers_and_persists(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            root = Path(folder)
            authority = Runtime.__new__(Runtime)
            authority.path = root / 'authority.sqlite'
            authority.root = root
            authority.allowed = ['a.md', 'b.md', 'c.md']
            authority.write = True
            authority.generation = 'fixture-generation'
            authority.encoder = type('Identity', (), {'identity': 'fixture-model'})()
            authority.db = sqlite3.connect(authority.path)
            authority.db.row_factory = sqlite3.Row
            authority.lock = None
            with authority.db:
                authority.db.executescript('CREATE TABLE chunks(id TEXT PRIMARY KEY,path TEXT,revision INTEGER,sha TEXT,start INTEGER,stop INTEGER,text TEXT,active INTEGER); CREATE TABLE jobs(id TEXT, pending INTEGER);')
                for identity, path, text in [('a', 'a.md', 'TaskGroup task_group Python3.11 C++ ->> backup'), ('b', 'b.md', 'task group Python3.12 C -> backup'), ('c', 'c.md', 'backup backup backup')]:
                    (root/path).write_text(text, encoding='utf-8')
                    authority.db.execute('INSERT INTO chunks VALUES(?,?,1,?,0,?,?,1)', (identity,path,hashlib.sha256(text.encode()).hexdigest(),len(text),text))
            runtime = KnowledgeRuntime(authority)
            try:
                result = runtime.handle({'op':'search','mode':'bm25_or','query':'task_group absent','limit':8})
                self.assertEqual([hit['id'] for hit in result['hits']], ['a'])
                for query in ['Python3.11', 'C++', '->>']:
                    self.assertEqual([h['id'] for h in runtime.handle({'op':'search','mode':'bm25_or','query':query})['hits']], ['a'])
                lexical_path = Path(str(authority.path) + '.lexical.sqlite')
                self.assertTrue(lexical_path.is_file())
                with closing(sqlite3.connect(lexical_path)) as db:
                    self.assertIn('fts5', db.execute("SELECT sql FROM sqlite_master WHERE name='lexical'").fetchone()[0])
                trace = []
                runtime.lexical.db.set_trace_callback(trace.append)
                runtime.handle({'op':'search','mode':'bm25_or','query':'backup'})
                self.assertTrue(any('bm25(lexical)' in sql and ' OR ' not in sql for sql in trace))
                (root/'a.md').write_text('edited externally', encoding='utf-8')
                self.assertEqual(runtime.handle({'op':'search','mode':'bm25_or','query':'task_group'})['hits'], [])
            finally:
                runtime.close()
            with closing(sqlite3.connect(lexical_path)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM lexical').fetchone()[0], 3)
            # Read-only restart reuses the persisted snapshot, never rewrites it.
            authority.db = sqlite3.connect(authority.path)
            authority.db.row_factory = sqlite3.Row
            authority.write = False
            reader = KnowledgeRuntime(authority)
            try:
                self.assertEqual(reader.handle({'op':'search','mode':'bm25_or','query':'backup'})['hits'][0]['id'], 'c')
                with self.assertRaisesRegex(ValueError, '128'):
                    reader.handle({'op':'search','mode':'bm25_or','query':' '.join('t'+str(n) for n in range(129))})
                authority.db.execute("UPDATE chunks SET active=0 WHERE id='c'")
                authority.db.commit()
                with self.assertRaisesRegex(ValueError, 'snapshot stale'):
                    reader.handle({'op':'search','mode':'bm25_or','query':'backup'})
            finally:
                reader.close()
            with closing(sqlite3.connect(lexical_path)) as db:
                db.execute("UPDATE binding SET owner='wrong-owner'")
                db.commit()
            authority.db = sqlite3.connect(authority.path)
            authority.db.row_factory = sqlite3.Row
            reader = KnowledgeRuntime(authority)
            try:
                with self.assertRaisesRegex(ValueError, 'ownership'):
                    reader.handle({'op':'search','mode':'bm25_or','query':'backup'})
            finally:
                reader.close()


class FusionContract(unittest.TestCase):
    def test_frozen_per_query_rrf_one_based_k60_and_id_ties(self):
        from tools import knowledge_runtime
        self.assertTrue(hasattr(knowledge_runtime, 'fuse_ranks'), 'deterministic RRF is missing')
        # Frozen independently worked lists, including overlap, disjoint ties and duplicates.
        fixtures = [(['c','a','b'], ['b','a','d'], ['b','a','c','d']),
                    (['z','a'], ['b','a'], ['a','b','z']),
                    ([], ['b','a'], ['b','a']),
                    (['b','b','a'], ['a'], ['a','b'])]
        for dense, lexical, expected in fixtures:
            with self.subTest(dense=dense, lexical=lexical):
                ranked = knowledge_runtime.fuse_ranks(dense, lexical)
                self.assertEqual([identity for identity, score in ranked], expected)
                for identity, score in ranked:
                    # Independent rank lookup (not the implementation's accumulator).
                    unique_dense, unique_lexical = list(dict.fromkeys(dense)), list(dict.fromkeys(lexical))
                    wanted = sum(1.0/(61 + branch.index(identity)) for branch in [unique_dense,unique_lexical] if identity in branch)
                    self.assertAlmostEqual(score, wanted, places=15)


class CompactContract(unittest.TestCase):
    def test_compact_version_two_is_lossless_and_removes_only_duplicates(self):
        from tools import knowledge_runtime
        self.assertTrue(hasattr(knowledge_runtime, 'compact_evidence'), 'compact v2 response is missing')
        hits = [{'id':'a','owner':'same','model':'same','text':'full alpha','revision':1,'sha256':'hash-a','start':0,'stop':10,'trust':'untrusted_source_data'},
                {'id':'b','owner':'same','model':'same','text':'full beta','revision':2,'sha256':'hash-b','start':3,'stop':12,'trust':'untrusted_source_data'}]
        result = {'hits':hits,'mode':'hybrid_rrf','pending':0,'answerability':'not_estimated'}
        packed = knowledge_runtime.compact_evidence(result)
        self.assertEqual(packed['contract_version'],2)
        self.assertEqual(packed['shared'],{'owner':'same','model':'same','trust':'untrusted_source_data'})
        self.assertEqual([{**packed['shared'],**hit} for hit in packed['hits']],hits)
        self.assertEqual(result['hits'],hits)
        self.assertEqual(knowledge_runtime.compact_evidence({'hits':[]})['shared'],{})
        self.assertEqual(knowledge_runtime.compact_evidence(hits[0])['evidence'],hits[0])


if __name__ == '__main__':
    unittest.main()
