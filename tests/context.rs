use assert_cmd::Command;
use serde_json::Value;
use std::fs;
#[test]
fn title_context_is_searchable_within_child_sections() {
    let t = tempfile::tempdir_in(
        std::env::var("TMPDIR").unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().into()),
    )
    .unwrap();
    let root = t.path().join("notes");
    fs::create_dir(&root).unwrap();
    let db = t.path().join("k.db");
    fs::write(
        root.join("unrelated-name.md"),
        "# SQLite\n## WAL\nCheckpoint latency is amortized through batching.",
    )
    .unwrap();
    let call = |args: &[&str]| -> Value {
        let o = Command::new(assert_cmd::cargo::cargo_bin!("borg-knowledge"))
            .arg("--db")
            .arg(&db)
            .args(args)
            .assert()
            .success()
            .get_output()
            .stdout
            .clone();
        serde_json::from_slice(&o).unwrap()
    };
    call(&[
        "index",
        "--root",
        root.to_str().unwrap(),
        "--allow",
        root.to_str().unwrap(),
    ]);
    let v = call(&["search", "SQLite checkpoint"]);
    assert_eq!(v["results"].as_array().unwrap().len(), 1);
    assert_eq!(v["results"][0]["heading"], "WAL");
}
