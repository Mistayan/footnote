"""Agent memory hook: payload shapes, opt-in metrics, the memory pack and recall, and the save request the agent gets at Stop.

    python -I tests/test_memory_hook.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import memory_hook as h  # noqa: E402

BIN = ROOT / "target" / "debug" / ("footnote.exe" if os.name == "nt" else "footnote")


def hook(d: str, event: dict) -> str:
    return subprocess.run([sys.executable, "-I", str(ROOT / "tools/memory_hook.py")], input=json.dumps(event),
                          capture_output=True, text=True, env={**os.environ, "FOOTNOTE_STATE_DIR": d}).stdout


class Units(unittest.TestCase):
    def test_grok_camel_case_payload(self):
        e = h.normalize({"hookEventName": "stop", "hook_event_name": "Stop", "sessionId": "g1", "workspaceRoot": "/w",
                         "stopHookActive": True})
        self.assertEqual((e["name"], e["session"], e["cwd"], e["stop_active"]), ("Stop", "g1", "/w", True))

    def test_metrics_only_when_switched_on(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["FOOTNOTE_STATE_DIR"] = d
            with h.timed("hook.test", False):
                pass
            self.assertFalse((Path(d) / "metrics.jsonl").exists())
            with self.assertRaises(ValueError):
                with h.timed("hook.test", True, start=True):
                    raise ValueError("boom")
            rows = [json.loads(x) for x in (Path(d) / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["start"], "hook.test")
            self.assertEqual((rows[1]["span"], rows[1]["ok"]), ("hook.test", False))


@unittest.skipUnless(BIN.exists(), "build the footnote binary first (cargo build)")
class EndToEnd(unittest.TestCase):
    def test_pack_recall_and_the_save_request(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "memory.json").write_text(json.dumps({"footnote": str(BIN), "every_turns": 2}), encoding="utf-8")
            os.environ["FOOTNOTE_STATE_DIR"] = d
            h.footnote(h.settings(), ["remember"], json.dumps([{"text": "Johan wants relative % gaps in every benchmark table.",
                                                                 "kind": "preference", "scope": "global", "observed_at": "2026-11-14"}]))
            start = json.loads(hook(d, {"hook_event_name": "SessionStart", "cwd": str(ROOT), "session_id": "s1"}))
            self.assertIn("relative % gaps", start["hookSpecificOutput"]["additionalContext"])
            # A prompt starting with "-" is a query, never a command-line option.
            out = hook(d, {"hook_event_name": "UserPromptSubmit", "cwd": str(ROOT), "session_id": "s1", "prompt": "- benchmark tables gaps"})
            self.assertIn("relative % gaps", json.loads(out)["hookSpecificOutput"]["additionalContext"])
            # One prompt so far: no request yet.
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1"}), "")
            hook(d, {"hook_event_name": "UserPromptSubmit", "cwd": str(ROOT), "session_id": "s1", "prompt": "next"})
            ask = json.loads(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1"}))
            self.assertEqual(ask["decision"], "block")
            self.assertIn("footnote_remember", ask["reason"])
            self.assertIn('"borgknowledge"', ask["reason"])  # the project scope the agent must use
            # The agent saved and stops again: no second request.
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1", "stop_hook_active": True}), "")
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1"}), "")

    def test_remember_command_needs_no_hook_and_triggers_vectors(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "memory.json").write_text(json.dumps({"footnote": str(BIN)}), encoding="utf-8")
            hook(d, {"hook_event_name": "UserPromptSubmit", "cwd": str(ROOT), "session_id": "s2", "prompt": "/remember"})
            self.assertTrue(json.loads((Path(d) / "memory-hook" / "s2.json").read_text(encoding="utf-8"))["embed"])
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s2"}), "")
            self.assertFalse(json.loads((Path(d) / "memory-hook" / "s2.json").read_text(encoding="utf-8"))["embed"])


if __name__ == "__main__":
    unittest.main()
