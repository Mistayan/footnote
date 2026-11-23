#!/usr/bin/env python3
"""Extract agent tool calls from Antigravity (`agy`) conversation stores.

Each store is `<root>/conversations/<id>.db`, opened read-only. Every tool-call step becomes one JSONL row:
conversation, step, time, status, tool and argument keys. Argument values (command text, paths) are added only
with `--with-args`, for local replays; never commit that output. `--summary` writes aggregate counts only.

Run with `python -I` because the stores hold private conversations. Format notes: README.md next to this file.
"""

import argparse
import collections
import contextlib
import datetime
import json
from pathlib import Path
import sqlite3
import sys

STEP_TOOL_CALL = 132
STATUS_DONE = 3
STEP_COLUMNS = ("idx", "step_type", "status", "metadata", "step_payload")

# Field numbers, verified against agy stores from 20 to 22 Nov 2026 (README.md).
META_TIME = 1  # google.protobuf.Timestamp-like: 1 seconds, 2 nanos
META_TOOL_CALL = 4  # 1 call id, 2 tool name, 3 JSON arguments
CALL_ID, CALL_NAME, CALL_ARGS = 1, 2, 3
PAYLOAD_STEP_TYPE, PAYLOAD_STATUS, PAYLOAD_METADATA, PAYLOAD_ARG_MAP = 1, 4, 5, 140
ARG_ENTRY, ARG_KEY, ARG_VALUE = 1, 1, 2


class ProtobufError(ValueError):
    pass


def read_varint(buf, pos):
    """Return (value, next position) for the base-128 varint at `pos`."""
    value = shift = 0
    while True:
        if pos >= len(buf):
            raise ProtobufError("truncated varint")
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7
        if shift >= 70:
            raise ProtobufError("varint longer than 10 bytes")


def iter_fields(buf):
    """Yield (field number, wire type, value) for each field of one message; no schema needed."""
    pos = 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        field, wire = key >> 3, key & 7
        if field == 0:
            raise ProtobufError("field number 0")
        if wire == 0:
            value, pos = read_varint(buf, pos)
        elif wire == 2:
            size, pos = read_varint(buf, pos)
            if pos + size > len(buf):
                raise ProtobufError("truncated length-delimited field")
            value, pos = bytes(buf[pos:pos + size]), pos + size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            if pos + size > len(buf):
                raise ProtobufError("truncated fixed-width field")
            value, pos = bytes(buf[pos:pos + size]), pos + size
        else:
            raise ProtobufError(f"unsupported wire type {wire}")
        yield field, wire, value


def first_fields(buf):
    """Map field number to its first value (later repeats are ignored)."""
    out = {}
    for field, _, value in iter_fields(buf or b""):
        out.setdefault(field, value)
    return out


def decode_time(buf):
    """UTC datetime from a Timestamp message, or None."""
    if not isinstance(buf, bytes):
        return None
    fields = first_fields(buf)
    seconds = fields.get(1)
    if not isinstance(seconds, int):
        return None
    nanos = fields.get(2, 0) if isinstance(fields.get(2, 0), int) else 0
    stamp = datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc)
    return stamp + datetime.timedelta(microseconds=nanos // 1000)


def iso(stamp):
    return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z") if stamp else None


def decode_arg_map(payload_fields):
    """Argument map at payload field 140: repeated {1 key, 2 value}. Present even where the JSON is missing."""
    raw = payload_fields.get(PAYLOAD_ARG_MAP)
    if not isinstance(raw, bytes):
        return None
    out = {}
    for field, wire, entry in iter_fields(raw):
        if field == ARG_ENTRY and wire == 2:
            item = first_fields(entry)
            key = item.get(ARG_KEY)
            if isinstance(key, bytes):
                value = item.get(ARG_VALUE, b"")
                out[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace") if isinstance(value, bytes) else value
    return out


def decode_step(idx, step_type, status, metadata, payload, problems, with_args=False):
    """One tool-call row, or None when the step is not a tool call. Format drift is counted in `problems`."""
    if step_type != STEP_TOOL_CALL:
        return None
    try:
        meta = first_fields(metadata)
        pay = first_fields(payload)
    except ProtobufError:
        problems["bad_protobuf"] += 1
        return None
    if pay.get(PAYLOAD_STEP_TYPE) != STEP_TOOL_CALL:
        problems["payload_step_type_mismatch"] += 1
    if pay.get(PAYLOAD_STATUS, status) != status:
        problems["payload_status_mismatch"] += 1
    if not meta and isinstance(pay.get(PAYLOAD_METADATA), bytes):
        problems["metadata_from_payload"] += 1
        meta = first_fields(pay[PAYLOAD_METADATA])
    raw_call = meta.get(META_TOOL_CALL)
    if not isinstance(raw_call, bytes):
        problems["tool_call_missing"] += 1
        return None
    call = first_fields(raw_call)
    name = call.get(CALL_NAME)
    if not isinstance(name, bytes) or not name:
        problems["tool_name_missing"] += 1
        return None
    stamp = decode_time(meta.get(META_TIME))
    if stamp is None:
        problems["time_missing"] += 1
    args, source = None, None
    raw_args = call.get(CALL_ARGS)
    if isinstance(raw_args, bytes) and raw_args:
        try:
            args, source = json.loads(raw_args.decode("utf-8")), "json"
        except (UnicodeDecodeError, ValueError):
            problems["args_not_json"] += 1
        if source and not isinstance(args, dict):
            problems["args_not_object"] += 1
            args, source = None, None
    if source is None:
        try:
            args = decode_arg_map(pay)
        except ProtobufError:
            problems["bad_arg_map"] += 1
            args = None
        source = "map" if args is not None else None
    row = {
        "conversation": None,
        "step": idx,
        "time": iso(stamp),
        "status": status,
        "tool": name.decode("utf-8", "replace"),
        "json_args": source == "json",
        "arg_keys": sorted(args) if args else [],
    }
    if with_args:
        row["args"] = args
    return row


def default_roots(home=None):
    home = Path(home or Path.home())
    roots = [home / ".gemini" / "antigravity-cli"]
    roots += sorted((home / ".t3" / "userdata" / "providers" / "antigravity").glob("*/antigravity-acp"))
    return roots


def root_kind(root):
    parts = [p.lower() for p in Path(root).parts]
    if ".t3" in parts:
        return "t3"
    if parts and parts[-1] == "antigravity-cli":
        return "cli"
    return "other"


def connect_ro(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def iter_store(path, problems, with_args=False, step_types=None):
    """Yield tool-call rows of one conversation store; count step types into `step_types` if given."""
    with contextlib.closing(connect_ro(path)) as con:
        columns = {row[1] for row in con.execute("PRAGMA table_info(steps)")}
        missing = [c for c in STEP_COLUMNS if c not in columns]
        if missing:
            problems["steps_columns_missing"] += 1
            return
        if step_types is not None:
            for step_type, count in con.execute("SELECT step_type, COUNT(*) FROM steps GROUP BY step_type"):
                step_types[str(step_type)] += count
        query = "SELECT idx, step_type, status, metadata, step_payload FROM steps WHERE step_type = ? ORDER BY idx"
        for idx, step_type, status, metadata, payload in con.execute(query, (STEP_TOOL_CALL,)):
            row = decode_step(idx, step_type, status, metadata, payload, problems, with_args)
            if row:
                row["conversation"] = Path(path).stem
                yield row


def in_window(row, since, until):
    day = (row["time"] or "")[:10]
    return (not since or day >= since) and (not until or day <= until)


def extract(roots, with_args=False, since=None, until=None):
    """Return (rows, summary) for every store under `roots`. The summary holds aggregate counts only."""
    problems = collections.Counter()
    step_types = collections.Counter()
    rows, stores = [], collections.Counter()
    for root in roots:
        kind = root_kind(root)
        for db in sorted((Path(root) / "conversations").glob("*.db")):
            stores[kind] += 1
            for row in iter_store(db, problems, with_args, step_types):
                if in_window(row, since, until):
                    row["root"] = kind
                    rows.append(row)
    return rows, summarize(rows, stores, problems, step_types, since, until)


def summarize(rows, stores, problems, step_types, since=None, until=None):
    by_tool = collections.Counter(r["tool"] for r in rows)
    with_json = collections.Counter(r["tool"] for r in rows if r["json_args"])
    read_json = [r for r in rows if r["tool"] == "read_file" and r["json_args"]]
    days = collections.Counter((r["time"] or "unknown")[:10] for r in rows)
    return {
        "window": {"since": since, "until": until},
        "stores": dict(sorted(stores.items())),
        "conversations_with_calls": len({(r["root"], r["conversation"]) for r in rows}),
        "calls": len(rows),
        "calls_done": sum(r["status"] == STATUS_DONE for r in rows),
        "calls_with_json_args": sum(r["json_args"] for r in rows),
        "by_status": {str(k): v for k, v in sorted(collections.Counter(r["status"] for r in rows).items())},
        "by_day": dict(sorted(days.items())),
        "by_tool": dict(by_tool.most_common()),
        "by_tool_with_json_args": dict(with_json.most_common()),
        "read_file_with_json_args": {
            "ranged": sum("StartLine" in r["arg_keys"] or "EndLine" in r["arg_keys"] for r in read_json),
            "whole": sum(not ({"StartLine", "EndLine"} & set(r["arg_keys"])) for r in read_json),
            "not_done": sum(r["status"] != STATUS_DONE for r in read_json),
        },
        "step_types_seen": dict(sorted(step_types.items(), key=lambda kv: int(kv[0]))),
        "problems": dict(sorted(problems.items())),
    }


def day_arg(text):
    datetime.date.fromisoformat(text)
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", action="append", type=Path,
                        help="Store root holding conversations/*.db (repeatable). Default: the agy CLI root and every T3 root.")
    parser.add_argument("--out", type=Path, help="Write JSONL rows here (default: stdout unless --summary only).")
    parser.add_argument("--summary", type=Path, help="Write aggregate counts as JSON here ('-' for stdout).")
    parser.add_argument("--with-args", action="store_true",
                        help="Include argument values (commands, paths). Private: local use only, never commit.")
    parser.add_argument("--since", type=day_arg, help="First UTC day to keep, YYYY-MM-DD.")
    parser.add_argument("--until", type=day_arg, help="Last UTC day to keep, YYYY-MM-DD.")
    parser.add_argument("--strict", action="store_true", help="Exit 2 when any format problem was counted.")
    args = parser.parse_args(argv)

    roots = args.root or default_roots()
    rows, summary = extract(roots, args.with_args, args.since, args.until)
    for path in (args.out, args.summary):
        if path and str(path) != "-":
            path.parent.mkdir(parents=True, exist_ok=True)
    if args.out or not args.summary:
        sink = args.out.open("w", encoding="utf-8", newline="\n") if args.out else sys.stdout
        with contextlib.ExitStack() as stack:
            if args.out:
                stack.enter_context(sink)
            for row in rows:
                sink.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if args.summary:
        text = json.dumps(summary, indent=2) + "\n"
        if str(args.summary) == "-":
            sys.stdout.write(text)
        else:
            args.summary.write_text(text, encoding="utf-8")
    if summary["problems"]:
        print(f"format problems: {summary['problems']} (see README.md)", file=sys.stderr)
        if args.strict:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
