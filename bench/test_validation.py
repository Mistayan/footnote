"""Harness validation gate: if this fails, no engine result from this bench may be trusted.

Rule 1: our BM25 (OR) on SciFact must land within 0.02 of the published BM25 nDCG@10 (0.665), the same task with the same metric.
Rule 2: no non-partial receipt may report non-deterministic rankings.
Run after every change to metrics.py, fetch.py or engines.py: `python bench/test_validation.py`.
"""
import unittest

from report import retrieval_receipts


class Gate(unittest.TestCase):
    def test_bm25_matches_the_published_baseline(self):
        scores = [r["metrics"]["ndcg@10"] for f, r in retrieval_receipts()
                  if r["dataset"]["id"] == "scifact" and r["engine"]["id"] == "bm25-or-lexical" and not r["partial"]]
        self.assertTrue(scores, "run: python bench/run.py scifact bm25-or-lexical")
        self.assertLess(abs(scores[-1] - 0.665), 0.02, f"BM25 on SciFact is {scores[-1]}, published 0.665: the harness is wrong")

    def test_receipts_are_deterministic(self):
        bad = [f.name for f, r in retrieval_receipts()
               if not r["partial"] and r["determinism"]["checked"] and not r["determinism"]["identical_rankings"]]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
