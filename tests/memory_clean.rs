use assert_cmd::Command;
use serde_json::{Value, json};
use std::time::Duration;

/// A scheduled cleaning whose agent cannot start retires nothing, records the failure and retries tomorrow (#437).
#[test]
fn a_failed_scheduled_cleaning_changes_nothing_and_retries_tomorrow() {
    let dir = tempfile::tempdir().unwrap();
    let state = dir.path();
    let run = |args: &[&str], stdin: Option<Value>| {
        let mut c = Command::new(assert_cmd::cargo::cargo_bin!("footnote"));
        c.env("FOOTNOTE_STATE_DIR", state)
            .env("FOOTNOTE_POLICY_FILE", state.join("no-policy.json"))
            .env("PATH", state.join("no-agents")) // no `claude` to run
            .args(args)
            .timeout(Duration::from_secs(30));
        if let Some(v) = stdin {
            c.write_stdin(v.to_string());
        }
        c.output().unwrap()
    };
    let db = state.join("memory.db");
    let today = time::OffsetDateTime::now_utc().date();
    let m = |text: &str| json!({"text": text, "kind": "fact", "scope": "alpha", "observed_at": today.to_string()});
    let saved = run(
        &["--db", db.to_str().unwrap(), "remember"],
        Some(json!([
            m("Pool size is 64."),
            m("Deploys go out on Fridays.")
        ])),
    );
    assert!(saved.status.success());
    let live = || -> i64 {
        rusqlite::Connection::open(&db)
            .unwrap()
            .query_row(
                "SELECT count(*) FROM sources WHERE status='indexed'",
                [],
                |r| r.get(0),
            )
            .unwrap()
    };
    let before = live();
    assert!(before > 0);

    let cleaned = run(&["memory-clean", "--scheduled", "--agent", "claude"], None);
    assert!(!cleaned.status.success());
    let st: Value =
        serde_json::from_slice(&std::fs::read(state.join("memory-clean.json")).unwrap()).unwrap();
    assert_eq!(st["failures"], 1);
    assert_eq!(
        st["next_due"],
        (today + time::Duration::days(1)).to_string()
    );
    assert_eq!(live(), before, "a failed run retires nothing");
}
