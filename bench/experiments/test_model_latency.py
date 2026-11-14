"""Timing must encode every query individually, after unmeasured warmup."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import model_latency


class ModelLatencyTests(unittest.TestCase):
    def test_single_query_calls_include_duplicates_and_exclude_warmup(self):
        calls = []

        def embed(texts, kind):
            calls.append((texts, kind))
            return SimpleNamespace(shape=(1, 384))

        encoder = SimpleNamespace(embed=embed)
        with patch.object(model_latency.time, "perf_counter", side_effect=[0, .001, 1, 1.003, 2, 2.002]):
            result = model_latency.measure(encoder, ["first", "second", "first"])
        self.assertEqual(calls, [(["first"], "query")] * 4 + [(["second"], "query"), (["first"], "query")])
        self.assertEqual(result, {"queries": 3, "dimensions": 384, "p50": 2.0, "p95": 3.0})

    def test_empty_query_set_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "requires queries"):
            model_latency.measure(None, [])


if __name__ == "__main__":
    unittest.main()
