//! Plug-and-play registration: point every detected agent at this corpus.
//!
//! Each agent's MCP entry runs `footnote --db <DB> mcp`, a thin stdio
//! front-end. The daemon, token and audit log are automatic, so the only thing
//! written here is "where is the corpus" — no secrets, no per-agent tuning.
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

const SERVER: &str = "footnote";

fn home() -> Result<PathBuf> {
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .context("cannot determine the home directory")
}

/// Normalise for config files: forward slashes avoid TOML/JSON escaping traps.
fn portable(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

fn command(db: &Path) -> Result<Value> {
    let exe = std::env::current_exe().context("locate this executable")?;
    Ok(json!({
        "command": portable(&exe),
        "args": ["--db", portable(db), "mcp"],
    }))
}

fn backup(path: &Path) -> Result<()> {
    if path.exists() {
        let mut backup_path = path.to_path_buf();
        let name = format!(
            "{}.{SERVER}-backup",
            path.file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_default()
        );
        backup_path.set_file_name(name);
        if !backup_path.exists() {
            std::fs::copy(path, &backup_path)?;
        }
    }
    Ok(())
}

fn write_json(path: &Path, entry: &Value, dry_run: bool) -> Result<&'static str> {
    merge_json(path, dry_run, |root| {
        let servers = root
            .entry("mcpServers".to_string())
            .or_insert_with(|| json!({}))
            .as_object_mut()
            .with_context(|| format!("{}: mcpServers is not an object", path.display()))?;
        if servers.get(SERVER).is_some() {
            return Ok(false);
        }
        servers.insert(SERVER.to_string(), entry.clone());
        Ok(true)
    })
}

/// Read a JSON object file (missing or empty: `{}`), let `change` edit it, and write it back only when it changed,
/// with a one-time backup and an atomic replace.
fn merge_json(
    path: &Path,
    dry_run: bool,
    change: impl FnOnce(&mut serde_json::Map<String, Value>) -> Result<bool>,
) -> Result<&'static str> {
    let stamp = file_stamp(path);
    let mut root: Value = if path.exists() {
        let raw =
            std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
        if raw.trim().is_empty() {
            json!({})
        } else {
            serde_json::from_str(&raw)
                .with_context(|| format!("{} is not valid JSON", path.display()))?
        }
    } else {
        json!({})
    };
    let object = root
        .as_object_mut()
        .with_context(|| format!("{} is not a JSON object", path.display()))?;
    if !change(object)? {
        return Ok("already registered");
    }
    if !dry_run {
        backup(path)?;
        if let Some(parent) = path.parent()
            && !parent.as_os_str().is_empty()
        {
            std::fs::create_dir_all(parent)?;
        }
        replace_atomically(
            path,
            &stamp,
            format!("{}\n", serde_json::to_string_pretty(&root)?),
        )?;
    }
    Ok("registered")
}

/// (modified time, length) of a file, to notice a concurrent writer.
fn file_stamp(path: &Path) -> Option<(std::time::SystemTime, u64)> {
    let meta = std::fs::metadata(path).ok()?;
    Some((meta.modified().ok()?, meta.len()))
}

/// Replace `path` through a temp file and a rename, so a crash never leaves a
/// half-written agent config. Agents such as Claude Code rewrite their own file
/// while running: if it changed since we read it, stop instead of overwriting.
fn replace_atomically(
    path: &Path,
    read_stamp: &Option<(std::time::SystemTime, u64)>,
    text: String,
) -> Result<()> {
    if &file_stamp(path) != read_stamp {
        bail!(
            "{} changed while it was being updated (the agent is probably running); close it and re-run install",
            path.display()
        );
    }
    let mut temp = path.to_path_buf();
    temp.set_file_name(format!(
        "{}.footnote-tmp",
        path.file_name()
            .map(|n| n.to_string_lossy())
            .unwrap_or_default()
    ));
    std::fs::write(&temp, text).with_context(|| format!("write {}", temp.display()))?;
    std::fs::rename(&temp, path).with_context(|| format!("replace {}", path.display()))
}

fn write_codex_toml(path: &Path, db: &Path, dry_run: bool) -> Result<&'static str> {
    codex_server(path, SERVER, db, dry_run)
}

fn codex_server(path: &Path, name: &str, db: &Path, dry_run: bool) -> Result<&'static str> {
    let exe = std::env::current_exe().context("locate this executable")?;
    let header = format!("[mcp_servers.{name}]");
    let block = format!(
        "\n{header}\ncommand = \"{}\"\nargs = [\"--db\", \"{}\", \"mcp\"]\n",
        portable(&exe),
        portable(db)
    );
    append_once(path, &header, &block, dry_run)
}

/// Append `block` to a text file unless `marker` is already in it (creating the file and its folder if needed).
fn append_once(path: &Path, marker: &str, block: &str, dry_run: bool) -> Result<&'static str> {
    let existing = if path.exists() {
        std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?
    } else {
        String::new()
    };
    if existing.contains(marker) {
        return Ok("already registered");
    }
    if !dry_run {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        backup(path)?;
        let mut text = existing.clone();
        if !text.is_empty() && !text.ends_with('\n') {
            text.push('\n');
        }
        text.push_str(block);
        std::fs::write(path, text)?;
    }
    Ok("registered")
}

/// Register a logon task that keeps one daemon per corpus running, then start it.
///
/// Task Scheduler owns the process, so the daemon inherits no agent handles —
/// the reason the proxy must never spawn it itself.
fn register_daemon(db: &Path, dry_run: bool) -> Value {
    let endpoint = crate::daemon::endpoint_name(db);
    let task = format!("footnote-{}", endpoint.trim_start_matches("footnote-"));
    #[cfg(windows)]
    {
        let exe = match std::env::current_exe() {
            Ok(exe) => exe,
            Err(e) => return json!({"task": task, "status": format!("error: {e}")}),
        };
        let command = format!(
            "\"{}\" --db \"{}\" serve --mcp --daemon",
            portable(&exe),
            portable(db)
        );
        if dry_run {
            return json!({"task": task, "status": "dry-run", "command": command});
        }
        let created = std::process::Command::new("schtasks")
            .args([
                "/create", "/f", "/tn", &task, "/sc", "onlogon", "/tr", &command,
            ])
            .output();
        match created {
            Ok(out) if out.status.success() => {
                let _ = std::process::Command::new("schtasks")
                    .args(["/run", "/tn", &task])
                    .output();
                json!({
                    "task": task,
                    "status": "registered at logon and started now",
                    "command": command,
                })
            }
            Ok(out) => json!({
                "task": task,
                "status": "not registered",
                "detail": String::from_utf8_lossy(&out.stderr).trim().to_string(),
                "command": command,
            }),
            Err(e) => json!({"task": task, "status": format!("error: {e}"), "command": command}),
        }
    }
    #[cfg(not(windows))]
    {
        json!({
            "task": task,
            "status": "manual on this platform",
            "hint": "run `footnote --db <DB> serve --mcp --daemon` from your session manager",
        })
    }
}

/// Register the corpus in Claude Code, Codex CLI and Gemini CLI when present.
pub fn run(db: &Option<PathBuf>, dry_run: bool) -> Result<Value> {
    let Some(db) = db.as_deref() else {
        bail!("--db is required: install registers a specific corpus");
    };
    let db = std::path::absolute(db).unwrap_or_else(|_| db.to_path_buf());
    if !db.exists() {
        bail!(
            "corpus database {} does not exist; index a root first",
            db.display()
        );
    }
    let home = home()?;
    let entry = command(&db)?;
    let mut report: Vec<Value> = Vec::new();

    let claude = home.join(".claude.json");
    let codex = home.join(".codex/config.toml");
    let gemini = home.join(".gemini/settings.json");

    let targets: Vec<(&str, PathBuf)> = vec![
        ("claude-code", claude),
        ("codex", codex),
        ("gemini-cli", gemini),
    ];
    for (agent, path) in targets {
        let detected = if agent == "claude-code" {
            path.exists() || home.join(".claude").exists()
        } else {
            path.parent().map(|p| p.exists()).unwrap_or(false)
        };
        if !detected {
            report.push(json!({"agent": agent, "status": "not detected", "path": portable(&path)}));
            continue;
        }
        let status = if agent == "codex" {
            write_codex_toml(&path, &db, dry_run)?
        } else {
            write_json(&path, &entry, dry_run)?
        };
        report.push(json!({"agent": agent, "status": status, "path": portable(&path)}));
    }

    Ok(json!({
        "dry_run": dry_run,
        "corpus": portable(&db),
        "entry": entry,
        "targets": report,
        "daemon": register_daemon(&db, dry_run),
        "note": "each agent runs `footnote --db <DB> mcp`; the daemon, token and audit log are automatic. An entry named `borg` from before the rename still points at the old executable: delete it from the agent config",
    }))
}

const MEMORY_SERVER: &str = "footnote-memory";
const HOOK_MARK: &str = "memory_hook.py";

/// Add an MCP server entry under `mcpServers`, leaving an existing entry of that name untouched.
fn add_server(path: &Path, name: &str, entry: &Value, dry_run: bool) -> Result<&'static str> {
    merge_json(path, dry_run, |root| {
        let servers = root
            .entry("mcpServers".to_string())
            .or_insert_with(|| json!({}))
            .as_object_mut()
            .with_context(|| format!("{}: mcpServers is not an object", path.display()))?;
        if servers.contains_key(name) {
            return Ok(false);
        }
        servers.insert(name.to_string(), entry.clone());
        Ok(true)
    })
}

/// Add the memory hook command to every listed event of a Claude-format `hooks` object, once.
fn add_hooks(
    path: &Path,
    events: &[(&str, u64)],
    command: &str,
    dry_run: bool,
) -> Result<&'static str> {
    merge_json(path, dry_run, |root| {
        let hooks = root
            .entry("hooks".to_string())
            .or_insert_with(|| json!({}))
            .as_object_mut()
            .with_context(|| format!("{}: hooks is not an object", path.display()))?;
        let mut changed = false;
        for (event, timeout) in events {
            let list = hooks
                .entry(event.to_string())
                .or_insert_with(|| json!([]))
                .as_array_mut()
                .with_context(|| format!("{}: hooks.{event} is not an array", path.display()))?;
            if !list.iter().any(|g| g.to_string().contains(HOOK_MARK)) {
                list.push(
                    json!({"hooks": [{"type": "command", "command": command, "timeout": timeout}]}),
                );
                changed = true;
            }
        }
        Ok(changed)
    })
}

/// Quote a path only when it must be: an unquoted command runs the same under bash (Claude Code), PowerShell (Grok) and cmd.
fn shell_word(path: &Path, warnings: &mut Vec<String>) -> String {
    let p = portable(path);
    if p.contains(' ') {
        warnings.push(format!(
            "{p} contains a space: the hook command is quoted for bash; Grok runs hooks under PowerShell, so set GROK_SHELL=bash for it"
        ));
        format!("\"{p}\"")
    } else {
        p
    }
}

/// `install --memory`: one agent memory database for every detected agent, its MCP server, the memory hook and a
/// /remember command. Claude Code's files also serve Grok, which reads ~/.claude.json and ~/.claude/settings.json.
pub fn memory(dry_run: bool) -> Result<Value> {
    let home = home()?;
    let state = crate::state::state_dir()?;
    let db = state.join("memory.db");
    let exe = std::env::current_exe().context("locate this executable")?;
    let python = crate::semantic::python();
    let script = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tools")
        .join(HOOK_MARK);
    for (what, p) in [("Python interpreter", &python), ("memory hook", &script)] {
        if !p.is_file() {
            bail!(
                "{what} not found at {} (set FOOTNOTE_PYTHON to a Python 3.10+ interpreter)",
                p.display()
            );
        }
    }
    let mut warnings = Vec::new();
    let command = format!(
        "{} -I {}",
        shell_word(&python, &mut warnings),
        shell_word(&script, &mut warnings)
    );
    let entry = json!({"command": portable(&exe), "args": ["--db", portable(&db), "mcp"]});
    // The same three events everywhere: pack at start, recall per prompt, and at Stop the request that makes the agent save
    // its memories (Codex and DeepSeek's bridge have no compaction or end-of-session event, and none is needed).
    let events = [("SessionStart", 15), ("UserPromptSubmit", 10), ("Stop", 5)];
    // /remember is the save request itself: the agent writes its memories with the footnote_remember tool.
    let remember = "Footnote memory: save what is worth remembering from this conversation with the footnote_remember tool (MCP server footnote-memory). Each memory is one self-contained sentence with absolute dates. kind: preference (how the user likes to work), fact (a decision, convention or date), fix (a problem, its cause and the fix) or session (what was achieved, what is left). scope: \"global\" for what applies everywhere, otherwise this project's repository folder name in lower case. observed_at: today's date. Skip what is already remembered or readable in the code. Then confirm in one short line.\n";
    let mut report: Vec<Value> = Vec::new();
    let mut add =
        |agent: &str, what: &str, path: &Path, status: Result<&'static str>| -> Result<()> {
            report.push(
                json!({"agent": agent, "what": what, "path": portable(path), "status": status?}),
            );
            Ok(())
        };

    if !dry_run {
        crate::state::ensure_private_dir(&state)?;
        if !db.exists() {
            drop(crate::app::open(&db, true)?); // empty memory database, so read tools work before the first memory
        }
    }
    let settings = state.join("memory.json");
    let defaults = json!({"footnote": portable(&exe), "db": portable(&db)});
    add(
        "all",
        "settings",
        &settings,
        merge_json(&settings, dry_run, |root| {
            let mut changed = false;
            for (k, v) in defaults.as_object().into_iter().flatten() {
                if !root.contains_key(k) {
                    root.insert(k.clone(), v.clone());
                    changed = true;
                }
            }
            Ok(changed)
        }),
    )?;

    let claude = home.join(".claude");
    let grok = home.join(".grok");
    if claude.exists() || grok.exists() {
        let agent = match (claude.exists(), grok.exists()) {
            (true, true) => "claude-code + grok",
            (true, false) => "claude-code",
            _ => "grok (through Claude Code files)",
        };
        let mcp = home.join(".claude.json");
        add(
            agent,
            "mcp server",
            &mcp,
            add_server(&mcp, MEMORY_SERVER, &entry, dry_run),
        )?;
        let hooks = claude.join("settings.json");
        add(
            agent,
            "hooks",
            &hooks,
            add_hooks(&hooks, &events, &command, dry_run),
        )?;
        let cmd = claude.join("commands").join("remember.md");
        add(
            agent,
            "/remember",
            &cmd,
            append_once(&cmd, "Footnote", remember, dry_run),
        )?;
    }
    if grok.exists() {
        // Grok lists only its own config.toml servers; same TOML keys as Codex. Its hooks come from ~/.claude/settings.json.
        let config = grok.join("config.toml");
        add(
            "grok",
            "mcp server",
            &config,
            codex_server(&config, MEMORY_SERVER, &db, dry_run),
        )?;
    }
    let codex = home.join(".codex");
    if codex.exists() {
        let config = codex.join("config.toml");
        add(
            "codex",
            "mcp server",
            &config,
            codex_server(&config, MEMORY_SERVER, &db, dry_run),
        )?;
        let hooks = codex.join("hooks.json");
        add(
            "codex",
            "hooks",
            &hooks,
            add_hooks(&hooks, &events, &command, dry_run),
        )?;
        let prompt = codex.join("prompts").join("remember.md");
        add(
            "codex",
            "/remember",
            &prompt,
            append_once(&prompt, "Footnote", remember, dry_run),
        )?;
    }
    let patch = home.join(".dsh/profiles/desktop/cordis.patch.yml");
    if patch.exists() {
        // DeepSeek Harness: its Claude Code hooks bridge runs a dedicated hooks file (not all of Claude's hooks),
        // and an mcp-client entry serves the memory database.
        // The bridge package itself (@deepseek-ai/dsh-hooks-claude-code, pinned to the app's version) is installed with
        // DeepSeek's plugin manager.
        let hooks = home.join(".dsh").join("footnote-memory-hooks.json");
        add(
            "deepseek-harness",
            "hooks",
            &hooks,
            add_hooks(&hooks, &events, &command, dry_run),
        )?;
        let block = format!(
            "# Footnote agent memory (footnote install --memory)\n- insert:\n    - id: {MEMORY_SERVER}-hooks\n      name: \"@deepseek-ai/dsh-hooks-claude-code\"\n      config:\n        configPath: \"{}\"\n    - id: {MEMORY_SERVER}-mcp\n      name: \"@deepseek-ai/dsh-mcp-client\"\n      config:\n        transport: stdio\n        serverName: {MEMORY_SERVER}\n        command: \"{}\"\n        args: [\"--db\", \"{}\", \"mcp\"]\n        env: {{}}\n        cwd: \"{}\"\n        toolCallTimeoutMs: 60000\n        closeTimeoutMs: 5000\n        expandTemplates: false\n        failOnStartupError: false\n",
            portable(&hooks),
            portable(&exe),
            portable(&db),
            portable(&home)
        );
        let marker = format!("id: {MEMORY_SERVER}-hooks");
        add(
            "deepseek-harness",
            "hooks bridge + mcp server",
            &patch,
            append_once(&patch, &marker, &block, dry_run),
        )?;
    }
    let gemini = home.join(".gemini/settings.json");
    if gemini.parent().is_some_and(Path::exists) {
        add(
            "gemini-cli",
            "mcp server",
            &gemini,
            add_server(&gemini, MEMORY_SERVER, &entry, dry_run),
        )?;
    }
    Ok(json!({
        "dry_run": dry_run,
        "memory_db": portable(&db),
        "hook": command,
        "targets": report,
        "warnings": warnings,
        "note": "restart each agent to load the hooks; Grok asks once to trust a folder before it runs hooks. Extraction uses your Claude Code CLI by default; change the extractor or list sensitive projects in the settings file",
    }))
}
