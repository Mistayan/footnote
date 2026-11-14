use assert_cmd::Command;
use serde_json::{Value, json};
use std::{fs, path::Path};

fn cmd(db: &Path, args: &[&str]) -> Command {
    let mut c = Command::new(assert_cmd::cargo::cargo_bin!("footnote"));
    c.arg("--db").arg(db).args(args);
    c
}
fn run(db: &Path, args: &[&str], stdin: Option<Value>) -> Value {
    let mut c = cmd(db, args);
    if let Some(v) = stdin {
        c.write_stdin(v.to_string());
    }
    serde_json::from_slice(&c.assert().success().get_output().stdout).unwrap()
}
fn fails(db: &Path, args: &[&str], stdin: Value) -> String {
    let out = cmd(db, args)
        .write_stdin(stdin.to_string())
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    String::from_utf8(out).unwrap()
}
fn mem(text: &str, kind: &str, scope: &str, date: &str) -> Value {
    json!({"text": text, "kind": kind, "scope": scope, "observed_at": date})
}
fn texts(v: &Value) -> Vec<String> {
    v["memories"]
        .as_array()
        .unwrap()
        .iter()
        .map(|m| m["text"].as_str().unwrap().to_string())
        .collect()
}

#[test]
fn memories_are_scoped_deduplicated_superseded_and_forgotten() {
    let t = tempfile::tempdir().unwrap();
    let db = t.path().join("memory.db");
    let stored = run(
        &db,
        &["remember"],
        Some(json!([
            mem(
                "Johan wants relative % gaps in benchmark tables.",
                "preference",
                "global",
                "2026-11-13"
            ),
            mem(
                "Footnote v1.2 was released on 2026-11-03.",
                "fact",
                "footnote",
                "2026-11-04"
            ),
            mem(
                "Cargo looked missing: Rust is in Program Files, not on the shell PATH.",
                "fix",
                "footnote",
                "2026-11-14"
            ),
            mem(
                "Arkea uses the internal mirror for every package install.",
                "fact",
                "arkea",
                "2026-11-10"
            ),
        ])),
    );
    assert_eq!(stored["stored"].as_array().unwrap().len(), 4);
    // The same memory again is a duplicate, not a second row.
    let again = run(
        &db,
        &["remember"],
        Some(json!([mem(
            "Johan wants relative % gaps in benchmark tables.",
            "preference",
            "global",
            "2026-11-13"
        )])),
    );
    assert_eq!(again["duplicates"], 1);

    // Pack: the global preference first, this project's memories next, never another project's.
    let pack = run(&db, &["memory-pack", "--project", "footnote"], None);
    let p = texts(&pack);
    assert_eq!(p[0], "Johan wants relative % gaps in benchmark tables.");
    assert_eq!(p.len(), 3);
    assert!(!p.iter().any(|x| x.contains("Arkea")));

    // Recall is scoped the same way.
    let r = run(
        &db,
        &[
            "memory-recall",
            "package install mirror",
            "--project",
            "footnote",
        ],
        None,
    );
    assert!(!texts(&r).iter().any(|x| x.contains("Arkea")));
    let r = run(
        &db,
        &[
            "memory-recall",
            "package install mirror",
            "--project",
            "arkea",
        ],
        None,
    );
    assert!(texts(&r)[0].contains("Arkea"));

    // Hits say they are agent memories, with kind, scope and date in the heading.
    let release = run(
        &db,
        &["memory-recall", "released", "--project", "footnote"],
        None,
    );
    let id = release["memories"][0]["id"].as_i64().unwrap();
    let hit = run(&db, &["get", &id.to_string()], None);
    assert_eq!(hit["freshness"], "agent_memory");
    assert_eq!(hit["heading"], "fact · footnote · 2026-11-04");

    // A correction supersedes the old fact: only the new one is recalled.
    run(
        &db,
        &["remember"],
        Some(
            json!([{"text": "Footnote v1.2 was released on 2026-11-05.", "kind": "fact", "scope": "footnote", "observed_at": "2026-11-14", "supersedes": id}]),
        ),
    );
    let r = texts(&run(
        &db,
        &["memory-recall", "released", "--project", "footnote"],
        None,
    ));
    assert!(
        r.iter().any(|x| x.contains("2026-11-05")) && !r.iter().any(|x| x.contains("2026-11-03"))
    );

    // Forget removes it from recall and from the pack.
    let fix = run(
        &db,
        &["memory-recall", "cargo PATH", "--project", "footnote"],
        None,
    )["memories"][0]["id"]
        .as_i64()
        .unwrap();
    run(&db, &["forget", &fix.to_string()], None);
    assert!(
        !texts(&run(&db, &["memory-pack", "--project", "footnote"], None))
            .iter()
            .any(|x| x.contains("Cargo"))
    );

    // Invalid input is refused.
    assert!(
        fails(
            &db,
            &["remember"],
            json!([mem("x", "opinion", "global", "2026-11-14")])
        )
        .contains("kind")
    );
    assert!(
        fails(
            &db,
            &["remember"],
            json!([mem("x", "fact", "global", "14/11/2026")])
        )
        .contains("YYYY-MM-DD")
    );
}

#[test]
fn corpus_and_memory_databases_never_mix() {
    let t = tempfile::tempdir().unwrap();
    let root = t.path().join("notes");
    fs::create_dir(&root).unwrap();
    fs::write(root.join("a.md"), "# A\nsome text\n").unwrap();
    let r = root.to_str().unwrap();
    let corpus = t.path().join("corpus.db");
    run(&corpus, &["index", "--root", r, "--allow", r], None);
    let before = fs::read(&corpus).unwrap();
    assert!(
        fails(
            &corpus,
            &["remember"],
            json!([mem("x", "fact", "global", "2026-11-14")])
        )
        .contains("corpus")
    );
    assert_eq!(
        fs::read(&corpus).unwrap(),
        before,
        "a refused remember must not touch the corpus"
    );

    let memory = t.path().join("memory.db");
    run(
        &memory,
        &["remember"],
        Some(json!([mem("y", "fact", "global", "2026-11-14")])),
    );
    let out = cmd(&memory, &["index", "--root", r, "--allow", r])
        .assert()
        .failure()
        .get_output()
        .stdout
        .clone();
    assert!(String::from_utf8(out).unwrap().contains("memory database"));
}

#[test]
fn agents_can_remember_over_mcp_but_never_into_a_corpus() {
    let t = tempfile::tempdir().unwrap();
    let call = |db: &Path, tool: &str, args: Value| -> Value {
        let lines = [
            json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}),
            json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":tool,"arguments":args}}),
        ];
        let input: String = lines.iter().map(|v| format!("{v}\n")).collect();
        let out = cmd(db, &["serve", "--mcp"])
            .write_stdin(input)
            .assert()
            .success()
            .get_output()
            .stdout
            .clone();
        let last = String::from_utf8(out)
            .unwrap()
            .lines()
            .last()
            .unwrap()
            .to_string();
        serde_json::from_str::<Value>(&last).unwrap()["result"].clone()
    };
    let memory = t.path().join("memory.db");
    let ok = call(
        &memory,
        "footnote_remember",
        json!({"memories": [mem("Prefers French answers.", "preference", "global", "2026-11-14")]}),
    );
    assert_eq!(ok["isError"], false, "{ok}");
    assert_eq!(
        texts(&run(&memory, &["memory-pack"], None)),
        ["Prefers French answers."]
    );

    let root = t.path().join("notes");
    fs::create_dir(&root).unwrap();
    fs::write(root.join("a.md"), "# A\nsome text\n").unwrap();
    let r = root.to_str().unwrap();
    let corpus = t.path().join("corpus.db");
    run(&corpus, &["index", "--root", r, "--allow", r], None);
    let before = fs::read(&corpus).unwrap();
    let refused = call(
        &corpus,
        "footnote_remember",
        json!({"memories": [mem("x", "fact", "global", "2026-11-14")]}),
    );
    assert_eq!(refused["isError"], true);
    let refused = call(&corpus, "footnote_forget", json!({"id": 1}));
    assert_eq!(refused["isError"], true);
    assert_eq!(fs::read(&corpus).unwrap(), before);
}
