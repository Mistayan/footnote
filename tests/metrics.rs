//! Observability is opt-in: `--features metrics` records steps to `<state dir>/metrics.jsonl`; a normal build writes nothing.
use assert_cmd::Command;
use serde_json::{Value, json};
use std::path::Path;

fn footnote(state: &Path, db: &Path, args: &[&str], stdin: Option<Value>) -> Command {
    let mut c = Command::new(assert_cmd::cargo::cargo_bin!("footnote"));
    c.env("FOOTNOTE_STATE_DIR", state)
        .arg("--db")
        .arg(db)
        .args(args);
    if let Some(v) = stdin {
        c.write_stdin(v.to_string());
    }
    c
}

#[cfg(feature = "metrics")]
#[test]
fn steps_failures_and_summary_are_recorded() {
    let t = tempfile::tempdir().unwrap();
    let (state, db) = (t.path().join("state"), t.path().join("memory.db"));
    let mem = json!([{"text": "Footnote metrics test memory.", "kind": "fact", "scope": "global", "observed_at": "2026-11-14"}]);
    footnote(&state, &db, &["remember"], Some(mem))
        .assert()
        .success();
    footnote(&state, &db, &["memory-recall", "--", "metrics"], None)
        .assert()
        .success();
    footnote(&state, &db, &["forget", "999"], None)
        .assert()
        .failure(); // no such memory: a failed step
    let lines = std::fs::read_to_string(state.join("metrics.jsonl")).unwrap();
    assert!(lines.contains(r#""start":"cli.remember""#), "{lines}");
    assert!(lines.contains(r#""span":"cli.memory-recall""#), "{lines}");
    assert!(
        lines.contains(r#""span":"lexical.sync""#) || lines.contains(r#""span":"search.keywords""#),
        "{lines}"
    );
    let out = footnote(&state, &db, &["metrics"], None)
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let summary: Value = serde_json::from_slice(&out).unwrap();
    let steps = summary["steps"].as_array().unwrap();
    let forget = steps
        .iter()
        .find(|s| s["step"] == "cli.forget")
        .expect("forget recorded");
    assert_eq!(forget["failed"], 1);
    assert!(steps.iter().all(|s| s["p95_ms"].as_f64().unwrap() >= 0.0));
}

#[cfg(not(feature = "metrics"))]
#[test]
fn a_normal_build_records_nothing() {
    let t = tempfile::tempdir().unwrap();
    let (state, db) = (t.path().join("state"), t.path().join("memory.db"));
    let mem = json!([{"text": "No metrics here.", "kind": "fact", "scope": "global", "observed_at": "2026-11-14"}]);
    footnote(&state, &db, &["remember"], Some(mem))
        .assert()
        .success();
    assert!(!state.join("metrics.jsonl").exists());
    // the summary command does not exist without the feature
    footnote(&state, &db, &["metrics"], None).assert().failure();
}
