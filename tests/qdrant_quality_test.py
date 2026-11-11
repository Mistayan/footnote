"""Standalone experiment contracts; no production storage or model mutation."""
import os
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))


class RankingTests(unittest.TestCase):
    def test_tied_children_deduplicate_at_parent_level(self):
        path = REPO / 'tools/qdrant_quality.py'
        self.assertTrue(path.exists(), 'missing isolated quality harness')
        import qdrant_quality as quality
        documents = [{'id': 'b2', 'parent_id': 'b'}, {'id': 'a1', 'parent_id': 'a'},
                     {'id': 'b1', 'parent_id': 'b'}, {'id': 'c1', 'parent_id': 'c'}]
        points = [{'id': 1, 'score': .9}, {'id': 2, 'score': .9},
                  {'id': 3, 'score': .95}, {'id': 4, 'score': .8}]
        self.assertEqual(quality.rank_parents(points, documents), ['b', 'a', 'c'])
        self.assertEqual(quality.rank_parents(list(reversed(points)), documents), ['b', 'a', 'c'])


@unittest.skipUnless(os.environ.get('QDRANT_QUALITY_INTEGRATION') == '1', 'explicit real-server run')
class IntegrationTests(unittest.TestCase):
    def test_frozen_real_server_experiment_has_auditable_parent_metrics(self):
        import qdrant_quality as quality
        self.assertTrue(callable(getattr(quality, 'experiment', None)), 'missing real experiment')
        report = quality.experiment()
        run = Path(report['run'])
        self.assertEqual(report['server_identity']['version'], '1.19.2')
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertTrue(report['sources_stable'])
        self.assertTrue(report.get('paired_sqlite_qdrant'), 'missing harmonized SQLite/Qdrant experiment')
        self.assertEqual(len(report['summaries']), 60)
        self.assertTrue(all(s['answerable_queries'] == 12 for s in report['summaries']))
        self.assertTrue(all(s['no_answer_queries'] == 4 for s in report['summaries']))
        self.assertTrue(all(c['indexed_vectors_count'] == c['points_count'] for c in report['collections']))
        self.assertTrue(all(v['token_overflow'] == 0 for v in report['variants'] if v['layout'] == 'children'))
        freeze = json.loads((run / 'freeze.json').read_bytes())
        self.assertEqual(freeze['holdout_status'], 'REUSED/observed; not independent validation')
        self.assertLessEqual(freeze['frozen_utc'], report['first_inference_utc'])
        receipt = json.loads((run / 'evidence-sha256.json').read_bytes())
        self.assertGreater(len(receipt), 15)
        for name, expected in receipt.items():
            self.assertEqual(quality.sha(run / name), expected, name)
        self.assertEqual(quality.sha(run / 'freeze.json'), report['freeze_sha256'])
        import csv
        with (run / 'per-query.csv').open(encoding='utf-8', newline='') as stream:
            review = list(csv.DictReader(stream))
        self.assertEqual(len(review), 960)
        self.assertEqual(len([r for r in review if r['mode'] == 'sqlite_exact']), 192)
        self.assertEqual(len(report['primary_pair_per_query']), 32)
        self.assertTrue(all('sqlite_top5' in r and 'qdrant_top5' in r for r in report['primary_pair_per_query']))
        self.assertTrue(all(set(['query', 'relevant', 'top5', 'hits', 'p1', 'p3', 'p5',
                                 'ideal_p5', 'unjudged', 'snippets_sources']) <= set(r) for r in review))
        self.assertTrue((run / 'PER-QUERY-REVIEW.md').stat().st_size > 10000)
        print('REAL_EXPERIMENT=' + str(run), flush=True)


if __name__ == '__main__':
    unittest.main()
