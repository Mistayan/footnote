"""Test-first contracts for fixed fusion diagnostics; no runtime changes."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


class FusionTest(unittest.TestCase):
    def test_fixed_weight_scores_ties_and_missing_branch(self):
        path = ROOT / 'tools/fusion_experiment.py'
        self.assertTrue(path.exists(), 'fusion experiment implementation missing')
        import fusion_experiment as f
        import technical_quality as tq
        dense, lexical = ['a', 'b', 'c'], ['c', 'b', 'z']
        self.assertEqual(f.rank_fusion(dense, lexical, 'equal')[0], tq.fuse(dense, lexical))
        for branch, weights in {'equal': (1, 1), 'dense2': (2, 1), 'lexical2': (1, 2), 'dense_only': (1, 0)}.items():
            names, evidence = f.rank_fusion(dense, lexical, branch)
            self.assertEqual(evidence['a']['dense_rank'], 1)
            self.assertIsNone(evidence['a']['lexical_rank'])
            self.assertAlmostEqual(evidence['b']['score'], sum(weights) / 62)
            self.assertEqual(names, sorted(evidence, key=lambda n: (-evidence[n]['score'], n)))
        self.assertEqual(f.rank_fusion(['b', 'a'], ['z'], 'dense_only')[0], ['b', 'a'])
        self.assertEqual(f.rank_fusion([], [], 'equal'), ([], {}))
        with self.assertRaises(ValueError):
            f.rank_fusion(dense, lexical, 'tuned')

    def test_actual_two_block_experiment_and_integrity(self):
        import fusion_experiment as f
        import uuid
        import json
        self.assertTrue(callable(getattr(f, 'experiment', None)), 'actual experiment missing')
        run = ROOT / 'artifacts/fusion-experiments' / ('paired-' + uuid.uuid4().hex)
        report = f.experiment(run)
        self.assertEqual(report['rows'], 768)
        self.assertEqual(report['parent_count'], 136)
        self.assertEqual(report['query_count'], 32)
        self.assertEqual(report['baseline_history_top5_parity'], {n: 32 for n in f.MODELS})
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertTrue(f.verify_run(run))
        rows = json.loads((run / 'raw-results.json').read_bytes())
        self.assertEqual(len({(r['id'], r['variant'], r['branch'], r['block']) for r in rows}), 768)
        self.assertEqual({r['block'] for r in rows}, {0, 1})
        data = (run / 'raw-results.json').read_bytes()
        try:
            (run / 'raw-results.json').write_bytes(data + b' ')
            with self.assertRaises(AssertionError):
                f.verify_run(run)
        finally:
            (run / 'raw-results.json').write_bytes(data)
        self.assertTrue(f.verify_run(run))
        # Semantic review verification must not rely only on byte manifests.
        import hashlib
        receipt_path = run / 'evidence-sha256.json'
        original_receipt = receipt_path.read_bytes()
        rows[0]['unjudged'] = ['fabricated-status']
        try:
            (run / 'raw-results.json').write_text(json.dumps(rows), encoding='utf-8')
            receipt = json.loads(original_receipt)
            receipt['raw-results.json'] = hashlib.sha256((run / 'raw-results.json').read_bytes()).hexdigest()
            receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
            with self.assertRaises(AssertionError):
                f.verify_run(run)
        finally:
            (run / 'raw-results.json').write_bytes(data)
            receipt_path.write_bytes(original_receipt)
        self.assertTrue(f.verify_run(run))
        print('FUSION_TEST_RUN=' + str(run), flush=True)


if __name__ == '__main__':
    unittest.main()
