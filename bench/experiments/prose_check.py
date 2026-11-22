"""Static and dynamic prose-off checks for Lean B (#239, LEAN-B-BENCH.md).

Confirms that Lean B's prose rules stay off for durable human-facing text:
documentation, commit messages, PR/issue bodies, and user-facing prose.
"""
import json, pathlib, re, sys

_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_MD_LINK_URL = re.compile(r"\]\([^)]+\)")
_SHORTHAND = re.compile(r"(?:\bw/(?=\s|[a-zA-Z])|\bb/c\b|\bpls\b|\bimpl\b|\bcfg\b)", re.IGNORECASE)
_PROSE_ARROW = re.compile(r"[A-Za-z0-9)]\s*(?:->|=>)\s*[A-Za-z(]")
_CONNECTIVES = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "will", "would", "can", "could",
    "should", "may", "might", "must", "this", "that", "these", "those",
    "which", "where", "when", "while", "because", "since", "although", "if",
    "so", "it", "its", "they", "their", "them", "we", "our", "you", "your",
    "and", "or", "but", "for", "with", "from", "into", "to", "of", "in", "on",
    "by", "as", "not", "no",
}


def check_static(rules_path):
    """Verify section 4 of LEAN-B.md lists all required prose-off categories."""
    text = pathlib.Path(rules_path).read_text(encoding="utf-8")
    sec4 = text.split("## 4.", 1)[1].split("\n## ", 1)[0].lower() if "## 4." in text else ""
    required = ("documentation", "commit messages", "pr and issue bodies", "user or customer reads")
    return all(term in sec4 for term in required)


def _strip_code_and_markup(text):
    cleaned = _FENCED_CODE.sub(" ", text)
    cleaned = _INLINE_CODE.sub(" ", cleaned)
    cleaned = _MD_LINK_URL.sub("]", cleaned)
    lines = []
    for raw in cleaned.splitlines():
        s = raw.strip()
        if not s or s.startswith("|") or s.startswith("#"):
            continue
        if re.match(r"^(?:Co-Authored-By:|Closes\s+#|Part of\s+#)", s, re.IGNORECASE):
            continue
        s = re.sub(r"^(?:[-*+]\s+|\d+\.\s+|>\s*)", "", s)
        if s:
            lines.append(s)
    return "\n".join(lines)


def _commit_message_body(cmd):
    m = re.search(r"\bgit\s+commit\b(.*)$", cmd, re.DOTALL)
    if not m:
        return ""
    rest = m.group(1)
    heredoc = re.search(r"<<['\"]?([A-Za-z0-9_]+)['\"]?\s*\n(.*?)\n\1(?:\s|$)", rest, re.DOTALL)
    if heredoc:
        lines = heredoc.group(2).strip().splitlines()
        return "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    flags = re.findall(r"(?:^|\s)(?:-m|-am)\s*(['\"])(.*?)\1", rest, re.DOTALL)
    if len(flags) > 1:
        return "\n".join(msg for _, msg in flags[1:])
    if len(flags) == 1:
        lines = flags[0][1].strip().splitlines()
        return "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    return ""


def _pr_body_from_cmd(cmd):
    heredoc = re.search(r"gh\s+(?:pr|issue)\s+(?:create|edit)\b.*?<<['\"]?([A-Za-z0-9_]+)['\"]?\s*\n(.*?)\n\1(?:\s|$)", cmd, re.DOTALL)
    if heredoc:
        return heredoc.group(2).strip()
    m = re.search(r"gh\s+(?:pr|issue)\s+(?:create|edit)\b.*?--body\s+(['\"])(.*?)\1", cmd, re.DOTALL)
    return m.group(2).strip() if m else ""


def extract_artifacts(session_jsonl):
    """Extract durable human-facing prose artifacts (commit bodies, PR/issue bodies, Markdown docs) from a session."""
    artifacts = []
    for line in open(session_jsonl, encoding="utf-8", errors="replace"):
        try:
            v = json.loads(line)
        except ValueError:
            continue
        if v.get("type") != "assistant":
            continue
        content = (v.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if b.get("type") != "tool_use":
                continue
            name = b.get("name", "").split("__")[-1]
            inp = b.get("input") or {}
            if name in ("Bash", "PowerShell"):
                cmd = inp.get("command", "")
                if "git commit" in cmd:
                    body = _commit_message_body(cmd)
                    if body:
                        artifacts.append(("commit", body))
                if "gh pr " in cmd or "gh issue " in cmd:
                    body = _pr_body_from_cmd(cmd)
                    if body:
                        artifacts.append(("pr", body))
            elif name in ("pull_request_create", "pull_request_update", "pull_request_respond", "create_issue", "comment_on_issue"):
                body = inp.get("body", "")
                if isinstance(body, str) and body.strip():
                    artifacts.append(("pr", body))
            elif name in ("Write", "Edit", "MultiEdit"):
                fp = str(inp.get("file_path", ""))
                if fp.lower().endswith(".md"):
                    if name == "Write" and isinstance(inp.get("content"), str):
                        artifacts.append(("doc", inp["content"]))
                    elif name == "Edit" and isinstance(inp.get("new_string"), str):
                        artifacts.append(("doc", inp["new_string"]))
                    elif name == "MultiEdit":
                        for ed in inp.get("edits") or []:
                            if isinstance(ed, dict) and isinstance(ed.get("new_string"), str):
                                artifacts.append(("doc", ed["new_string"]))
    return artifacts


def is_compressed(text):
    """Return concrete violation reasons if durable prose shows telegraphic/fragment compression."""
    prose = _strip_code_and_markup(text)
    if not prose:
        return []
    reasons = []
    if _SHORTHAND.search(prose):
        reasons.append("telegraphic shorthand token in durable prose")
    if _PROSE_ARROW.search(prose):
        reasons.append("arrow shorthand inside durable prose")
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", prose)
        if len(re.findall(r"[A-Za-z]+", s)) >= 3
    ]
    if len(sentences) >= 3:
        bare = 0
        for s in sentences:
            words = {w.lower() for w in re.findall(r"[A-Za-z]+", s)}
            if not (words & _CONNECTIVES):
                bare += 1
        if bare / len(sentences) >= 0.6:
            reasons.append("telegraphic fragment sentences missing articles/connectives")
    return reasons


def check_session(session_jsonl):
    """Return {prose_checked, prose_violations, prose_off_ok} for a Claude Code session transcript."""
    if not session_jsonl or not pathlib.Path(session_jsonl).is_file():
        return {"prose_checked": 0, "prose_violations": 0, "prose_off_ok": True}
    artifacts = extract_artifacts(session_jsonl)
    violations = 0
    for _, text in artifacts:
        if is_compressed(text):
            violations += 1
    return {
        "prose_checked": len(artifacts),
        "prose_violations": violations,
        "prose_off_ok": violations == 0,
    }


if __name__ == "__main__":
    print(json.dumps(check_session(sys.argv[1])))
