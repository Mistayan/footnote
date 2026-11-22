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

/// The most `SKILL.md` lines an agent's prose change may change and still go live without review (#470): the larger of
/// `REWRITE_FLOOR` and a `REWRITE_SHARE`th of the live file. Measured on the two edits of
/// `bench/experiments/SKILL-EDIT-COST-2026-11-21.md`: fixing the one wrong step changed 2 lines (1 out, 1 in), and the
/// unrelated step each session added made 3. The floor of 6 lets a fix to one step of up to 3 lines through; the quarter
/// holds back edits that rewrite much of a longer skill. A one-line unrelated addition still passes: the request text keeps
/// those out, and trials (#447) catch what does harm.
const REWRITE_FLOOR: usize = 6;
const REWRITE_SHARE: usize = 4;

fn rewrite_limit(live_lines: usize) -> usize {
    REWRITE_FLOOR.max(live_lines / REWRITE_SHARE)
}

/// A line as compared for the rewrite limit: trailing whitespace dropped, and a numbered list item's number replaced by
/// `#`, so renumbering the steps after an inserted one does not count as changing them.
fn compared(line: &str) -> String {
    let line = line.trim_end();
    let body = line.trim_start();
    let indent = &line[..line.len() - body.len()];
    let digits = body.len() - body.trim_start_matches(|c: char| c.is_ascii_digit()).len();
    let rest = &body[digits..];
    if digits > 0 && (rest.starts_with(". ") || rest.starts_with(") ")) {
        format!("{indent}#{rest}")
    } else {
        line.to_string()
    }
}

/// Lines removed plus lines added between two texts, by longest common subsequence on `compared` lines. Past the diff table
/// cap, every line counts as changed.
fn changed_lines(a: &str, b: &str) -> usize {
    let (a, b): (Vec<String>, Vec<String>) = (
        a.lines().map(compared).collect(),
        b.lines().map(compared).collect(),
    );
    if a.len().saturating_mul(b.len()) > DIFF_CELLS {
        return a.len() + b.len();
    }
    let mut row = vec![0usize; b.len() + 1];
    for x in &a {
        let mut diag = 0;
        for (j, y) in b.iter().enumerate() {
            let up = row[j + 1];
            row[j + 1] = if x == y { diag + 1 } else { up.max(row[j]) };
            diag = up;
        }
    }
    let common = row[b.len()];
    a.len() + b.len() - 2 * common
}

/// When an agent's change rewrites more of the live `SKILL.md` than `rewrite_limit` allows: what it changes, and the limit.
fn rewrite(from: Option<&Path>, changes: &Map<String, Value>) -> Option<Value> {
    let new = changes.iter().find_map(|(k, v)| {
        inside(k)
            .is_ok_and(|p| p == Path::new("SKILL.md"))
            .then(|| v.as_str())
            .flatten()
    })?;
    let old = fs::read_to_string(from?.join("SKILL.md")).ok()?;
    let (n, limit) = (changed_lines(&old, new), rewrite_limit(old.lines().count()));
    (n > limit).then(|| json!({"changed_lines": n, "limit": limit, "lines": old.lines().count()}))
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
/// The user's change is live at once. An agent's change must also pass `lint`; when it touches anything but Markdown, or
/// changes more of `SKILL.md` than `rewrite_limit` allows, it is kept as a pending revision, not served, until the user
/// approves it, and no other agent change is taken meanwhile.
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
    // An agent's prose change that rewrites more than the step it was asked to fix waits for review, like a script (#470).
    let held = (origin == Origin::Agent)
        .then(|| rewrite(from.as_deref(), changes))
        .flatten();
    let goes_live = origin == Origin::User || (prose_only(changes) && held.is_none());
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
        if let Some(held) = &held {
            let rev_meta = history(state, scope, &stem)
                .join(n.to_string())
                .join("meta.json");
            if let Some(mut m) = read_json(&rev_meta) {
                m["rewrite"] = held.clone();
                write_json(&rev_meta, &m)?;
            }
        }
    }
    write_json(&meta_file, &meta)?;
    reindex(state)?;
    let mut out = json!({
        "name": name, "scope": scope, "revision": n,
        "status": if goes_live { "live" } else { "pending" },
        "path": target.join("SKILL.md")
    });
    if let Some(held) = held {
        out["rewrite"] = held;
    }
    Ok(out)
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
                "at": rev["at"], "by": rev["by"], "rewrite": rev["rewrite"],
                "files": history(state, scope, &crate::skills::file_stem(name)).join(n.to_string()).join("files"),
            }))
        })
        .collect()
}

/// Lines of context kept around each change, the most lines shown per file, and the largest table the line diff builds.
const DIFF_CONTEXT: usize = 3;
const DIFF_LINES: usize = 400;
const DIFF_CELLS: usize = 4_000_000;
/// The longest folded run that keeps its lines for unfolding; a longer one is only counted.
const DIFF_FOLD: usize = 500;

/// What the pending change to a skill changes, line by line, against the revision it would replace (#472): the review the
/// user does before `approve`, in the window or the terminal. Text files only; a binary or very large file is named with
/// a note to open the folder.
pub fn diff(state: &Path, name: &str, scope: &str) -> Result<Value> {
    let stem = check(name, scope)?;
    let meta = read_json(&meta_path(state, scope, &stem))
        .with_context(|| format!("no agent version of `{name}` for scope {scope}"))?;
    let n = meta["pending"]["revision"]
        .as_u64()
        .with_context(|| format!("no change to `{name}` is waiting for review"))?;
    let hist = history(state, scope, &stem);
    let new = hist.join(n.to_string()).join("files");
    let old = meta["pending"]["base_revision"]
        .as_u64()
        .map(|b| hist.join(b.to_string()).join("files"));
    let rev = read_json(&hist.join(n.to_string()).join("meta.json")).unwrap_or_default();
    let mut files = Vec::new();
    for rel in rev["changed"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
    {
        let Ok(path) = inside(rel) else { continue };
        let before = old.as_ref().and_then(|d| fs::read(d.join(&path)).ok());
        let after = fs::read(new.join(&path)).ok();
        let status = match (&before, &after) {
            (None, Some(_)) => "added",
            (Some(_), None) => "removed",
            _ => "changed",
        };
        let text =
            |v: Option<Vec<u8>>| v.map_or(Some(String::new()), |b| String::from_utf8(b).ok());
        let lines = match (text(before), text(after)) {
            (Some(a), Some(b)) => {
                line_diff(&a, &b).ok_or("too large to show here; open the folder")
            }
            _ => Err("not text; open the folder"),
        };
        files.push(match lines {
            Ok(lines) => json!({"file": rel, "status": status, "lines": lines}),
            Err(note) => json!({"file": rel, "status": status, "lines": [], "note": note}),
        });
    }
    Ok(json!({
        "name": name, "scope": scope, "revision": n, "base_revision": meta["pending"]["base_revision"],
        "folder": new, "files": files
    }))
}

/// A line diff by longest common subsequence: `{op, text, old, new}` with op " ", "-" or "+" and each side's line number
/// (null on the side without the line), runs of unchanged lines far from a
/// change folded into one "…" line. `None` when the files are too large for the table.
fn line_diff(a: &str, b: &str) -> Option<Vec<Value>> {
    let (a, b): (Vec<&str>, Vec<&str>) = (a.lines().collect(), b.lines().collect());
    if a.len().saturating_mul(b.len()) > DIFF_CELLS {
        return None;
    }
    let w = b.len() + 1;
    let mut t = vec![0u32; (a.len() + 1) * w];
    for i in (0..a.len()).rev() {
        for j in (0..b.len()).rev() {
            t[i * w + j] = if a[i] == b[j] {
                t[(i + 1) * w + j + 1] + 1
            } else {
                t[(i + 1) * w + j].max(t[i * w + j + 1])
            };
        }
    }
    // (op, text, line in the old file, line in the new file), lines counted from 1.
    let mut ops: Vec<(&str, &str, Option<usize>, Option<usize>)> = Vec::new();
    let (mut i, mut j) = (0, 0);
    while i < a.len() || j < b.len() {
        if i < a.len() && j < b.len() && a[i] == b[j] {
            ops.push((" ", a[i], Some(i + 1), Some(j + 1)));
            (i, j) = (i + 1, j + 1);
        } else if i < a.len() && (j == b.len() || t[(i + 1) * w + j] >= t[i * w + j + 1]) {
            ops.push(("-", a[i], Some(i + 1), None));
            i += 1;
        } else {
            ops.push(("+", b[j], None, Some(j + 1)));
            j += 1;
        }
    }
    let near = |k: usize| {
        ops[k.saturating_sub(DIFF_CONTEXT)..(k + DIFF_CONTEXT + 1).min(ops.len())]
            .iter()
            .any(|(op, ..)| *op != " ")
    };
    let line = |(op, text, old, new): &(&str, &str, Option<usize>, Option<usize>)| json!({"op": op, "text": text, "old": old, "new": new});
    // A folded run keeps its lines (up to DIFF_FOLD) so the reviewer can unfold the context around a change.
    let fold = |run: &[(&str, &str, Option<usize>, Option<usize>)]| {
        let n = run.len();
        let mut v = json!({"op": "…", "text": format!("{n} unchanged line{}", if n == 1 { "" } else { "s" })});
        if n <= DIFF_FOLD {
            v["lines"] = run.iter().map(line).collect();
        } else {
            v["text"] = json!(format!(
                "{n} unchanged lines (open the folder to read them)"
            ));
        }
        v
    };
    let mut out = Vec::new();
    let mut skipped = 0;
    for (k, (op, text, old, new)) in ops.iter().enumerate() {
        if *op == " " && !near(k) {
            skipped += 1;
            continue;
        }
        if skipped > 0 {
            out.push(fold(&ops[k - skipped..k]));
            skipped = 0;
        }
        if out.len() >= DIFF_LINES {
            out.push(json!({"op": "…", "text": "more changes: open the folder"}));
            return Some(out);
        }
        out.push(line(&(*op, *text, *old, *new)));
    }
    if skipped > 0 {
        out.push(fold(&ops[ops.len() - skipped..]));
    }
    Some(out)
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

    /// The skill and the two agent edits measured in `bench/experiments/SKILL-EDIT-COST-2026-11-21.md` (script path cut).
    const FADE: &str = "---\nname: css-fade\ndescription: Add a fade transition to dropdowns and menus in plain CSS.\n---\n# Add a fade to a dropdown or menu\n\n1. On the closed element set `opacity: 0` and `transition: opacity 160ms ease` (the shorthand).\n2. On the open state (for example `.dropdown.open`) set `opacity: 1`.\n3. Check the file: `node skills/css-fade/scripts/check.mjs <css file>`. It must print OK.\n";
    const FADE_SMALL: &str = "---\nname: css-fade\ndescription: Add a fade transition to dropdowns and menus in plain CSS.\n---\n# Add a fade to a dropdown or menu\n\n1. On the closed element set `opacity: 0` and `transition: opacity 160ms ease` (the shorthand), and also add a separate longhand `transition-duration: 160ms;` line right after it. The check script requires a standalone `transition-duration` declaration and fails on the shorthand alone.\n2. On the open state (for example `.dropdown.open`) set `opacity: 1`.\n3. Optionally add a `@media (prefers-reduced-motion: reduce)` rule that sets `transition: none` on the element.\n4. Check the file: `node skills/css-fade/scripts/check.mjs <css file>`. It must print OK.\n";
    const FADE_LARGE: &str = "---\nname: css-fade\ndescription: Add a fade transition to dropdowns and menus in plain CSS.\n---\n# Add a fade to a dropdown or menu\n\n1. On the closed element set `opacity: 0` and the transition as longhands, not the shorthand: `transition-property: opacity;`, `transition-duration: 160ms;`, `transition-timing-function: ease;`. The check script looks for a `transition-duration` declaration and fails on `transition: opacity 160ms ease`.\n2. On the open state (for example `.dropdown.open`) set `opacity: 1`.\n3. If the closed element is not hidden with `display: none`, also set `pointer-events: none` when closed and `pointer-events: auto` when open, so an invisible menu does not catch clicks.\n4. Check the file: `node skills/css-fade/scripts/check.mjs <css file>`. It must print OK.\n";

    #[test]
    fn changed_lines_ignore_renumbering_and_trailing_whitespace() {
        assert_eq!(changed_lines("a\nb\nc\n", "a\nb\nc\n"), 0);
        assert_eq!(changed_lines("a\nb\n", "a  \nb\t\n"), 0);
        assert_eq!(changed_lines("a\nb\nc\n", "a\nB\nc\n"), 2);
        assert_eq!(changed_lines("a\n", "a\nb\n"), 1);
        // Inserting step 2 renumbers the old step 2: only the new line counts.
        assert_eq!(
            changed_lines("1. one\n2. two\n", "1. one\n2. new\n3. two\n"),
            1
        );
        assert_eq!(compared("  12) step "), "  #) step");
        assert_eq!(
            compared("2024. was a year"),
            "2024. was a year".replace("2024", "#")
        );
        assert_eq!(compared("1.5 litres"), "1.5 litres");
        // The measured edits: the fix (1 out, 1 in) plus the unrelated step each one added.
        assert_eq!(changed_lines(FADE, FADE_SMALL), 3);
        assert_eq!(changed_lines(FADE, FADE_LARGE), 3);
    }

    #[test]
    fn the_rewrite_limit_has_a_floor_and_a_share() {
        assert_eq!(rewrite_limit(9), 6);
        assert_eq!(rewrite_limit(24), 6);
        assert_eq!(rewrite_limit(100), 25);
        assert_eq!(rewrite_limit(500), 125);
    }

    #[test]
    fn an_agent_rewrite_over_the_limit_waits_for_review_and_a_step_fix_goes_live() {
        let t = tempfile::tempdir().unwrap();
        let s = t.path();
        let base = skill_md("rewrite", "Check things.");
        let body: String = (1..=8).map(|i| format!("{i}. Step {i}.\n")).collect();
        let v1 = format!("{base}{body}");
        change(
            s,
            "rewrite",
            "global",
            &changes(&[("SKILL.md", &v1)]),
            "start",
            Origin::User,
        )
        .unwrap();
        let lines = v1.lines().count();
        assert_eq!(rewrite_limit(lines), REWRITE_FLOOR);

        // The measured edits stay live: 3 changed lines.
        let fix = v1
            .replace("2. Step 2.", "2. Step 2, done right.")
            .replace("4. Step 4.", "4. Step 4.\n5. Extra.");
        assert_eq!(changed_lines(&v1, &fix), 3);
        let r = agent_edit(s, "rewrite", &fix);
        assert_eq!(r["status"], "live", "{r}");
        assert!(r["rewrite"].is_null());

        // Exactly at the limit: live. One line over: pending, never served.
        let at: String = fix
            .replace("1. Step 1.", "1. One.")
            .replace("3. Step 3.", "3. Three.")
            .replace("Extra.", "Extra!");
        assert_eq!(changed_lines(&fix, &at), REWRITE_FLOOR);
        assert_eq!(agent_edit(s, "rewrite", &at)["status"], "live");
        let over = at
            .replace("Step 5.", "Five.")
            .replace("Step 6.", "Six.")
            .replace("Step 7.", "Seven.")
            .replace("Step 8.", "Eight.");
        assert_eq!(changed_lines(&at, &over), REWRITE_FLOOR + 2);
        let r = agent_edit(s, "rewrite", &over);
        assert_eq!(r["status"], "pending", "{r}");
        assert_eq!(r["rewrite"]["changed_lines"], REWRITE_FLOOR + 2);
        assert_eq!(r["rewrite"]["limit"], REWRITE_FLOOR);
        let served = live(s, "global", "rewrite").join("SKILL.md");
        assert_eq!(fs::read_to_string(&served).unwrap(), at);
        assert_eq!(pending(s)[0]["rewrite"]["changed_lines"], REWRITE_FLOOR + 2);

        // The user approves it: served.
        approve(s, "rewrite", "global").unwrap();
        assert_eq!(fs::read_to_string(&served).unwrap(), over);
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

    #[test]
    fn line_diff_keeps_changes_with_context_and_folds_the_rest() {
        let ops = |v: &[Value]| {
            v.iter()
                .map(|l| l["op"].as_str().unwrap().to_string())
                .collect::<String>()
        };
        let a: String = (1..=20).map(|i| format!("l{i}\n")).collect();
        let b = a.replace("l10\n", "ten\n");
        let d = line_diff(&a, &b).unwrap();
        // 6 unchanged folded, 3 context, the change, 3 context, 7 folded.
        assert_eq!(ops(&d), "…   -+   …");
        assert_eq!(d[0]["text"], "6 unchanged lines");
        // A fold keeps its lines, numbered, for unfolding.
        let hidden = d[0]["lines"].as_array().unwrap();
        assert_eq!(hidden.len(), 6);
        assert_eq!(
            (hidden[0]["text"].as_str(), hidden[0]["old"].as_u64()),
            (Some("l1"), Some(1))
        );
        assert_eq!(d[9]["lines"].as_array().map(Vec::len), Some(7));
        assert_eq!(
            (d[4]["text"].as_str(), d[5]["text"].as_str()),
            (Some("l10"), Some("ten"))
        );
        // Line numbers on each side; null on the side without the line.
        assert_eq!(
            (d[4]["old"].as_u64(), d[4]["new"].as_u64()),
            (Some(10), None)
        );
        assert_eq!(
            (d[5]["old"].as_u64(), d[5]["new"].as_u64()),
            (None, Some(10))
        );
        assert_eq!(
            (d[6]["old"].as_u64(), d[6]["new"].as_u64()),
            (Some(11), Some(11))
        );
        assert_eq!(ops(&line_diff("", "x\ny\n").unwrap()), "++");
        assert_eq!(ops(&line_diff("same\n", "same\n").unwrap()), "…");
        let huge = "x\n".repeat(2_001);
        assert!(line_diff(&huge, &huge).is_none(), "over the table cap");
    }

    #[test]
    fn diff_shows_the_pending_change_against_what_it_replaces() {
        let t = tempfile::tempdir().unwrap();
        let s = t.path();
        let md = skill_md("differ", "Check things.");
        revise(
            s,
            "differ",
            "global",
            &changes(&[("SKILL.md", &md), ("scripts/run.sh", "echo a\necho b\n")]),
            "first",
        )
        .unwrap();
        assert!(diff(s, "differ", "global").is_err(), "nothing pending");
        let r = change(
            s,
            "differ",
            "global",
            &changes(&[
                ("scripts/run.sh", "echo a\necho c\n"),
                ("scripts/new.sh", "true\n"),
            ]),
            "why",
            Origin::Agent,
        )
        .unwrap();
        assert_eq!(r["status"], "pending");
        let d = diff(s, "differ", "global").unwrap();
        assert_eq!(d["revision"], r["revision"]);
        assert!(
            Path::new(d["folder"].as_str().unwrap())
                .join("scripts/run.sh")
                .is_file()
        );
        let file = |f: &str| {
            d["files"]
                .as_array()
                .unwrap()
                .iter()
                .find(|x| x["file"] == f)
                .unwrap()
                .clone()
        };
        let run = file("scripts/run.sh");
        assert_eq!(run["status"], "changed");
        let lines: Vec<String> = run["lines"]
            .as_array()
            .unwrap()
            .iter()
            .map(|l| {
                format!(
                    "{}{}",
                    l["op"].as_str().unwrap(),
                    l["text"].as_str().unwrap()
                )
            })
            .collect();
        assert_eq!(lines, [" echo a", "-echo b", "+echo c"]);
        assert_eq!(file("scripts/new.sh")["status"], "added");
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
