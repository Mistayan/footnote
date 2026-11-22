import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
from explore_cost import explore


def test_counts_reads_and_turns_until_the_first_edit():
    def call(mid, tid, name, **inp):
        return {"type": "assistant", "message": {"id": mid, "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}

    def result(tid, text):
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}

    first = call("m1", "a", "Read", file_path="x.rs")
    first["message"]["usage"] = {"input_tokens": 3, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 9000}
    rows = [first, result("a", "x" * 398),
            call("m2", "b", "Bash", command="rg foo"), call("m2", "c", "Bash", command="cargo test"),
            result("b", "y" * 78), result("c", "z" * 4000),
            call("m3", "d", "Edit"), call("m4", "e", "Read"), result("e", "w" * 4000)]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows))
    try:
        # 400 and 80 bytes once JSON-quoted; cargo test is not a read, the Read after the edit is outside the window
        assert explore(f.name) == {"read_calls": 2, "read_tokens": 120, "turns_before_edit": 2, "edited": True,
                                 "fixed_overhead": 9003}
    finally:
        os.unlink(f.name)


def test_shell_edit_ends_exploration_and_ignores_benign_redirects():
    from explore_cost import is_shell_edit, recall_stats

    assert is_shell_edit("cat <<'EOF' > app.py\nprint(1)\nEOF")
    assert is_shell_edit("sed -i 's/foo/bar/' src/lib.rs")
    assert is_shell_edit("python -c \"from pathlib import Path; Path('x.py').write_text('ok')\"")
    assert not is_shell_edit("rg foo src 2>/dev/null")
    assert not is_shell_edit("pytest -q 2>&1")
    assert not is_shell_edit("python -c \"assert 5 > 3\"")

    def call(mid, tid, name, **inp):
        return {"type": "assistant", "message": {"id": mid, "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}

    def result(tid, text):
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}

    rows = [
        call("m1", "a", "Bash", command="cat README.md"),
        result("a", "x" * 198),
        call("m2", "b", "Bash", command="cat <<'EOF' > app.py\nprint(1)\nEOF"),
        result("b", ""),
        call("m3", "c", "Read", file_path="later.py"),
        result("c", "y" * 400),
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows))
    act_rows = [
        {"t": 1, "event": "recall", "session": "s1", "ids": [10], "anchor_hits": 1},
        {"t": 2, "event": "recall_miss", "session": "s1", "ids": [], "reason": "no_match"},
        {"t": 3, "event": "recall_skip", "session": "s1", "ids": [], "reason": "already_shown"},
        {"t": 4, "event": "recall", "session": "other", "ids": [20], "anchor_hits": 2},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as af:
        af.write("\n".join(json.dumps(r) for r in act_rows))
    try:
        assert explore(f.name) == {"read_calls": 1, "read_tokens": 50, "turns_before_edit": 1, "edited": True, "fixed_overhead": 0}
        assert recall_stats(af.name, "s1") == {"recall_hits": 1, "recall_misses": 1, "recall_skips": 1, "recall_anchor_hits": 1}
    finally:
        os.unlink(f.name)
        os.unlink(af.name)
