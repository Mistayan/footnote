"""Read and search spend before the first edit (#240), from a Claude Code session file: read/search calls, the tokens their
results added (bytes/4, as session_costs.py) and the model turns before the first edit. Counts only, no text kept.

python -I bench/experiments/explore_cost.py SESSION.jsonl
"""
import json, os, re, sys

EDIT = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ = {"Read", "Grep", "Glob", "LSP", "footnote_code"}
SHELL_READ = re.compile(r"\s*(cat|head|tail|less|sed -n|grep|rg|find|ls|tree|wc|git (grep|show|log|diff)|Get-Content|Select-String|Get-ChildItem)\b")
_SHELL_WRITE_CMD = re.compile(
    r"(?:\b(?:tee|patch|Set-Content|Add-Content|Out-File)\b"
    r"|\b(?:sed|perl)\s+-i\b"
    r"|\bgit\s+apply\b"
    r"|(?:\.write_text|\.write_bytes|WriteAllText|writeFileSync)\s*\("
    r"|\bopen\s*\([^)]*,\s*['\"][wax][+tb]*['\"]"
    r"|(?:^|[;&|]\s*)(?:cat|echo|printf)\b[^>]*>>?\s*(?!/dev/null\b|&\d+\b)\S+)"
)
_SHELL_REDIRECT = re.compile(
    r"(?:^|\s)\d*>>?\s*(?!/dev/null\b|&\d+\b)"
    r"(?:[\w./\\-]+[/\\][\w./\\-]+|[\w.-]+\.(?:py|rs|ts|tsx|js|jsx|txt|md|json|toml|yaml|yml|sh|ps1|c|cpp|h|go|java))\b"
)


def is_shell_edit(cmd):
    if not cmd:
        return False
    if _SHELL_WRITE_CMD.search(cmd):
        return True
    unquoted = re.sub(r"'[^']*'|\"[^\"]*\"", " ", cmd)
    return bool(_SHELL_REDIRECT.search(unquoted))


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
                cmd = (b.get("input") or {}).get("command", "") if name in ("Bash", "PowerShell") else ""
                if name in EDIT or is_shell_edit(cmd):
                    out.update(turns_before_edit=turns - 1, edited=True)
                    return out
                if name in READ or (name in ("Bash", "PowerShell") and SHELL_READ.match(cmd)):
                    reads.add(b.get("id"))
                    out["read_calls"] += 1
        elif v.get("type") == "user":
            for b in content:
                if b.get("type") == "tool_result" and b.get("tool_use_id") in reads:
                    out["read_tokens"] += len(json.dumps(b.get("content", ""), ensure_ascii=False)) // 4
    out["turns_before_edit"] = turns
    return out


def recall_stats(activity_path, session_id=None):
    """{recall_hits, recall_misses, recall_skips, recall_anchor_hits} from memory-hook/activity.jsonl (#241)."""
    out = {"recall_hits": 0, "recall_misses": 0, "recall_skips": 0, "recall_anchor_hits": 0}
    if not activity_path or not os.path.exists(activity_path):
        return out
    for line in open(activity_path, encoding="utf-8", errors="replace"):
        try:
            v = json.loads(line)
        except ValueError:
            continue
        if session_id is not None and v.get("session") != session_id:
            continue
        ev = v.get("event")
        if ev == "recall":
            out["recall_hits"] += 1
            out["recall_anchor_hits"] += int(v.get("anchor_hits", 0) or 0)
        elif ev == "recall_miss":
            out["recall_misses"] += 1
        elif ev == "recall_skip":
            out["recall_skips"] += 1
    return out


if __name__ == "__main__":
    print(json.dumps(explore(sys.argv[1])))
