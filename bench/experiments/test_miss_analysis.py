import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import miss_analysis as ma  # noqa: E402


class MissAnalysis(unittest.TestCase):
    def test_buckets(self):
        self.assertEqual([ma.bucket(r) for r in (1, 10, 11, 20, 21, 100, None)],
                         ["top 10", "top 10", "11-20", "11-20", "21-100", "21-100", "not in top 100"])

    def test_misses_are_attributed_to_the_arm_that_found_them(self):
        recs = [{"fused": 3, "lexical": 50, "dense": 1},       # found: not a miss
                {"fused": 15, "lexical": 2, "dense": 40},      # lexical alone had it
                {"fused": None, "lexical": None, "dense": 7},  # dense alone had it
                {"fused": 30, "lexical": 5, "dense": 9},       # both arms had it, fusion lost it
                {"fused": None, "lexical": None, "dense": None}]
        self.assertEqual(ma.summarize(recs), {
            "fused top 10": 1, "fused 11-20": 1, "fused not in top 100": 2, "fused 21-100": 1,
            "missed: lexical top 10 only": 1, "missed: dense top 10 only": 1,
            "missed: both arms top 10": 1, "missed: neither arm top 10": 1})


if __name__ == "__main__":
    unittest.main()
