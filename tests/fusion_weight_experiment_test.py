"""Finite fusion diagnostic tests; real models and isolated server, no mocks."""
import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))


class FusionTest(unittest.TestCase):
    def test_weighted_formula_independent_and_incumbent_parity(self):
        self.assertIsNotNone(importlib.util.find_spec('fusion_weight_experiment'), 'fusion implementation missing')
        import fusion_weight_experiment as f
        import technical_quality as tq
        dense, lexical = ['a', 'b', 'c'], ['c', 'd', 'b']
        for weights in [(1, 0), (0, 1), (1, 1), (2, 1), (4, 1), (1, 2)]:
            expected = {}
            for name in set(dense + lexical):
                value = sum(w / (60 + branch.index(name) + 1) for branch, w in zip((dense, lexical), weights) if w and name in branch)
                if value:
                    expected[name] = value
            ranked, attribution = f.fusion(dense, lexical, weights)
            self.assertEqual(ranked, sorted(expected, key=lambda n: (-expected[n], n)))
            for name in ranked:
                self.assertAlmostEqual(attribution[name]['score'], expected[name], places=16)
                self.assertAlmostEqual(attribution[name]['dense_contribution'] + attribution[name]['lexical_contribution'], expected[name], places=16)
        self.assertEqual(f.fusion(dense, lexical, (1, 1))[0], tq.fuse(dense, lexical))
        self.assertEqual(f.fusion([], [], (1, 1)), ([], {}))

    def test_real_model_recipe_parity(self):
        import fusion_weight_experiment as f
        self.assertTrue(hasattr(f, 'encoders'), 'resident model factory missing')
        import numpy as np
        import multilingual_embedding_experiment as m
        for name, encoder in f.encoders().items():
            old = m.verified_encoder(REPO / 'artifacts/models' / ('minilm' if name.startswith('minilm') else 'e5-small'), cap=128 if name == 'e5_parent128' else None)
            for kind in ('query', 'passage'):
                texts = ['Pourquoi WAL exige le même ordinateur ?', 'must not ' * 600]
                actual = encoder.encode(texts, kind)
                np.testing.assert_array_equal(actual, old.encode(texts, kind))
                tokens = encoder.tokenizer.encode_batch([encoder.manifest[kind + '_prefix'] + t for t in texts])
                ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
                mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
                inputs = dict(input_ids=ids, attention_mask=mask, token_type_ids=np.zeros_like(ids))
                hidden = encoder.session.run(None, {i.name: inputs[i.name] for i in encoder.session.get_inputs()})[0]
                expected = np.stack([h[a.astype(bool)].mean(axis=0, dtype=np.float64) for h, a in zip(hidden, mask)])
                expected /= np.linalg.norm(expected, axis=1, keepdims=True)
                np.testing.assert_allclose(actual, expected, atol=1e-7)

    def test_real_server_matrix_provenance_and_tamper_rejection(self):
        import fusion_weight_experiment as f
        self.assertTrue(hasattr(f, 'experiment'), 'matrix runner missing')
        import uuid
        run = REPO / 'artifacts/fusion-weights' / ('paired-' + uuid.uuid4().hex)
        report = f.experiment(run)
        self.assertEqual(report['rows'], 1152)
        self.assertEqual(report['actual_http_query_calls'], 1152)
        self.assertTrue(f.verify_run(run))
        target = run / 'raw-results.json'
        original = target.read_bytes()
        target.write_bytes(original + b' ')
        try:
            with self.assertRaises(AssertionError):
                f.verify_run(run)
        finally:
            target.write_bytes(original)
        self.assertTrue(f.verify_run(run))
        print('VERIFIED_RUN=' + str(run), flush=True)


if __name__ == '__main__':
    unittest.main()
