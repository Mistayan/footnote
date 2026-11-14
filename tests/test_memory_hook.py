"""Agent memory hook: transcript reading, LLM answer parsing, scope and sensitivity rules, and one end-to-end run with the
built footnote binary and the keyword extractor (no LLM, nothing leaves the machine).

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


def transcript(path: Path) -> Path:
    lines = [
        {"type": "user", "timestamp": "2026-11-14T09:00:00Z", "message": {"role": "user", "content": "Please use relative % gaps in every benchmark table, always."}},
        {"type": "assistant", "timestamp": "2026-11-14T09:00:05Z", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Done. The fix was adding the Rust bin folder to PATH before calling cargo."},
            {"type": "tool_use", "name": "Bash", "input": {"command": "secret tool input"}}]}},
        {"type": "user", "timestamp": "2026-11-14T09:01:00Z", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "huge tool output that must never be extracted"}]}},
        {"type": "system", "timestamp": "2026-11-14T09:02:00Z", "content": "ignored"},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


class Units(unittest.TestCase):
    def test_read_turns_keeps_text_only_and_resumes(self):
        with tempfile.TemporaryDirectory() as d:
            t = transcript(Path(d) / "t.jsonl")
            turns, n, date = h.read_turns(t, 0)
            self.assertEqual([r for r, _ in turns], ["user", "assistant"])
            self.assertNotIn("tool output", h.segment_text(turns))
            self.assertNotIn("secret tool input", h.segment_text(turns))
            self.assertEqual((n, date), (4, "2026-11-14"))
            self.assertEqual(h.read_turns(t, n)[0], [])

    def test_codex_transcript_skips_injected_instructions(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "rollout.jsonl"
            rows = [{"type": "session_meta", "payload": {"cwd": "x"}},
                    {"type": "response_item", "timestamp": "2026-11-13T09:20:00Z", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "system rules"}]}},
                    {"type": "response_item", "timestamp": "2026-11-13T09:20:00Z", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# AGENTS.md instructions\n<INSTRUCTIONS>..."}]}},
                    {"type": "response_item", "timestamp": "2026-11-13T09:21:00Z", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Prune the merged branches."}]}},
                    {"type": "response_item", "timestamp": "2026-11-13T09:22:00Z", "payload": {"type": "custom_tool_call", "input": "git branch"}},
                    {"type": "response_item", "timestamp": "2026-11-13T09:23:00Z", "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Deleted two merged branches."}]}}]
            t.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            turns, _, date = h.read_turns(t, 0)
            self.assertEqual(turns, [("user", "Prune the merged branches."), ("assistant", "Deleted two merged branches.")])
            self.assertEqual(date, "2026-11-13")

    def test_grok_camel_case_payload(self):
        e = h.normalize({"hookEventName": "user_prompt_submit", "hook_event_name": "UserPromptSubmit", "sessionId": "g1",
                         "workspaceRoot": "/w", "prompt": "hi", "lastAssistantMessage": "done"})
        self.assertEqual((e["name"], e["session"], e["cwd"], e["prompt"], e["answer"]), ("UserPromptSubmit", "g1", "/w", "hi", "done"))

    def test_parse_memories_tolerates_prose_and_drops_bad_items(self):
        raw = 'Here you go:\n```json\n[{"text": "a", "kind": "fact", "scope": "global"}, {"text": "b", "kind": "opinion"}, 3]\n```'
        self.assertEqual(h.parse_memories(raw), [{"text": "a", "kind": "fact", "scope": "global"}])
        self.assertEqual(h.parse_memories("nothing"), [])

    def test_finalize_scopes_and_sensitive_projects(self):
        items = [{"text": "pref", "kind": "preference", "scope": "global"},
                 {"text": "proj", "kind": "fact", "scope": "project", "supersedes": 7},
                 {"text": "made up", "kind": "fact", "scope": "project", "supersedes": 99}]
        out = h.finalize(items, "footnote", "2026-11-14", "s1", True, {7})
        self.assertEqual([m["scope"] for m in out], ["global", "footnote", "footnote"])
        self.assertEqual(out[1]["supersedes"], 7)
        self.assertNotIn("supersedes", out[2])
        # Sensitive project through a non-local LLM: only global memories survive.
        self.assertEqual([m["text"] for m in h.finalize(items, "x", "2026-11-14", "s1", False, set())], ["pref"])

    def test_local_endpoints(self):
        self.assertTrue(h.is_local("http://localhost:11434/v1"))
        self.assertTrue(h.is_local("http://127.0.0.1:1234/v1"))
        self.assertFalse(h.is_local("https://api.openai.com/v1"))

    def test_keyword_fallback(self):
        out = h.keyword_memories([("user", "I prefer short answers in French."), ("assistant", "The fix was a missing PATH entry.")])
        self.assertEqual([m["kind"] for m in out], ["preference", "fix"])


@unittest.skipUnless(BIN.exists(), "build the footnote binary first (cargo build)")
class EndToEnd(unittest.TestCase):
    def test_extract_then_pack_and_recall(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["FOOTNOTE_STATE_DIR"] = d
            (Path(d) / "memory.json").write_text(json.dumps({"footnote": str(BIN), "extractor": {"route": "none"}}), encoding="utf-8")
            t = transcript(Path(d) / "t.jsonl")
            h.extract("s1", str(t), str(ROOT))
            s = h.settings()
            pack = h.footnote(s, ["memory-pack", "--project", "borgknowledge"])["memories"]
            self.assertTrue(any("relative % gaps" in m["text"] and m["scope"] == "global" for m in pack), pack)
            self.assertTrue(any(m["kind"] == "fix" and m["scope"] == "borgknowledge" for m in pack), pack)
            # A second run reads only new lines: nothing new, nothing stored twice.
            h.extract("s1", str(t), str(ROOT))
            self.assertEqual(len(h.footnote(s, ["memory-pack", "--project", "borgknowledge"])["memories"]), len(pack))
            # The SessionStart hook prints the pack as additional context.
            out = subprocess.run([sys.executable, "-I", str(ROOT / "tools/memory_hook.py")], input=json.dumps(
                {"hook_event_name": "SessionStart", "cwd": str(ROOT), "session_id": "s1"}), capture_output=True, text=True,
                env={**os.environ, "FOOTNOTE_STATE_DIR": d})
            ctx = json.loads(out.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("relative % gaps", ctx)

    def test_journal_when_no_transcript_is_readable(self):
        """Grok-style: no readable transcript, the hook journals prompts and final answers, and catches up at next start."""
        with tempfile.TemporaryDirectory() as d:
            os.environ["FOOTNOTE_STATE_DIR"] = d
            (Path(d) / "memory.json").write_text(json.dumps({"footnote": str(BIN), "extractor": {"route": "none"}, "every_turns": 99}), encoding="utf-8")
            run = lambda ev: subprocess.run([sys.executable, "-I", str(ROOT / "tools/memory_hook.py")], input=json.dumps(ev),
                                            capture_output=True, text=True, env={**os.environ, "FOOTNOTE_STATE_DIR": d})
            run({"hook_event_name": "UserPromptSubmit", "sessionId": "g1", "cwd": str(ROOT), "prompt": "I prefer tables over bullet lists for results."})
            run({"hook_event_name": "Stop", "sessionId": "g1", "cwd": str(ROOT), "lastAssistantMessage": "Noted."})
            self.assertEqual(len(h.journal("g1").read_text(encoding="utf-8").splitlines()), 2)
            h.extract("g1", "", str(ROOT))  # what catch-up at the next SessionStart runs in the background
            pack = h.footnote(h.settings(), ["memory-pack"])["memories"]
            self.assertTrue(any("tables over bullet lists" in m["text"] for m in pack), pack)
            self.assertEqual(h.progress("g1")[1]["turns_done"], 1)


if __name__ == "__main__":
    unittest.main()
