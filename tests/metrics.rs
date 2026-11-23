//! Observability is opt-in at run time (#517): option `memory.metrics` (or a `--features metrics` build) records steps to
//! `<state dir>/metrics.jsonl`; with the option off nothing is written.
use assert_cmd::Command;
use serde_json::{Value, json};
use std::path::Path;

fn footnote(state: &Path, db: &Path, args: &[&str], stdin: Option<Value>) -> Command {
    let mut c = Command::new(assert_cmd::cargo::cargo_bin!("footnote"));
    c.env("FOOTNOTE_STATE_DIR", state)
        .env_remove("FOOTNOTE_METRICS")
        .arg("--db")
        .arg(db)
        .args(args);
    if let Some(v) = stdin {
        c.write_stdin(v.to_string());
    }
    c
}

fn json_out(c: &mut Command) -> Value {
    let out = c.assert().success().get_output().stdout.clone();
    serde_json::from_slice(&out).unwrap()
}

fn metrics_on(state: &Path) {
    std::fs::create_dir_all(state).unwrap();
    std::fs::write(
        state.join("memory.json"),
        json!({"metrics": true}).to_string(),
    )
    .unwrap();
}

#[test]
fn steps_failures_and_summary_are_recorded() {
    let t = tempfile::tempdir().unwrap();
    let (state, db) = (t.path().join("state"), t.path().join("memory.db"));
    metrics_on(&state);
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
    let summary = json_out(&mut footnote(&state, &db, &["metrics"], None));
    assert_eq!(summary["on"], true);
    let steps = summary["steps"].as_array().unwrap();
    let forget = steps
        .iter()
        .find(|s| s["step"] == "cli.forget")
        .expect("forget recorded");
    assert_eq!(forget["failed"], 1);
    assert!(steps.iter().all(|s| s["p95_ms"].as_f64().unwrap() >= 0.0));
}

/// Every MCP request writes a span with its outcome: the transport's `serve.<method>` and the tool's `mcp.<tool>`.
#[test]
fn every_mcp_request_and_tool_records_its_outcome() {
    let t = tempfile::tempdir().unwrap();
    let (state, db) = (t.path().join("state"), t.path().join("memory.db"));
    metrics_on(&state);
    let mem = json!([{"text": "Spans for every tool call.", "kind": "fact", "scope": "global", "observed_at": "2026-11-23"}]);
    footnote(&state, &db, &["remember"], Some(mem))
        .assert()
        .success();
    let lines = [
        json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}),
        json!({"jsonrpc":"2.0","method":"notifications/initialized"}),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"footnote_recall","arguments":{"query":"spans"}}}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"footnote_get","arguments":{"id":987654}}}),
        json!({"jsonrpc":"2.0","id":4,"method":"no/such"}),
    ];
    let input: String = lines.iter().map(|v| format!("{v}\n")).collect();
    footnote(&state, &db, &["serve", "--mcp", "--no-audit"], None)
        .write_stdin(input)
        .assert()
        .success();
    let rows: Vec<Value> = std::fs::read_to_string(state.join("metrics.jsonl"))
        .unwrap()
        .lines()
        .map(|l| serde_json::from_str(l).unwrap())
        .filter(|v: &Value| v.get("span").is_some())
        .collect();
    let outcome = |name: &str| -> Vec<bool> {
        rows.iter()
            .filter(|v| v["span"] == name)
            .map(|v| v["ok"].as_bool().unwrap())
            .collect()
    };
    assert_eq!(outcome("serve.initialize"), [true]);
    assert_eq!(outcome("serve.notification"), [true]);
    assert_eq!(outcome("mcp.footnote_recall"), [true], "{rows:?}");
    assert_eq!(outcome("mcp.footnote_get"), [false], "{rows:?}");
    assert_eq!(outcome("serve.tools/call"), [true, false]);
    assert_eq!(outcome("serve.no/such"), [false]);
}

/// A step that keeps failing shows up in `footnote status` (#517); a single failure does not.
#[test]
fn status_reports_steps_that_fail_again_and_again() {
    let t = tempfile::tempdir().unwrap();
    let (state, db) = (t.path().join("state"), t.path().join("memory.db"));
    metrics_on(&state);
    let status = || json_out(&mut footnote(&state, &db, &["status"], None));
    footnote(&state, &db, &["forget", "999"], None)
        .assert()
        .failure();
    assert_eq!(status()["failing"]["steps"], json!([]));
    for _ in 0..2 {
        footnote(&state, &db, &["forget", "999"], None)
            .assert()
            .failure();
    }
    let failing = &status()["failing"];
    assert_eq!(failing["steps"][0]["step"], "cli.forget", "{failing}");
    assert_eq!(failing["steps"][0]["failed"], 3);
    assert!(
        failing["summary"]
            .as_str()
            .unwrap()
            .starts_with("cli.forget failed 3 of 3 times"),
        "{failing}"
    );
}

#[cfg(not(feature = "metrics"))]
#[test]
fn metrics_off_records_nothing() {
    let t = tempfile::tempdir().unwrap();
    let (state, db) = (t.path().join("state"), t.path().join("memory.db"));
    let mem = json!([{"text": "No metrics here.", "kind": "fact", "scope": "global", "observed_at": "2026-11-14"}]);
    footnote(&state, &db, &["remember"], Some(mem))
        .assert()
        .success();
    footnote(&state, &db, &["forget", "999"], None)
        .assert()
        .failure();
    assert!(!state.join("metrics.jsonl").exists());
    let summary = json_out(&mut footnote(&state, &db, &["metrics"], None));
    assert_eq!(summary["on"], false);
    assert_eq!(summary["steps"], json!([]));
}
