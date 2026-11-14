import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ranking_chart as rc  # noqa: E402

RECEIPT = {"dataset": {"id": "syntec"}, "engine": {"id": "icm"}, "metrics": {"ndcg@10": 0.79635, "queries_scored": 100},
           "latency_ms": {"p50": 13.891}, "determinism": {"checked": True, "identical_rankings": False}}


class RankingChart(unittest.TestCase):
    def test_row_keeps_failed_determinism(self):
        self.assertEqual(rc.row(RECEIPT), {"ds": "syntec", "eng": "icm", "q": 0.7964, "p50": 13.9, "n": 100, "det": False})

    def test_render_needs_exactly_one_placeholder(self):
        self.assertEqual(rc.render("x=__DATA__;", [{"a": 1}]), 'x=[{"a": 1}];')
        with self.assertRaises(ValueError):
            rc.render("no placeholder", [])

    def test_template_is_data_driven(self):
        self.assertEqual((Path(rc.HERE) / "ranking_template.html").read_text(encoding="utf-8").count("__DATA__"), 1)


if __name__ == "__main__":
    unittest.main()
