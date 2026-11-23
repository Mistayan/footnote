"""Tests for extract.py and replay_lean.py on a synthetic conversation store.

Run: python -m unittest discover -s bench/agy-history -p "test_*.py"
"""

import collections
import contextlib
import datetime
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(f"agy_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract = load("extract")
replay_lean = load("replay_lean")


def varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def field(number, value):
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    if isinstance(value, str):
        value = value.encode("utf-8")
    return varint(number << 3 | 2) + varint(len(value)) + value


def timestamp(seconds, nanos):
    return field(1, seconds) + field(2, nanos)


def tool_call_step(seconds, nanos, name, args, status, call_id="call_1", arg_map=None):
    """Metadata and payload as agy writes them for step type 132 (see README.md)."""
    call = field(1, call_id) + field(2, name) + (field(3, json.dumps(args)) if args is not None else b"")
    metadata = field(1, timestamp(seconds, nanos)) + field(3, 2) + field(4, call) + field(6, timestamp(seconds, 0))
    entries = b"".join(field(1, field(1, k) + field(2, v)) for k, v in (arg_map or {}).items())
    payload = field(1, 132) + field(4, status) + field(5, metadata) + (field(140, entries) if arg_map else b"")
    return metadata, payload


SCHEMA = """CREATE TABLE steps (idx integer, step_type integer NOT NULL DEFAULT 0, status integer NOT NULL DEFAULT 0,
has_subtrajectory numeric NOT NULL DEFAULT false, metadata blob, error_details blob, permissions blob, task_details blob,
render_info blob, step_payload blob, step_format integer NOT NULL DEFAULT 0, PRIMARY KEY (idx))"""

# 2026-11-20T14:10:32Z
T0 = 1795183832


def build_store(path, steps):
    with contextlib.closing(sqlite3.connect(path)) as con:
        con.execute(SCHEMA)
        for idx, (step_type, status, metadata, payload) in enumerate(steps):
            con.execute("INSERT INTO steps (idx, step_type, status, metadata, step_payload) VALUES (?, ?, ?, ?, ?)",
                        (idx, step_type, status, metadata, payload))
        con.commit()


class ProtobufReaderTest(unittest.TestCase):
    def test_varint_round_trip(self):
        for value in (0, 1, 127, 128, 300, 2**32, T0):
            self.assertEqual(extract.read_varint(varint(value), 0), (value, len(varint(value))))

    def test_truncated_input_is_an_error(self):
        with self.assertRaises(extract.ProtobufError):
            extract.read_varint(b"\x80", 0)
        with self.assertRaises(extract.ProtobufError):
            list(extract.iter_fields(field(3, "abc")[:-1]))

    def test_fields_in_order_with_wire_types(self):
        buf = field(1, 132) + field(2, "x") + varint(3 << 3 | 5) + b"\x01\x02\x03\x04"
        self.assertEqual(list(extract.iter_fields(buf)), [(1, 0, 132), (2, 2, b"x"), (3, 5, b"\x01\x02\x03\x04")])


class DecodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "antigravity-cli"
        (self.root / "conversations").mkdir(parents=True)
        model_text = field(1, timestamp(T0, 0))
        steps = [
            (15, 3, model_text, field(1, 15)),  # a model turn, not a tool call
            (132, 3, *tool_call_step(T0, 833_430_000, "read_file", {"Path": "a.rs", "StartLine": 1, "EndLine": 9}, 3)),
            (132, 7, *tool_call_step(T0 + 86400, 5_000_000, "read_file", {"Path": "b.png"}, 7)),
            (132, 3, *tool_call_step(T0 + 60, 0, "run_command", {"CommandLine": "git status", "WaitMsBeforeAsync": 500}, 3)),
            (132, 5, *tool_call_step(T0 + 120, 0, "run_command", None, 5, arg_map={"CommandLine": "cargo test"})),
        ]
        build_store(self.root / "conversations" / "conv-a.db", [(s[0], s[1], s[2], s[3]) for s in steps])
        self.rows, self.summary = extract.extract([self.root])

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_step_type_132_is_a_tool_call(self):
        self.assertEqual(self.summary["calls"], 4)
        self.assertEqual(self.summary["step_types_seen"], {"15": 1, "132": 4})

    def test_timestamp_from_metadata_field_1(self):
        self.assertEqual(self.rows[0]["time"], "2026-11-20T14:10:32.833Z")
        self.assertEqual(self.rows[1]["time"], "2026-11-21T14:10:32.005Z")
        self.assertEqual(self.summary["by_day"], {"2026-11-20": 3, "2026-11-21": 1})

    def test_row_fields_without_values(self):
        first = self.rows[0]
        self.assertEqual(first["conversation"], "conv-a")
        self.assertEqual((first["step"], first["status"], first["tool"], first["root"]), (1, 3, "read_file", "cli"))
        self.assertEqual(first["arg_keys"], ["EndLine", "Path", "StartLine"])
        self.assertNotIn("args", first)
        self.assertNotIn("a.rs", json.dumps(self.rows))

    def test_status_and_argument_counts(self):
        self.assertEqual(self.summary["by_status"], {"3": 2, "5": 1, "7": 1})
        self.assertEqual(self.summary["calls_done"], 2)
        self.assertEqual(self.summary["by_tool_with_json_args"], {"read_file": 2, "run_command": 1})
        self.assertEqual(self.summary["read_file_with_json_args"], {"ranged": 1, "whole": 1, "not_done": 1})
        self.assertEqual(self.summary["problems"], {})

    def test_missing_json_falls_back_to_the_argument_map(self):
        row = self.rows[3]
        self.assertFalse(row["json_args"])
        self.assertEqual(row["arg_keys"], ["CommandLine"])

    def test_with_args_and_day_window(self):
        rows, summary = extract.extract([self.root], with_args=True, since="2026-11-21", until="2026-11-21")
        self.assertEqual([r["args"] for r in rows], [{"Path": "b.png"}])
        self.assertEqual(summary["calls"], 1)

    def test_store_is_opened_read_only(self):
        with contextlib.closing(extract.connect_ro(self.root / "conversations" / "conv-a.db")) as con:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("DELETE FROM steps")

    def test_format_drift_is_counted(self):
        problems = collections.Counter()
        metadata, payload = tool_call_step(T0, 0, "read_file", {"Path": "x"}, 3)
        self.assertIsNone(extract.decode_step(1, 132, 3, field(1, timestamp(T0, 0)), payload, problems))
        self.assertIsNotNone(extract.decode_step(2, 132, 3, metadata, field(1, 140) + field(4, 3), problems))
        self.assertEqual(problems, {"tool_call_missing": 1, "payload_step_type_mismatch": 1})
        bad = collections.Counter()
        self.assertIsNone(extract.decode_step(3, 132, 3, b"\x0a\x05ab", payload, bad))
        self.assertEqual(bad, {"bad_protobuf": 1})


class ReplayTest(unittest.TestCase):
    def test_decisions_and_rates(self):
        rows = [
            {"conversation": "c", "step": i, "status": 3, "tool": "run_command", "json_args": True,
             "args": {"CommandLine": cmd}}
            for i, cmd in enumerate(["git status", "Write-Host hi", "cargo test"])
        ]
        rows.append({"conversation": "c", "step": 9, "status": 5, "tool": "run_command", "json_args": False,
                     "args": {"CommandLine": "ignored"}})
        calls = replay_lean.replayable(rows)
        self.assertEqual(len(calls), 3)
        seen = []

        def fake_run(argv, input, capture_output, env, timeout):
            event = json.loads(input)
            seen.append(event)
            self.assertEqual(argv[1:], ["hook", "lean"])
            cmd = event["toolCall"]["args"]["CommandLine"]
            state = Path(env["FOOTNOTE_STATE_DIR"])
            (state / "usage").mkdir(exist_ok=True)
            decision = "pass" if cmd.startswith("Write-Host") else "rewrite"
            with (state / "usage" / "lean-hooks.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps({"decision": decision, "reason": "not-covered" if decision == "pass" else None,
                                      "program": cmd.split()[0] if decision == "rewrite" else None}) + "\n")
            out = {"decision": "allow"}
            if decision == "rewrite":
                out["overwrite"] = {"CommandLine": "footnote run -- " + cmd}
            return subprocess.CompletedProcess(argv, 0, json.dumps(out).encode(), b"")

        results, summary = replay_lean.replay(calls, Path("footnote"), run=fake_run)
        self.assertEqual(seen[0]["hookEventName"], "PreToolUse")
        self.assertEqual(seen[0]["toolCall"]["name"], "run_command")
        self.assertEqual([r["decision"] for r in results], ["rewrite", "pass", "rewrite"])
        self.assertEqual(results[0]["rewritten"], "footnote run -- git status")
        self.assertEqual((summary["calls"], summary["rewrite"], summary["pass"], summary["error"]), (3, 2, 1, 0))
        self.assertEqual(summary["rewrite_rate"], 0.6667)
        self.assertEqual(summary["pass_reasons"], {"not-covered": 1})
        self.assertEqual(summary["rewrite_programs"], {"git": 1, "cargo": 1})

    def test_classify(self):
        self.assertEqual(replay_lean.classify(0, '{"decision":"allow"}'), ("pass", None))
        self.assertEqual(replay_lean.classify(0, ""), ("pass", None))
        self.assertEqual(replay_lean.classify(1, ""), ("error", None))
        self.assertEqual(replay_lean.classify(0, "not json"), ("error", None))
        self.assertEqual(replay_lean.classify(0, '{"decision":"allow","overwrite":{"CommandLine":"x"}}'),
                         ("rewrite", "x"))


if __name__ == "__main__":
    unittest.main()
