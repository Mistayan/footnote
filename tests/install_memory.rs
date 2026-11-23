use assert_cmd::Command;
use serde_json::{Value, json};
use std::{fs, path::Path};

fn install(home: &Path, state: &Path, python: &Path, dry_run: bool) -> Value {
    let mut c = Command::new(assert_cmd::cargo::cargo_bin!("footnote"));
    c.args(["install", "--memory"])
        .env("USERPROFILE", home)
        .env("HOME", home)
        .env("FOOTNOTE_STATE_DIR", state)
        .env("FOOTNOTE_PYTHON", python);
    if dry_run {
        c.arg("--dry-run");
    }
    serde_json::from_slice(&c.assert().success().get_output().stdout).unwrap()
}
fn read(p: &Path) -> Value {
    serde_json::from_str(&fs::read_to_string(p).unwrap()).unwrap()
}

#[test]
fn memory_install_registers_every_detected_agent_once_and_keeps_existing_config() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    let python = t.path().join("python.exe");
    // Deliberately absent: installing memory must not depend on Python.
    for d in [".claude", ".codex", ".grok", ".dsh/profiles/desktop"] {
        fs::create_dir_all(home.join(d)).unwrap();
    }
    let existing = json!({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "other-tool hook"}]}]}});
    fs::write(home.join(".claude/settings.json"), existing.to_string()).unwrap();
    fs::write(home.join(".codex/config.toml"), "model = \"gpt\"\n").unwrap();
    fs::write(
        home.join(".dsh/profiles/desktop/cordis.patch.yml"),
        "- id: ui-theme\n  config:\n    fontSize: 12\n",
    )
    .unwrap();

    // A dry run writes nothing.
    install(&home, &state, &python, true);
    assert_eq!(read(&home.join(".claude/settings.json")), existing);
    assert!(!state.join("memory.db").exists());

    let first = install(&home, &state, &python, false);
    assert!(
        first["targets"]
            .as_array()
            .unwrap()
            .iter()
            .all(|t| t["status"] == "registered"),
        "{first}"
    );
    assert!(state.join("memory.db").exists());

    // Claude Code (and Grok, which reads these files): MCP server, hooks next to the existing ones, /remember.
    let claude = read(&home.join(".claude.json"));
    assert_eq!(claude["mcpServers"]["footnote-memory"]["args"][2], "mcp");
    let settings = read(&home.join(".claude/settings.json"));
    let starts = settings["hooks"]["SessionStart"].as_array().unwrap();
    assert_eq!(starts.len(), 2);
    assert_eq!(starts[0]["hooks"][0]["command"], "other-tool hook");
    assert!(
        starts[1]["hooks"][0]["command"]
            .as_str()
            .unwrap()
            .ends_with(" hook")
    );
    for event in ["UserPromptSubmit", "Stop"] {
        assert!(
            settings["hooks"][event].to_string().contains(" hook"),
            "{event}"
        );
    }
    assert!(
        fs::read_to_string(home.join(".claude/commands/remember.md"))
            .unwrap()
            .contains("footnote_remember")
    );
    assert!(
        settings["hooks"].get("PreCompact").is_none(),
        "no extraction events any more"
    );

    // Codex: TOML server appended after the user's own keys, hooks for the events Codex has.
    let toml = fs::read_to_string(home.join(".codex/config.toml")).unwrap();
    assert!(toml.starts_with("model = \"gpt\"") && toml.contains("[mcp_servers.footnote-memory]"));
    let codex = read(&home.join(".codex/hooks.json"));
    assert!(codex["hooks"]["Stop"].to_string().contains(" hook"));
    assert!(codex["hooks"].get("PreCompact").is_none());

    assert!(
        fs::read_to_string(home.join(".grok/config.toml"))
            .unwrap()
            .contains("[mcp_servers.footnote-memory]")
    );

    // DeepSeek Harness: dedicated hooks file and an insert patch for its hooks bridge and MCP client.
    let patch = fs::read_to_string(home.join(".dsh/profiles/desktop/cordis.patch.yml")).unwrap();
    assert!(patch.starts_with("- id: ui-theme"));
    assert!(
        patch.contains("@deepseek-ai/dsh-hooks-claude-code")
            && patch.contains("@deepseek-ai/dsh-mcp-client")
    );
    let dsh = read(&home.join(".dsh/footnote-memory-hooks.json"));
    assert!(dsh["hooks"]["SessionStart"].to_string().contains(" hook"));
    assert!(
        dsh["hooks"].get("SessionEnd").is_none(),
        "the DeepSeek bridge drops SessionEnd"
    );

    // Settings point the hook at this binary and database.
    let s = read(&state.join("memory.json"));
    assert!(s["db"].as_str().unwrap().ends_with("memory.db"));

    // A second run changes nothing.
    let before = fs::read_to_string(home.join(".claude/settings.json")).unwrap();
    let second = install(&home, &state, &python, false);
    assert!(
        second["targets"]
            .as_array()
            .unwrap()
            .iter()
            .all(|t| t["status"] == "already registered"),
        "{second}"
    );
    assert_eq!(
        fs::read_to_string(home.join(".claude/settings.json")).unwrap(),
        before
    );
    assert_eq!(
        fs::read_to_string(home.join(".dsh/profiles/desktop/cordis.patch.yml"))
            .unwrap()
            .matches("id: footnote-memory-hooks")
            .count(),
        1
    );
}

#[test]
fn memory_install_migrates_python_hooks_without_replacing_other_hooks_or_metadata() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    fs::create_dir_all(home.join(".codex")).unwrap();
    let path = home.join(".codex/hooks.json");
    let existing = json!({"custom": true, "hooks": {"Stop": [{"matcher": "existing", "hooks": [
        {"type": "command", "command": "other-tool hook", "timeout": 7},
        {"type": "command", "command": "python -I /old/memory_hook.py", "command_windows": "python -I C:/old/memory_hook.py", "timeout": 5, "statusMessage": "Memory"}
    ]}]}});
    fs::write(&path, existing.to_string()).unwrap();
    let python = t.path().join("not-installed-python");
    install(&home, &state, &python, true);
    assert_eq!(read(&path), existing);
    let report = install(&home, &state, &python, false);
    let migrated = read(&path);
    assert_eq!(migrated["custom"], true);
    assert_eq!(migrated["hooks"]["Stop"].as_array().unwrap().len(), 1);
    let group = &migrated["hooks"]["Stop"][0];
    assert_eq!(group["matcher"], "existing");
    assert_eq!(group["hooks"][0], existing["hooks"]["Stop"][0]["hooks"][0]);
    assert_eq!(group["hooks"][1]["command"], report["hook"]);
    assert!(!migrated.to_string().contains("memory_hook.py"));
    assert_eq!(group["hooks"][1]["timeout"], 5);
    assert_eq!(group["hooks"][1]["statusMessage"], "Memory");
    assert_eq!(
        read(&home.join(".codex/hooks.json.footnote-backup")),
        existing
    );
    let before = fs::read(&path).unwrap();
    install(&home, &state, &python, false);
    assert_eq!(fs::read(&path).unwrap(), before);
}

#[test]
fn memory_uninstall_removes_only_what_install_added_and_keeps_memories() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    let python = t.path().join("python.exe");
    for d in [".claude", ".codex", ".grok", ".dsh/profiles/desktop"] {
        fs::create_dir_all(home.join(d)).unwrap();
    }
    let existing = json!({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "other-tool hook"}]}]}});
    fs::write(home.join(".claude/settings.json"), existing.to_string()).unwrap();
    let toml = "model = \"gpt\"\n\n[mcp_servers.other]\ncommand = \"other\"\n";
    fs::write(home.join(".codex/config.toml"), toml).unwrap();
    let patch = "- id: ui-theme\n  config:\n    fontSize: 12\n";
    fs::write(home.join(".dsh/profiles/desktop/cordis.patch.yml"), patch).unwrap();
    install(&home, &state, &python, false);

    let uninstall = |dry_run: bool| -> Value {
        let mut c = Command::new(assert_cmd::cargo::cargo_bin!("footnote"));
        c.args(["uninstall", "--memory"])
            .env("USERPROFILE", &home)
            .env("HOME", &home)
            .env("FOOTNOTE_STATE_DIR", &state);
        if dry_run {
            c.arg("--dry-run");
        }
        serde_json::from_slice(&c.assert().success().get_output().stdout).unwrap()
    };
    let status = || -> Value {
        let out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
            .arg("status")
            .env("USERPROFILE", &home)
            .env("HOME", &home)
            .env("FOOTNOTE_STATE_DIR", &state)
            .output()
            .unwrap();
        serde_json::from_slice(&out.stdout).unwrap()
    };
    let registered = |s: &Value| -> Vec<bool> {
        s["products"]["memory"]["agents"]
            .as_array()
            .unwrap()
            .iter()
            .flat_map(|a| {
                [
                    a["mcp_server"].as_bool().unwrap(),
                    a["hooks"].as_bool().unwrap(),
                ]
            })
            .collect()
    };
    let before = status();
    assert_eq!(before["products"]["memory"]["memories"], 0, "{before}");
    assert_eq!(
        before["products"]["code"]["built"],
        cfg!(feature = "code"),
        "{before}"
    );
    assert!(registered(&before).iter().all(|r| *r), "{before}");
    // A dry run reports and changes nothing.
    let installed = fs::read_to_string(home.join(".claude/settings.json")).unwrap();
    assert!(
        uninstall(true)["targets"]
            .as_array()
            .unwrap()
            .iter()
            .any(|t| t["status"] == "removed")
    );
    assert_eq!(
        fs::read_to_string(home.join(".claude/settings.json")).unwrap(),
        installed
    );

    let report = uninstall(false);
    assert!(
        report["kept"].as_str().unwrap().contains("memory.db"),
        "{report}"
    );
    // Other tools' entries survive; ours are gone everywhere.
    assert_eq!(read(&home.join(".claude/settings.json")), existing);
    assert!(
        read(&home.join(".claude.json"))["mcpServers"]
            .get("footnote-memory")
            .is_none()
    );
    assert_eq!(
        fs::read_to_string(home.join(".codex/config.toml")).unwrap(),
        toml
    );
    assert!(
        !fs::read_to_string(home.join(".grok/config.toml"))
            .unwrap_or_default()
            .contains("footnote-memory")
    );
    assert_eq!(
        fs::read_to_string(home.join(".dsh/profiles/desktop/cordis.patch.yml")).unwrap(),
        patch
    );
    assert!(!home.join(".dsh/footnote-memory-hooks.json").exists());
    assert!(!home.join(".claude/commands/remember.md").exists());
    assert!(state.join("memory.db").exists() && state.join("memory.json").exists());

    let after = status();
    assert!(registered(&after).iter().all(|r| !*r), "{after}");
    // Twice is harmless.
    let again = uninstall(false);
    assert!(
        again["targets"]
            .as_array()
            .unwrap()
            .iter()
            .all(|t| t["status"] == "not present"),
        "{again}"
    );
}

#[test]
fn antigravity_memory_install_status_and_uninstall_preserve_existing_config() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    let python = t.path().join("python.exe");
    fs::create_dir_all(home.join(".gemini/config")).unwrap();
    let existing_mcp = json!({"mcpServers": {"playwright": {"command": "npx", "args": ["-y", "@playwright/mcp"]}}});
    fs::write(
        home.join(".gemini/config/mcp_config.json"),
        existing_mcp.to_string(),
    )
    .unwrap();
    let existing_hooks = json!({"lint": {"Stop": [{"type": "command", "command": "lint.sh"}]}});
    fs::write(
        home.join(".gemini/config/hooks.json"),
        existing_hooks.to_string(),
    )
    .unwrap();

    let gemini_settings = home.join(".gemini/settings.json");
    let old_settings = json!({
        "mcpServers": {
            "keep": {"command": "keep"},
            "footnote": {"command": "footnote", "args": ["--db", "library.db", "mcp"]},
            "footnote-memory": {"command": "footnote", "args": ["--db", "memory.db", "mcp"]}
        },
        "hooks": {
            "BeforeAgent": [{"matcher": "*", "hooks": [
                {"type": "command", "command": "footnote hook", "timeout": 10000},
                {"type": "command", "command": "keep.sh"}
            ]}]
        },
        "other": true
    });
    let original = old_settings.to_string();
    fs::write(&gemini_settings, &original).unwrap();

    let first = install(&home, &state, &python, false);
    assert_eq!(fs::read_to_string(&gemini_settings).unwrap(), original);
    assert!(
        first["targets"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|t| t["agent"] == "antigravity")
            .all(|t| t["status"] == "registered"),
        "{first}"
    );

    let mcp = read(&home.join(".gemini/config/mcp_config.json"));
    assert_eq!(
        mcp["mcpServers"]["playwright"],
        existing_mcp["mcpServers"]["playwright"]
    );
    assert_eq!(mcp["mcpServers"]["footnote-memory"]["args"][2], "mcp");

    let hooks = read(&home.join(".gemini/config/hooks.json"));
    assert_eq!(hooks["lint"], existing_hooks["lint"]);
    for ev in ["SessionStart", "PreInvocation", "Stop"] {
        assert!(
            hooks["footnote-memory"][ev][0]["command"]
                .as_str()
                .unwrap()
                .ends_with(" hook"),
            "{ev}: {hooks}"
        );
    }

    let skill = fs::read_to_string(home.join(".gemini/config/skills/remember/SKILL.md")).unwrap();
    assert!(skill.starts_with("---\nname: remember\n") && skill.contains("footnote_remember"));

    let status_out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .arg("status")
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .env("FOOTNOTE_STATE_DIR", &state)
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let status: Value = serde_json::from_slice(&status_out).unwrap();
    let agy = status["products"]["memory"]["agents"]
        .as_array()
        .unwrap()
        .iter()
        .find(|a| a["agent"] == "antigravity")
        .unwrap();
    assert_eq!(
        (agy["mcp_server"].as_bool(), agy["hooks"].as_bool()),
        (Some(true), Some(true))
    );
    assert!(
        status["products"]["memory"]["agents"]
            .as_array()
            .unwrap()
            .iter()
            .all(|a| a["agent"] != "gemini-cli")
    );

    // Second run is idempotent.
    let second = install(&home, &state, &python, false);
    assert!(
        second["targets"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|t| t["agent"] == "antigravity")
            .all(|t| t["status"] == "already registered"),
        "{second}"
    );

    // Uninstall removes only Footnote's entries, preserving existing servers and hooks.
    Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .args(["uninstall", "--memory"])
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .env("FOOTNOTE_STATE_DIR", &state)
        .assert()
        .success();
    assert_eq!(
        read(&home.join(".gemini/config/mcp_config.json")),
        existing_mcp
    );
    assert_eq!(
        read(&home.join(".gemini/config/hooks.json")),
        existing_hooks
    );
    assert!(
        !home
            .join(".gemini/config/skills/remember/SKILL.md")
            .exists()
    );
    assert_eq!(
        read(&gemini_settings),
        json!({
            "mcpServers": {"keep": {"command": "keep"}},
            "hooks": {"BeforeAgent": [{"matcher": "*", "hooks": [{"type": "command", "command": "keep.sh"}]}]},
            "other": true
        })
    );
}

#[test]
fn t3_code_antigravity_provider_dir_is_installed_reported_and_uninstalled() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    let python = t.path().join("python.exe");
    let t3_cfg = home.join(".t3/userdata/providers/antigravity/abc123/config");
    fs::create_dir_all(&t3_cfg).unwrap();
    let existing_mcp =
        json!({"mcpServers": {"cloudflare": {"url": "https://mcp.cloudflare.com/mcp"}}});
    fs::write(t3_cfg.join("mcp_config.json"), existing_mcp.to_string()).unwrap();

    let first = install(&home, &state, &python, false);
    assert!(
        first["targets"]
            .as_array()
            .unwrap()
            .iter()
            .filter(|t| t["agent"] == "antigravity (t3-code)")
            .all(|t| t["status"] == "registered"),
        "{first}"
    );

    let mcp = read(&t3_cfg.join("mcp_config.json"));
    assert_eq!(
        mcp["mcpServers"]["cloudflare"],
        existing_mcp["mcpServers"]["cloudflare"]
    );
    assert_eq!(mcp["mcpServers"]["footnote-memory"]["args"][2], "mcp");

    let hooks = read(&t3_cfg.join("hooks.json"));
    for ev in ["SessionStart", "PreInvocation", "Stop"] {
        assert!(
            hooks["footnote-memory"][ev][0]["command"]
                .as_str()
                .unwrap()
                .ends_with(" hook"),
            "{ev}: {hooks}"
        );
    }

    let status_out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .arg("status")
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .env("FOOTNOTE_STATE_DIR", &state)
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let status: Value = serde_json::from_slice(&status_out).unwrap();
    let agy = status["products"]["memory"]["agents"]
        .as_array()
        .unwrap()
        .iter()
        .find(|a| a["agent"] == "antigravity (t3-code)")
        .unwrap();
    assert_eq!(
        (agy["mcp_server"].as_bool(), agy["hooks"].as_bool()),
        (Some(true), Some(true))
    );

    // Uninstall removes only Footnote's entries, keeping cloudflare intact.
    Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .args(["uninstall", "--memory"])
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .env("FOOTNOTE_STATE_DIR", &state)
        .assert()
        .success();
    assert_eq!(read(&t3_cfg.join("mcp_config.json")), existing_mcp);
    assert_eq!(read(&t3_cfg.join("hooks.json")), json!({}));
}

#[test]
fn bare_install_wires_both_memory_and_lean_by_default() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    let t3_cfg = home.join(".t3/userdata/providers/antigravity/abc123/config");
    fs::create_dir_all(&t3_cfg).unwrap();
    fs::create_dir_all(home.join(".claude")).unwrap();

    let out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .arg("install")
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .env("FOOTNOTE_STATE_DIR", &state)
        .assert()
        .success()
        .get_output()
        .stdout
        .clone();
    let v: Value = serde_json::from_slice(&out).unwrap();
    assert!(v.get("memory_db").is_some(), "{v}");
    assert!(v.get("lean").is_some(), "{v}");

    let t3_hooks = read(&t3_cfg.join("hooks.json"));
    assert!(t3_hooks.get("footnote-memory").is_some(), "{t3_hooks}");
    assert!(t3_hooks.get("footnote-lean").is_some(), "{t3_hooks}");
    let t3_mcp = read(&t3_cfg.join("mcp_config.json"));
    assert_eq!(t3_mcp["mcpServers"]["footnote-memory"]["args"][2], "mcp");
}

#[test]
fn install_replaces_and_uninstall_removes_docker_daemon_memory_hooks() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    let claude = home.join(".claude");
    fs::create_dir_all(&claude).unwrap();
    let path = claude.join("settings.json");
    let docker_hook = |cmd: &str, timeout: u64| json!({"hooks": [{"type": "command", "command": cmd, "timeout": timeout}]});
    let other = json!({"type": "command", "command": "footnote-lint", "timeout": 5});
    let non_docker = json!({
        "type": "command",
        "command": "wrapper exec -i footnote footnote hook",
        "timeout": 5
    });
    let win_quoted = "\"C:/Program Files/Docker/Docker/resources/bin/docker.exe\" exec -i footnote footnote hook";
    let linux_docker = "/usr/bin/docker exec -i footnote-me footnote hook";
    let win_plain = "C:/Users/me/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe exec -i footnote footnote hook";
    let docker_settings = json!({"hooks": {
        "SessionStart": [docker_hook(win_quoted, 15)],
        "UserPromptSubmit": [docker_hook(linux_docker, 10)],
        "Stop": [docker_hook(win_plain, 5), {"hooks": [other.clone(), non_docker.clone()]}]
    }})
    .to_string();

    // 1. Uninstall directly removes Docker hooks without a prior native install, leaving non-Docker hooks alone.
    fs::write(&path, &docker_settings).unwrap();
    Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
        .args(["uninstall", "--memory"])
        .env("USERPROFILE", &home)
        .env("HOME", &home)
        .env("FOOTNOTE_STATE_DIR", &state)
        .assert()
        .success();
    let settings = read(&path);
    assert_eq!(
        settings["hooks"],
        json!({"Stop": [{"hooks": [other.clone(), non_docker.clone()]}]}),
        "{settings}"
    );

    // 2. Install replaces Docker hooks in place with the native hook (no double hooks), keeping other hooks.
    fs::write(&path, &docker_settings).unwrap();
    let python = t.path().join("python.exe");
    let report = install(&home, &state, &python, false);
    let settings = read(&path);
    for event in ["SessionStart", "UserPromptSubmit", "Stop"] {
        let commands: Vec<&str> = settings["hooks"][event]
            .as_array()
            .unwrap()
            .iter()
            .flat_map(|g| g["hooks"].as_array().unwrap())
            .filter_map(|h| h["command"].as_str())
            .filter(|c| !c.contains("footnote-lint") && !c.starts_with("wrapper "))
            .collect();
        assert_eq!(
            commands,
            [report["hook"].as_str().unwrap()],
            "{event}: {settings}"
        );
    }
    assert!(settings.to_string().contains("footnote-lint"), "{settings}");
    assert!(settings.to_string().contains("wrapper exec"), "{settings}");
}

/// #578: a Claude Code profile kept with `CLAUDE_CONFIG_DIR` (`~/.claude-2`) gets the same hooks and MCP server as the
/// default one, found even when the installer runs without the variable; a `~/.claude*` folder with no sessions is left
/// alone, and uninstall clears both profiles.
#[test]
fn claude_code_profiles_beside_the_default_are_installed_and_uninstalled() {
    let t = tempfile::tempdir().unwrap();
    let (home, state) = (t.path().join("home"), t.path().join("state"));
    for d in [".claude", ".claude-2/projects", ".claude-old"] {
        fs::create_dir_all(home.join(d)).unwrap();
    }
    fs::write(home.join(".claude-2/.claude.json"), "{}").unwrap();
    fs::write(home.join(".claude-old/.claude.json"), "{}").unwrap();
    let run = |args: &[&str]| -> Value {
        let out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
            .args(args)
            .env("USERPROFILE", &home)
            .env("HOME", &home)
            .env("FOOTNOTE_STATE_DIR", &state)
            .env_remove("CLAUDE_CONFIG_DIR")
            .assert()
            .success()
            .get_output()
            .stdout
            .clone();
        serde_json::from_slice(&out).unwrap()
    };
    let installed = run(&["install", "--memory", "--lean"]);
    let profile = home.join(".claude-2");
    let mcp = read(&profile.join(".claude.json"));
    assert_eq!(
        mcp["mcpServers"]["footnote-memory"]["args"][2], "mcp",
        "{installed}"
    );
    let settings = read(&profile.join("settings.json"));
    for event in ["SessionStart", "UserPromptSubmit", "Stop"] {
        assert!(
            settings["hooks"][event].to_string().contains(" hook\""),
            "{event}: {settings}"
        );
    }
    let lean = settings["hooks"]["PreToolUse"][0].clone();
    assert_eq!(lean["matcher"], "Bash|PowerShell|Read", "{settings}");
    assert!(
        lean["hooks"][0]["command"]
            .as_str()
            .unwrap()
            .ends_with(" hook lean")
    );
    assert!(profile.join("commands/remember.md").is_file());
    // No sessions in it: not a profile Claude Code uses.
    assert!(!home.join(".claude-old/settings.json").exists());
    assert_eq!(read(&home.join(".claude-old/.claude.json")), json!({}));

    let status = run(&["status"]);
    assert!(
        status.to_string().contains("claude-code (.claude-2)"),
        "{status}"
    );

    run(&["uninstall", "--memory", "--lean"]);
    let settings = read(&profile.join("settings.json"));
    assert!(
        !settings.to_string().contains("footnote"),
        "hooks left: {settings}"
    );
    assert!(
        read(&profile.join(".claude.json"))["mcpServers"]
            .get("footnote-memory")
            .is_none()
    );
}
