import json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
from explore_cost import explore


def test_counts_reads_and_turns_until_the_first_edit():
    def call(mid, tid, name, **inp):
        return {"type": "assistant", "message": {"id": mid, "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}

    def result(tid, text):
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text}]}}

    rows = [call("m1", "a", "Read", file_path="x.rs"), result("a", "x" * 398),
            call("m2", "b", "Bash", command="rg foo"), call("m2", "c", "Bash", command="cargo test"),
            result("b", "y" * 78), result("c", "z" * 4000),
            call("m3", "d", "Edit"), call("m4", "e", "Read"), result("e", "w" * 4000)]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r) for r in rows))
    try:
        # 400 and 80 bytes once JSON-quoted; cargo test is not a read, the Read after the edit is outside the window
        assert explore(f.name) == {"read_calls": 2, "read_tokens": 120, "turns_before_edit": 2, "edited": True}
    finally:
        os.unlink(f.name)
