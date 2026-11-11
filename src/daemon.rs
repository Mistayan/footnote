//! One shared, resident daemon per corpus, reachable by every agent.
//!
//! Transport is a local socket: a named pipe on Windows (`\\.\pipe\...`, local
//! only, owner-scoped) or a Unix domain socket elsewhere. There is no TCP port.
//! The first line on every connection is a token handshake read from a per-user
//! file, so a local process that guesses the endpoint still cannot talk to it.
//!
//! Agents never manage this process: their MCP entry points at `borg-knowledge
//! mcp`, which connects to the daemon and spawns it on demand. That is what makes
//! one warm corpus shared by Claude Code, Codex and Gemini at the same time.
use crate::mcp::{Shared, session_loop};
use anyhow::{Context, Result};
use interprocess::local_socket::{GenericNamespaced, ListenerOptions, Stream, prelude::*};
use std::{
    io::{BufRead, BufReader, Write},
    path::Path,
    sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    },
    time::{Duration, Instant},
};

/// Endpoint name derived from the corpus path, so separate databases never share
/// a daemon and a moved corpus gets its own.
pub fn endpoint_name(db: &Path) -> String {
    let canonical = std::fs::canonicalize(db).unwrap_or_else(|_| db.to_path_buf());
    let digest = crate::app::hash(canonical.to_string_lossy().as_bytes());
    format!("borg-knowledge-{}", &digest[..16])
}

fn endpoint_of(db: &Path) -> String {
    endpoint_name(db)
}

/// Run the daemon: accept many concurrent agents, one thread each.
pub fn run(shared: Shared) -> Result<()> {
    let endpoint = endpoint_of(&shared.db);
    let name = endpoint.as_str().to_ns_name::<GenericNamespaced>()?;
    let listener = ListenerOptions::new()
        .name(name)
        .create_sync()
        .with_context(|| {
            format!(
                "cannot create a daemon endpoint for {} (another daemon may already serve it)",
                shared.db.display()
            )
        })?;
    // Record the pid so operators (and tests) can stop an owned daemon without
    // killing every other borg-knowledge process on the machine.
    if let Ok(state) = crate::state::state_dir() {
        let _ = std::fs::create_dir_all(&state);
        let _ = std::fs::write(state.join("daemon.pid"), std::process::id().to_string());
    }
    let shared = Arc::new(shared);
    for connection in listener.incoming() {
        let stream = match connection {
            Ok(stream) => stream,
            Err(e) => {
                eprintln!("borg-knowledge daemon: accept failed: {e}");
                continue;
            }
        };
        let shared = Arc::clone(&shared);
        std::thread::spawn(move || {
            let mut reader = BufReader::new(&stream);
            let mut out = &stream;
            if let Err(e) = session_loop(&mut reader, &mut out, &shared, true) {
                // A rejected handshake or a dropped agent is routine, not fatal.
                eprintln!("borg-knowledge daemon: session ended: {e:#}");
            }
        });
    }
    Ok(())
}

/// Connect to this corpus's daemon. Never spawns a child process: a daemon
/// started by an agent would inherit the agent's stdout pipe on Windows and
/// keep it open after this process exits, hanging the agent. `install` registers
/// the daemon at logon instead; when it is absent, the caller serves stdio
/// in-process.
pub fn connect(db: &Path) -> Result<Stream> {
    let endpoint = endpoint_of(db);
    Ok(Stream::connect(
        endpoint.as_str().to_ns_name::<GenericNamespaced>()?,
    )?)
}

/// Stdio front-end for agents: use the shared daemon when it is running,
/// otherwise serve this session in-process.
///
/// The agent always speaks plain MCP on its stdin/stdout; the socket and the
/// token are invisible to it and to the user.
pub fn proxy(shared: &Shared) -> Result<()> {
    match connect(&shared.db) {
        Ok(stream) => proxy_over_stream(stream),
        Err(_) => {
            // No resident daemon: stay functional, just not shared.
            eprintln!(
                "borg-knowledge: no shared daemon for this corpus; serving in-process \
                 (run `borg-knowledge --db <DB> serve --mcp --daemon` or re-run install to share one)"
            );
            let stdin = std::io::stdin();
            let mut reader = BufReader::new(stdin.lock());
            let stdout = std::io::stdout();
            let mut out = stdout.lock();
            session_loop(&mut reader, &mut out, shared, false)
        }
    }
}

fn proxy_over_stream(mut stream: Stream) -> Result<()> {
    let token = crate::state::load_or_create_token()?;
    let handshake = serde_json::json!({"borg":{"token":token}});
    writeln!(stream, "{handshake}")?;
    stream.flush()?;

    let stream = Arc::new(stream);
    let requests = Arc::new(AtomicUsize::new(0));
    let responses = Arc::new(AtomicUsize::new(0));

    // Daemon -> agent.
    let reader_stream = Arc::clone(&stream);
    let sent_responses = Arc::clone(&responses);
    let _pump_out = std::thread::spawn(move || -> Result<()> {
        let mut reader = BufReader::new(&*reader_stream);
        let stdout = std::io::stdout();
        let mut out = stdout.lock();
        let mut line = Vec::new();
        loop {
            line.clear();
            if reader.read_until(b'\n', &mut line)? == 0 {
                break;
            }
            out.write_all(&line)?;
            out.flush()?;
            sent_responses.fetch_add(1, Ordering::Relaxed);
        }
        Ok(())
    });

    // Agent -> daemon.
    let writer_stream = Arc::clone(&stream);
    let sent_requests = Arc::clone(&requests);
    let stdin = std::io::stdin();
    let mut reader = BufReader::new(stdin.lock());
    let mut writer = &*writer_stream;
    let mut line = Vec::new();
    loop {
        line.clear();
        if reader.read_until(b'\n', &mut line)? == 0 {
            break;
        }
        if line.iter().all(u8::is_ascii_whitespace) {
            continue;
        }
        // Count requests (messages carrying an id) so we know when the last
        // response has been delivered before exiting on stdin EOF.
        if String::from_utf8_lossy(&line).contains("\"id\"") {
            sent_requests.fetch_add(1, Ordering::Relaxed);
        }
        writer.write_all(&line)?;
        writer.flush()?;
    }

    // Drain the last reply(s) so a closing agent does not lose its answer. The
    // daemon keeps the socket open until we go away, so this thread is not
    // joined: process exit ends it, which is also what releases the connection.
    let deadline = Instant::now() + Duration::from_secs(3);
    while Instant::now() < deadline
        && responses.load(Ordering::Relaxed) < requests.load(Ordering::Relaxed)
    {
        std::thread::sleep(Duration::from_millis(10));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::BufReader;

    fn shared(token: &str) -> Shared {
        let dir = std::env::temp_dir().join(format!("borg-handshake-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let audit = crate::audit::Audit::open(&dir.join("audit.jsonl"), None).unwrap();
        Shared::new(&dir.join("corpus.db"), Some(audit), Some(token.to_string()))
    }

    fn run(input: &str, token: &str) -> (Result<()>, String) {
        let shared = shared(token);
        let mut reader = BufReader::new(input.as_bytes());
        let mut out: Vec<u8> = Vec::new();
        let result = session_loop(&mut reader, &mut out, &shared, true);
        (result, String::from_utf8_lossy(&out).to_string())
    }

    #[test]
    fn a_correct_token_is_accepted_and_served() {
        let token = "a".repeat(64);
        let input = format!(
            "{{\"borg\":{{\"token\":\"{token}\"}}}}\n{}\n",
            r#"{"jsonrpc":"2.0","id":1,"method":"tools/list"}"#
        );
        let (result, out) = run(&input, &token);
        assert!(result.is_ok(), "{result:?}");
        assert!(out.contains("\"tools\""), "{out}");
    }

    #[test]
    fn a_wrong_token_is_rejected_before_any_tool_runs() {
        let token = "a".repeat(64);
        let wrong = "b".repeat(64);
        let input = format!(
            "{{\"borg\":{{\"token\":\"{wrong}\"}}}}\n{}\n",
            r#"{"jsonrpc":"2.0","id":1,"method":"tools/list"}"#
        );
        let (result, out) = run(&input, &token);
        assert!(result.is_err(), "wrong token accepted");
        assert!(out.is_empty(), "server replied before authenticating");
    }

    #[test]
    fn a_connection_that_skips_the_handshake_is_rejected() {
        let token = "a".repeat(64);
        let input = format!("{}\n", r#"{"jsonrpc":"2.0","id":1,"method":"tools/list"}"#);
        let (result, out) = run(&input, &token);
        assert!(result.is_err(), "unauthenticated connection accepted");
        assert!(out.is_empty());
    }
}
