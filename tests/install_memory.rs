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
    fs::write(&python, "").unwrap(); // only its existence is checked
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
    assert!(starts[1].to_string().contains("memory_hook.py"));
    for event in ["UserPromptSubmit", "Stop"] {
        assert!(
            settings["hooks"][event]
                .to_string()
                .contains("memory_hook.py"),
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
    assert!(
        codex["hooks"]["Stop"]
            .to_string()
            .contains("memory_hook.py")
    );
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
    assert!(
        dsh["hooks"]["SessionStart"]
            .to_string()
            .contains("memory_hook.py")
    );
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
