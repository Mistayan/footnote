"""Explicit metadata contracts, independent of model inference."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.knowledge_runtime import KnowledgeRuntime


class MetadataContracts(unittest.TestCase):
    def test_prefilter_both_branches_and_presentation(self):
        from tools.knowledge_runtime.lexical import LexicalIndex
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = sqlite3.connect(':memory:')
            db.row_factory = sqlite3.Row
            db.execute('CREATE TABLE chunks(id,path,revision,sha,start,stop,text,active)')
            for i in range(80):
                db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,1)', (str(i), 'bad.md', 1, 'hash', 0, 6, 'python'))
            db.execute("INSERT INTO chunks VALUES('good','good.md',1,'hash',0,6,'python',1)")
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps({'schema_version': 1, 'sources': {'good.md': {'documented_version': '3.11'}}}))
            calls = []
            def hydrate(identity):
                row = db.execute('SELECT * FROM chunks WHERE id=?', (identity,)).fetchone()
                return dict(id=identity, path=row['path'], owner='owner', model='model', revision=1, sha256='hash')
            def remote_request(method, path, body):
                calls.append(body)
                self.assertEqual(body['filter'], {'must': [{'has_id': ['good']}]})
                return {'points': [{'id': 'good', 'score': 1.0, 'payload': {k: hydrate('good')[k] for k in ('owner','model','id','revision','sha256')}}]}
            authority = SimpleNamespace(path=root/'authority.sqlite', allowed=['good.md','bad.md'], db=db,
                generation='owner', encoder=SimpleNamespace(identity='model', encode=lambda *a: [[1.0]]),
                remote=SimpleNamespace(request=remote_request), write=True, hydrate=hydrate, pending=lambda: 0,
                close=db.close)
            runtime = KnowledgeRuntime(authority, source_manifest=manifest)
            runtime.metadata.reconcile()
            authority.write = False
            self.assertEqual(runtime.handle({'op':'search','mode':'semantic','query':'python','constraints':{'documented_version':'3.11'}})['hits'][0]['id'], 'good')
            calls.clear()
            authority.write = True
            for mode in ('bm25_or', 'hybrid_rrf', 'semantic'):
                result = runtime.handle({'op':'search','mode':mode,'query':'python','constraints':{'documented_version':'3.11'}})
                self.assertEqual([hit['id'] for hit in result['hits']], ['good'])
                self.assertEqual(result['hits'][0]['source_metadata'], {'documented_version':'3.11'})
            self.assertEqual(len(calls), 2)
            def change_manifest_during_query(method, path, body):
                result = remote_request(method, path, body)
                manifest.write_text(json.dumps({'schema_version':1,'sources':{'good.md':{'documented_version':'3.12'}}}))
                return result
            authority.remote.request = change_manifest_during_query
            self.assertEqual(runtime.handle({'op':'search','mode':'hybrid_rrf','query':'python','constraints':{'documented_version':'3.11'}})['hits'], [])
            runtime.close()

    def test_manifest_is_explicit_strict_and_revision_bound(self):
        from tools.knowledge_runtime.metadata import MetadataIndex, validate_fields
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = sqlite3.connect(':memory:')
            db.row_factory = sqlite3.Row
            db.execute('CREATE TABLE chunks(id,path,revision,sha,active)')
            db.execute("INSERT INTO chunks VALUES('one','one.md',1,'hash',1)")
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps({'schema_version': 1, 'sources': {'one.md': {'technology': 'python', 'documented_version': '3.11'}}}))
            authority = SimpleNamespace(path=root/'authority.sqlite', allowed=['one.md'], db=db,
                                        generation='owner', encoder=SimpleNamespace(identity='model'), write=True)
            index = MetadataIndex(authority, manifest)
            with self.assertRaisesRegex(ValueError, 'sync'):
                index.eligible({'documented_version': '3.11'})
            index.reconcile()
            self.assertEqual(index.eligible({'documented_version': '3.11'}), ['one'])
            self.assertEqual(index.eligible({'documented_version': '3.12'}), [])
            self.assertNotIn('language', index.present({'id': 'one'}, {} )['source_metadata'])
            manifest.write_text(json.dumps({'schema_version': 1, 'sources': {'one.md': {}}}))
            with self.assertRaisesRegex(ValueError, 'sync'):
                index.eligible({})
            index.reconcile()
            self.assertEqual(index.eligible({'documented_version': '3.11'}), [])
            with self.assertRaisesRegex(ValueError, 'source_manifest'):
                KnowledgeRuntime(authority)
            stored = json.loads(index.path.read_text())
            stored['owner'] = 'foreign'
            index.path.write_text(json.dumps(stored))
            with self.assertRaisesRegex(ValueError, 'ownership'):
                index.reconcile()
            index.path.unlink()  # test-owned derived recovery, never authority
            index.reconcile()
            authority.root = root/'sources'
            authority.root.mkdir()
            in_source = authority.root/'manifest.json'
            in_source.write_bytes(manifest.read_bytes())
            with self.assertRaisesRegex(ValueError, 'separate'):
                MetadataIndex(authority, in_source)
            authority.write = False
            self.assertEqual(MetadataIndex(authority, manifest).eligible({}), ['one'])
            db.execute('UPDATE chunks SET revision=2')
            with self.assertRaisesRegex(ValueError, 'sync'):
                index.eligible({})
            for invalid in ({'secret': 'token'}, {'technology': '../secret'}, {'language': None}, {'status': True}):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    validate_fields(invalid)
            db.close()
