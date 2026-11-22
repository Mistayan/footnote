use assert_cmd::Command;
use serde_json::{Value, json};
use std::{fs, path::Path, time::Duration};

fn footnote(state: &Path, policy: &Path, args: &[&str]) -> Value {
    let out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .env("FOOTNOTE_STATE_DIR", state)
        .env("FOOTNOTE_POLICY_FILE", policy)
        .args(args)
        .timeout(Duration::from_secs(15))
        .output()
        .unwrap();
    serde_json::from_slice(&out.stdout).unwrap()
}
fn option<'a>(all: &'a Value, key: &str) -> &'a Value {
    all["options"]
        .as_array()
        .unwrap()
        .iter()
        .find(|o| o["key"] == key)
        .unwrap()
}

#[test]
fn the_switch_silences_the_hook_and_company_policy_wins() {
    let dir = tempfile::tempdir().unwrap();
    let (state, policy) = (dir.path().join("state"), dir.path().join("policy.json"));
    fs::create_dir_all(&state).unwrap();

    let all = footnote(&state, &policy, &["options"]);
    let enabled = option(&all, "memory.enabled");
    assert_eq!(
        (enabled["value"].clone(), enabled["source"].clone()),
        (json!(true), json!("default"))
    );
    assert!(
        enabled["gain"].as_str().unwrap().len() > 10
            && enabled["cost"].as_str().unwrap().len() > 10
    );

    // Bad values are refused and nothing is written.
    assert!(
        footnote(
            &state,
            &policy,
            &["config", "set", "memory.recall_limit", "99"]
        )["error"]
            .is_string()
    );
    assert!(
        footnote(
            &state,
            &policy,
            &["config", "set", "memory.enabled", "maybe"]
        )["error"]
            .is_string()
    );
    assert!(footnote(&state, &policy, &["config", "set", "memory.nope", "1"])["error"].is_string());
    assert!(!state.join("memory.json").exists());

    // Off: the hook answers nothing and keeps no session state; other settings in the file survive.
    fs::write(state.join("memory.json"), r#"{"every_turns": 4}"#).unwrap();
    assert_eq!(
        footnote(
            &state,
            &policy,
            &["config", "set", "memory.enabled", "false"]
        )["value"],
        false
    );
    let saved: Value =
        serde_json::from_slice(&fs::read(state.join("memory.json")).unwrap()).unwrap();
    assert_eq!(saved, json!({"every_turns": 4, "enabled": false}));
    let out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .env("FOOTNOTE_STATE_DIR", &state)
        .env("FOOTNOTE_POLICY_FILE", &policy)
        .arg("hook")
        .write_stdin(
            json!({"hook_event_name": "SessionStart", "session_id": "s", "cwd": "."}).to_string(),
        )
        .timeout(Duration::from_secs(15))
        .output()
        .unwrap();
    assert!(out.status.success() && out.stdout.is_empty(), "{out:?}");
    assert!(
        !state.join("memory-hook").exists(),
        "a switched-off hook wrote state"
    );

    // Company policy: forced value, shown as locked with its reason, and the user cannot change it.
    fs::write(&policy, r#"{"options": {"memory.enabled": {"value": true, "reason": "required on managed laptops"}}}"#).unwrap();
    let locked = footnote(&state, &policy, &["config", "get", "memory.enabled"]);
    assert_eq!(
        (locked["value"].clone(), locked["locked"].clone()),
        (json!(true), json!(true))
    );
    assert_eq!(locked["reason"], "required on managed laptops");
    let refused = footnote(
        &state,
        &policy,
        &["config", "set", "memory.enabled", "false"],
    );
    assert!(
        refused["error"]
            .as_str()
            .unwrap()
            .contains("required on managed laptops"),
        "{refused}"
    );

    // A broken policy file is an error, never a silent unlock.
    fs::write(&policy, "{not json").unwrap();
    assert!(footnote(&state, &policy, &["options"])["error"].is_string());
}

#[test]
fn lean_rules_and_prose_options_validate_choices_and_policy_locks() {
    let dir = tempfile::tempdir().unwrap();
    let (state, policy) = (dir.path().join("state"), dir.path().join("policy.json"));
    fs::create_dir_all(&state).unwrap();

    let all = footnote(&state, &policy, &["options"]);
    let lean_rules = option(&all, "memory.lean_rules");
    assert_eq!(lean_rules["value"], false);
    assert_eq!(lean_rules["default"], false);

    let lean_prose = option(&all, "memory.lean_prose");
    assert_eq!(lean_prose["value"], "full");
    assert_eq!(
        lean_prose["choices"],
        json!(["off", "lite", "full", "ultra"])
    );

    assert_eq!(
        footnote(
            &state,
            &policy,
            &["config", "set", "memory.lean_rules", "true"]
        )["value"],
        true
    );
    for level in ["off", "lite", "full", "ultra"] {
        assert_eq!(
            footnote(
                &state,
                &policy,
                &["config", "set", "memory.lean_prose", level]
            )["value"],
            level
        );
    }
    assert!(
        footnote(
            &state,
            &policy,
            &["config", "set", "memory.lean_prose", "verbose"]
        )["error"]
            .is_string()
    );

    fs::write(
        &policy,
        r#"{"options": {"memory.lean_prose": {"value": "lite", "reason": "readable prose in team sessions"}}}"#,
    )
    .unwrap();
    let locked = footnote(&state, &policy, &["config", "get", "memory.lean_prose"]);
    assert_eq!(locked["value"], "lite");
    assert_eq!(locked["locked"], true);
    let refused = footnote(
        &state,
        &policy,
        &["config", "set", "memory.lean_prose", "ultra"],
    );
    assert!(
        refused["error"]
            .as_str()
            .unwrap()
            .contains("readable prose")
    );
}
