//! End-to-end checks for the zero-configuration agent path.
//!
//! These deliberately avoid starting a child daemon: on Windows a spawned child
//! inherits the test binary's stdout pipe and keeps it open, which hangs the test
//! harness. The shared-daemon protocol is covered by unit tests inside
//! `src/daemon.rs`, which bind the listener in-process.
use assert_cmd::Command;
use serde_json::Value;
use std::{fs, path::PathBuf};

fn bin() -> Command {
    Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
}

fn tmp() -> tempfile::TempDir {
    tempfile::tempdir_in(
        std::env::var("TMPDIR").unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().into()),
    )
    .unwrap()
}

fn fixture(t: &tempfile::TempDir) -> PathBuf {
    let root = t.path().join("notes");
    fs::create_dir(&root).unwrap();
    fs::write(
        root.join("sqlite.md"),
        "# SQLite\n## WAL\nCheckpoint latency is amortized by batching writes.\n",
    )
    .unwrap();
    let db = t.path().join("k.db");
    bin()
        .arg("--db")
        .arg(&db)
        .args(["index", "--root"])
        .arg(&root)
        .arg("--allow")
        .arg(&root)
        .assert()
        .success();
    db
}

#[test]
fn an_agent_gets_working_tools_and_automatic_security_state() {
    let t = tmp();
    let db = fixture(&t);
    let state = t.path().join("state");

    let input = format!(
        "{}\n{}\n",
        serde_json::json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}),
        serde_json::json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"footnote_stats","arguments":{}}}),
    );
    let out = bin()
        .env("FOOTNOTE_STATE_DIR", &state)
        .arg("--db")
        .arg(&db)
        .arg("mcp")
        .write_stdin(input)
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let stdout = String::from_utf8(out).unwrap();
    assert!(stdout.contains("serverInfo"), "{stdout}");
    assert!(
        stdout.contains("_meta"),
        "tool result not audit-bound: {stdout}"
    );

    // Security material appears without any flag or key file being supplied.
    for name in ["audit.jsonl", "audit.key"] {
        assert!(state.join(name).exists(), "missing automatic {name}");
    }
    // And the automatic log verifies against the automatic key.
    let verified = bin()
        .args(["audit", "verify", "--file"])
        .arg(state.join("audit.jsonl"))
        .arg("--mac-key")
        .arg(state.join("audit.key"))
        .output()
        .unwrap();
    assert!(verified.status.success(), "{verified:?}");
    let report: Value = serde_json::from_slice(&verified.stdout).unwrap();
    assert_eq!(report["entries"], 1);
    assert_eq!(report["mac"], "verified");
}

#[test]
fn install_dry_run_writes_nothing() {
    let t = tmp();
    let db = fixture(&t);
    let home = t.path().join("home");
    fs::create_dir_all(home.join(".codex")).unwrap();

    let out = bin()
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .arg("--db")
        .arg(&db)
        .args(["install", "--dry-run"])
        .output()
        .unwrap();
    assert!(out.status.success(), "{out:?}");
    let report: Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(report["dry_run"], true);
    // Windows registers a logon task (dry run: nothing created); elsewhere registration is manual for now.
    let expected = if cfg!(windows) {
        "dry-run"
    } else {
        "manual on this platform"
    };
    assert_eq!(report["daemon"]["status"], expected);
    assert!(
        !home.join(".codex/config.toml").exists(),
        "dry run wrote an agent config"
    );
}

/// The install path really writes config, so the user does not hand-edit files.
#[test]
fn install_registers_detected_agents() {
    let t = tmp();
    let db = fixture(&t);
    let home = t.path().join("home");
    fs::create_dir_all(home.join(".codex")).unwrap();
    fs::create_dir_all(home.join(".gemini/config")).unwrap();

    let out = bin()
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .arg("--db")
        .arg(&db)
        .arg("install")
        .output()
        .unwrap();
    assert!(out.status.success(), "{out:?}");

    let codex = fs::read_to_string(home.join(".codex/config.toml")).unwrap();
    assert!(codex.contains("[mcp_servers.footnote]"), "{codex}");
    assert!(codex.contains("mcp"), "{codex}");

    let agy: Value = serde_json::from_str(
        &fs::read_to_string(home.join(".gemini/config/mcp_config.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(agy["mcpServers"]["footnote"]["args"][2], "mcp");
    assert!(!home.join(".gemini/settings.json").exists());
}

/// The memory hook's per-prompt recall through a daemon started on demand, which leaves by itself once idle.
/// The daemon's stdio is null, so it cannot hold the harness's pipes open (see the module note).
#[test]
fn the_hook_recalls_through_a_resident_daemon_that_leaves_when_idle() {
    use std::process::{Command as Std, Stdio};
    let t = tmp();
    let db = t.path().join("memory.db");
    let state = t.path().join("state");
    // Metrics on (#517): every daemon request writes a span with its outcome.
    std::fs::create_dir_all(&state).unwrap();
    std::fs::write(state.join("memory.json"), r#"{"metrics": true}"#).unwrap();
    let memory = serde_json::json!([{"text": "Always show relative % gaps in every benchmark table.", "kind": "preference",
                                     "scope": "global", "observed_at": "2026-11-15"}]);
    bin()
        .arg("--db")
        .arg(&db)
        .arg("remember")
        .write_stdin(memory.to_string())
        .assert()
        .success();
    let recall = |extra: &[&str]| {
        bin()
            .env("FOOTNOTE_STATE_DIR", &state)
            .arg("--db")
            .arg(&db)
            .args(["memory-recall", "--resident"])
            .args(extra)
            .args(["--", "benchmark table gaps"])
            .output()
            .unwrap()
    };
    let answered =
        |o: &std::process::Output| !String::from_utf8_lossy(&o.stdout).contains("\"error\"");
    // No daemon: --resident fails, so the hook falls back to its own search.
    assert!(!answered(&recall(&[])));

    let mut daemon = Std::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .env("FOOTNOTE_STATE_DIR", &state)
        .arg("--db")
        .arg(&db)
        .args([
            "serve",
            "--mcp",
            "--daemon",
            "--no-audit",
            "--idle-seconds",
            "2",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    let mut out = recall(&[]);
    for _ in 0..50 {
        if answered(&out) {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
        out = recall(&[]);
    }
    let v: Value = serde_json::from_slice(&out.stdout).unwrap_or_else(|_| panic!("{out:?}"));
    assert!(v["memories"].to_string().contains("relative % gaps"), "{v}");

    // Idle with no session open: the daemon exits on its own.
    let mut gone = None;
    for _ in 0..100 {
        gone = daemon.try_wait().unwrap();
        if gone.is_some() {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
    if gone.is_none() {
        daemon.kill().unwrap();
        panic!("daemon still running after its idle time");
    }
    let spans: Vec<Value> = std::fs::read_to_string(state.join("metrics.jsonl"))
        .unwrap()
        .lines()
        .filter_map(|l| serde_json::from_str(l).ok())
        .filter(|v: &Value| v["span"].is_string())
        .collect();
    for name in ["daemon.tools/call", "mcp.footnote_memory_recall"] {
        assert!(
            spans.iter().any(|v| v["span"] == name && v["ok"] == true),
            "{name} missing: {spans:?}"
        );
    }
}

/// `footnote update` replaces the binary under a running daemon: the daemon leaves so the next hook call starts the
/// new build (#515), even with no idle limit (the logon task's daemon).
#[test]
fn a_daemon_leaves_once_its_binary_is_replaced() {
    use std::process::{Command as Std, Stdio};
    let t = tmp();
    let db = fixture(&t);
    let exe = t
        .path()
        .join(format!("footnote{}", std::env::consts::EXE_SUFFIX));
    fs::copy(assert_cmd::cargo::cargo_bin!("footnote"), &exe).unwrap();
    let mut daemon = Std::new(&exe)
        .env("FOOTNOTE_STATE_DIR", t.path().join("state"))
        .arg("--db")
        .arg(&db)
        .args(["serve", "--mcp", "--daemon", "--no-audit"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    std::thread::sleep(std::time::Duration::from_secs(2));
    assert!(daemon.try_wait().unwrap().is_none(), "daemon did not start");

    // What `footnote update` does: set the running binary aside, put another build in its place.
    fs::rename(&exe, t.path().join("footnote.replaced")).unwrap();
    fs::write(&exe, b"another build").unwrap();
    let mut gone = None;
    for _ in 0..150 {
        gone = daemon.try_wait().unwrap();
        if gone.is_some() {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
    if gone.is_none() {
        daemon.kill().unwrap();
        panic!("daemon still serving the old build after the update");
    }
}

/// An agent's relay outlives its daemon: once the daemon stops (an install replacing the binary, a crash), the
/// next call is answered in-process instead of the agent losing its memory tools until it reconnects.
#[test]
fn an_agent_keeps_its_tools_when_the_daemon_stops() {
    use std::io::{BufRead, BufReader, Write};
    use std::process::{Command as Std, Stdio};
    let t = tmp();
    let db = t.path().join("memory.db");
    let state = t.path().join("state");
    let memory = serde_json::json!([{"text": "The relay falls back in-process.", "kind": "fact",
                                     "scope": "global", "observed_at": "2026-11-17"}]);
    bin()
        .arg("--db")
        .arg(&db)
        .arg("remember")
        .write_stdin(memory.to_string())
        .assert()
        .success();
    let footnote = || {
        let mut c = Std::new(assert_cmd::cargo::cargo_bin!("footnote"));
        c.env("FOOTNOTE_STATE_DIR", &state).arg("--db").arg(&db);
        c
    };
    let mut daemon = footnote()
        .args([
            "serve",
            "--mcp",
            "--daemon",
            "--no-audit",
            "--idle-seconds",
            "30",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    // Wait until the daemon answers, so the relay below really connects to it.
    let up = || {
        let o = footnote()
            .args(["memory-recall", "--resident", "--", "relay"])
            .output()
            .unwrap();
        !String::from_utf8_lossy(&o.stdout).contains("\"error\"")
    };
    assert!((0..50).any(|_| up() || {
        std::thread::sleep(std::time::Duration::from_millis(100));
        false
    }));

    let mut relay = footnote()
        .arg("mcp")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut input = relay.stdin.take().unwrap();
    let mut output = BufReader::new(relay.stdout.take().unwrap());
    let mut call = |id: u64| {
        let req = serde_json::json!({"jsonrpc":"2.0","id":id,"method":"tools/list"});
        writeln!(input, "{req}").unwrap();
        input.flush().unwrap();
        let mut line = String::new();
        output.read_line(&mut line).unwrap();
        let v: Value =
            serde_json::from_str(&line).unwrap_or_else(|_| panic!("reply {id}: {line:?}"));
        assert_eq!(v["id"], id, "{v}");
        assert!(v["result"]["tools"].is_array(), "{v}");
    };
    call(1);
    daemon.kill().unwrap();
    daemon.wait().unwrap();
    call(2);
    call(3);
    drop(call);
    drop(input);
    let done = relay.wait_with_output().unwrap();
    assert!(done.status.success(), "{done:?}");
    assert!(
        String::from_utf8_lossy(&done.stderr).contains("serving in-process"),
        "{done:?}"
    );
}

/// The memory hook starts a daemon only when none is there. A daemon that is there but slow to answer (still loading its
/// models after a start, or busy) keeps its socket and the hook answers that prompt by keyword: a second daemon would take
/// the socket over (on Unix a new listener replaces the socket file) and leave the first one holding its models with no new
/// connection.
#[cfg(unix)]
#[test]
fn the_hook_starts_a_daemon_only_when_none_is_there() {
    use std::os::unix::net::{UnixListener, UnixStream};
    use std::process::{Command as Std, Stdio};
    use std::sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    };
    use std::time::{Duration, Instant};
    /// A daemon this test started, stopped when dropped: also when an assertion fails half-way.
    struct Started(std::process::Child);
    impl Drop for Started {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
    let t = tmp();
    let state = t.path().join("state");
    fs::create_dir_all(&state).unwrap();
    let db = state.join("memory.db");
    let memory = serde_json::json!([{"text": "Always show relative % gaps in every benchmark table.", "kind": "preference",
                                     "scope": "global", "observed_at": "2026-11-23"}]);
    bin()
        .env("FOOTNOTE_STATE_DIR", &state)
        .arg("--db")
        .arg(&db)
        .arg("remember")
        .write_stdin(memory.to_string())
        .assert()
        .success();
    // A model folder makes the hook recall through the resident daemon; the hook itself never loads it.
    fs::write(
        state.join("memory.json"),
        serde_json::json!({"models": [t.path().join("model")], "resident": true, "idle_seconds": 2}).to_string(),
    )
    .unwrap();
    let hook = |session: &str| {
        let event = serde_json::json!({"hook_event_name": "UserPromptSubmit", "session_id": session,
                                       "cwd": env!("CARGO_MANIFEST_DIR"), "prompt": "benchmark table gaps"});
        let out = bin()
            .env("FOOTNOTE_STATE_DIR", &state)
            .arg("hook")
            .write_stdin(event.to_string())
            .output()
            .unwrap();
        assert!(out.status.success(), "{out:?}");
        String::from_utf8(out.stdout).unwrap()
    };
    let pid = || fs::read_to_string(state.join("daemon.pid")).unwrap_or_default();
    let start_daemon = || {
        Started(
            Std::new(assert_cmd::cargo::cargo_bin!("footnote"))
                .env("FOOTNOTE_STATE_DIR", &state)
                .arg("--db")
                .arg(&db)
                .args(["serve", "--mcp", "--daemon", "--no-audit"])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .unwrap(),
        )
    };

    // The daemon's socket path, from a daemon started and killed (the socket file stays behind).
    let daemon = start_daemon();
    let deadline = Instant::now() + Duration::from_secs(10);
    let sock = loop {
        let found = fs::read_dir(&state)
            .unwrap()
            .flatten()
            .map(|e| e.path())
            .find(|p| p.extension().is_some_and(|x| x == "sock"));
        if let Some(sock) = found {
            break sock;
        }
        assert!(Instant::now() < deadline, "the daemon made no socket");
        std::thread::sleep(Duration::from_millis(50));
    };
    drop(daemon);
    let _ = fs::remove_file(&sock);

    // A daemon that accepts connections and does not answer yet, like one still loading its models.
    let listener = UnixListener::bind(&sock).unwrap();
    let accepted = Arc::new(AtomicUsize::new(0));
    let count = Arc::clone(&accepted);
    std::thread::spawn(move || {
        let mut held = Vec::new();
        for stream in listener.incoming().flatten() {
            count.fetch_add(1, Ordering::SeqCst);
            held.push(stream);
        }
    });
    let before = pid();
    assert!(hook("slow").contains("relative % gaps"), "keyword answer");
    std::thread::sleep(Duration::from_millis(1500)); // a daemon the hook started would have bound the socket by now
    let seen = accepted.load(Ordering::SeqCst);
    assert!(seen >= 1, "the hook did not try the daemon");
    let _probe = UnixStream::connect(&sock).unwrap();
    std::thread::sleep(Duration::from_millis(200));
    assert_eq!(
        accepted.load(Ordering::SeqCst),
        seen + 1,
        "another daemon took the socket over"
    );
    assert_eq!(pid(), before, "the hook started a second daemon");

    // A real daemon that answers in time but fails this call (the model folder does not exist): it keeps its socket too.
    fs::remove_file(&sock).unwrap();
    let mut daemon = start_daemon();
    let serving = daemon.0.id().to_string();
    let deadline = Instant::now() + Duration::from_secs(10);
    while !(pid() == serving && UnixStream::connect(&sock).is_ok()) {
        assert!(Instant::now() < deadline, "the daemon did not start");
        std::thread::sleep(Duration::from_millis(50));
    }
    assert!(
        hook("failing").contains("relative % gaps"),
        "keyword answer"
    );
    std::thread::sleep(Duration::from_millis(1500));
    assert_eq!(pid(), serving, "the hook started a second daemon");
    assert!(daemon.0.try_wait().unwrap().is_none(), "the daemon stopped");
    drop(daemon);

    // No daemon at all: the hook starts one for the next prompts, which leaves after its idle time.
    let _ = fs::remove_file(&sock);
    let before = pid();
    assert!(hook("none").contains("relative % gaps"), "keyword answer");
    let deadline = Instant::now() + Duration::from_secs(10);
    let started = loop {
        let now = pid();
        if now != before && UnixStream::connect(&sock).is_ok() {
            break now;
        }
        assert!(
            Instant::now() < deadline,
            "no daemon started when none was there"
        );
        std::thread::sleep(Duration::from_millis(100));
    };
    let alive = || {
        Std::new("kill")
            .args(["-0", started.trim()])
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|s| s.success())
    };
    let deadline = Instant::now() + Duration::from_secs(20);
    while alive() {
        if Instant::now() > deadline {
            let _ = Std::new("kill").arg(started.trim()).status();
            panic!("the daemon the hook started did not leave after its idle time");
        }
        std::thread::sleep(Duration::from_millis(200));
    }
}

/// Each product's switch (goal 12): off removes its tools from the agent's list and refuses calls at once, on a server
/// already running; the other products keep working.
#[test]
fn a_switched_off_product_leaves_the_agents_tools() {
    let t = tmp();
    let corpus = fixture(&t);
    let memory = t.path().join("memory.db");
    let state = t.path().join("state");
    let footnote = || {
        let mut c = bin();
        c.env("FOOTNOTE_STATE_DIR", &state);
        c
    };
    let session = |db: &PathBuf, calls: &[Value]| -> Vec<Value> {
        let input: String = calls.iter().map(|c| format!("{c}\n")).collect();
        let out = footnote()
            .arg("--db")
            .arg(db)
            .arg("mcp")
            .write_stdin(input)
            .output()
            .unwrap();
        String::from_utf8_lossy(&out.stdout)
            .lines()
            .map(|l| serde_json::from_str(l).unwrap())
            .collect()
    };
    let list = serde_json::json!({"jsonrpc":"2.0","id":1,"method":"tools/list"});
    let call = |name: &str, args: Value| serde_json::json!({"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":name,"arguments":args}});
    let names = |r: &Value| -> Vec<String> {
        r["result"]["tools"]
            .as_array()
            .unwrap()
            .iter()
            .map(|t| t["name"].as_str().unwrap().to_string())
            .collect()
    };
    let refused = |r: &Value| {
        r["result"]["isError"] == true && r["result"].to_string().contains("switched off")
    };
    let set = |key: &str, v: &str| {
        footnote()
            .args(["config", "set", key, v])
            .assert()
            .success()
    };

    let note = serde_json::json!([{"text": "Switches are per product.", "kind": "fact", "scope": "global", "observed_at": "2026-11-17"}]);
    footnote()
        .arg("--db")
        .arg(&memory)
        .arg("remember")
        .write_stdin(note.to_string())
        .assert()
        .success();
    let on = session(&memory, std::slice::from_ref(&list));
    assert!(
        names(&on[0]).contains(&"footnote_remember".to_string()),
        "{on:?}"
    );

    if names(&on[0]).iter().any(|n| n == "footnote_code") {
        set("code.enabled", "false");
        let r = session(
            &memory,
            &[
                list.clone(),
                call("footnote_code", serde_json::json!({"target": "main"})),
            ],
        );
        assert!(!names(&r[0]).iter().any(|n| n == "footnote_code"), "{r:?}");
        assert!(
            names(&r[0]).iter().any(|n| n == "footnote_remember"),
            "{r:?}"
        );
        assert!(refused(&r[1]), "{r:?}");
    }

    set("memory.enabled", "false");
    let r = session(
        &memory,
        &[list.clone(), call("footnote_stats", serde_json::json!({}))],
    );
    assert!(
        !names(&r[0])
            .iter()
            .any(|n| n == "footnote_remember" || n == "footnote_stats"),
        "{r:?}"
    );
    assert!(refused(&r[1]), "{r:?}");
    // Library is its own switch: its corpus still answers while Memory is off.
    let r = session(
        &corpus,
        &[call(
            "footnote_recall",
            serde_json::json!({"query": "checkpoint"}),
        )],
    );
    assert_eq!(r[0]["result"]["isError"], false, "{r:?}");

    set("library.enabled", "false");
    let r = session(
        &corpus,
        &[
            list.clone(),
            call(
                "footnote_recall",
                serde_json::json!({"query": "checkpoint"}),
            ),
        ],
    );
    assert!(
        !names(&r[0]).iter().any(|n| n == "footnote_recall"),
        "{r:?}"
    );
    assert!(refused(&r[1]), "{r:?}");

    set("memory.enabled", "true");
    let r = session(&memory, &[call("footnote_stats", serde_json::json!({}))]);
    assert_eq!(r[0]["result"]["isError"], false, "{r:?}");

    let status: Value =
        serde_json::from_slice(&footnote().arg("status").output().unwrap().stdout).unwrap();
    assert_eq!(status["products"]["library"]["enabled"], false, "{status}");
}
