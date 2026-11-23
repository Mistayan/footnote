//! Integration tests for #351 (Lean D2: PreToolUse hook, `footnote gain`, `install --lean --remove-rtk`, `uninstall --lean`).
use assert_cmd::cargo::cargo_bin_cmd;
use serde_json::{Value, json};
use std::fs;
use tempfile::TempDir;

#[test]
fn hook_lean_rewrites_supported_bash_and_passes_through_pipes() {
    let state = TempDir::new().unwrap();
    let payload = json!({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {
            "command": "cargo test --workspace",
            "timeout": 120000
        }
    });
    let out = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .env("PATH", "")
        .args(["hook", "lean"])
        .write_stdin(payload.to_string())
        .output()
        .unwrap();
    assert!(out.status.success(), "{out:?}");
    let v: Value = serde_json::from_slice(&out.stdout).unwrap();
    let rewritten = v["hookSpecificOutput"]["updatedInput"]["command"]
        .as_str()
        .unwrap();
    assert!(
        rewritten.ends_with(" run -- cargo test --workspace") && rewritten.contains("footnote"),
        "expected absolute-path fallback rewrite when PATH is empty, got {rewritten:?}"
    );
    assert_eq!(v["hookSpecificOutput"]["updatedInput"]["timeout"], 120000);
    assert_eq!(v["hookSpecificOutput"]["permissionDecision"], "allow");

    // When `footnote` IS on PATH, the hook emits the compact `footnote run -- ...` form.
    let bin_dir = assert_cmd::cargo::cargo_bin!("footnote")
        .parent()
        .unwrap()
        .to_path_buf();
    let out_on_path = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .env("PATH", &bin_dir)
        .args(["hook", "lean"])
        .write_stdin(payload.to_string())
        .output()
        .unwrap();
    assert!(out_on_path.status.success(), "{out_on_path:?}");
    let v_path: Value = serde_json::from_slice(&out_on_path.stdout).unwrap();
    assert_eq!(
        v_path["hookSpecificOutput"]["updatedInput"]["command"],
        "footnote run -- cargo test --workspace"
    );

    // A pipe into anything but head/tail must pass through untouched (empty stdout).
    let piped = json!({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "rg foo src | sort"}
    });
    let out2 = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["hook", "lean"])
        .write_stdin(piped.to_string())
        .output()
        .unwrap();
    assert!(out2.status.success(), "{out2:?}");
    assert!(
        String::from_utf8_lossy(&out2.stdout).trim().is_empty(),
        "piped command must not be rewritten"
    );

    // #565: a compound line keeps its `cd` and pipe; only the filtered program is wrapped.
    // #572: Claude Code's PowerShell tool gets the same treatment as Bash.
    for (tool, cmd, want) in [
        (
            "Bash",
            "cd D:/x && cargo test 2>&1 | head -40",
            "cd D:/x && footnote run -- cargo test 2>&1 | head -40",
        ),
        (
            "PowerShell",
            "Set-Location D:/x; git status",
            "Set-Location D:/x; footnote run -- git status",
        ),
    ] {
        let payload = json!({
            "hook_event_name": "PreToolUse",
            "tool_name": tool,
            "tool_input": {"command": cmd}
        });
        let out = cargo_bin_cmd!("footnote")
            .env("FOOTNOTE_STATE_DIR", state.path())
            .env("PATH", &bin_dir)
            .args(["hook", "lean"])
            .write_stdin(payload.to_string())
            .output()
            .unwrap();
        let v: Value = serde_json::from_slice(&out.stdout).unwrap();
        assert_eq!(
            v["hookSpecificOutput"]["updatedInput"]["command"], want,
            "{tool}: {v}"
        );
    }
}

#[test]
fn hook_lean_rewrites_antigravity_tool_calls() {
    let state = TempDir::new().unwrap();
    let bin_dir = assert_cmd::cargo::cargo_bin!("footnote")
        .parent()
        .unwrap()
        .to_path_buf();

    // 1. Antigravity PreToolUse sends `toolCall: { name: "run_command", args: { CommandLine } }`
    //    and expects `{ "decision": "allow", "overwrite": { "CommandLine": ... } }`.
    let agy_payload = json!({
        "conversationId": "conv-123",
        "hookEventName": "PreToolUse",
        "toolCall": {
            "id": "toolu_01",
            "name": "run_command",
            "args": {
                "CommandLine": "cargo test --workspace",
                "WaitMsBeforeAsync": 5000
            }
        }
    });
    let agy_out = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .env("PATH", &bin_dir)
        .args(["hook", "lean"])
        .write_stdin(agy_payload.to_string())
        .output()
        .unwrap();
    assert!(agy_out.status.success(), "{agy_out:?}");
    let agy_v: Value = serde_json::from_slice(&agy_out.stdout).unwrap();
    assert_eq!(agy_v["decision"], "allow", "{agy_v}");
    assert_eq!(
        agy_v["overwrite"]["CommandLine"], "footnote run -- cargo test --workspace",
        "{agy_v}"
    );
    assert!(
        agy_v.get("hookSpecificOutput").is_none(),
        "Antigravity must not receive Claude hookSpecificOutput: {agy_v}"
    );

    // A chained line gets each filtered part wrapped (#565).
    let agy_chain = json!({
        "conversationId": "conv-123",
        "hookEventName": "PreToolUse",
        "toolCall": {
            "id": "toolu_02",
            "name": "run_command",
            "args": { "CommandLine": "Set-Location D:/x; git status && git diff" }
        }
    });
    let agy_chain_out = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .env("PATH", &bin_dir)
        .args(["hook", "lean"])
        .write_stdin(agy_chain.to_string())
        .output()
        .unwrap();
    assert_eq!(
        serde_json::from_slice::<Value>(&agy_chain_out.stdout).unwrap()["overwrite"]["CommandLine"],
        "Set-Location D:/x; footnote run -- git status && footnote run -- git diff"
    );

    // Antigravity passthrough (nothing filtered) must emit explicit `{"decision": "allow"}`
    // because Antigravity treats a missing `decision` field as a denial.
    let agy_chain = json!({
        "conversationId": "conv-123",
        "hookEventName": "PreToolUse",
        "toolCall": {
            "id": "toolu_02",
            "name": "run_command",
            "args": { "CommandLine": "Write-Host hi; Get-ChildItem -Name" }
        }
    });
    let agy_pass = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .env("PATH", &bin_dir)
        .args(["hook", "lean"])
        .write_stdin(agy_chain.to_string())
        .output()
        .unwrap();
    assert!(agy_pass.status.success(), "{agy_pass:?}");
    assert_eq!(
        serde_json::from_slice::<Value>(&agy_pass.stdout).unwrap(),
        json!({"decision": "allow"})
    );
}

#[test]
fn hook_lean_logs_one_safe_decision_per_call_and_gain_counts_it() {
    let state = TempDir::new().unwrap();
    let run = |input: &str| {
        cargo_bin_cmd!("footnote")
            .env("FOOTNOTE_STATE_DIR", state.path())
            .args(["hook", "lean"])
            .write_stdin(input.to_owned())
            .assert()
            .success();
    };
    let claude = json!({"hook_event_name": "PreToolUse", "tool_name": "Bash",
        "cwd": "PRIVATE_CWD", "tool_input": {"command": "git log -- PRIVATE_ARGUMENT"}});
    let codex = json!({"hook_event_name": "PreToolUse", "tool_name": "Bash", "turn_id": "PRIVATE_TURN",
        "tool_input": {"command": "cargo test > PRIVATE_OUT"}});
    let agy = json!({"hookEventName": "PreToolUse", "conversationId": "PRIVATE_SESSION",
        "toolCall": {"name": "run_command", "args": {"CommandLine": "PRIVATE_PROGRAM hi"}}});
    for event in [&claude, &codex, &agy] {
        run(&event.to_string());
    }
    run("not-json-PRIVATE_EVENT");

    let usage = state.path().join("usage.json");
    fs::write(&usage, r#"{"lean_enabled":false}"#).unwrap();
    run(&codex.to_string());
    fs::write(&usage, r#"{"lean_log":false}"#).unwrap();
    run(&claude.to_string());

    let log = state.path().join("usage/lean-hooks.jsonl");
    let raw = fs::read_to_string(&log).unwrap();
    assert!(!raw.contains("PRIVATE_"), "{raw}");
    let rows: Vec<Value> = raw
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(rows.len(), 5);
    assert_eq!(rows[0]["agent"], "claude-code");
    assert_eq!(rows[0]["tool"], "bash");
    assert_eq!(rows[0]["program"], "git");
    assert_eq!(rows[0]["decision"], "rewrite");
    assert_eq!(rows[1]["agent"], "codex");
    assert_eq!(rows[1]["reason"], "compound");
    assert_eq!(rows[2]["agent"], "antigravity");
    assert_eq!(rows[2]["tool"], "run_command");
    assert!(rows[2]["program"].is_null());
    assert_eq!(rows[2]["reason"], "not-covered");
    assert_eq!(rows[3]["decision"], "error");
    assert_eq!(rows[4]["reason"], "disabled");

    // Rotate the existing log and make sure the report reads both segments.
    fs::write(&log, format!("{raw}{}", " ".repeat(512 * 1024))).unwrap();
    fs::write(&usage, "{}").unwrap();
    run(&codex.to_string());
    assert!(log.with_extension("jsonl.old").exists());
    assert_eq!(fs::read_to_string(&log).unwrap().lines().count(), 1);

    let gain = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .arg("gain")
        .output()
        .unwrap();
    assert!(gain.status.success(), "{gain:?}");
    let output: Value = serde_json::from_slice(&gain.stdout).unwrap();
    let hooks = &output["hook_decisions"];
    assert_eq!(hooks["by_agent"]["claude-code"]["rewrite_rate"], 1.0);
    assert_eq!(hooks["by_agent"]["codex"]["calls"], 3);
    assert_eq!(hooks["by_agent"]["codex"]["pass_reasons"]["compound"], 2);
    assert_eq!(hooks["by_agent"]["unknown"]["errors"], 1);
    assert_eq!(
        hooks["top_pass_reasons"][0],
        json!({"reason": "compound", "calls": 2})
    );
}

#[test]
fn gain_reports_shell_savings_miss_rate_and_attrib() {
    let state = TempDir::new().unwrap();
    let mut noisy = String::new();
    for i in 0..40 {
        noisy.push_str(&format!("   Compiling dep-{i} v0.1.0\n"));
    }
    for i in 0..25 {
        noisy.push_str(&format!("test m::case_{i} ... ok\n"));
    }
    noisy.push_str("test result: ok. 25 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n");

    let run_out = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["run", "--stdin", "--family", "cargo-test"])
        .write_stdin(noisy)
        .output()
        .unwrap();
    assert!(run_out.status.success());
    let text = String::from_utf8(run_out.stdout).unwrap();
    let handle = text
        .split("footnote output ")
        .nth(1)
        .unwrap()
        .split_whitespace()
        .next()
        .unwrap()
        .to_string();

    let ret = cargo_bin_cmd!("footnote")
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["output", &handle, "--head", "3"])
        .output()
        .unwrap();
    assert!(ret.status.success());

    let gain = cargo_bin_cmd!("footnote")
        .env("USERPROFILE", state.path())
        .env("HOME", state.path())
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["gain", "--days", "7", "--attrib"])
        .output()
        .unwrap();
    assert!(gain.status.success(), "{gain:?}");
    let v: Value = serde_json::from_slice(&gain.stdout).unwrap();
    assert_eq!(v["shell"]["commands"], 1, "{v}");
    assert!(v["shell"]["saved_bytes"].as_u64().unwrap() > 500, "{v}");
    assert_eq!(v["shell"]["handles_stored"], 1, "{v}");
    assert_eq!(v["shell"]["handles_retrieved"], 1, "{v}");
    assert_eq!(v["shell"]["miss_rate"], 1.0, "{v}");
    assert_eq!(v["shell"]["by_family"][0]["family"], "cargo-test", "{v}");
    assert!(v["attribution"]["totals"].is_object(), "{v}");
}

#[test]
fn remove_rtk_removes_only_the_obsolete_codex_rule() {
    let home = TempDir::new().unwrap();
    let state = TempDir::new().unwrap();
    let rules = home.path().join(".codex/rules/default.rules");
    fs::create_dir_all(rules.parent().unwrap()).unwrap();
    let before = concat!(
        "# Keep this comment\r\n",
        "prefix_rule(pattern=[\"cargo\", \"test\"], decision=\"allow\")\r\n",
    );
    let legacy = concat!(
        "# RTK is mandatory for these local repositories. It is installed under\r\n",
        "# C:\\example\\rtk and already present in Codex's\r\n",
        "# inherited PATH, but the elevated Windows sandbox cannot execute it directly.\r\n",
        "prefix_rule(\r\n",
        "    pattern = [\"rtk\"],\r\n",
        "    decision = \"allow\",\r\n",
        "    justification = \"RTK is the required command wrapper for local development tasks\",\r\n",
        "    match = [\r\n",
        "        \"rtk --version\",\r\n",
        "    ],\r\n",
        ")\r\n",
    );
    let after =
        "# A rule the user added\r\nprefix_rule(pattern=[\"rtk\", \"git\"], decision=\"prompt\")";
    let original = format!("{before}{legacy}{after}");
    let expected = format!("{before}{after}");
    fs::write(&rules, &original).unwrap();

    let invoke = |args: &[&str]| {
        let output = cargo_bin_cmd!("footnote")
            .env("USERPROFILE", home.path())
            .env("HOME", home.path())
            .env("FOOTNOTE_STATE_DIR", state.path())
            .args(args)
            .output()
            .unwrap();
        assert!(output.status.success(), "{output:?}");
        serde_json::from_slice::<Value>(&output.stdout).unwrap()
    };
    let dry = invoke(&["install", "--remove-rtk", "--dry-run"]);
    assert!(
        dry["rtk_removed"]
            .as_array()
            .unwrap()
            .iter()
            .any(|entry| { entry["what"] == "rtk prefix rule" && entry["status"] == "removed" })
    );
    assert_eq!(fs::read_to_string(&rules).unwrap(), original);
    assert!(!rules.with_extension("rules.footnote-backup").exists());

    invoke(&["install", "--remove-rtk"]);
    assert_eq!(fs::read_to_string(&rules).unwrap(), expected);
    assert_eq!(
        fs::read_to_string(rules.with_extension("rules.footnote-backup")).unwrap(),
        original
    );

    invoke(&["install", "--remove-rtk"]);
    invoke(&["uninstall", "--lean"]);
    assert_eq!(fs::read_to_string(&rules).unwrap(), expected);
}

#[test]
fn install_lean_remove_rtk_and_uninstall_lean_preserves_memory_hooks() {
    let home = TempDir::new().unwrap();
    let state = TempDir::new().unwrap();
    fs::create_dir_all(home.path().join(".claude")).unwrap();
    fs::create_dir_all(home.path().join(".codex")).unwrap();
    fs::create_dir_all(home.path().join(".gemini/config")).unwrap();
    let t3_cfg = home
        .path()
        .join(".t3/userdata/providers/antigravity/abc123/config");
    fs::create_dir_all(&t3_cfg).unwrap();
    let gemini_settings = home.path().join(".gemini/settings.json");
    let old_settings = json!({
        "hooks": {
            "BeforeTool": [{"matcher": "run_shell_command", "hooks": [
                {"type": "command", "command": "footnote hook lean", "timeout": 5000},
                {"type": "command", "command": "keep.sh", "timeout": 5000}
            ]}],
            "SessionStart": [{"matcher": "*", "hooks": [{"type": "command", "command": "footnote hook"}]}]
        }
    });
    let original = old_settings.to_string();
    fs::write(&gemini_settings, &original).unwrap();

    // Seed Claude settings with an existing Footnote Memory hook AND an RTK hook.
    let claude_settings = home.path().join(".claude/settings.json");
    fs::write(
        &claude_settings,
        serde_json::to_string_pretty(&json!({
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude", "timeout": 10}]}
                ],
                "SessionStart": [
                    {"hooks": [{"type": "command", "command": "footnote hook", "timeout": 15}]}
                ]
            }
        }))
        .unwrap(),
    )
    .unwrap();

    // 1. --dry-run must not mutate files.
    let dry = cargo_bin_cmd!("footnote")
        .env("USERPROFILE", home.path())
        .env("HOME", home.path())
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["install", "--lean", "--remove-rtk", "--dry-run"])
        .output()
        .unwrap();
    assert!(dry.status.success(), "{dry:?}");
    let after_dry = fs::read_to_string(&claude_settings).unwrap();
    assert!(
        after_dry.contains("rtk hook claude"),
        "dry-run modified file"
    );
    assert!(!after_dry.contains("hook lean"), "dry-run modified file");

    // 2. Real install --lean --remove-rtk installs Lean hook and removes RTK hook.
    let ins = cargo_bin_cmd!("footnote")
        .env("USERPROFILE", home.path())
        .env("HOME", home.path())
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["install", "--lean", "--remove-rtk"])
        .output()
        .unwrap();
    assert!(ins.status.success(), "{ins:?}");
    let after_ins = fs::read_to_string(&claude_settings).unwrap();
    assert!(
        !after_ins.contains("rtk hook claude"),
        "rtk hook remained: {after_ins}"
    );
    assert!(
        after_ins.contains("hook lean"),
        "lean hook missing: {after_ins}"
    );
    assert!(
        after_ins.contains("footnote hook"),
        "memory hook should stay intact: {after_ins}"
    );
    // Antigravity PreToolUse must use the grouped `{matcher: "run_command", hooks: [...]}` schema
    // in both `~/.gemini/config/hooks.json` and T3 Code's isolated provider dir.
    for hooks_path in [
        home.path().join(".gemini/config/hooks.json"),
        t3_cfg.join("hooks.json"),
    ] {
        let agy_hooks: Value =
            serde_json::from_str(&fs::read_to_string(&hooks_path).unwrap()).unwrap();
        assert_eq!(
            agy_hooks["footnote-lean"]["PreToolUse"][0]["matcher"],
            "run_command",
            "{}: {agy_hooks}",
            hooks_path.display()
        );
        assert!(
            agy_hooks["footnote-lean"]["PreToolUse"][0]["hooks"][0]["command"]
                .as_str()
                .unwrap()
                .contains("hook lean"),
            "{}: {agy_hooks}",
            hooks_path.display()
        );
    }
    assert_eq!(fs::read_to_string(&gemini_settings).unwrap(), original);

    // 3. Second install is idempotent ("already registered").
    let ins2 = cargo_bin_cmd!("footnote")
        .env("USERPROFILE", home.path())
        .env("HOME", home.path())
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["install", "--lean"])
        .output()
        .unwrap();
    assert!(ins2.status.success());
    let v2: Value = serde_json::from_slice(&ins2.stdout).unwrap();
    assert!(
        v2["targets"]
            .as_array()
            .unwrap()
            .iter()
            .all(|t| t["status"] == "already registered"),
        "{v2}"
    );

    // 4. uninstall --lean removes only Lean hooks, keeping Memory hooks intact.
    let un = cargo_bin_cmd!("footnote")
        .env("USERPROFILE", home.path())
        .env("HOME", home.path())
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["uninstall", "--lean"])
        .output()
        .unwrap();
    assert!(un.status.success(), "{un:?}");
    let mut expected = old_settings;
    expected["hooks"]["BeforeTool"][0]["hooks"]
        .as_array_mut()
        .unwrap()
        .remove(0);
    let actual: Value =
        serde_json::from_str(&fs::read_to_string(&gemini_settings).unwrap()).unwrap();
    assert_eq!(actual, expected);
    let after_un = fs::read_to_string(&claude_settings).unwrap();
    assert!(
        !after_un.contains("hook lean"),
        "lean hook remained: {after_un}"
    );
    assert!(
        after_un.contains("footnote hook"),
        "memory hook was accidentally removed: {after_un}"
    );
    let t3_after: Value =
        serde_json::from_str(&fs::read_to_string(t3_cfg.join("hooks.json")).unwrap()).unwrap();
    assert!(
        t3_after.get("footnote-lean").is_none(),
        "t3-code lean hook remained: {t3_after}"
    );
}

#[test]
fn gain_missed_ranks_uncovered_prefixes_without_leaking_arguments_or_payloads() {
    let home = TempDir::new().unwrap();
    let state = TempDir::new().unwrap();
    let claude_proj = home.path().join(".claude/projects/demo");
    let codex_sess = home.path().join(".codex/sessions/2026/11/21");
    fs::create_dir_all(&claude_proj).unwrap();
    fs::create_dir_all(&codex_sess).unwrap();

    let today = time::OffsetDateTime::now_utc().date().to_string();
    let ts = format!("{today}T08:00:00Z");

    // Claude transcript: a covered command and three uncovered calls with private arguments.
    let claude_lines = [
        json!({
            "type": "assistant",
            "timestamp": ts,
            "message": {"content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "cargo test --workspace"}},
                {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "cd /private/secret-repo && gh api repos/org/priv/issues?secret=LEAK_ARG_1 | sort"}},
                {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "curl -H 'X-Token: LEAK_HEADER' https://internal.example/v1"}},
                {"type": "tool_use", "id": "t4", "name": "Bash", "input": {"command": "git diff | sort && cat /private/secret-repo"}}
            ]}
        }),
        json!({
            "type": "user",
            "timestamp": ts,
            "message": {"content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "x".repeat(9000)},
                {"type": "tool_result", "tool_use_id": "t2", "content": format!("SECRET_PAYLOAD_BODY_{}", "a".repeat(6000))},
                {"type": "tool_result", "tool_use_id": "t3", "content": format!("RAW_HTTP_BODY_{}", "b".repeat(1500))},
                {"type": "tool_result", "tool_use_id": "t4", "content": "fallback output"}
            ]}
        }),
    ];
    fs::write(
        claude_proj.join("session.jsonl"),
        claude_lines
            .iter()
            .map(|v| v.to_string() + "\n")
            .collect::<String>(),
    )
    .unwrap();

    // Codex transcript: 1 covered (`git status`) + 1 uncovered (`docker ps`).
    let codex_lines = [
        json!({
            "timestamp": ts,
            "type": "response_item",
            "payload": {"type": "function_call", "call_id": "c1", "name": "exec_command", "arguments": "{\"cmd\":\"git status\"}"}
        }),
        json!({
            "timestamp": ts,
            "type": "response_item",
            "payload": {"type": "function_call_output", "call_id": "c1", "output": "On branch main\n"}
        }),
        json!({
            "timestamp": ts,
            "type": "response_item",
            "payload": {"type": "function_call", "call_id": "c2", "name": "exec_command", "arguments": "{\"cmd\":\"docker ps --filter name=PRIVATE_CONTAINER_99 | sort\"}"}
        }),
        json!({
            "timestamp": ts,
            "type": "response_item",
            "payload": {"type": "function_call_output", "call_id": "c2", "output": format!("CONTAINER_ROW_{}", "c".repeat(3200))}
        }),
    ];
    fs::write(
        codex_sess.join("rollout.jsonl"),
        codex_lines
            .iter()
            .map(|v| v.to_string() + "\n")
            .collect::<String>(),
    )
    .unwrap();

    // Antigravity transcript (T3 Code provider layout): 1 covered (`git diff`) + 1 uncovered (`kubectl get`).
    let agy_logs = home.path().join(
        ".t3/userdata/providers/antigravity/prov1/antigravity-acp/brain/conv1/.system_generated/logs",
    );
    fs::create_dir_all(&agy_logs).unwrap();
    let agy_lines = [
        json!({
            "step_index": 3,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "status": "DONE",
            "created_at": ts,
            "model": "gemini-4-neon-medium",
            "input_tokens": 1200,
            "cache_read_tokens": 8000,
            "output_tokens": 120,
            "tool_calls": [
                {"name": "run_command", "args": {"CommandLine": "\"git diff\""}},
                {"name": "run_command", "args": {"CommandLine": "\"kubectl get pods -n PRIVATE_NS_42 | sort\""}}
            ]
        }),
        json!({
            "step_index": 4,
            "source": "MODEL",
            "type": "GENERIC",
            "status": "DONE",
            "created_at": ts,
            "content": "diff --git a/src/lib.rs b/src/lib.rs\n"
        }),
        json!({
            "step_index": 5,
            "source": "MODEL",
            "type": "GENERIC",
            "status": "DONE",
            "created_at": ts,
            "content": format!("POD_ROW_{}", "d".repeat(2400))
        }),
    ];
    let agy_body: String = agy_lines.iter().map(|v| v.to_string() + "\n").collect();
    fs::write(agy_logs.join("transcript.jsonl"), &agy_body).unwrap();
    // Duplicate `transcript_full.jsonl` must be ignored so calls are never double-counted.
    fs::write(agy_logs.join("transcript_full.jsonl"), &agy_body).unwrap();

    let out = cargo_bin_cmd!("footnote")
        .env("USERPROFILE", home.path())
        .env("HOME", home.path())
        .env("CLAUDE_CONFIG_DIR", home.path().join(".claude"))
        .env("CODEX_HOME", home.path().join(".codex"))
        .env("GEMINI_HOME", home.path().join(".gemini"))
        .env("FOOTNOTE_STATE_DIR", state.path())
        .args(["gain", "--missed", "--days", "7"])
        .output()
        .unwrap();
    assert!(out.status.success(), "{out:?}");
    let raw_out = String::from_utf8(out.stdout).unwrap();
    let v: Value = serde_json::from_str(&raw_out).unwrap();
    let m = &v["missed"];
    assert_eq!(m["total_shell_calls"], 8, "{v}");
    assert_eq!(m["covered_calls"], 3, "{v}");
    assert_eq!(m["uncovered_calls"], 5, "{v}");
    assert_eq!(m["by_agent"]["claude-code"]["uncovered_calls"], 3, "{v}");
    assert_eq!(m["by_agent"]["codex"]["covered_calls"], 1, "{v}");
    assert_eq!(m["by_agent"]["antigravity"]["covered_calls"], 1, "{v}");

    let top = m["top_uncovered"].as_array().unwrap();
    assert_eq!(top.len(), 5, "{top:?}");
    assert_eq!(top[0]["prefix"], "gh api");
    assert_eq!(top[1]["prefix"], "docker ps");
    assert_eq!(top[2]["prefix"], "kubectl get");
    assert_eq!(top[3]["prefix"], "curl");
    assert_eq!(top[4]["prefix"], "git diff");

    // Privacy invariant: zero arguments, paths, headers, or raw payloads may appear in the report.
    for forbidden in [
        "LEAK_ARG_1",
        "LEAK_HEADER",
        "PRIVATE_CONTAINER_99",
        "PRIVATE_NS_42",
        "SECRET_PAYLOAD_BODY",
        "RAW_HTTP_BODY",
        "CONTAINER_ROW",
        "POD_ROW",
        "/private/secret-repo",
        "internal.example",
    ] {
        assert!(
            !raw_out.contains(forbidden),
            "forbidden token `{forbidden}` leaked into gain --missed output:\n{raw_out}"
        );
    }
}
