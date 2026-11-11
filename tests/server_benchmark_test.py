"""Standalone benchmark contract tests; no production storage or network."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


class ServerBenchmarkTests(unittest.TestCase):
    def test_rrf_uses_one_based_rank_and_stable_id_ties(self):
        import server_benchmark as bench
        self.assertTrue(hasattr(bench, 'fuse'), 'standalone RRF implementation missing')
        self.assertEqual(bench.fuse([3, 2], [2, 3], 5), [2, 3])
        self.assertEqual(bench.fuse([9, 8], [], 1), [9])

    def test_run_storage_must_be_new_child_of_owned_artifacts(self):
        import server_benchmark as bench
        import tempfile
        self.assertTrue(hasattr(bench, 'new_run'), 'isolated run boundary missing')
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / 'artifacts' / 'server-benchmark'
            run = bench.new_run(base)
            self.assertEqual(run.parent, base.resolve())
            self.assertTrue(run.is_dir())
            self.assertNotEqual(run, bench.new_run(base))
            with self.assertRaises(ValueError):
                bench.new_run(Path('D:/Second Brain/.qdrant_storage'))

    def test_real_server_resident_pipeline_and_owned_cleanup(self):
        import server_benchmark as bench
        self.assertTrue(hasattr(bench, 'benchmark'), 'real server harness missing')
        from hybrid_dataset import QUERIES
        report = bench.benchmark(document_count=64, repeats=1, queries=QUERIES[:2], concurrency=2)
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertTrue(report['sources_stable'])
        self.assertEqual(report['collection']['indexed_vectors_count'], 64)
        self.assertTrue(report['resident_recipe_matches_existing_helper'])
        self.assertEqual(len(report['summaries']), 4)
        self.assertEqual(sum(s['samples'] for s in report['summaries']), 8)
        self.assertTrue(all(s['citations_current'] == s['samples'] * 5 for s in report['summaries']))
        print('integration evidence:', report['run'])


if __name__ == '__main__':
    unittest.main()
