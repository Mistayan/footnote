"""Deterministic public-corpus retrieval evaluation contract."""
import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'tools/technical_quality.py'


class QualityTests(unittest.TestCase):
    def test_metrics_distinguish_incompatibility_from_relevance(self):
        self.assertTrue(MODULE.exists(), 'technical quality harness must exist')
        spec = importlib.util.spec_from_file_location('technical_quality', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.score(['old', 'good', 'other'], {'relevant': ['good'], 'incompatible': ['old']})
        self.assertEqual(result['top1'], 0)
        self.assertEqual(result['mrr'], 0.5)
        self.assertEqual(result['recall_at_5'], 1)
        self.assertEqual(result['incompatible_at_5'], 1)
        self.assertEqual(result['incompatible_at_1'], 1)
        self.assertIsNone(result['no_answer_false_acceptance'])

    def module(self):
        spec = importlib.util.spec_from_file_location('technical_quality', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_fts_and_rrf_are_deterministic(self):
        m = self.module()
        db = m.lexical_index([{'id': 'a', 'text': 'SQLite WAL checkpoint'}, {'id': 'b', 'text': 'SQLite backup'}])
        self.assertEqual(m.lexical_search(db, 'SQLite checkpoint'), ['a'])
        self.assertEqual(m.lexical_search(db, 'absenttoken'), [])
        self.assertEqual(m.fuse(['b', 'a'], ['a', 'b'])[:2], ['a', 'b'])
        db.close()

    def test_excerpt_is_exact_and_missing_anchor_fails(self):
        m = self.module()
        text = 'prefix ' * 50 + 'evidence needle\n' + 'suffix ' * 50
        excerpt = m.excerpt(text, 'evidence needle', 120)
        self.assertEqual(text[excerpt['start']:excerpt['end']], excerpt['text'])
        self.assertIn('evidence needle', excerpt['text'])
        with self.assertRaises(ValueError):
            m.excerpt(text, 'invented phrase', 120)

    def test_resident_matches_existing_helper(self):
        m = self.module()
        import sys
        sys.path.insert(0, str(MODULE.parent))
        from embed import encode
        import numpy as np
        model = MODULE.parents[1] / 'artifacts/models/minilm'
        resident = m.ResidentEncoder(model)
        before = resident.session
        texts = ['SQLite WAL checkpoint', 'annulation des tâches Python']
        actual = resident.encode(texts, 'query')
        expected = encode(model, {'kind': 'query', 'texts': texts})['vectors']
        np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=1e-6)
        resident.encode(['another passage'], 'passage')
        self.assertIs(before, resident.session)
        self.assertEqual(actual.shape, (2, 384))

    def test_source_normalization_excludes_active_html(self):
        m = self.module()
        self.assertEqual(m.source_text(b'<p>SQLite &amp; WAL</p><script>evil()</script><style>bad</style>', 'https://www.sqlite.org/wal.html'), 'SQLite & WAL')
        self.assertEqual(m.source_text(b'abc\r\ndef', 'https://raw.githubusercontent.com/python/cpython/x.rst'), 'abc\ndef')

    def test_frozen_inputs_reject_tampering(self):
        m = self.module()
        import tempfile
        import json
        scratch = pathlib.Path('C:/Users/johan/AppData/Local/hermes/cache/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = pathlib.Path(directory)
            (root / 'data').write_bytes(b'frozen')
            m.save(root / 'freeze.json', {'files': {'data': m.digest(b'frozen')}, 'harness_sha256': m.digest(MODULE.read_bytes())})
            self.assertIn('files', m.verify_snapshot(root))
            (root / 'data').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'frozen input changed'):
                m.verify_snapshot(root)

    def test_judgments_are_bounded_disjoint_and_explicit(self):
        m = self.module()
        names = {p[0] for p in m.PASSAGES}
        self.assertEqual(len(m.DEVELOPMENT), 12)
        self.assertEqual(len(m.HOLDOUT), 12)
        self.assertFalse({q[0] for q in m.DEVELOPMENT} & {q[0] for q in m.HOLDOUT})
        for query, relevant, incompatible, category in m.DEVELOPMENT + m.HOLDOUT:
            self.assertTrue(set(relevant + incompatible) <= names)
            self.assertFalse(set(relevant) & set(incompatible))
        self.assertEqual({len(v) for v in m.NO_ANSWER.values()}, {4})

    def test_child_chunks_preserve_offsets_and_parent_mapping(self):
        m = self.module()
        encoders = [m.ResidentEncoder(MODULE.parents[1] / 'artifacts/models' / name)
                    for name in ('minilm', 'e5-small')]
        text = ('SQLite WAL café annulation 日本語 ' * 120)
        corpus = [{'id': 'parent', 'source': 'public', 'start': 17,
                   'end': 17 + len(text), 'text': text}]
        children = m.child_chunks(corpus, encoders)
        self.assertGreater(len(children), 1)
        self.assertEqual(''.join(c['text'] for c in children), text)
        for child in children:
            self.assertEqual(child['parent_id'], 'parent')
            self.assertEqual(text[child['start'] - 17:child['end'] - 17], child['text'])
            for encoder in encoders:
                self.assertLess(encoder.token_count(child['text'], 'passage'), encoder.manifest['max_length'])
        self.assertEqual(m.parent_ranking([c['id'] for c in children], children), ['parent'])

    def test_threshold_uses_development_only(self):
        m = self.module()
        dev = [{'split': 'development', 'relevant': ['a'], 'max_cosine': .8},
               {'split': 'development', 'relevant': [], 'max_cosine': .4}]
        self.assertEqual(m.fit_threshold(dev), .8)
        with self.assertRaises(ValueError):
            m.fit_threshold(dev + [{'split': 'holdout', 'relevant': [], 'max_cosine': .99}])
        self.assertEqual(m.score([], {'relevant': [], 'incompatible': []})['no_answer_false_acceptance'], 0)


if __name__ == '__main__':
    unittest.main()
