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
pub fn seen(state: &Path, project: &str, root: &str) -> Result<()> {
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
    let tmp = path.with_extension("json.tmp");
    fs::write(
        &tmp,
        json!({"name": project, "path": kept_root, "first_seen": first, "last_seen": today()})
            .to_string(),
    )?;
    fs::rename(&tmp, &path)?;
    Ok(())
}

/// Every recorded project, most recently used first.
pub fn list(state: &Path) -> Result<Value> {
    let mut projects: Vec<Value> = match fs::read_dir(state.join("projects")) {
        Ok(entries) => entries
            .flatten()
            .filter(|e| e.path().extension().is_some_and(|x| x == "json"))
            .filter_map(|e| serde_json::from_slice(&fs::read(e.path()).ok()?).ok())
            .collect(),
        Err(_) => Vec::new(),
    };
    projects.sort_by(|a, b| b["last_seen"].as_str().cmp(&a["last_seen"].as_str()));
    let memories = memories_by_project(state)?;
    for p in &mut projects {
        let root = p["path"].as_str().unwrap_or_default().to_string();
        let name = p["name"].as_str().unwrap_or_default().to_string();
        p["exists"] = json!(Path::new(&root).is_dir());
        p["memories"] = json!(memories.get(&name).copied().unwrap_or(0));
        #[cfg(feature = "code")]
        {
            p["code_graph"] =
                json!(crate::app::code_db(Path::new(&root)).is_ok_and(|db| db.exists()));
        }
        if p["exists"] == true {
            p["git"] = git_state(&root);
        }
        if let Some(ask) = waiting(state, &name) {
            p["ask"] = json!({"kind": ask["kind"], "asked_at": ask["asked_at"]});
        }
    }
    Ok(json!({"projects": projects}))
}

/// How long a request from the window waits for an agent turn in its project before it is dropped.
const ASK_TTL_SECS: i64 = 24 * 3600;

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
