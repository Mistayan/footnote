#!/usr/bin/env python3
"""Summarize a recorded Claude Code turn and its Footnote activity without emitting text."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re


MEMORY_READS = {
    "mcp__footnote-memory__footnote_get": "mcp_get",
    "mcp__footnote-memory__footnote_recall": "mcp_recall",
}


def rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


def hook_deliveries(path, session, start, end):
    pack = None
    recalls = Counter()
    for row in rows(path):
        if row.get("session") != session:
            continue
        stamp = datetime.fromtimestamp(row["t"] / 1000, timezone.utc)
        if stamp <= start and row["event"] == "pack" and (pack is None or stamp >= pack[0]):
            pack = (stamp, Counter(row["ids"]))
        elif start <= stamp < end and row["event"] == "recall":
            recalls.update(row["ids"])
    if pack is None:
        raise ValueError("no session-start pack was logged before the turn")
    return {"hook_pack": pack[1], "hook_recall": recalls}


def result_text(body):
    if isinstance(body, str):
        return body
    return "\n".join(part.get("text", "") for part in body or [] if part.get("type") == "text")


def retrieved_ids(text):
    try:
        payload = json.loads(text)
    except ValueError:
        # Compact memory results start each hit with `[id · heading]`.
        return [int(id_) for id_ in re.findall(r"^\[(\d+) · ", text, re.MULTILINE)]
    if isinstance(payload, dict):
        payload = payload.get("results", [payload])
    return [
        hit["id"] for hit in payload
        if isinstance(hit, dict) and isinstance(hit.get("id"), int) and isinstance(hit.get("text"), str)
    ] if isinstance(payload, list) else []


def replay(transcript, activity, start, end, required):
    hooks = hook_deliveries(activity, transcript.stem, start, end)
    delivered = {**hooks, "mcp_recall": Counter(), "mcp_get": Counter()}
    requests, tool_calls, skill_listing = {}, {}, None
    tool_batches = set()
    logged_reads, failed_reads = Counter(), Counter()
    final = []
    for row in rows(transcript):
        if not row.get("timestamp") or row.get("sessionId") != transcript.stem:
            continue
        stamp = instant(row["timestamp"])
        attachment = row.get("attachment") or {}
        if stamp <= start and attachment.get("type") == "skill_listing":
            listing = attachment.get("content")
            if isinstance(listing, str):
                skill_listing = {"skills": attachment.get("skillCount"), "bytes": len(listing.encode())}
        if not start <= stamp < end:
            continue
        message = row.get("message") or {}
        content = message.get("content")
        if not isinstance(content, list):
            continue
        if row["type"] == "assistant" and message.get("id") and not message.get("model", "").startswith("<"):
            key = (message["id"], row.get("requestId"))
            use = message.get("usage")
            if use is not None:
                requests[key] = use
            for part in content:
                if part["type"] == "tool_use":
                    tool_batches.add(key)
                    tool_calls[part["id"]] = part["name"]
                elif part["type"] == "text":
                    final.append((key, part["text"]))
        elif row["type"] == "user":
            for part in content:
                if part["type"] != "tool_result":
                    continue
                source = MEMORY_READS.get(tool_calls.get(part["tool_use_id"]))
                if source is None:
                    continue
                logged_reads[source] += 1
                if part.get("is_error"):
                    failed_reads[source] += 1
                else:
                    delivered[source].update(retrieved_ids(result_text(part.get("content"))))
    if not requests or not final:
        raise ValueError("turn needs recorded model usage and a final answer")
    if tool_batches - requests.keys() or final[-1][0] in tool_batches:
        raise ValueError("turn must end with a recorded model answer")
    if sum(logged_reads.values()) != sum(name in MEMORY_READS for name in tool_calls.values()):
        raise ValueError("one or more memory reads lack a recorded result")
    final_key = final[-1][0]
    final_text = "\n".join(text for key, text in final if key == final_key)
    references = {id_ for id_ in required if re.search(rf"(?<!\d){id_}(?!\d)", final_text)}
    hook_ids = set(hooks["hook_pack"]) | set(hooks["hook_recall"])
    mcp_ids = set(delivered["mcp_get"]) | set(delivered["mcp_recall"])
    all_deliveries = sum(delivered.values(), Counter())
    input_tokens = [
        sum(count.get(key, 0) for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        for count in requests.values()
    ]
    return {
        "window_utc": [time.astimezone(timezone.utc).isoformat() for time in (start, end)],
        "model_requests": len(requests),
        "tool_round_trips": len(tool_batches),
        "tool_calls": len(tool_calls),
        "peak_input_tokens": max(input_tokens),
        "cumulative_input_tokens": sum(input_tokens),
        "cached_input_tokens": sum(count.get("cache_read_input_tokens", 0) for count in requests.values()),
        "text_deliveries": all_deliveries.total(),
        "repeat_deliveries": all_deliveries.total() - len(all_deliveries),
        "sources": {
            source: {
                "delivered": ids.total(),
                "distinct": len(ids),
                "required_referenced_in_final_answer": len(ids.keys() & references),
            }
            for source, ids in delivered.items()
        },
        "mcp_reads": dict(logged_reads),
        "failed_mcp_reads": dict(failed_reads),
        "required": sorted(required),
        "required_missed_by_hooks_and_retrieved_by_mcp": sorted((required - hook_ids) & mcp_ids),
        "required_referenced_in_final_answer": sorted(references),
        "initial_skill_listing_in_trace": skill_listing,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--activity", type=Path, required=True)
    parser.add_argument("--start", required=True, type=instant)
    parser.add_argument("--end", required=True, type=instant, help="Exclusive end of the complete task turn.")
    parser.add_argument("--required", type=int, nargs="+", required=True, help="Annotated memory IDs for the task.")
    args = parser.parse_args()
    if args.start >= args.end:
        parser.error("--start must precede --end")
    try:
        summary = replay(args.transcript, args.activity, args.start, args.end, set(args.required))
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
