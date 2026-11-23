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

/// A daemon a test started, stopped when dropped: also when an assertion fails half-way.
#[cfg(unix)]
struct Started(std::process::Child);
#[cfg(unix)]
impl Drop for Started {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

/// A daemon that a test did not start itself (the memory hook did), stopped by pid when dropped.
#[cfg(unix)]
struct StartedElsewhere(String);
#[cfg(unix)]
impl Drop for StartedElsewhere {
    fn drop(&mut self) {
        let _ = std::process::Command::new("kill")
            .arg(self.0.trim())
            .stderr(std::process::Stdio::null())
            .status();
    }
}

/// A state folder holding a memory database with one memory, for the tests that start daemons.
#[cfg(unix)]
fn memory_state(t: &tempfile::TempDir) -> (PathBuf, PathBuf) {
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
    (state, db)
}

/// Resident recall on, through a model folder the hook itself never loads.
#[cfg(unix)]
fn resident_settings(t: &tempfile::TempDir, state: &std::path::Path, idle_seconds: u64) {
    fs::write(
        state.join("memory.json"),
        serde_json::json!({"models": [t.path().join("model")], "resident": true, "idle_seconds": idle_seconds})
            .to_string(),
    )
    .unwrap();
}

/// `serve --mcp --daemon` with an idle limit, as the memory hook starts one on demand, or without, as a service or the
/// logon task starts one on purpose.
#[cfg(unix)]
fn start_daemon(state: &std::path::Path, db: &std::path::Path, idle: Option<u64>) -> Started {
    use std::process::Stdio;
    let mut c = std::process::Command::new(assert_cmd::cargo::cargo_bin!("footnote"));
    c.env("FOOTNOTE_STATE_DIR", state)
        .arg("--db")
        .arg(db)
        .args(["serve", "--mcp", "--daemon", "--no-audit"]);
    if let Some(idle) = idle {
        c.args(["--idle-seconds", &idle.to_string()]);
    }
    Started(
        c.stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap(),
    )
}

/// The pid in `daemon.pid`: the daemon that bound the socket last.
#[cfg(unix)]
fn daemon_pid(state: &std::path::Path) -> String {
    fs::read_to_string(state.join("daemon.pid"))
        .unwrap_or_default()
        .trim()
        .to_string()
}

/// The daemon's socket path once a daemon made it.
#[cfg(unix)]
fn socket_of(state: &std::path::Path) -> Option<PathBuf> {
    fs::read_dir(state)
        .ok()?
        .flatten()
        .map(|e| e.path())
        .find(|p| p.extension().is_some_and(|x| x == "sock"))
}

/// Wait up to `secs` for `done`, else fail with `what`.
#[cfg(unix)]
fn wait_for(secs: u64, what: &str, mut done: impl FnMut() -> bool) {
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(secs);
    while !done() {
        assert!(std::time::Instant::now() < deadline, "{what}");
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}

/// A daemon serves the socket: a connection to the path is accepted.
#[cfg(unix)]
fn serves(state: &std::path::Path) -> bool {
    socket_of(state).is_some_and(|s| std::os::unix::net::UnixStream::connect(s).is_ok())
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

/// One `UserPromptSubmit` event, as an agent sends it.
#[cfg(unix)]
fn prompt_event(session: &str) -> String {
    serde_json::json!({"hook_event_name": "UserPromptSubmit", "session_id": session,
                       "cwd": env!("CARGO_MANIFEST_DIR"), "prompt": "benchmark table gaps"})
    .to_string()
}

/// The memory hook on one prompt; what it answers.
#[cfg(unix)]
fn run_hook(state: &std::path::Path, session: &str) -> String {
    let out = bin()
        .env("FOOTNOTE_STATE_DIR", state)
        .arg("hook")
        .write_stdin(prompt_event(session))
        .output()
        .unwrap();
    assert!(out.status.success(), "{out:?}");
    String::from_utf8(out.stdout).unwrap()
}

/// The process runs and is not a zombie. `ps` asks nothing of the daemon: a connection to its socket would count as a
/// session and push its idle exit back.
#[cfg(unix)]
fn running(pid: &str) -> bool {
    std::process::Command::new("ps")
        .args(["-o", "stat=", "-p", pid])
        .output()
        .is_ok_and(|o| {
            let stat = String::from_utf8_lossy(&o.stdout);
            o.status.success() && !stat.trim().is_empty() && !stat.trim().starts_with('Z')
        })
}

/// The memory hook starts a daemon only when none is there (#647). A daemon that is there but slow to answer (still
/// loading its models after a start, or busy) keeps its socket and the hook answers that prompt by keyword: a second daemon
/// would take the socket over (on Unix a new listener replaces the socket file) and leave the first one holding its models
/// with no new connection.
#[cfg(unix)]
#[test]
fn the_hook_starts_a_daemon_only_when_none_is_there() {
    use std::os::unix::net::{UnixListener, UnixStream};
    use std::sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    };
    let t = tmp();
    let (state, db) = memory_state(&t);
    resident_settings(&t, &state, 2);

    // The daemon's socket path, from a daemon started and stopped (the socket file stays behind).
    let daemon = start_daemon(&state, &db, None);
    wait_for(10, "the daemon made no socket", || {
        socket_of(&state).is_some()
    });
    let sock = socket_of(&state).unwrap();
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
    let before = daemon_pid(&state);
    assert!(
        run_hook(&state, "slow").contains("relative % gaps"),
        "keyword answer"
    );
    // Time for a daemon the hook started to bind the socket, or to find it served and leave: either connects here first.
    std::thread::sleep(std::time::Duration::from_millis(1500));
    assert_eq!(
        accepted.load(Ordering::SeqCst),
        1,
        "the hook connected more than once, or started a daemon"
    );
    let _probe = UnixStream::connect(&sock).unwrap();
    wait_for(5, "another daemon took the socket over", || {
        accepted.load(Ordering::SeqCst) == 2
    });
    assert_eq!(
        daemon_pid(&state),
        before,
        "the hook started a second daemon"
    );

    // A real daemon that answers in time but fails this call (the model folder does not exist): it keeps its socket too.
    fs::remove_file(&sock).unwrap();
    let mut daemon = start_daemon(&state, &db, None);
    let serving = daemon.0.id().to_string();
    wait_for(10, "the daemon did not start", || {
        daemon_pid(&state) == serving && serves(&state)
    });
    assert!(
        run_hook(&state, "failing").contains("relative % gaps"),
        "keyword answer"
    );
    std::thread::sleep(std::time::Duration::from_millis(1500));
    assert_eq!(
        daemon_pid(&state),
        serving,
        "the hook started a second daemon"
    );
    assert!(daemon.0.try_wait().unwrap().is_none(), "the daemon stopped");
    drop(daemon);

    // No daemon at all: the hook starts one for the next prompts, which leaves after its idle time.
    let _ = fs::remove_file(&sock);
    let before = daemon_pid(&state);
    assert!(
        run_hook(&state, "none").contains("relative % gaps"),
        "keyword answer"
    );
    wait_for(10, "no daemon started when none was there", || {
        daemon_pid(&state) != before && serves(&state)
    });
    let started = StartedElsewhere(daemon_pid(&state));
    wait_for(
        20,
        "the daemon the hook started did not leave after its idle time",
        || !running(&started.0),
    );
}

/// A daemon started on demand (an idle limit, as the memory hook starts one) leaves at once when a daemon already serves
/// the socket, instead of taking the socket over from it.
#[cfg(unix)]
#[test]
fn a_daemon_started_on_demand_leaves_when_one_already_serves() {
    let t = tmp();
    let (state, db) = memory_state(&t);
    let mut serving = start_daemon(&state, &db, None);
    let pid = serving.0.id().to_string();
    wait_for(10, "the first daemon did not start", || {
        daemon_pid(&state) == pid && serves(&state)
    });
    let mut late = start_daemon(&state, &db, Some(30));
    let mut left = None;
    wait_for(
        10,
        "a daemon started on demand stayed beside the running one",
        || {
            left = late.0.try_wait().unwrap();
            left.is_some()
        },
    );
    assert!(left.unwrap().success(), "{left:?}");
    assert_eq!(
        daemon_pid(&state),
        pid,
        "the daemon started on demand bound the socket"
    );
    assert!(
        serves(&state),
        "the socket no longer reaches the running daemon"
    );
    assert!(
        serving.0.try_wait().unwrap().is_none(),
        "the running daemon stopped"
    );
}

/// Daemons started on demand at the same moment take turns: one binds the socket, the others find it served and leave.
#[cfg(unix)]
#[test]
fn daemons_started_on_demand_together_leave_one_serving() {
    let t = tmp();
    let (state, db) = memory_state(&t);
    let mut daemons: Vec<Started> = (0..4)
        .map(|_| start_daemon(&state, &db, Some(30)))
        .collect();
    wait_for(10, "more than one daemon kept running", || {
        daemons
            .iter_mut()
            .map(|d| d.0.try_wait().unwrap().is_none())
            .filter(|running| *running)
            .count()
            == 1
    });
    let mut survivor = None;
    for d in &mut daemons {
        match d.0.try_wait().unwrap() {
            None => survivor = Some(d.0.id().to_string()),
            Some(status) => assert!(status.success(), "{status:?}"),
        }
    }
    assert_eq!(
        Some(daemon_pid(&state)),
        survivor,
        "the daemon left running is not the one serving"
    );
    assert!(serves(&state));
}

/// Hooks that fire together with no daemon running start one daemon between them, not one each.
#[cfg(unix)]
#[test]
fn hooks_that_fire_together_start_one_daemon() {
    use std::io::Write;
    use std::process::{Command as Std, Stdio};
    let t = tmp();
    let (state, db) = memory_state(&t);
    resident_settings(&t, &state, 30);
    let mut hooks: Vec<_> = (0..4)
        .map(|_| {
            Std::new(assert_cmd::cargo::cargo_bin!("footnote"))
                .env("FOOTNOTE_STATE_DIR", &state)
                .arg("hook")
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .unwrap()
        })
        .collect();
    for (i, hook) in hooks.iter_mut().enumerate() {
        let mut stdin = hook.stdin.take().unwrap();
        stdin
            .write_all(prompt_event(&format!("together-{i}")).as_bytes())
            .unwrap();
    }
    for mut hook in hooks {
        assert!(hook.wait().unwrap().success());
    }
    // The daemons the hooks started, by their command line (the hook passes this database path).
    let pattern = format!("{} serve --mcp --daemon", db.display());
    let daemons = || -> Vec<String> {
        let out = Std::new("pgrep").args(["-f", &pattern]).output().unwrap();
        String::from_utf8_lossy(&out.stdout)
            .split_whitespace()
            .map(str::to_string)
            .collect()
    };
    wait_for(10, "no daemon started", || serves(&state));
    let _stop: Vec<StartedElsewhere> = daemons().into_iter().map(StartedElsewhere).collect();
    wait_for(10, "more than one daemon kept running", || {
        daemons().len() == 1
    });
    assert_eq!(
        daemons(),
        vec![daemon_pid(&state)],
        "the daemon left running is not the one serving"
    );
}

/// A daemon started on purpose (no idle limit: a service, the logon task) still takes the socket over from one started on
/// demand, which then leaves once idle: a service that starts after a hook already started a daemon serves all the same.
#[cfg(unix)]
#[test]
fn a_daemon_started_on_purpose_takes_the_socket_from_one_started_on_demand() {
    let t = tmp();
    let (state, db) = memory_state(&t);
    let mut on_demand = start_daemon(&state, &db, Some(2));
    let first = on_demand.0.id().to_string();
    wait_for(10, "the daemon started on demand did not start", || {
        daemon_pid(&state) == first && serves(&state)
    });
    let mut service = start_daemon(&state, &db, None);
    let second = service.0.id().to_string();
    wait_for(
        10,
        "the daemon started on purpose did not take the socket",
        || daemon_pid(&state) == second,
    );
    assert!(serves(&state));
    let mut left = None;
    wait_for(
        20,
        "the daemon started on demand did not leave once idle",
        || {
            left = on_demand.0.try_wait().unwrap();
            left.is_some()
        },
    );
    assert!(
        service.0.try_wait().unwrap().is_none(),
        "the daemon started on purpose stopped"
    );
    assert!(serves(&state));
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
