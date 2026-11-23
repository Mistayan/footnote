import unittest

from concise_memory import excerpt, usage


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


if __name__ == "__main__":
    unittest.main()
