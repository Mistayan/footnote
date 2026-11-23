import json
from pathlib import Path
import tempfile
import unittest

from claude_context_replay import instant, replay


class ContextReplayTest(unittest.TestCase):
    def test_reconstructs_parallel_reads_and_counts_only_annotated_references(self):
        session = "example-session"
        start = instant("2026-11-22T14:45:00Z")
        end = instant("2026-11-22T14:46:00Z")
        stamp = int(start.timestamp() * 1000)
        activity = [
            {"session": session, "t": stamp - 1, "event": "pack", "ids": [2, 3]},
            {"session": "another", "t": stamp, "event": "recall", "ids": [7]},
            {"session": session, "t": stamp + 1, "event": "recall", "ids": [2]},
        ]

        def assistant(second, key, *content):
            return {
                "type": "assistant", "timestamp": f"2026-11-22T14:45:{second}Z",
                "sessionId": session, "requestId": key, "message": {
                    "id": key, "usage": {"input_tokens": 1, "cache_read_input_tokens": 9},
                    "content": list(content),
                },
            }

        get = {"type": "tool_use", "id": "get", "name": "mcp__footnote-memory__footnote_get"}
        recall = {"type": "tool_use", "id": "recall", "name": "mcp__footnote-memory__footnote_recall"}
        transcript = [
            assistant("01", "one", get),
            assistant("02", "one", recall),
            {"type": "user", "timestamp": "2026-11-22T14:45:03Z", "sessionId": session, "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "get", "is_error": True, "content": "error"},
                    {"type": "tool_result", "tool_use_id": "recall",
                     "content": [{"type": "text", "text": '[{"id":7,"text":"private fixture"},'
                                                          '{"id":2,"already_shown":true}]'}]},
                ],
            }},
            assistant("04", "two", {"type": "text", "text": "Memory 7 and reference 26, private fixture."}),
        ]
        with tempfile.TemporaryDirectory() as root:
            paths = [Path(root) / f"{session}.jsonl", Path(root) / "activity.jsonl"]
            for path, records in zip(paths, [transcript, activity]):
                path.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
            result = replay(*paths, start, end, {6, 7})

        self.assertEqual(result["tool_calls"], 2)
        self.assertEqual(result["tool_round_trips"], 1)
        self.assertEqual(result["cumulative_input_tokens"], 20)
        self.assertEqual(result["repeat_deliveries"], 1)
        self.assertEqual(result["required_referenced_in_final_answer"], [7])
        self.assertEqual(result["required_missed_by_hooks_and_retrieved_by_mcp"], [7])
        self.assertEqual(result["failed_mcp_reads"], {"mcp_get": 1})
        self.assertNotIn("private fixture", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
