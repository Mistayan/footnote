"""Agent memory hook: payload shapes, opt-in metrics, the memory pack and recall, and the save request the agent gets at Stop.

    python -I tests/test_memory_hook.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
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
            (Path(d) / "memory.json").write_text(json.dumps({"footnote": str(BIN), "every_turns": 3}), encoding="utf-8")
            os.environ["FOOTNOTE_STATE_DIR"] = d
            h.footnote(h.settings(), ["remember"], json.dumps([{"text": "Johan wants relative % gaps in every benchmark table.",
                                                                 "kind": "preference", "scope": "global", "observed_at": "2026-11-14"}]))
            start = json.loads(hook(d, {"hook_event_name": "SessionStart", "cwd": str(ROOT), "session_id": "s1"}))
            self.assertIn("relative % gaps", start["hookSpecificOutput"]["additionalContext"])
            self.assertIn("say so in a few words", start["hookSpecificOutput"]["additionalContext"])  # memory use is visible
            # A prompt starting with "-" is a query, never a command-line option.
            out = hook(d, {"hook_event_name": "UserPromptSubmit", "cwd": str(ROOT), "session_id": "s1", "prompt": "- benchmark tables gaps"})
            self.assertIn("relative % gaps", json.loads(out)["hookSpecificOutput"]["additionalContext"])
            # A long accented prompt is cut to the byte limit, not rejected (it used to fail and log an error).
            hook(d, {"hook_event_name": "UserPromptSubmit", "cwd": str(ROOT), "session_id": "s1", "prompt": "é" * 400})
            self.assertFalse((Path(d) / "memory-hook" / "hook.log").exists())
            # Two prompts so far, every_turns is 3: no request yet.
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1"}), "")
            hook(d, {"hook_event_name": "UserPromptSubmit", "cwd": str(ROOT), "session_id": "s1", "prompt": "next"})
            ask = json.loads(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1"}))
            self.assertEqual(ask["decision"], "block")
            self.assertIn("footnote_remember", ask["reason"])
            self.assertIn('"borgknowledge"', ask["reason"])
            self.assertIn("what you saved", ask["reason"])  # the user sees a receipt  # the project scope the agent must use
            # The agent saved and stops again: no second request.
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1", "stop_hook_active": True}), "")
            self.assertEqual(set(json.loads((Path(d) / "memory-hook" / "s1.json").read_text(encoding="utf-8"))), {"turns", "asked_at", "embed"})
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s1"}), "")

    def test_remember_command_needs_no_hook_and_triggers_vectors(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "memory.json").write_text(json.dumps({"footnote": str(BIN)}), encoding="utf-8")
            hook(d, {"hook_event_name": "UserPromptSubmit", "cwd": str(ROOT), "session_id": "s2", "prompt": "/remember"})
            self.assertTrue(json.loads((Path(d) / "memory-hook" / "s2.json").read_text(encoding="utf-8"))["embed"])
            self.assertEqual(hook(d, {"hook_event_name": "Stop", "cwd": str(ROOT), "session_id": "s2"}), "")
            self.assertFalse(json.loads((Path(d) / "memory-hook" / "s2.json").read_text(encoding="utf-8"))["embed"])

    @unittest.skipUnless((ROOT / "artifacts/models/gte-small").exists(), "needs the gte-small model")
    def test_resident_recall_starts_a_daemon_and_answers_by_keyword_meanwhile(self):
        with tempfile.TemporaryDirectory() as d:
            model = str(ROOT / "artifacts/models/gte-small")
            (Path(d) / "memory.json").write_text(json.dumps({"footnote": str(BIN), "models": [model], "resident": True,
                                                             "idle_seconds": 3}), encoding="utf-8")
            os.environ["FOOTNOTE_STATE_DIR"] = d
            s = h.settings()
            h.footnote(s, ["remember", "--model", model], json.dumps([{"text": "Johan wants relative % gaps in every benchmark table.",
                                                                        "kind": "preference", "scope": "global", "observed_at": "2026-11-15"}]))
            # No daemon yet: answered by keyword, and a daemon is started in the background.
            self.assertIn("relative % gaps", h.recall(s, "borgknowledge", "benchmark table gaps")[0]["text"])
            for _ in range(100):
                try:
                    out = h.footnote(s, ["memory-recall", "--resident", "--model", model, "--", "how should tables show differences"])
                    break
                except RuntimeError:
                    time.sleep(0.1)
            else:
                self.fail("the daemon never answered")
            self.assertIn("hybrid", out["mode"])  # found by meaning, through the daemon
            self.assertIn("relative % gaps", out["memories"][0]["text"])
            time.sleep(6)  # idle: the daemon leaves by itself
            with self.assertRaises(RuntimeError):
                h.footnote(s, ["memory-recall", "--resident", "--", "tables"])


if __name__ == "__main__":
    unittest.main()
