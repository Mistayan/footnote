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
    let live_before = if meta["dropped"] == false {
        meta["revision"].clone()
    } else {
        Value::Null
    };
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
        // An agent's edit is on trial against what it replaced (#447); the user's own change ends any trial.
        meta["trial"] = trial(origin == Origin::Agent, n, &live_before);
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
    meta["trial"] = trial(true, n, &live_now);
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
    restore_as(state, name, scope, n, &format!("restored revision {n}"))
}

fn restore_as(state: &Path, name: &str, scope: &str, n: u64, reason: &str) -> Result<Value> {
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
        reason,
        Origin::User,
        true,
    )?;
    meta["revision"] = json!(made);
    meta["dropped"] = json!(false);
    meta["trial"] = Value::Null;
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
    meta["trial"] = Value::Null;
    write_json(&meta_file, &meta)?;
    reindex(state)?;
    Ok(json!({"name": name, "scope": scope, "dropped": true}))
}

/// A trial for revision `n` against the revision it replaced, when `on` and there was one; else none.
fn trial(on: bool, n: u64, previous: &Value) -> Value {
    if on && previous.is_u64() {
        json!({"revision": n, "previous": previous})
    } else {
        Value::Null
    }
}

/// Suggestions, reads, script runs and script failures in a set of outcome rows.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct Tally {
    suggested: u64,
    read: u64,
    runs: u64,
    failures: u64,
}

impl Tally {
    fn of<'a>(rows: impl IntoIterator<Item = &'a Value>) -> Self {
        let mut t = Self::default();
        for r in rows {
            match r["event"].as_str() {
                Some("suggested") => t.suggested += 1,
                Some("read") => t.read += 1,
                Some("run") => {
                    t.runs += 1;
                    t.failures += u64::from(r["ok"] == false);
                }
                _ => {}
            }
        }
        t
    }
    fn read_rate(self) -> f64 {
        if self.suggested == 0 {
            0.0
        } else {
            self.read as f64 / self.suggested as f64
        }
    }
    fn failure_rate(self) -> f64 {
        if self.runs == 0 {
            0.0
        } else {
            self.failures as f64 / self.runs as f64
        }
    }
    fn json(self) -> Value {
        json!({"suggested": self.suggested, "read": self.read, "runs": self.runs, "failures": self.failures})
    }
}

/// The rows of the last `uses` suggestions among `rows` (oldest first), with what followed each.
fn last_uses(rows: Vec<&Value>, uses: u64) -> Vec<&Value> {
    let starts: Vec<usize> = rows
        .iter()
        .enumerate()
        .filter(|(_, r)| r["event"] == "suggested")
        .map(|(i, _)| i)
        .collect();
    let from = starts
        .len()
        .checked_sub(uses as usize)
        .map_or(0, |skip| starts[skip]);
    rows.into_iter().skip(from).collect()
}

/// Ends each trial whose revision was suggested `uses` times (#447). It compares those suggestions with the last `uses` of
/// the revision it replaced (of the curated skill when that was the copy) and rolls back, as a new revision, when the
/// agent's revision fails scripts more often or is read less than half as often. Returns what it decided. With so few
/// uses this is a guardrail against clear regressions, not a statistical test.
pub fn end_trials(state: &Path, uses: u64) -> Result<Vec<Value>> {
    let on_trial: Vec<Value> = all(state)
        .into_iter()
        .filter(|m| m["trial"].is_object())
        .collect();
    if on_trial.is_empty() {
        return Ok(vec![]);
    }
    let log = fs::read_to_string(crate::skill_outcomes::log_path(state)).unwrap_or_default();
    let rows: Vec<Value> = log
        .lines()
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect();
    let mut decided = vec![];
    for m in on_trial {
        let (Some(name), Some(scope)) = (m["name"].as_str(), m["scope"].as_str()) else {
            continue;
        };
        let (Some(n), Some(prev)) = (
            m["trial"]["revision"].as_u64(),
            m["trial"]["previous"].as_u64(),
        ) else {
            continue;
        };
        let stem = crate::skills::file_stem(name);
        let mine = |r: &&Value| r["skill"] == name && (scope == "global" || r["project"] == scope);
        let new: Vec<&Value> = rows
            .iter()
            .filter(mine)
            .filter(|r| r["rev"] == n && r["scope"] == scope)
            .collect();
        let tried = Tally::of(new.iter().copied());
        if tried.suggested < uses {
            continue;
        }
        // The copy of a curated skill was never served on its own: its baseline is the curated skill.
        let copy = read_json(
            &history(state, scope, &stem)
                .join(prev.to_string())
                .join("meta.json"),
        )
        .and_then(|r| {
            r["reason"]
                .as_str()
                .map(|s| s.starts_with("copied from the curated skill"))
        })
        .unwrap_or(false);
        let base_rows: Vec<&Value> = rows
            .iter()
            .filter(mine)
            .filter(|r| {
                if copy {
                    r["rev"].is_null()
                } else {
                    r["rev"] == prev && r["scope"] == scope
                }
            })
            .collect();
        let base = Tally::of(last_uses(base_rows, uses));
        let worse = base.suggested > 0
            && (tried.failure_rate() > base.failure_rate()
                || tried.read_rate() < base.read_rate() / 2.0);
        let verdict = if base.suggested == 0 {
            "kept, no baseline"
        } else if worse {
            "rolled back"
        } else {
            "kept"
        };
        let result = json!({"verdict": verdict, "uses": uses, "revision": tried.json(), "previous": base.json()});
        let rev_meta = history(state, scope, &stem)
            .join(n.to_string())
            .join("meta.json");
        if let Some(mut r) = read_json(&rev_meta) {
            r["trial"] = result.clone();
            write_json(&rev_meta, &r)?;
        }
        if worse {
            restore_as(
                state,
                name,
                scope,
                prev,
                &format!("rolled back revision {n} after its trial"),
            )?;
        } else {
            let meta_file = meta_path(state, scope, &stem);
            if let Some(mut meta) = read_json(&meta_file) {
                meta["trial"] = Value::Null;
                write_json(&meta_file, &meta)?;
            }
        }
        decided.push(json!({"name": name, "scope": scope, "trial": result}));
    }
    Ok(decided)
}

/// Trials in progress: skill, scope, the revision on trial and the one it replaced.
pub fn trials(state: &Path) -> Vec<Value> {
    all(state)
        .into_iter()
        .filter(|m| m["trial"].is_object())
        .map(|m| json!({"name": m["name"], "scope": m["scope"], "revision": m["trial"]["revision"], "previous": m["trial"]["previous"]}))
        .collect()
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

/// The agent version served for `name` in `project`: the project's, else the one for every project, as its `SKILL.md`,
/// scope and live revision.
pub fn serving(state: &Path, name: &str, project: &str) -> Option<(PathBuf, String, u64)> {
    let stem = crate::skills::file_stem(name);
    [project, "global"].into_iter().find_map(|scope| {
        let md = live(state, scope, &stem).join("SKILL.md");
        let meta = read_json(&meta_path(state, scope, &stem))?;
        let rev = meta["revision"].as_u64()?;
        (meta["dropped"] == false && meta["name"] == name && md.is_file())
            .then(|| (md, scope.to_string(), rev))
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
            Some((
                live(s, "global", "fresh").join("SKILL.md"),
                "global".into(),
                1
            ))
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
        assert_eq!(
            serving(s, "tidy", "acme"),
            Some((md.clone(), "acme".into(), 3))
        );
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

    /// `n` suggestions of `name` served as `rev` (None: the curated skill), each read, with one script run each; the first
    /// `fail` runs fail.
    fn uses(s: &Path, name: &str, rev: Option<u64>, n: usize, fail: usize) {
        fs::create_dir_all(s.join("memory-hook")).unwrap();
        let w = crate::skill_outcomes::Watch {
            name: name.into(),
            theme: "t".into(),
            scope: rev.map(|_| "global".into()),
            rev,
            ..Default::default()
        };
        for i in 0..n {
            crate::skill_outcomes::append(s, "p", &w, "suggested", None);
            crate::skill_outcomes::append(s, "p", &w, "read", None);
            crate::skill_outcomes::append(s, "p", &w, "run", Some(i >= fail));
        }
    }

    fn agent_edit(s: &Path, name: &str, text: &str) -> Value {
        change(
            s,
            name,
            "global",
            &changes(&[("SKILL.md", text)]),
            "the skill missed a step",
            Origin::Agent,
        )
        .unwrap()
    }

    #[test]
    fn a_trial_rolls_back_an_edit_that_fails_more_and_keeps_one_that_does_not() {
        let t = tempfile::tempdir().unwrap();
        let s = t.path();
        let v1 = skill_md("trial", "Check things.");
        let v2 = format!("{v1}Also check the other thing.\n");
        revise(s, "trial", "global", &changes(&[("SKILL.md", &v1)]), "user").unwrap();
        uses(s, "trial", Some(1), 5, 0);
        assert_eq!(agent_edit(s, "trial", &v2)["revision"], 2);
        assert_eq!(trials(s).len(), 1);
        uses(s, "trial", Some(2), 3, 1);
        assert!(end_trials(s, 5).unwrap().is_empty(), "not enough uses yet");
        uses(s, "trial", Some(2), 2, 2);
        let d = end_trials(s, 5).unwrap();
        assert_eq!(d[0]["trial"]["verdict"], "rolled back", "{d:?}");
        assert_eq!(d[0]["trial"]["revision"]["failures"], 3);
        let md = live(s, "global", "trial").join("SKILL.md");
        assert_eq!(fs::read_to_string(&md).unwrap(), v1);
        assert!(trials(s).is_empty());
        let revs = revisions(s, "trial", "global").unwrap();
        assert_eq!(revs["live"], 3);
        assert_eq!(revs["revisions"][1]["trial"]["verdict"], "rolled back");

        // A good edit stays. Baseline: the last 5 uses of revision 3, which never failed.
        uses(s, "trial", Some(3), 5, 0);
        assert_eq!(agent_edit(s, "trial", &v2)["revision"], 4);
        uses(s, "trial", Some(4), 5, 0);
        assert_eq!(end_trials(s, 5).unwrap()[0]["trial"]["verdict"], "kept");
        assert_eq!(fs::read_to_string(&md).unwrap(), v2);
        assert!(trials(s).is_empty());
    }

    #[test]
    fn a_first_edit_is_judged_against_the_curated_skill_and_the_user_can_end_a_trial() {
        let t = tempfile::tempdir().unwrap();
        let s = t.path();
        let curated = s.join("curated").join("trial");
        fs::create_dir_all(&curated).unwrap();
        let v1 = skill_md("trial", "Check things.");
        fs::write(curated.join("SKILL.md"), &v1).unwrap();
        crate::skills::index(s, "web", &[s.join("curated")]).unwrap();
        uses(s, "trial", None, 5, 0); // the curated skill, before any copy
        let r = agent_edit(s, "trial", &format!("{v1}More.\n"));
        assert_eq!(r["revision"], 2, "revision 1 is the copy");
        uses(s, "trial", Some(2), 5, 0);
        assert_eq!(
            end_trials(s, 5).unwrap()[0]["trial"]["previous"]["suggested"],
            5
        );

        // The user's own change ends a trial without a verdict.
        agent_edit(s, "trial", &format!("{v1}Even more.\n"));
        assert_eq!(trials(s).len(), 1);
        revise(s, "trial", "global", &changes(&[("SKILL.md", &v1)]), "user").unwrap();
        assert!(trials(s).is_empty());
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
