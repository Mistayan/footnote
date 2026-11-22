//! Update and rollback of the installed binary (#126). Data lives in the state folder, apart from the binary, so neither
//! touches it. The binary being replaced is kept beside the new one as `<name>.replaced-<time>`; only the newest such copy is
//! kept (one a running daemon still uses cannot be removed and is left for later). Windows lets a running binary be renamed,
//! which is what makes updating in place possible.
use anyhow::{Context, Result, bail, ensure};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};

fn stamp() -> String {
    let t = time::OffsetDateTime::now_utc();
    format!(
        "{:04}{:02}{:02}{:02}{:02}{:02}",
        t.year(),
        t.month() as u8,
        t.day(),
        t.hour(),
        t.minute(),
        t.second()
    )
}

/// The replaced copies beside `exe`, newest first (the time in their name sorts them).
fn replaced(exe: &Path) -> Result<Vec<PathBuf>> {
    let name = exe
        .file_name()
        .context("binary name")?
        .to_string_lossy()
        .into_owned();
    let prefix = format!("{name}.replaced-");
    let mut found: Vec<PathBuf> = std::fs::read_dir(exe.parent().context("binary folder")?)?
        .flatten()
        .map(|e| e.path())
        .filter(|p| {
            p.file_name()
                .is_some_and(|n| n.to_string_lossy().starts_with(&prefix))
        })
        .collect();
    found.sort();
    found.reverse();
    Ok(found)
}

/// Replace the running binary with `from`, after checking that `from` is a Footnote binary that runs.
pub fn update(from: &Path) -> Result<Value> {
    let exe = std::env::current_exe()?;
    let out = std::process::Command::new(from)
        .arg("--version")
        .output()
        .with_context(|| format!("cannot run {}", from.display()))?;
    let version = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if !out.status.success() || !version.starts_with("footnote ") {
        bail!("{} is not a Footnote binary that runs", from.display());
    }
    let warning = lacks_llama(from).then_some(
        "the new binary has no llama.cpp, and Memory is configured with a GGUF model: recall will rank by keyword only and new memories get no vectors. Install a release build, or build with `--features llama` (CONTRIBUTING.md)"
    );
    let keep = exe.with_file_name(format!(
        "{}.replaced-{}",
        exe.file_name().context("binary name")?.to_string_lossy(),
        stamp()
    ));
    std::fs::rename(&exe, &keep).context("set the current binary aside")?;
    if let Err(e) = std::fs::copy(from, &exe) {
        let _ = std::fs::rename(&keep, &exe); // put the old one back
        return Err(e).context("copy the new binary into place");
    }
    // Keep only the newest replaced copy; one still in use stays until a later update.
    for old in replaced(&exe)?.into_iter().skip(1) {
        let _ = std::fs::remove_file(old);
    }
    Ok(
        json!({"updated": exe, "version": version, "previous": keep, "warning": warning, "note": "`footnote rollback` puts the previous binary back; data in the state folder is not touched"}),
    )
}

/// #515: Memory is configured with a GGUF model and `from` says (in `models list`) it has no llama.cpp. A binary too old to
/// say gives no warning.
fn lacks_llama(from: &Path) -> bool {
    let Ok(state) = crate::state::state_dir() else {
        return false;
    };
    let models: Vec<PathBuf> = footnote_core::config::product_settings(&state, "memory")
        .ok()
        .and_then(|s| serde_json::from_value(s["models"].clone()).ok())
        .unwrap_or_default();
    if !models.iter().any(|m| m.join("model.gguf").exists()) {
        return false;
    }
    let Ok(out) = std::process::Command::new(from)
        .args(["models", "list"])
        .output()
    else {
        return false;
    };
    serde_json::from_slice::<Value>(&out.stdout).is_ok_and(|v| v["llama"] == json!(false))
}

const LATEST: &str = "https://api.github.com/repos/bobcat88/footnote/releases/latest";

/// `0.1.0-alpha.3` as comparable parts: the numbers, then the pre-release (none sorts after any pre-release).
fn parse(v: &str) -> (Vec<u64>, Option<Vec<String>>) {
    let v = v.trim().trim_start_matches('v');
    let (core, pre) = v.split_once('-').map_or((v, None), |(c, p)| (c, Some(p)));
    let nums = core.split('.').map(|n| n.parse().unwrap_or(0)).collect();
    (
        nums,
        pre.map(|p| p.split('.').map(str::to_string).collect()),
    )
}

/// Whether `latest` is a later version than `current` (semantic versioning, pre-releases included).
fn newer(latest: &str, current: &str) -> bool {
    let (ln, lp) = parse(latest);
    let (cn, cp) = parse(current);
    if ln != cn {
        return ln > cn;
    }
    match (lp, cp) {
        (None, Some(_)) => true,
        (Some(_), None) | (None, None) => false,
        (Some(l), Some(c)) => {
            for (a, b) in l.iter().zip(&c) {
                let ord = match (a.parse::<u64>(), b.parse::<u64>()) {
                    (Ok(x), Ok(y)) => x.cmp(&y),
                    _ => a.cmp(b),
                };
                if ord != std::cmp::Ordering::Equal {
                    return ord.is_gt();
                }
            }
            l.len() > c.len()
        }
    }
}

fn get_text(url: &str) -> Result<String> {
    let mut r = crate::models::agent()
        .get(url)
        .header("User-Agent", "footnote-update")
        .header("Accept", "application/vnd.github+json")
        .call()
        .with_context(|| format!("read {url}"))?;
    Ok(r.body_mut().read_to_string()?)
}

/// The latest release and its Windows installer asset.
fn latest() -> Result<(String, Value, Option<Value>)> {
    let release: Value =
        serde_json::from_str(&get_text(LATEST)?).context("GitHub's release answer")?;
    let tag = release["tag_name"]
        .as_str()
        .context("the release has no tag")?
        .to_string();
    let asset = release["assets"].as_array().and_then(|a| {
        a.iter()
            .find(|x| {
                x["name"]
                    .as_str()
                    .is_some_and(|n| n.starts_with("Footnote-Setup-") && n.ends_with("-x64.exe"))
            })
            .cloned()
    });
    Ok((tag.trim_start_matches('v').to_string(), release, asset))
}

/// `footnote update --check`: this version, the latest release, and whether it is newer.
pub fn check() -> Result<Value> {
    let current = env!("CARGO_PKG_VERSION");
    let (version, release, asset) = latest()?;
    Ok(json!({
        "installed": current, "latest": version, "newer": newer(&version, current),
        "published_at": release["published_at"], "page": release["html_url"], "notes": release["body"],
        "installer": asset.as_ref().map(|a| a["name"].clone()), "bytes": asset.as_ref().map(|a| a["size"].clone()),
    }))
}

/// `footnote update --download`: fetch the latest Windows installer into `<state>/updates` and check it against the
/// release's own `.sha256` file. Nothing runs here; the launcher starts the installer and closes itself.
pub fn download() -> Result<Value> {
    let current = env!("CARGO_PKG_VERSION");
    let (version, release, asset) = latest()?;
    if !newer(&version, current) {
        return Ok(json!({"up_to_date": true, "installed": current, "latest": version}));
    }
    let asset = asset.context("this release has no Windows installer")?;
    let name = asset["name"].as_str().unwrap_or_default().to_string();
    ensure!(
        !name.contains(['/', '\\']) && !name.contains(".."),
        "unexpected installer name {name}"
    );
    let url = asset["browser_download_url"]
        .as_str()
        .context("installer address")?;
    let sum_url = release["assets"]
        .as_array()
        .and_then(|a| {
            a.iter()
                .find(|x| x["name"].as_str() == Some(&format!("{name}.sha256")))
        })
        .and_then(|x| x["browser_download_url"].as_str())
        .context("this release publishes no checksum for its installer")?;
    let expected = get_text(sum_url)?
        .split_whitespace()
        .next()
        .unwrap_or_default()
        .to_lowercase();
    ensure!(expected.len() == 64, "unreadable checksum file");
    let dir = crate::state::state_dir()?.join("updates");
    crate::state::ensure_private_dir(&dir)?;
    let to = dir.join(&name);
    // Already fetched and verified (the launcher downloads first, then installs when the user restarts): reuse it.
    if to.is_file() && crate::models::sha256_file(&to).is_ok_and(|got| got == expected) {
        return Ok(
            json!({"installer": to, "version": version, "sha256": expected, "cached": true}),
        );
    }
    let part = dir.join(format!("{name}.part"));
    let mut job = footnote_core::jobs::Job::start(
        &crate::state::state_dir()?,
        "update.download",
        &name,
        "bytes",
    )?;
    let fetched = crate::models::download(url, &part, &mut job);
    job.finish(&fetched);
    fetched?;
    let got = crate::models::sha256_file(&part)?;
    if got != expected {
        let _ = std::fs::remove_file(&part);
        bail!("the installer's SHA-256 does not match the release's checksum; nothing was kept");
    }
    std::fs::rename(&part, &to)?;
    // Older downloads are not needed once a newer one is verified.
    for old in std::fs::read_dir(&dir)?.flatten() {
        if old.path() != to {
            let _ = std::fs::remove_file(old.path());
        }
    }
    Ok(json!({"installer": to, "version": version, "sha256": got}))
}

/// Put the newest replaced binary back in place; the current one is set aside as a replaced copy too.
pub fn rollback() -> Result<Value> {
    let exe = std::env::current_exe()?;
    let previous = replaced(&exe)?
        .into_iter()
        .next()
        .context("no previous binary to roll back to (none was kept by `footnote update`)")?;
    let current = exe.with_file_name(format!(
        "{}.rolled-back-{}",
        exe.file_name().context("binary name")?.to_string_lossy(),
        stamp()
    ));
    std::fs::rename(&exe, &current).context("set the current binary aside")?;
    if let Err(e) = std::fs::rename(&previous, &exe) {
        let _ = std::fs::rename(&current, &exe);
        return Err(e).context("move the previous binary into place");
    }
    Ok(json!({"restored": exe, "from": previous, "set_aside": current}))
}

#[cfg(test)]
mod tests {
    #[test]
    fn versions_compare_with_pre_releases() {
        use super::newer;
        assert!(newer("0.1.0-alpha.3", "0.1.0-alpha.2"));
        assert!(newer("v0.1.0-alpha.10", "0.1.0-alpha.9"));
        assert!(newer("0.1.0", "0.1.0-alpha.3"));
        assert!(newer("0.2.0-alpha.1", "0.1.9"));
        assert!(!newer("0.1.0-alpha.3", "0.1.0-alpha.3"));
        assert!(!newer("0.1.0-alpha.2", "0.1.0-alpha.3"));
        assert!(!newer("0.1.0-alpha.3", "0.1.0"));
    }
}
