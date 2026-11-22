//! Projects Footnote has seen: every folder an agent session started in is recorded by the hook, so a new project appears with
//! no setup. `footnote projects` lists them with what Footnote knows: memories, code graph, and git work not yet committed or
//! pushed. One small file per project under `<state>/projects/`, so concurrent sessions never rewrite each other's projects.
use anyhow::Result;
use serde_json::{Value, json};
use std::{fs, path::Path};

fn file_name(project: &str) -> String {
    let safe: String = project
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || "._-".contains(c) {
                c
            } else {
                '-'
            }
        })
        .collect();
    if safe.trim_matches(['.', '-']).is_empty() {
        "unnamed".into()
    } else {
        safe
    }
}

fn today() -> String {
    time::OffsetDateTime::now_utc().date().to_string()
}

/// Record that an agent session started in `root` for `project` (the hook's name for it). Same name, same project: a second
/// clone of one repository updates the path to the latest one used, except a linked git worktree (`.git` is a file) never
/// overwrites an existing main checkout path, so worktree sessions do not hide the main repository's code graph.
/// `agent` is the agent whose session it is (`claude`, `codex`, ... or empty when unknown): the commit button runs that one.
pub fn seen(state: &Path, project: &str, root: &str, agent: &str) -> Result<()> {
    if ignored(state).contains(project) {
        return Ok(()); // the user asked Footnote to leave this project alone
    }
    let dir = state.join("projects");
    footnote_core::state::ensure_private_dir(&dir)?;
    let path = dir.join(format!("{}.json", file_name(project)));
    let prev = fs::read(&path)
        .ok()
        .and_then(|b| serde_json::from_slice::<Value>(&b).ok());
    let first = prev
        .as_ref()
        .and_then(|v| v["first_seen"].as_str().map(str::to_string))
        .unwrap_or_else(today);
    let kept_root = prev
        .as_ref()
        .and_then(|v| v["path"].as_str())
        .filter(|old| {
            let old_p = Path::new(old);
            let new_p = Path::new(root);
            old_p.is_dir() && new_p.join(".git").is_file() && !old_p.join(".git").is_file()
        })
        .unwrap_or(root);
    let agent = if agent.is_empty() {
        prev.as_ref()
            .and_then(|v| v["agent"].as_str())
            .unwrap_or_default()
            .to_string()
    } else {
        agent.to_string()
    };
    let tmp = path.with_extension("json.tmp");
    fs::write(
        &tmp,
        json!({"name": project, "path": kept_root, "first_seen": first, "last_seen": today(), "agent": agent})
            .to_string(),
    )?;
    fs::rename(&tmp, &path)?;
    Ok(())
}

/// Every recorded project, most recently used first, and the names the user chose to ignore. `quick` gives names and folders
/// only (what the launcher checks before opening a folder): no git, memory or code-graph reads. Otherwise the git reads,
/// two short `git` runs per project, run side by side, so many projects cost about as much as one.
pub fn list(state: &Path, quick: bool) -> Result<Value> {
    let skip = ignored(state);
    let mut projects: Vec<Value> = match fs::read_dir(state.join("projects")) {
        Ok(entries) => entries
            .flatten()
            .filter(|e| e.path().extension().is_some_and(|x| x == "json"))
            .filter_map(|e| serde_json::from_slice::<Value>(&fs::read(e.path()).ok()?).ok())
            .filter(|p| !p["name"].as_str().is_some_and(|n| skip.contains(n)))
            .collect(),
        Err(_) => Vec::new(),
    };
    projects.sort_by(|a, b| b["last_seen"].as_str().cmp(&a["last_seen"].as_str()));
    let ignored: Vec<&String> = skip.iter().collect();
    if quick {
        return Ok(json!({"projects": projects, "ignored": ignored}));
    }
    let memories = memories_by_project(state)?;
    let roots: Vec<String> = projects
        .iter()
        .map(|p| p["path"].as_str().unwrap_or_default().to_string())
        .collect();
    let gits: Vec<Option<Value>> = std::thread::scope(|s| {
        let runs: Vec<_> = roots
            .iter()
            .map(|root| s.spawn(move || Path::new(root).is_dir().then(|| git_state(root))))
            .collect();
        runs.into_iter().map(|h| h.join().ok().flatten()).collect()
    });
    for ((p, root), git) in projects.iter_mut().zip(&roots).zip(gits) {
        let name = p["name"].as_str().unwrap_or_default().to_string();
        p["exists"] = json!(Path::new(root).is_dir());
        p["memories"] = json!(memories.get(&name).copied().unwrap_or(0));
        #[cfg(feature = "code")]
        {
            p["code_graph"] =
                json!(crate::app::code_db(Path::new(root)).is_ok_and(|db| db.exists()));
        }
        if let Some(git) = git {
            p["git"] = git;
        }
        if let Some(ask) = waiting(state, &name) {
            p["ask"] = json!({"kind": ask["kind"], "asked_at": ask["asked_at"]});
        }
    }
    Ok(json!({"projects": projects, "ignored": ignored}))
}

fn ignored_path(state: &Path) -> std::path::PathBuf {
    state.join("projects-ignored.json")
}

/// The projects the user chose to ignore (by the hook's name for them).
fn ignored(state: &Path) -> std::collections::BTreeSet<String> {
    fs::read(ignored_path(state))
        .ok()
        .and_then(|b| serde_json::from_slice::<Value>(&b).ok())
        .and_then(|v| {
            v["names"].as_array().map(|a| {
                a.iter()
                    .filter_map(|n| n.as_str().map(str::to_string))
                    .collect()
            })
        })
        .unwrap_or_default()
}

/// `footnote projects add <folder>`: list a folder before any agent session starts there (the launcher's Add project). It
/// gets the name and top folder a session there would record: the git remote's name, else the folder's, at the repository's
/// top. Adding an ignored project stops ignoring it.
pub fn add(state: &Path, folder: &str) -> Result<Value> {
    let dir = Path::new(folder);
    anyhow::ensure!(dir.is_dir(), "{folder} is not a folder");
    let top = crate::hook::git(folder, &["rev-parse", "--show-toplevel"]);
    let root = if top.is_empty() {
        folder.replace('\\', "/")
    } else {
        top
    };
    let name = crate::hook::project_of(&root);
    anyhow::ensure!(!name.is_empty(), "{folder} has no name to list it under");
    if ignored(state).contains(&name) {
        ignore(state, &name, false)?;
    }
    seen(state, &name, &root, "")?;
    Ok(json!({"added": true, "name": name, "path": root}))
}

/// `footnote projects ignore <name>` (or `unignore`): Footnote stops listing the project and stops recording it when an agent
/// starts a session there; its memories stay. Unignored, it comes back with its next session.
pub fn ignore(state: &Path, project: &str, on: bool) -> Result<Value> {
    anyhow::ensure!(!project.trim().is_empty(), "name a project");
    let mut names = ignored(state);
    if on {
        names.insert(project.to_string());
        let _ = fs::remove_file(
            state
                .join("projects")
                .join(format!("{}.json", file_name(project))),
        );
        let _ = fs::remove_file(ask_path(state, project));
    } else {
        names.remove(project);
    }
    footnote_core::state::ensure_private_dir(state)?;
    let path = ignored_path(state);
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, json!({"names": names}).to_string())?;
    fs::rename(&tmp, &path)?;
    Ok(json!({"project": project, "ignored": on, "names": names}))
}

/// How long a request from the window waits for an agent turn in its project before it is dropped.
const ASK_TTL_SECS: i64 = 24 * 3600;

const COMMIT_RUN: &str = "You were started unattended by the user, from the Footnote window, to commit and push the \
uncommitted work in this repository ({path}, {n} changed file(s)). Read `git log --oneline -15` for its conventions, then \
`git status` and `git diff`. Group the changes into logical commits with clear messages in those conventions, then push the \
current branch (`git push`; with no upstream, `git push -u origin HEAD`). Never force-push, rewrite history or edit files. \
You cannot ask anything: leave uncommitted any change that looks unintended, generated or secret (keys, tokens, .env \
files) and name it. End with at most three short lines: what you committed, whether the push worked, what you left.";

/// How long an unattended commit may take before it is stopped.
const COMMIT_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(600);

/// `footnote agent-commit <project>`: commit and push the project's uncommitted work now, unattended, with the agent last
/// used there (Claude Code or Codex, else whichever is installed). Claude Code may run git only; Codex runs in its
/// workspace sandbox with network for the push. Memory's hook stays off for the run. Returns the agent's last lines and the
/// work left after it.
pub fn commit_now(state: &Path, project: &str) -> Result<Value> {
    let known: Value = fs::read(
        state
            .join("projects")
            .join(format!("{}.json", file_name(project))),
    )
    .ok()
    .and_then(|b| serde_json::from_slice(&b).ok())
    .ok_or_else(|| anyhow::anyhow!("no project named {project}: `footnote projects` lists them"))?;
    let root = known["path"].as_str().unwrap_or_default().to_string();
    anyhow::ensure!(
        Path::new(&root).is_dir(),
        "the folder of {project} no longer exists: {root}"
    );
    let before = git_state(&root)["uncommitted"].as_u64().unwrap_or(0);
    anyhow::ensure!(before > 0, "nothing to commit in {root}");
    let prompt = COMMIT_RUN
        .replace("{path}", &root)
        .replace("{n}", &before.to_string());
    let last = known["agent"].as_str().unwrap_or_default();
    let order: Vec<&str> = if last == "codex" {
        vec!["codex", "claude"]
    } else {
        vec!["claude", "codex"]
    };
    let mut tried = Vec::new();
    for agent in order {
        match run_agent(agent, &root, &prompt) {
            Ok(said) => {
                let after = git_state(&root);
                let _ = fs::remove_file(ask_path(state, project)); // a queued request is answered too
                return Ok(json!({"project": project, "agent": agent, "before": before,
                    "uncommitted": after["uncommitted"], "unpushed": after["unpushed"], "said": said.trim()}));
            }
            Err(e)
                if e.downcast_ref::<std::io::Error>()
                    .is_some_and(|io| io.kind() == std::io::ErrorKind::NotFound) =>
            {
                tried.push(agent);
            }
            Err(e) => return Err(e),
        }
    }
    anyhow::bail!(
        "neither `{}` is installed on PATH: the request can wait for the next agent turn instead",
        tried.join("` nor `")
    )
}

fn codex_command(out_file: &std::path::Path) -> std::process::Command {
    // `--full-auto` is rejected by Codex 0.171+ (#542); approval and sandbox are spelled out.
    let mut c = std::process::Command::new("codex");
    c.args([
        "-a",
        "never",
        "exec",
        "--sandbox",
        "workspace-write",
        "-c",
        "sandbox_workspace_write.network_access=true",
        "--ephemeral",
        "-o",
    ])
    .arg(out_file)
    .arg("-");
    c
}

fn run_agent(agent: &str, root: &str, prompt: &str) -> Result<String> {
    use anyhow::Context;
    use std::io::Write;
    use std::process::{Command, Stdio};
    use wait_timeout::ChildExt;
    let out_file = std::env::temp_dir().join(format!("footnote-commit-{}.txt", std::process::id()));
    let mut cmd = if agent == "claude" {
        let mut c = Command::new("claude");
        c.args([
            "-p",
            "--strict-mcp-config",
            "--no-session-persistence",
            "--output-format",
            "json",
            "--allowedTools",
        ]);
        c.args([
            "Bash(git status:*)",
            "Bash(git diff:*)",
            "Bash(git log:*)",
            "Bash(git add:*)",
            "Bash(git commit:*)",
            "Bash(git push:*)",
            "Bash(git rev-parse:*)",
            "Bash(git branch:*)",
            "Bash(git remote:*)",
        ]);
        c
    } else {
        codex_command(&out_file)
    };
    cmd.current_dir(root)
        .env("FOOTNOTE_HOOK_OFF", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    let mut child = cmd.spawn()?;
    child
        .stdin
        .take()
        .context("no stdin")?
        .write_all(prompt.as_bytes())?;
    let mut stdout = child.stdout.take().context("no stdout")?;
    let reader = std::thread::spawn(move || {
        let mut s = String::new();
        let _ = std::io::Read::read_to_string(&mut stdout, &mut s);
        s
    });
    let Some(status) = child.wait_timeout(COMMIT_TIMEOUT)? else {
        let _ = child.kill();
        let _ = child.wait();
        anyhow::bail!(
            "`{agent}` was stopped after {} minutes",
            COMMIT_TIMEOUT.as_secs() / 60
        );
    };
    let out = reader.join().unwrap_or_default();
    anyhow::ensure!(status.success(), "`{agent}` failed ({status})");
    if agent == "claude" {
        let v: Value = serde_json::from_str(out.trim()).context("`claude` did not answer JSON")?;
        anyhow::ensure!(
            v["is_error"] != true,
            "`claude` reported an error: {}",
            v["result"].as_str().unwrap_or_default()
        );
        return Ok(v["result"].as_str().unwrap_or_default().to_string());
    }
    let said = fs::read_to_string(&out_file).unwrap_or(out);
    let _ = fs::remove_file(&out_file);
    Ok(said)
}

const COMMIT_ASK: &str = "Footnote: the user asks, from the Footnote window, that you commit and push the uncommitted work in \
the folder {path} ({n} changed file(s) when they asked). Run `git status` and read the diff there, group the changes into \
logical commits with clear messages that follow the repository's conventions, then push the current branch. Never \
force-push; ask the user first if a change looks unintended, a file looks secret, or anything would be destructive. Then tell \
the user in one line what you committed and pushed.";

fn ask_path(state: &Path, project: &str) -> std::path::PathBuf {
    state
        .join("agent-asks")
        .join(format!("{}.json", file_name(project)))
}

fn now() -> i64 {
    time::OffsetDateTime::now_utc().unix_timestamp()
}

/// The request waiting for `project`, if any and not expired (an expired one is removed).
fn waiting(state: &Path, project: &str) -> Option<Value> {
    let path = ask_path(state, project);
    let ask: Value = serde_json::from_slice(&fs::read(&path).ok()?).ok()?;
    if now() - ask["asked_at"].as_i64().unwrap_or(0) > ASK_TTL_SECS {
        let _ = fs::remove_file(&path);
        return None;
    }
    Some(ask)
}

/// `footnote agent-ask <project>`: queue a commit-and-push request for the next agent turn in that project (a session
/// start, a prompt, or the end of a turn, which then continues with it). The text is fixed here; the window only names the
/// project. `--cancel` withdraws it.
pub fn ask(state: &Path, project: &str, cancel: bool) -> Result<Value> {
    let path = ask_path(state, project);
    if cancel {
        let had = fs::remove_file(&path).is_ok();
        return Ok(json!({"project": project, "cancelled": had}));
    }
    let known: Value = fs::read(
        state
            .join("projects")
            .join(format!("{}.json", file_name(project))),
    )
    .ok()
    .and_then(|b| serde_json::from_slice(&b).ok())
    .ok_or_else(|| anyhow::anyhow!("no project named {project}: `footnote projects` lists them"))?;
    let root = known["path"].as_str().unwrap_or_default().to_string();
    anyhow::ensure!(
        Path::new(&root).is_dir(),
        "the folder of {project} no longer exists: {root}"
    );
    let n = git_state(&root)["uncommitted"].as_u64().unwrap_or(0);
    anyhow::ensure!(n > 0, "nothing to commit in {root}");
    footnote_core::state::ensure_private_dir(&state.join("agent-asks"))?;
    let ask = json!({"kind": "commit", "project": project, "path": root, "uncommitted": n, "asked_at": now()});
    let tmp = path.with_extension("json.tmp");
    fs::write(&tmp, ask.to_string())?;
    fs::rename(&tmp, &path)?;
    Ok(
        json!({"queued": true, "project": project, "path": root, "uncommitted": n,
        "note": "the next agent turn in this project receives it: a new prompt or session, or the end of a turn, which then continues with it"}),
    )
}

/// Claim the waiting request for `project`, once: the rename succeeds for one session only. The text to give the agent.
pub fn take(state: &Path, project: &str) -> Option<String> {
    let path = ask_path(state, project);
    if !path.exists() {
        return None;
    }
    let ask = waiting(state, project)?;
    let claimed = path.with_extension(format!("taken-{}", std::process::id()));
    fs::rename(&path, &claimed).ok()?;
    let _ = fs::remove_file(&claimed);
    (ask["kind"] == "commit").then(|| {
        COMMIT_ASK
            .replace("{path}", ask["path"].as_str().unwrap_or_default())
            .replace("{n}", &ask["uncommitted"].to_string())
    })
}

/// Files changed but not committed, and commits not pushed (null without an upstream branch); null outside a repository.
fn git_state(root: &str) -> Value {
    let status = crate::hook::git(root, &["status", "--porcelain"]);
    let top = crate::hook::git(root, &["rev-parse", "--show-toplevel"]);
    if top.is_empty() {
        return Value::Null;
    }
    let unpushed = crate::hook::git(root, &["rev-list", "--count", "@{u}..HEAD"])
        .parse::<u64>()
        .ok();
    json!({"uncommitted": status.lines().filter(|l| !l.trim().is_empty()).count(), "unpushed": unpushed})
}

fn memories_by_project(state: &Path) -> Result<std::collections::HashMap<String, i64>> {
    let db = crate::status::memory_db(state)?;
    if !db.exists() {
        return Ok(Default::default());
    }
    let c = crate::app::open(&db, false)?;
    let mut q = c.prepare(
        "SELECT m.scope, count(*) FROM memories m JOIN sources s ON s.id=m.source_id WHERE s.status='indexed' GROUP BY m.scope",
    )?;
    let rows = q.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?)))?;
    Ok(rows.collect::<rusqlite::Result<_>>()?)
}

#[cfg(test)]
mod tests {
    #[test]
    fn codex_commit_arguments_are_pinned() {
        let c = super::codex_command(std::path::Path::new("out.txt"));
        let args: Vec<_> = c
            .get_args()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        assert_eq!(
            args,
            [
                "-a",
                "never",
                "exec",
                "--sandbox",
                "workspace-write",
                "-c",
                "sandbox_workspace_write.network_access=true",
                "--ephemeral",
                "-o",
                "out.txt",
                "-",
            ]
        );
    }

    #[test]
    fn a_folder_added_by_hand_is_listed_under_its_name_and_unignored() {
        let dir = tempfile::tempdir().unwrap();
        let state = dir.path().join("state");
        let folder = dir.path().join("Shop-API");
        std::fs::create_dir_all(&folder).unwrap();
        let folder = folder.to_string_lossy().into_owned();
        super::ignore(&state, "shop-api", true).unwrap();
        let added = super::add(&state, &folder).unwrap();
        assert_eq!(added["name"], "shop-api", "{added}");
        let listed = super::list(&state, true).unwrap();
        assert_eq!(listed["projects"][0]["name"], "shop-api", "{listed}");
        assert_eq!(listed["ignored"], serde_json::json!([]));
        assert!(super::add(&state, &dir.path().join("missing").to_string_lossy()).is_err());
    }

    #[test]
    fn an_ignored_project_is_neither_listed_nor_recorded_until_unignored() {
        let dir = tempfile::tempdir().unwrap();
        let state = dir.path();
        let root = state.join("scratch");
        std::fs::create_dir_all(&root).unwrap();
        let root = root.to_string_lossy();
        super::seen(state, "scratch", &root, "").unwrap();
        super::seen(state, "kept", &root, "").unwrap();
        let names = |v: serde_json::Value| -> Vec<String> {
            v["projects"]
                .as_array()
                .unwrap()
                .iter()
                .map(|p| p["name"].as_str().unwrap().to_string())
                .collect()
        };
        assert_eq!(names(super::list(state, true).unwrap()).len(), 2);
        super::ignore(state, "scratch", true).unwrap();
        super::seen(state, "scratch", &root, "").unwrap(); // a new session there records nothing
        let listed = super::list(state, true).unwrap();
        assert_eq!(names(listed.clone()), ["kept"]);
        assert_eq!(listed["ignored"], serde_json::json!(["scratch"]));
        super::ignore(state, "scratch", false).unwrap();
        super::seen(state, "scratch", &root, "").unwrap();
        assert_eq!(names(super::list(state, true).unwrap()).len(), 2);
    }

    #[test]
    fn a_request_is_taken_once_and_names_the_folder() {
        let dir = tempfile::tempdir().unwrap();
        let state = dir.path();
        let root = state.join("repo");
        std::fs::create_dir_all(&root).unwrap();
        // Queued by hand: `ask` needs a git repository with changes, which the integration test covers.
        std::fs::create_dir_all(state.join("agent-asks")).unwrap();
        let path = super::ask_path(state, "repo");
        let ask = serde_json::json!({"kind": "commit", "project": "repo", "path": root.to_string_lossy(), "uncommitted": 3,
            "asked_at": super::now()});
        std::fs::write(&path, ask.to_string()).unwrap();
        assert!(super::waiting(state, "repo").is_some());
        let text = super::take(state, "repo").expect("the first turn takes it");
        assert!(
            text.contains(&*root.to_string_lossy()) && text.contains("3 changed file(s)"),
            "{text}"
        );
        assert!(super::take(state, "repo").is_none(), "only once");
        // An expired request is dropped, not delivered.
        let old = serde_json::json!({"kind": "commit", "path": "x", "uncommitted": 1, "asked_at": super::now() - 2 * super::ASK_TTL_SECS});
        std::fs::write(&path, old.to_string()).unwrap();
        assert!(super::take(state, "repo").is_none());
        assert!(!path.exists());
        // Cancelling removes it.
        std::fs::write(&path, ask.to_string()).unwrap();
        assert_eq!(super::ask(state, "repo", true).unwrap()["cancelled"], true);
        assert!(super::take(state, "repo").is_none());
    }

    #[test]
    fn project_names_become_safe_file_names() {
        assert_eq!(super::file_name("footnote"), "footnote");
        assert_eq!(
            super::file_name("dossier financier/../x"),
            "dossier-financier-..-x"
        );
        assert_eq!(super::file_name(".."), "unnamed");
    }
}
