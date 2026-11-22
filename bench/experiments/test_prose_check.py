import json, os, pathlib, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
from prose_check import check_session, check_static, is_compressed


def test_static_rules_list_prose_off_targets():
    rules = pathlib.Path(__file__).resolve().parents[2] / "rules/lean/LEAN-B.md"
    assert check_static(rules)


def test_normal_prose_and_code_blocks_pass_while_compressed_durable_prose_fails():
    def bash_call(mid, tid, cmd):
        return {"type": "assistant", "message": {"id": mid, "content": [{"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": cmd}}]}}

    def write_doc(mid, tid, path, content):
        return {"type": "assistant", "message": {"id": mid, "content": [{"type": "tool_use", "id": tid, "name": "Write", "input": {"file_path": path, "content": content}}]}}

    # Clean session: normal prose in commit body, PR body, and Markdown docs, plus code arrows/cfg inside backticks.
    clean_doc = (
        "# Setup\n\n"
        "The hook reads your settings file and uses `cfg -> out` inside code spans.\n\n"
        "```rust\n"
        "fn map(cfg: Config) -> Out { todo!() }\n"
        "```\n\n"
        "When the check finishes, the script writes a summary report.\n"
    )
    clean_rows = [
        bash_call("m1", "a", "git commit -m \"fix(hook): guard empty input\" -m \"Prevented a panic when stdin is empty by returning early with no context.\""),
        bash_call("m2", "b", "gh pr create --title \"fix(hook): empty stdin\" --body \"This pull request ensures the hook ignores empty events without failing.\""),
        write_doc("m3", "c", "docs/GUIDE.md", clean_doc),
    ]
    bad_rows = [
        bash_call("m1", "a", "git commit -m \"fix(hook): empty input\" -m \"Fix panic w/ empty stdin -> return early. Add test. Pass checks.\""),
        bash_call("m2", "b", "gh pr create --title \"fix(hook): empty stdin\" --body \"Updated cfg handler. Fix bug. Pass tests. Ship now.\""),
    ]
    assert not is_compressed(clean_doc)
    assert is_compressed("Fix parser bug. Handle empty input. Skip invalid token. Pass all checks.")

    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as cf:
        cf.write("\n".join(json.dumps(r) for r in clean_rows))
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as bf:
        bf.write("\n".join(json.dumps(r) for r in bad_rows))
    try:
        assert check_session(cf.name) == {"prose_checked": 3, "prose_violations": 0, "prose_off_ok": True}
        bad = check_session(bf.name)
        assert bad["prose_checked"] == 2
        assert bad["prose_violations"] == 2
        assert bad["prose_off_ok"] is False
    finally:
        os.unlink(cf.name)
        os.unlink(bf.name)
