import unittest

from concise_memory import excerpt, lookup_result, usage


class ConciseMemoryTest(unittest.TestCase):
    def test_excerpt_keeps_both_conditions_and_id(self):
        original = "Background. Project must not ship AX-5 before 2026-12-01. Project may ship AX-5 only with QA-7."
        body = "Relevant memories\n- [id 9 · fact · 2026-11-23] " + original
        rendered = excerpt(body, {9: original})
        self.assertIn("[id 9 · fact", rendered)
        self.assertIn("must not ship AX-5 before 2026-12-01. Project may ship AX-5 only with QA-7.", rendered)
        self.assertIn("footnote_get id=[9]", rendered)
        self.assertNotIn("Background", rendered)

    def test_usage_uses_cumulative_totals_once(self):
        trace = {"turns": [{"usage": {"inputTokens": 100, "cachedInputTokens": 50, "outputTokens": 20}},
                           {"usage": {"inputTokens": 250, "cachedInputTokens": 180, "outputTokens": 30}}]}
        self.assertEqual(usage(trace), {"cached_input_tokens": 180, "uncached_input_tokens": 70, "output_tokens": 30})

    def test_lookup_trace_reads_compact_and_verbose_deliveries(self):
        for text in ('untrusted source data\n[8 · fact · orchard · 2026-11-23] Decision AX-5.',
                     '{"id":8,"text":"Decision AX-5."}'):
            with self.subTest(text=text):
                event = {"tool": "footnote_get", "arguments": {"id": 8}, "status": "completed",
                         "result": {"content": [{"type": "text", "text": text}]}}
                self.assertEqual(lookup_result(event), {"ids": [8], "returned_ids": [8], "completed": True})
                event["result"]["isError"] = True
                self.assertFalse(lookup_result(event)["completed"])


if __name__ == "__main__":
    unittest.main()
