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
    }
    Ok(json!({"projects": projects}))
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
    fn project_names_become_safe_file_names() {
        assert_eq!(super::file_name("footnote"), "footnote");
        assert_eq!(
            super::file_name("dossier financier/../x"),
            "dossier-financier-..-x"
        );
        assert_eq!(super::file_name(".."), "unnamed");
    }
}
