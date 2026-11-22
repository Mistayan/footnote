"""Build the two A/B arms (memory 448, #242) as CLAUDE_CONFIG_DIR copies under ~/.claude-ab; the live ~/.claude and the live
Footnote state are only read. Usage: AB_SKILLS=<extra skill folders, os.pathsep-separated> AB_LIKEC4_WORKSPACE=<model dir> python setup_arms.py
(rebuilds both arms from scratch)."""
import json, os, pathlib, shutil, subprocess

H = pathlib.Path.home(); LIVE = H / ".claude"; GSD = LIVE / "disabled/gsd-2026-11-22"; ROOT = H / ".claude-ab"
FN = H / "AppData/Local/Programs/footnote/footnote.exe"; FSTATE = H / "AppData/Local/footnote"
SKILL_SRC = [LIVE / "skills", *map(pathlib.Path, filter(None, os.environ.get("AB_SKILLS", "").split(os.pathsep)))]  # deduped by folder name
CBM = (H / "AppData/Local/Programs/codebase-memory-mcp/codebase-memory-mcp.exe").as_posix()
BASE_MCP = {"codebase-memory-mcp": {"command": CBM, "args": []},
            "memory": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory@2.1.1"]},
            "context7": {"command": "npx", "args": ["-y", "@upstash/context7-mcp@4.6.0"]},
            "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@0.0.85"]},
            "likec4": {"command": "likec4-mcp", "args": ["--stdio", "--graphviz=wasm"],
                       "env": {"LIKEC4_WORKSPACE": os.environ.get("AB_LIKEC4_WORKSPACE", "")}}}
CBM_HOOK = "cmd.exe /d /v:off /s /c '\"\"%USERPROFILE%\\.claude\\hooks\\{}.cmd\"\"'"

def is_fn(h): return "footnote.exe" in h["command"]

def hooks_where(settings, keep):
    out = {}
    for ev, groups in settings.get("hooks", {}).items():
        g = [{**m, "hooks": [h for h in m["hooks"] if keep(h)]} for m in groups]
        g = [m for m in g if m["hooks"]]
        if g: out[ev] = g
    return out

def base(arm):
    d = ROOT / arm; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    for f in (".credentials.json", "CLAUDE.md", "RTK.md"): shutil.copy2(LIVE / f, d / f)
    shutil.copytree(LIVE / "plugins", d / "plugins")
    live = json.loads((LIVE / "settings.json").read_text(encoding="utf-8"))
    s = {k: live[k] for k in ("autoCompactWindow", "effortLevel", "extraKnownMarketplaces", "model", "permissions",
                              "skipDangerousModePermissionPrompt", "theme") if k in live}
    s["enabledPlugins"] = {"cloudflare@cloudflare": True}
    cj = json.loads((H / ".claude.json").read_text(encoding="utf-8")); cj.pop("projects", None); cj.pop("mcpServers", None)
    return d, s, cj

def write(d, s, cj, mcp):
    (d / "settings.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    (d / ".claude.json").write_text(json.dumps({**cj, "mcpServers": mcp}, indent=2), encoding="utf-8")

def skill_dirs():
    seen = {}
    for src in SKILL_SRC:
        for p in sorted(src.iterdir()):
            if (p / "SKILL.md").is_file(): seen.setdefault(p.name, p)
    return seen

def base_dev():
    d, s, cj = base("base-dev")
    gsd = json.loads((GSD / "settings.json").read_text(encoding="utf-8"))
    hooks = hooks_where(gsd, lambda h: not is_fn(h))  # GSD + impeccable hooks as they were, Footnote's removed
    for ev, matchers, name in (("SessionStart", ["startup", "resume", "clear", "compact"], "cbm-session-reminder"),
                               ("PostToolUse", ["Read"], "cbm-code-discovery-gate"), ("PreToolUse", ["Grep|Glob"], "cbm-code-discovery-gate"),
                               ("SubagentStart", ["*"], "cbm-subagent-reminder")):
        for m in matchers:
            hooks.setdefault(ev, []).append({"matcher": m, "hooks": [{"type": "command", "command": CBM_HOOK.format(name), "timeout": 5}]})
    s["hooks"] = json.loads(json.dumps(hooks).replace((LIVE / "hooks").as_posix() + "/", (d / "hooks").as_posix() + "/"))
    shutil.copytree(LIVE / "hooks", d / "hooks"); shutil.copytree(GSD / "hooks", d / "hooks", dirs_exist_ok=True)
    shutil.copytree(GSD / "gsd-core", d / "gsd-core")
    for n, p in skill_dirs().items(): shutil.copytree(p, d / "skills" / n)
    shutil.copytree(GSD / "skills", d / "skills", dirs_exist_ok=True); shutil.copytree(LIVE / "disabled/skills", d / "skills", dirs_exist_ok=True)
    for a in (LIVE / "agents", GSD / "agents", LIVE / "disabled/agents"): shutil.copytree(a, d / "agents", dirs_exist_ok=True)
    write(d, s, cj, BASE_MCP)

def footnote():
    d, s, cj = base("footnote")
    st = ROOT / "footnote-state"; shutil.rmtree(st, ignore_errors=True); st.mkdir()
    skip = {"models", "usage", "metrics.jsonl", "jobs", "outputs", "scratch", "memory-hook", "daemon.pid", "daemon.token"}
    for p in FSTATE.iterdir():  # memory, code graphs and corpora as the live MCP serves them; models are read in place
        if p.name in skip or ".bak" in p.name or "forked" in p.name or p.name.startswith(("audit.tmp", "memory.db.bak")): continue
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, st / p.name)
    mj = json.loads((st / "memory.json").read_text(encoding="utf-8")); mj["db"] = (st / "memory.db").as_posix()
    (st / "memory.json").write_text(json.dumps(mj, indent=2), encoding="utf-8")
    env = {**os.environ, "FOOTNOTE_STATE_DIR": str(st)}
    for cmd in (["config", "set", "memory.skills", "true"], ["skills", "index", "user", *map(str, skill_dirs().values())]):
        print(subprocess.run([str(FN), *cmd], env=env, capture_output=True, text=True, check=True).stdout.strip()[:300])
    live = json.loads((LIVE / "settings.json").read_text(encoding="utf-8"))
    s["hooks"] = hooks_where(live, is_fn)  # session, prompt, stop and lean hooks
    write(d, s, cj, {"footnote-memory": {"command": FN.as_posix(), "args": ["--db", (st / "memory.db").as_posix(), "mcp"],
                                         "env": {"FOOTNOTE_STATE_DIR": str(st)}}})

if __name__ == "__main__":
    base_dev(); footnote()
    for a in ("base-dev", "footnote"):
        d = ROOT / a; print(a, "skills", len(list((d / "skills").glob("*/SKILL.md"))) if (d / "skills").exists() else 0,
                            "agents", len(list((d / "agents").glob("*.md"))) if (d / "agents").exists() else 0)
