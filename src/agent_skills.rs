//! The agent skill layer (#444): versions of skills adapted from use, served in place of the curated skill of the same
//! name. The curated skill is never written: the first revision copies it, and later revisions change the copy.
//!
//! Layout under `<state>/skills/agent/`:
//! - `global/<name>/`, `project-<project>/<name>/`: the live files the agent reads (absent once dropped). The folder keeps
//!   the skill's name, so the outcome log (#443) recognizes its `SKILL.md` and `scripts/`.
//! - `.history/<scope>/<name>/skill.json`: name, scope, `base` (`<curated name>@<sha256 of its SKILL.md>`), the curated
//!   folder, the live revision and whether it was dropped.
//! - `.history/<scope>/<name>/<n>/files/` and `<n>/meta.json`: every revision in full, with its reason. Nothing deletes one.
//! - `.docs/`, `../agent.db`, `../agent.json`: the `agent` theme's index of live skills, rebuilt after each change.
//!
//! A project's version is served in that project only, before the version for every project.
use anyhow::{Context, Result, bail, ensure};
use serde_json::{Map, Value, json};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Component, Path, PathBuf};

/// The reserved theme the agent layer is indexed under.
pub const THEME: &str = "agent";
/// Caps on one skill: a skill is instructions and small scripts, not a project.
const MAX_FILES: usize = 200;
const MAX_BYTES: u64 = 2 * 1024 * 1024;

fn root(state: &Path) -> PathBuf {
    crate::skills::dir(state).join(THEME)
}

fn scope_dir(scope: &str) -> String {
    if scope == "global" {
        "global".into()
    } else {
        format!("project-{}", crate::skills::file_stem(scope))
    }
}

fn live(state: &Path, scope: &str, stem: &str) -> PathBuf {
    root(state).join(scope_dir(scope)).join(stem)
}

fn history(state: &Path, scope: &str, stem: &str) -> PathBuf {
    root(state)
        .join(".history")
        .join(scope_dir(scope))
        .join(stem)
}

fn check(name: &str, scope: &str) -> Result<String> {
    ensure!(
        !name.trim().is_empty() && name.len() <= 100,
        "a skill name has 1 to 100 characters"
    );
    ensure!(
        !scope.trim().is_empty() && scope.len() <= 100 && !scope.chars().any(char::is_control),
        "scope is \"global\" or a project name"
    );
    Ok(crate::skills::file_stem(name))
}

fn sha256(path: &Path) -> Option<String> {
    let bytes = fs::read(path).ok()?;
    Some(format!("{:x}", Sha256::digest(bytes)))
}

fn read_json(path: &Path) -> Option<Value> {
    serde_json::from_slice(&fs::read(path).ok()?).ok()
}

fn write_json(path: &Path, v: &Value) -> Result<()> {
    fs::write(path, serde_json::to_vec_pretty(v)?)
        .with_context(|| format!("writing {}", path.display()))
}

/// A path inside a skill folder: relative, plain components only.
fn inside(rel: &str) -> Result<PathBuf> {
    let p = Path::new(rel);
    ensure!(
        !rel.is_empty()
            && p.components().all(|c| matches!(c, Component::Normal(_)))
            && !rel.contains(':'),
        "{rel}: a skill file is a relative path inside the skill's folder"
    );
    Ok(p.to_path_buf())
}

/// Copies a skill folder, leaving out names that start with `_` or `.` (maintainer notes, VCS folders) and anything that is
/// not a plain file or folder. Refuses a folder past the caps.
fn copy_skill(from: &Path, to: &Path) -> Result<()> {
    let (mut files, mut bytes) = (0usize, 0u64);
    fs::create_dir_all(to)?;
    let walk = walkdir::WalkDir::new(from).min_depth(1).into_iter();
    for e in walk.filter_entry(|e| {
        let n = e.file_name().to_string_lossy();
        !n.starts_with('_') && !n.starts_with('.') && n != "node_modules"
    }) {
        let e = e?;
        let rel = e.path().strip_prefix(from)?;
        if e.file_type().is_dir() {
            fs::create_dir_all(to.join(rel))?;
        } else if e.file_type().is_file() {
            files += 1;
            bytes += e.metadata()?.len();
            ensure!(
                files <= MAX_FILES && bytes <= MAX_BYTES,
                "{}: a skill holds at most {MAX_FILES} files and {} MB",
                from.display(),
                MAX_BYTES / 1024 / 1024
            );
            fs::copy(e.path(), to.join(rel))?;
        }
    }
    Ok(())
}

/// Refuses a skill folder past the caps.
fn fits(dir: &Path) -> Result<()> {
    let (mut files, mut bytes) = (0usize, 0u64);
    for e in walkdir::WalkDir::new(dir).min_depth(1) {
        let e = e?;
        if e.file_type().is_file() {
            files += 1;
            bytes += e.metadata()?.len();
        }
    }
    ensure!(
        files <= MAX_FILES && bytes <= MAX_BYTES,
        "a skill holds at most {MAX_FILES} files and {} MB",
        MAX_BYTES / 1024 / 1024
    );
    Ok(())
}

/// The curated skill of that name: its theme and the folder holding its `SKILL.md`.
fn curated(state: &Path, name: &str) -> Option<(String, PathBuf)> {
    crate::skills::themes_on(state)
        .into_iter()
        .filter(|(theme, _)| theme != THEME)
        .find_map(|(theme, map)| {
            let skill = map.values().find(|s| s["name"] == name)?;
            let md = PathBuf::from(skill["path"].as_str()?);
            Some((theme, md.parent()?.to_path_buf()))
        })
}

fn next_revision(hist: &Path) -> u64 {
    fs::read_dir(hist)
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
        .filter_map(|e| e.file_name().to_string_lossy().parse::<u64>().ok())
        .max()
        .unwrap_or(0)
        + 1
}

/// Who asked for a change. An agent's change also passes `lint`, and one that touches anything but Markdown waits for the
/// user's review (#445).
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum Origin {
    User,
    Agent,
}

/// SKILL.md description, as the Agent Skills format allows it.
const MAX_DESCRIPTION: usize = 1024;
/// SKILL.md lines, as the Agent Skills format recommends.
const MAX_LINES: usize = 500;

/// The skill-check rules an agent's change must pass (`skills/write-a-skill/scripts/skill-check`, its FAIL rules): a
/// description of at most 1024 characters, a SKILL.md of at most 500 lines, and relative links in Markdown files that
/// resolve to a file inside the skill.
fn lint(files: &Path) -> Result<()> {
    let md = fs::read_to_string(files.join("SKILL.md"))?;
    let (_, desc) = crate::skills::front_matter(&md).context("SKILL.md has no description")?;
    ensure!(
        desc.chars().count() <= MAX_DESCRIPTION,
        "the description is {} characters (at most {MAX_DESCRIPTION})",
        desc.chars().count()
    );
    ensure!(
        md.lines().count() <= MAX_LINES,
        "SKILL.md is {} lines (at most {MAX_LINES}); move detail to references/",
        md.lines().count()
    );
    for e in walkdir::WalkDir::new(files) {
        let e = e?;
        if !e.file_type().is_file() || e.path().extension().is_none_or(|x| x != "md") {
            continue;
        }
        let text = fs::read_to_string(e.path())?;
        let dir = e.path().parent().unwrap_or(files);
        for target in md_links(&text) {
            let resolved = normalize(&dir.join(&target));
            ensure!(
                resolved.starts_with(normalize(files)) && resolved.is_file(),
                "{} links to {target}, which is not a file in the skill",
                e.path().strip_prefix(files).unwrap_or(e.path()).display()
            );
        }
    }
    Ok(())
}

/// Relative link targets of a Markdown text: `](target)` without a scheme, anchor removed.
fn md_links(text: &str) -> Vec<String> {
    let mut out = vec![];
    let mut rest = text;
    while let Some(i) = rest.find("](") {
        rest = &rest[i + 2..];
        let end = rest.find([')', ' ', '\t', '\n']).unwrap_or(rest.len());
        let target = rest[..end].split('#').next().unwrap_or_default();
        let scheme = target
            .split_once(':')
            .is_some_and(|(s, _)| !s.is_empty() && s.chars().all(|c| c.is_ascii_alphabetic()));
        if !target.is_empty() && !scheme {
            out.push(target.to_string());
        }
    }
    out
}

/// `a/./b/../c` as `a/c`, without touching the disk.
fn normalize(p: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for c in p.components() {
        match c {
            Component::ParentDir => {
                out.pop();
            }
            Component::CurDir => {}
            c => out.push(c),
        }
    }
    out
}

/// Records a new revision: the files of `from` (when given) with `changes` applied on top, checked, then made live unless
/// it waits for review.
#[allow(clippy::too_many_arguments)]
fn commit(
    state: &Path,
    name: &str,
    scope: &str,
    from: Option<&Path>,
    changes: &Map<String, Value>,
    reason: &str,
    origin: Origin,
    make_live: bool,
) -> Result<u64> {
    let stem = crate::skills::file_stem(name);
    let hist = history(state, scope, &stem);
    let n = next_revision(&hist);
    let rev = hist.join(n.to_string());
    let files = rev.join("files");
    let made = (|| -> Result<()> {
        match from {
            Some(from) => copy_skill(from, &files)?,
            None => fs::create_dir_all(&files)?,
        }
        for (rel, content) in changes {
            let path = files.join(inside(rel)?);
            match content {
                Value::String(text) => {
                    if let Some(parent) = path.parent() {
                        fs::create_dir_all(parent)?;
                    }
                    fs::write(&path, text)?;
                }
                Value::Null if path.is_file() => fs::remove_file(&path)?,
                Value::Null => {}
                _ => bail!("{rel}: new content is a string, or null to delete the file"),
            }
        }
        let md = fs::read_to_string(files.join("SKILL.md")).context("a skill needs a SKILL.md")?;
        let (found, _) = crate::skills::front_matter(&md)
            .context("SKILL.md needs front matter with a name and a description")?;
        ensure!(found == name, "SKILL.md names `{found}`, not `{name}`");
        fits(&files)?; // the caps apply to the result too
        if origin == Origin::Agent {
            lint(&files)?;
        }
        Ok(())
    })();
    if let Err(e) = made {
        let _ = fs::remove_dir_all(&rev);
        return Err(e);
    }
    let at = time::OffsetDateTime::now_utc()
        .format(&time::format_description::well_known::Rfc3339)
        .unwrap_or_default();
    write_json(
        &rev.join("meta.json"),
        &json!({
            "revision": n, "at": at, "reason": reason,
            "by": if origin == Origin::Agent { "agent" } else { "user" },
            "status": if make_live { "live" } else { "pending" },
            "changed": changes.keys().collect::<Vec<_>>(),
        }),
    )?;
    if make_live {
        make_live_from(&files, &live(state, scope, &stem))?;
    }
    Ok(n)
}

fn make_live_from(files: &Path, target: &Path) -> Result<()> {
    if target.exists() {
        fs::remove_dir_all(target)?;
    }
    copy_skill(files, target)
}

/// A change that only touches Markdown: instructions, not code.
fn prose_only(changes: &Map<String, Value>) -> bool {
    changes.keys().all(|k| {
        Path::new(k)
            .extension()
            .is_some_and(|x| x.eq_ignore_ascii_case("md"))
    })
}

fn meta_path(state: &Path, scope: &str, stem: &str) -> PathBuf {
    history(state, scope, stem).join("skill.json")
}

/// Changes a skill in the agent layer. The first change copies the curated skill of that name, if any, as a revision of its
/// own; a skill with no curated original starts from `changes`, which must then hold its `SKILL.md`. `changes` maps a path
/// inside the skill folder to its new text, or to null to delete that file.
///
/// The user's change is live at once. An agent's change must also pass `lint`; when it touches anything but Markdown it is
/// kept as a pending revision, not served, until the user approves it, and no other agent change is taken meanwhile.
pub fn change(
    state: &Path,
    name: &str,
    scope: &str,
    changes: &Map<String, Value>,
    reason: &str,
    origin: Origin,
) -> Result<Value> {
    let stem = check(name, scope)?;
    ensure!(!changes.is_empty(), "no change given");
    ensure!(!reason.trim().is_empty(), "say why the skill changes");
    let meta_file = meta_path(state, scope, &stem);
    fs::create_dir_all(history(state, scope, &stem))?;
    let mut meta = read_json(&meta_file)
        .unwrap_or_else(|| json!({"name": name, "scope": scope, "dropped": true}));
    ensure!(
        origin == Origin::User || meta["pending"].is_null(),
        "a change to `{name}` that touches its scripts is waiting for the user's review; tell the user that `footnote skills approve {name}` or `reject` settles it"
    );
    let target = live(state, scope, &stem);
    let from = if meta["dropped"] == false && target.is_dir() {
        Some(target.clone())
    } else if let Some((theme, folder)) = curated(state, name) {
        let n = commit(
            state,
            name,
            scope,
            Some(&folder),
            &Map::new(),
            &format!("copied from the curated skill (theme {theme})"),
            Origin::User,
            true,
        )?;
        meta["base"] = json!(format!(
            "{name}@{}",
            sha256(&folder.join("SKILL.md")).unwrap_or_default()
        ));
        meta["base_path"] = json!(folder);
        meta["revision"] = json!(n);
        meta["dropped"] = json!(false);
        Some(target.clone())
    } else {
        None
    };
    let goes_live = origin == Origin::User || prose_only(changes);
    let n = commit(
        state,
        name,
        scope,
        from.as_deref(),
        changes,
        reason,
        origin,
        goes_live,
    )?;
    if goes_live {
        meta["revision"] = json!(n);
        meta["dropped"] = json!(false);
    } else {
        let base = if meta["dropped"] == false {
            meta["revision"].clone()
        } else {
            Value::Null
        };
        meta["pending"] = json!({"revision": n, "base_revision": base});
    }
    write_json(&meta_file, &meta)?;
    reindex(state)?;
    Ok(json!({
        "name": name, "scope": scope, "revision": n,
        "status": if goes_live { "live" } else { "pending" },
        "path": target.join("SKILL.md")
    }))
}

/// The user's change: live at once.
pub fn revise(
    state: &Path,
    name: &str,
    scope: &str,
    changes: &Map<String, Value>,
    reason: &str,
) -> Result<Value> {
    change(state, name, scope, changes, reason, Origin::User)
}

fn set_status(state: &Path, scope: &str, stem: &str, n: u64, status: &str) -> Result<()> {
    let path = history(state, scope, stem)
        .join(n.to_string())
        .join("meta.json");
    let mut m = read_json(&path).context("revision metadata")?;
    m["status"] = json!(status);
    write_json(&path, &m)
}

/// Serves the pending agent change to a skill. Refused when the live skill changed since the change was proposed.
pub fn approve(state: &Path, name: &str, scope: &str) -> Result<Value> {
    let stem = check(name, scope)?;
    let meta_file = meta_path(state, scope, &stem);
    let mut meta = read_json(&meta_file)
        .with_context(|| format!("no agent version of `{name}` for scope {scope}"))?;
    let pending = meta["pending"].clone();
    let n = pending["revision"]
        .as_u64()
        .with_context(|| format!("no change to `{name}` is waiting for review"))?;
    let live_now = if meta["dropped"] == false {
        meta["revision"].clone()
    } else {
        Value::Null
    };
    ensure!(
        pending["base_revision"] == live_now,
        "`{name}` changed since this edit was proposed; reject it (`footnote skills reject {name}`) and let the agent propose again"
    );
    let files = history(state, scope, &stem)
        .join(n.to_string())
        .join("files");
    make_live_from(&files, &live(state, scope, &stem))?;
    set_status(state, scope, &stem, n, "approved")?;
    meta["revision"] = json!(n);
    meta["dropped"] = json!(false);
    meta["pending"] = Value::Null;
    write_json(&meta_file, &meta)?;
    reindex(state)?;
    Ok(json!({"name": name, "scope": scope, "revision": n, "status": "approved"}))
}

/// Refuses the pending agent change to a skill; it stays in the history as rejected.
pub fn reject(state: &Path, name: &str, scope: &str) -> Result<Value> {
    let stem = check(name, scope)?;
    let meta_file = meta_path(state, scope, &stem);
    let mut meta = read_json(&meta_file)
        .with_context(|| format!("no agent version of `{name}` for scope {scope}"))?;
    let n = meta["pending"]["revision"]
        .as_u64()
        .with_context(|| format!("no change to `{name}` is waiting for review"))?;
    set_status(state, scope, &stem, n, "rejected")?;
    meta["pending"] = Value::Null;
    write_json(&meta_file, &meta)?;
    Ok(json!({"name": name, "scope": scope, "revision": n, "status": "rejected"}))
}

/// Agent changes waiting for the user's review, with what they change and why.
pub fn pending(state: &Path) -> Vec<Value> {
    all(state)
        .into_iter()
        .filter_map(|m| {
            let n = m["pending"]["revision"].as_u64()?;
            let (name, scope) = (m["name"].as_str()?, m["scope"].as_str()?);
            let rev = read_json(
                &history(state, scope, &crate::skills::file_stem(name))
                    .join(n.to_string())
                    .join("meta.json"),
            )?;
            Some(json!({
                "name": name, "scope": scope, "revision": n, "reason": rev["reason"], "changed": rev["changed"],
                "files": history(state, scope, &crate::skills::file_stem(name)).join(n.to_string()).join("files"),
            }))
        })
        .collect()
}

/// Every revision of a skill, oldest first, with the live one marked.
pub fn revisions(state: &Path, name: &str, scope: &str) -> Result<Value> {
    let stem = check(name, scope)?;
    let hist = history(state, scope, &stem);
    let meta = read_json(&meta_path(state, scope, &stem))
        .with_context(|| format!("no agent version of `{name}` for scope {scope}"))?;
    let mut list: Vec<Value> = fs::read_dir(&hist)?
        .filter_map(Result::ok)
        .filter_map(|e| read_json(&e.path().join("meta.json")))
        .collect();
    list.sort_by_key(|r| r["revision"].as_u64());
    Ok(json!({
        "name": name, "scope": scope, "live": if meta["dropped"] == true { Value::Null } else { meta["revision"].clone() },
        "base": meta["base"], "revisions": list
    }))
}

/// Makes revision `n` live again, as a new revision: nothing is deleted.
pub fn restore(state: &Path, name: &str, scope: &str, n: u64) -> Result<Value> {
    let stem = check(name, scope)?;
    let meta_file = meta_path(state, scope, &stem);
    let mut meta = read_json(&meta_file)
        .with_context(|| format!("no agent version of `{name}` for scope {scope}"))?;
    let files = history(state, scope, &stem)
        .join(n.to_string())
        .join("files");
    ensure!(files.is_dir(), "`{name}` has no revision {n}");
    let made = commit(
        state,
        name,
        scope,
        Some(&files),
        &Map::new(),
        &format!("restored revision {n}"),
        Origin::User,
        true,
    )?;
    meta["revision"] = json!(made);
    meta["dropped"] = json!(false);
    write_json(&meta_file, &meta)?;
    reindex(state)?;
    Ok(json!({"name": name, "scope": scope, "revision": made, "restored": n}))
}

/// Stops serving the agent version: the curated skill, if any, is served again. Revisions stay.
pub fn drop_version(state: &Path, name: &str, scope: &str) -> Result<Value> {
    let stem = check(name, scope)?;
    let meta_file = meta_path(state, scope, &stem);
    let mut meta = read_json(&meta_file)
        .with_context(|| format!("no agent version of `{name}` for scope {scope}"))?;
    let target = live(state, scope, &stem);
    if target.exists() {
        fs::remove_dir_all(&target)?;
    }
    meta["dropped"] = json!(true);
    write_json(&meta_file, &meta)?;
    reindex(state)?;
    Ok(json!({"name": name, "scope": scope, "dropped": true}))
}

/// Every agent skill's `skill.json`.
fn all(state: &Path) -> Vec<Value> {
    let mut out = vec![];
    for scope in fs::read_dir(root(state).join(".history"))
        .into_iter()
        .flatten()
        .filter_map(Result::ok)
    {
        for skill in fs::read_dir(scope.path())
            .into_iter()
            .flatten()
            .filter_map(Result::ok)
        {
            if let Some(m) = read_json(&skill.path().join("skill.json")) {
                out.push(m);
            }
        }
    }
    out.sort_by(|a, b| {
        (a["name"].as_str(), a["scope"].as_str()).cmp(&(b["name"].as_str(), b["scope"].as_str()))
    });
    out
}

/// The agent skills, with `behind` when the curated skill changed since it was copied.
pub fn list(state: &Path) -> Vec<Value> {
    all(state)
        .into_iter()
        .map(|m| {
            let behind = m["base_path"].as_str().is_some_and(|folder| {
                let now = sha256(&Path::new(folder).join("SKILL.md")).unwrap_or_default();
                m["base"]
                    .as_str()
                    .and_then(|b| b.rsplit_once('@'))
                    .is_none_or(|(_, hash)| hash != now)
            });
            json!({
                "name": m["name"], "scope": m["scope"], "revision": m["revision"],
                "dropped": m["dropped"], "behind": behind
            })
        })
        .collect()
}

/// The `SKILL.md` served for `name` in `project`: the project's agent version, else the one for every project.
pub fn serving(state: &Path, name: &str, project: &str) -> Option<PathBuf> {
    let stem = crate::skills::file_stem(name);
    [project, "global"].into_iter().find_map(|scope| {
        let md = live(state, scope, &stem).join("SKILL.md");
        let meta = read_json(&meta_path(state, scope, &stem))?;
        (meta["dropped"] == false && meta["name"] == name && md.is_file()).then_some(md)
    })
}

/// Rebuilds the `agent` theme from the live agent skills; with none, the theme is off.
fn reindex(state: &Path) -> Result<()> {
    crate::skills::clear_index(state, THEME)?;
    let mut found = Map::new();
    for m in all(state).into_iter().filter(|m| m["dropped"] == false) {
        let (Some(name), Some(scope)) = (m["name"].as_str(), m["scope"].as_str()) else {
            continue;
        };
        let md = live(state, scope, &crate::skills::file_stem(name)).join("SKILL.md");
        let Some((_, desc)) = fs::read_to_string(&md)
            .ok()
            .as_deref()
            .and_then(crate::skills::front_matter)
        else {
            continue;
        };
        found.insert(
            format!("{}--{}", scope_dir(scope), crate::skills::file_stem(name)),
            json!({"name": name, "path": md, "description": desc, "scope": scope}),
        );
    }
    ensure!(
        found.len() <= crate::skills::MAX_SKILLS,
        "the agent layer holds at most {} live skills: drop some first",
        crate::skills::MAX_SKILLS
    );
    let docs = root(state).join(".docs");
    if found.is_empty() {
        if docs.exists() {
            fs::remove_dir_all(&docs)?;
        }
        return Ok(());
    }
    crate::skills::write_theme(state, THEME, &docs, &found)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn skill_md(name: &str, desc: &str) -> String {
        format!("---\nname: {name}\ndescription: {desc}\n---\n# {name}\n")
    }

    fn changes(pairs: &[(&str, &str)]) -> Map<String, Value> {
        pairs
            .iter()
            .map(|(k, v)| (k.to_string(), json!(v)))
            .collect()
    }

    #[test]
    fn paths_must_stay_inside_the_skill() {
        assert!(inside("SKILL.md").is_ok());
        assert!(inside("scripts/check.mjs").is_ok());
        for bad in [
            "",
            "../x",
            "/etc/passwd",
            "C:/x",
            "C:\\x",
            "a/../../x",
            "./x",
        ] {
            assert!(inside(bad).is_err(), "{bad}");
        }
    }

    #[test]
    fn a_new_skill_needs_its_own_matching_skill_md() {
        let t = tempfile::tempdir().unwrap();
        let s = t.path();
        let err = revise(s, "fresh", "global", &changes(&[("notes.md", "x")]), "why").unwrap_err();
        assert!(err.to_string().contains("SKILL.md"), "{err}");
        let err = revise(
            s,
            "fresh",
            "global",
            &changes(&[("SKILL.md", &skill_md("other", "d"))]),
            "why",
        )
        .unwrap_err();
        assert!(err.to_string().contains("names `other`"), "{err}");
        // A refused change leaves no revision behind.
        assert_eq!(next_revision(&history(s, "global", "fresh")), 1);
        let ok = revise(
            s,
            "fresh",
            "global",
            &changes(&[("SKILL.md", &skill_md("fresh", "Do a fresh thing."))]),
            "why",
        )
        .unwrap();
        assert_eq!(ok["revision"], 1);
        assert_eq!(
            serving(s, "fresh", "any"),
            Some(live(s, "global", "fresh").join("SKILL.md"))
        );
    }

    #[test]
    fn restore_and_drop_keep_every_revision() {
        let t = tempfile::tempdir().unwrap();
        let s = t.path();
        let v1 = skill_md("tidy", "Tidy a repo.");
        let v2 = skill_md("tidy", "Tidy a repo, then run the tests.");
        revise(s, "tidy", "acme", &changes(&[("SKILL.md", &v1)]), "first").unwrap();
        revise(s, "tidy", "acme", &changes(&[("SKILL.md", &v2)]), "second").unwrap();
        let md = live(s, "acme", "tidy").join("SKILL.md");
        assert_eq!(fs::read_to_string(&md).unwrap(), v2);
        assert_eq!(restore(s, "tidy", "acme", 1).unwrap()["revision"], 3);
        assert_eq!(fs::read_to_string(&md).unwrap(), v1);
        assert_eq!(serving(s, "tidy", "acme"), Some(md.clone()));
        assert_eq!(serving(s, "tidy", "other"), None);
        drop_version(s, "tidy", "acme").unwrap();
        assert_eq!(serving(s, "tidy", "acme"), None);
        let r = revisions(s, "tidy", "acme").unwrap();
        assert_eq!(r["live"], Value::Null);
        assert_eq!(r["revisions"].as_array().unwrap().len(), 3);
        assert_eq!(restore(s, "tidy", "acme", 2).unwrap()["revision"], 4);
        assert_eq!(fs::read_to_string(&md).unwrap(), v2);
    }

    #[test]
    fn links_are_relative_targets_without_scheme_or_anchor() {
        let text = "See [a](references/a.md#top), [web](https://x.y), [mail](mailto:a@b), [up](../x.md) and [here](#h).";
        assert_eq!(md_links(text), vec!["references/a.md", "../x.md"]);
    }

    #[test]
    fn agent_changes_pass_lint_and_script_changes_wait() {
        let t = tempfile::tempdir().unwrap();
        let s = t.path();
        let base = skill_md("lintme", "Check things.");
        revise(
            s,
            "lintme",
            "global",
            &changes(&[("SKILL.md", &base)]),
            "first",
        )
        .unwrap();
        let agent =
            |c: &[(&str, &str)]| change(s, "lintme", "global", &changes(c), "why", Origin::Agent);
        let long = format!("{base}{}", "line\n".repeat(MAX_LINES));
        assert!(agent(&[("SKILL.md", &long)]).is_err());
        let escaping = format!("{base}[x](../../outside.md)\n");
        assert!(agent(&[("SKILL.md", &escaping)]).is_err());
        let linked = format!("{base}[x](references/x.md)\n");
        assert_eq!(
            agent(&[("SKILL.md", &linked), ("references/x.md", "detail")]).unwrap()["status"],
            "live"
        );
        let r = agent(&[("scripts/run.sh", "echo hi")]).unwrap();
        assert_eq!(r["status"], "pending");
        assert!(!live(s, "global", "lintme").join("scripts/run.sh").exists());
        assert!(
            agent(&[("SKILL.md", &linked)]).is_err(),
            "one pending change at a time"
        );
        // The user may still change the skill; the pending change then no longer applies.
        revise(
            s,
            "lintme",
            "global",
            &changes(&[("SKILL.md", &base)]),
            "user",
        )
        .unwrap();
        assert!(
            approve(s, "lintme", "global")
                .unwrap_err()
                .to_string()
                .contains("changed since")
        );
        reject(s, "lintme", "global").unwrap();
        assert!(pending(s).is_empty());
    }

    #[test]
    fn caps_refuse_a_huge_skill() {
        let t = tempfile::tempdir().unwrap();
        let big = "x".repeat(MAX_BYTES as usize + 1);
        let err = revise(
            t.path(),
            "big",
            "global",
            &changes(&[("SKILL.md", &skill_md("big", "d")), ("blob.txt", &big)]),
            "why",
        )
        .unwrap_err();
        assert!(err.to_string().contains("at most"), "{err}");
    }
}
