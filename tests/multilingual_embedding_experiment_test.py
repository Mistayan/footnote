"""Public-only real artifact recipe/provenance tests; no runtime mutation."""
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))
SOURCES = REPO / 'artifacts/multilingual-embeddings/sources-8f28a3576bc24f32a685ec765c8d3f93'


class RecipeTest(unittest.TestCase):
    def test_exact_actual_multilingual_identity_and_hashes(self):
        import importlib.util
        spec = importlib.util.find_spec('multilingual_embedding_experiment')
        self.assertIsNotNone(spec, 'audited recipe builder is missing')
        import multilingual_embedding_experiment as m
        identities = json.loads((SOURCES / 'identities.json').read_bytes())
        recipe = m.audited_recipe(REPO / 'artifacts/models/e5-small', identities['e5'])
        self.assertEqual(recipe['repository'], 'Xenova/multilingual-e5-small')
        self.assertEqual(recipe['revision'], '761b726dd34fb83930e26aab4e9ac3899aa1fa78')
        self.assertEqual(recipe['upstream']['license'], 'mit')
        self.assertEqual(recipe['conversion_license'], 'NOT_DECLARED_IN_CONVERSION_CARD')
        self.assertEqual(recipe['max_length'], 512)
        self.assertEqual(recipe['query_prefix'], 'query: ')
        self.assertEqual(recipe['passage_prefix'], 'passage: ')
        with self.assertRaises(ValueError):
            m.audited_recipe(REPO / 'artifacts/models/e5-small', identities['minilm'])

    def test_real_onnx_pooling_prefix_tokenizer_and_baseline_parity(self):
        import multilingual_embedding_experiment as m
        self.assertTrue(hasattr(m, 'verified_encoder'), 'verified encoder missing')
        import numpy as np
        import technical_quality as tq
        texts = ['Pourquoi WAL exige le même ordinateur ?', 'SQLite readers and concurrent writers.']
        for name in ('minilm', 'e5-small'):
            e = m.verified_encoder(REPO / 'artifacts/models' / name)
            old = tq.ResidentEncoder(REPO / 'artifacts/models' / name)
            for kind in ('query', 'passage'):
                actual = e.encode(texts, kind)
                np.testing.assert_array_equal(actual, old.encode(texts, kind))
                tokens = e.tokenizer.encode_batch([e.manifest[kind + '_prefix'] + t for t in texts])
                ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
                mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
                data = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)}
                hidden = e.session.run(None, {v.name: data[v.name] for v in e.session.get_inputs()})[0]
                pooled = np.stack([h[a.astype(bool)].mean(axis=0, dtype=np.float64) for h, a in zip(hidden, mask)])
                pooled /= np.linalg.norm(pooled, axis=1, keepdims=True)
                np.testing.assert_allclose(actual, pooled, atol=1e-7)
                self.assertTrue(all(t.ids[-1] == 2 for t in tokens))
        e = m.verified_encoder(REPO / 'artifacts/models/e5-small', cap=128)
        self.assertEqual(e.manifest['max_length'], 128)
        self.assertEqual(len(e.tokenizer.encode('query: ' + 'word ' * 500).ids), 128)

    def test_saved_query_vectors_reject_semantic_hash_mismatch(self):
        import multilingual_embedding_experiment as m
        self.assertTrue(hasattr(m, 'audit_query_vectors'), 'query-vector provenance audit missing')
        import hashlib
        import tempfile
        import os
        import numpy as np
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as directory:
            run = Path(directory)
            vector = np.asarray([[0.25, 0.5]], dtype=np.float64)
            np.save(run / 'variant-query-vectors.npy', vector)
            row = {'id': 'q', 'variant': 'variant', 'query_vector_sha256': hashlib.sha256(vector[0].tobytes()).hexdigest()}
            self.assertTrue(m.audit_query_vectors(run, [row], [{'id': 'q'}]))
            row['query_vector_sha256'] = '0' * 64
            with self.assertRaises(AssertionError):
                m.audit_query_vectors(run, [row], [{'id': 'q'}])

    def test_real_paired_server_run_and_provenance(self):
        import multilingual_embedding_experiment as m
        self.assertTrue(hasattr(m, 'experiment'), 'paired runner missing')
        import uuid
        run = REPO / 'artifacts/multilingual-embeddings' / ('paired-' + uuid.uuid4().hex)
        report = m.experiment(run)
        self.assertEqual(report['rows'], 512)
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertEqual(report['gate_violations'], 0)
        self.assertTrue(m.verify_run(run))
        target = run / 'corpus.json'
        original = target.read_bytes()
        target.write_bytes(original + b' ')
        try:
            with self.assertRaises(AssertionError):
                m.verify_run(run)
        finally:
            target.write_bytes(original)
        self.assertTrue(m.verify_run(run))
        print('VERIFIED_RUN=' + str(run), flush=True)


if __name__ == '__main__':
    unittest.main()
