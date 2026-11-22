"""Read and search spend before the first edit (#240), from a Claude Code session file: read/search calls, the tokens their
results added (bytes/4, as session_costs.py) and the model turns before the first edit. Counts only, no text kept.

python -I bench/experiments/explore_cost.py SESSION.jsonl
"""
import json, re, sys

EDIT = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ = {"Read", "Grep", "Glob", "LSP", "footnote_code"}
# shortcut: shell edits (sed -i, redirects) do not end the window, shell reads are matched by their first word only;
# refine if a paired arm edits through the shell.
SHELL_READ = re.compile(r"\s*(cat|head|tail|less|sed -n|grep|rg|find|ls|tree|wc|git (grep|show|log|diff)|Get-Content|Select-String|Get-ChildItem)\b")


def explore(path):
    """{read_calls, read_tokens, turns_before_edit, edited, fixed_overhead}: turns are distinct model calls before the one
    that edits."""
    turns, seen, reads = 0, set(), set()
    # fixed_overhead (#242): the first call's whole prompt (system, tools, CLAUDE.md, injections, first message)
    out = {"read_calls": 0, "read_tokens": 0, "turns_before_edit": 0, "edited": False, "fixed_overhead": 0}
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            v = json.loads(line)
        except ValueError:
            continue
        m = v.get("message") or {}
        content = m.get("content") if isinstance(m.get("content"), list) else []
        if v.get("type") == "assistant":
            if m.get("id") not in seen:
                seen.add(m.get("id"))
                turns += 1
                u = m.get("usage") or {}
                if turns == 1:
                    out["fixed_overhead"] = sum(u.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
            for b in content:
                if b.get("type") != "tool_use":
                    continue
                name = b.get("name", "").split("__")[-1]
                if name in EDIT:
                    out.update(turns_before_edit=turns - 1, edited=True)
                    return out
                if name in READ or (name in ("Bash", "PowerShell") and SHELL_READ.match((b.get("input") or {}).get("command", ""))):
                    reads.add(b.get("id"))
                    out["read_calls"] += 1
        elif v.get("type") == "user":
            for b in content:
                if b.get("type") == "tool_result" and b.get("tool_use_id") in reads:
                    out["read_tokens"] += len(json.dumps(b.get("content", ""), ensure_ascii=False)) // 4
    out["turns_before_edit"] = turns
    return out


if __name__ == "__main__":
    print(json.dumps(explore(sys.argv[1])))
