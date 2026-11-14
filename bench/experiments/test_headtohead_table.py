"""Report regressions: receipt schema, selection and comparison boundaries."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import headtohead_table as report


class HeadToHeadTableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.receipt = {
            "protocol": "v1", "partial": False,
            "dataset": {"id": "syntec", "split": "test", "pin": {"sha256": "same-input"}, "queries": 100},
            "engine": {"id": "mem0"},
            "code": {"harness_sha256": "same-harness", "metrics_sha256": "same-metrics"},
            "metrics": {"ndcg@10": 0.727416, "recall@10": 0.87, "queries_scored": 100},
            "latency_ms": {"p50": 7.84, "p95": 14.97, "scope": "in-process"},
            "build": {"build_ms": 3324, "store_bytes": 2**20, "qdrant_bytes": 0, "model_cache_bytes": 2**21},
            "determinism": {"checked": True, "identical_rankings": True, "queries_checked": 100},
        }

    def write(self, stamp="20261113T070305Z", receipt=None):
        data = receipt if receipt is not None else self.receipt
        path = self.folder / f"{stamp}-{data['dataset']['id']}-{data['engine']['id']}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def render(self, *args):
        output = io.StringIO()
        with patch.object(report, "RECEIPTS", self.folder), patch("sys.argv", ["report", *args]), contextlib.redirect_stdout(output):
            report.main()
        return output.getvalue()

    def test_real_metric_keys_and_size_units(self):
        path = self.write()
        text = self.render()
        self.assertIn("| syntec | mem0 | 0.727 | 0.870 | 7.84 | 14.97 | 3.3 | 1.00 | 0.00 | 2.00 | 100 |", text)
        self.assertIn("Complete receipts: 1/27. Missing: 26.", text)
        self.assertIn(f"(../receipts/{path.name})", text)

    def test_missing_sizes_are_unknown_instead_of_zero(self):
        self.receipt["build"] = {"build_ms": 1}
        self.write()
        self.assertIn("| n/a | n/a | n/a |", self.render())

    def test_later_partial_or_dev_receipt_does_not_hide_full_test(self):
        original = self.write()
        for offset, changes in enumerate(({"partial": True}, {"dataset": {**self.receipt["dataset"], "split": "dev"}})):
            candidate = {**self.receipt, **changes}
            self.write(f"20261113T07040{offset}Z", candidate)
        with patch.object(report, "RECEIPTS", self.folder):
            self.assertEqual(report.latest("syntec", "mem0")[0], original)

    def test_since_excludes_stale_rows(self):
        self.write()
        text = self.render("--since", "20261113T080000Z")
        self.assertIn("Complete receipts: 0/27.", text)
        self.assertNotIn("| syntec | mem0 |", text)

    def test_mismatched_inputs_fail_before_printing_comparison(self):
        self.write()
        other = copy.deepcopy(self.receipt)
        other["engine"]["id"] = "cognee"
        other["dataset"]["pin"] = {"sha256": "different-input"}
        self.write(receipt=other)
        with self.assertRaisesRegex(ValueError, "incomparable inputs or harness for syntec"):
            self.render()

    def test_mixed_corpus_only_expects_scheduled_variants(self):
        text = self.render()
        self.assertIn("mix-fr-en/mem0-multilingual", text)
        self.assertNotIn("- mix-fr-en/mem0\n", text)

    def test_unchecked_determinism_stays_visible(self):
        self.receipt["determinism"] = {"checked": False, "identical_rankings": None, "queries_checked": 0}
        self.write()
        self.assertIn("| unchecked/failed |", self.render())

    def test_matched_track_has_twenty_runs_and_does_not_skip_mixed_controls(self):
        self.receipt["engine"]["id"] = "matched-sqlite-tantivy"
        self.write()
        text = self.render("--matched")
        self.assertIn("Complete receipts: 1/20.", text)
        self.assertIn("mix-fr-en/matched-lance-cc", text)
        self.assertIn("Encoding is excluded", text)
        self.assertNotIn("MCP transport", text)

    def test_matched_track_rejects_different_frozen_vectors(self):
        self.receipt["engine"] = {"id": "matched-sqlite-tantivy", "versions": {"input": {"files_sha256": {"vectors.npy": "one"}}}}
        self.write()
        other = copy.deepcopy(self.receipt)
        other["engine"]["id"] = "matched-lance-cc"
        other["engine"]["versions"]["input"]["files_sha256"]["vectors.npy"] = "two"
        self.write(receipt=other)
        with self.assertRaisesRegex(ValueError, "incomparable inputs"):
            self.render("--matched")


if __name__ == "__main__":
    unittest.main()
