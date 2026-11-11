"""Metric definitions must count returned distractors, not call hit rate precision."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from hybrid_benchmark import score, aggregate

class MetricsTest(unittest.TestCase):
    def test_precision_recall_and_multiple_evidence(self):
        s=score(['bad','a','b','x','y'], {'relevant':['a','b'],'forbidden':['bad']})
        self.assertEqual(s['precision_at_5'], 0.4)
        self.assertEqual(s['recall_at_5'],1)
        self.assertEqual(s['reciprocal_rank'],0.5)
        self.assertEqual(s['forbidden_at_5'],1)
        self.assertLess(s['ndcg_at_5'],1)
    def test_no_answer_is_not_an_automatic_semantic_success(self):
        s=score(['wrong'], {'relevant':[],'forbidden':[]})
        self.assertIsNone(s['recall_at_5'])
        self.assertEqual(s['no_answer_false_positive'],1)
        a=aggregate([s])
        self.assertIsNone(a['recall_at_5'])
        self.assertEqual(a['no_answer_false_positive_rate'],1)
if __name__=='__main__':unittest.main()
