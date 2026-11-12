import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics as m  # noqa: E402


class MetricTests(unittest.TestCase):
    def test_ndcg_hand_computed(self):
        # relevant: a (gain 1), c (gain 1). ranking puts a at 1 and c at 3.
        dcg = 1 / math.log2(2) + 1 / math.log2(4)
        ideal = 1 / math.log2(2) + 1 / math.log2(3)
        got = m.ndcg_at_k(["a", "b", "c"], {"a": 1, "c": 1}, 10)
        self.assertAlmostEqual(got, dcg / ideal, places=12)

    def test_ndcg_uses_graded_gain_and_ideal_order(self):
        # gains 2 and 1; best possible order is (2, 1). Reversed order must score below 1.
        best = m.ndcg_at_k(["x", "y"], {"x": 2, "y": 1}, 10)
        worse = m.ndcg_at_k(["y", "x"], {"x": 2, "y": 1}, 10)
        self.assertAlmostEqual(best, 1.0, places=12)
        self.assertLess(worse, 1.0)
        self.assertAlmostEqual(worse, (1 / 1 + 2 / math.log2(3)) / (2 / 1 + 1 / math.log2(3)), places=12)

    def test_ndcg_cutoff_and_missing_slots(self):
        self.assertEqual(m.ndcg_at_k(["n1", "n2", "a"], {"a": 1}, 2), 0.0)  # relevant item beyond k
        self.assertAlmostEqual(m.ndcg_at_k([], {"a": 1}, 10), 0.0)

    def test_recall_and_mrr(self):
        q = {"a": 1, "b": 1, "c": 0}
        self.assertAlmostEqual(m.recall_at_k(["z", "a", "q", "b"], q, 2), 0.5)
        self.assertAlmostEqual(m.recall_at_k(["z", "a", "q", "b"], q, 4), 1.0)
        self.assertAlmostEqual(m.mrr_at_k(["z", "a", "q", "b"], q, 10), 0.5)
        self.assertEqual(m.mrr_at_k(["z", "q"], q, 10), 0.0)

    def test_zero_label_is_not_relevant(self):
        self.assertEqual(m.recall_at_k(["c"], {"a": 1, "c": 0}, 5), 0.0)

    def test_query_without_positive_is_rejected(self):
        with self.assertRaises(ValueError):
            m.ndcg_at_k(["a"], {"a": 0}, 10)

    def test_dedupe_keeps_best_rank(self):
        self.assertEqual(m.dedupe(["a", "b", "a", "c", "b"]), ["a", "b", "c"])

    def test_evaluate_scores_unanswered_queries_as_zero(self):
        qrels = {"q1": {"a": 1}, "q2": {"b": 1}, "q3": {"c": 0}}  # q3 has no positive: not scored
        out = m.evaluate({"q1": ["a"]}, qrels)
        self.assertEqual(out["queries_scored"], 2)
        self.assertAlmostEqual(out["ndcg@10"], 0.5)
        self.assertAlmostEqual(out["recall@5"], 0.5)
        self.assertEqual(out["queries_empty"], 1)

    def test_recall_any_all(self):
        q = {"a": 1, "b": 1}
        self.assertEqual(m.recall_any_all_at_k(["a", "x", "y"], q, 3), (1.0, 0.0))
        self.assertEqual(m.recall_any_all_at_k(["a", "x", "b"], q, 3), (1.0, 1.0))
        self.assertEqual(m.recall_any_all_at_k(["x", "y", "a"], q, 2), (0.0, 0.0))

    def test_evaluate_collapses_chunks_of_one_document(self):
        out = m.evaluate({"q": ["a", "a", "b"]}, {"q": {"b": 1}})
        self.assertAlmostEqual(out["mrr@10"], 0.5)  # b is rank 2 once duplicates collapse


if __name__ == "__main__":
    unittest.main()
