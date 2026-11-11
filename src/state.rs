//! Zero-configuration security state.
//!
//! The audit log, its MAC key and the daemon token live in one per-user
//! directory and are created on first use. Nobody has to generate a secret, pass
//! a key file or remember a flag: security is the default and the plumbing is
//! automatic. `BORG_STATE_DIR` overrides the location (used by tests).
use anyhow::{Context, Result, bail};
use std::path::{Path, PathBuf};

pub fn state_dir() -> Result<PathBuf> {
    if let Some(dir) = std::env::var_os("BORG_STATE_DIR") {
        return Ok(PathBuf::from(dir));
    }
    let base = if cfg!(windows) {
        std::env::var_os("LOCALAPPDATA").map(PathBuf::from)
    } else {
        std::env::var_os("XDG_STATE_HOME")
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/state"))
            })
    };
    let base = base.context("cannot determine a per-user state directory; set BORG_STATE_DIR")?;
    Ok(base.join("borg-knowledge"))
}

pub fn audit_path() -> Result<PathBuf> {
    Ok(state_dir()?.join("audit.jsonl"))
}

pub fn key_path() -> Result<PathBuf> {
    Ok(state_dir()?.join("audit.key"))
}

pub fn token_path() -> Result<PathBuf> {
    Ok(state_dir()?.join("daemon.token"))
}

fn ensure_parent(path: &Path) -> Result<()> {
    if let Some(parent) = path.parent()
        && !parent.as_os_str().is_empty()
    {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("create state directory {}", parent.display()))?;
    }
    Ok(())
}

/// Create a file readable only by the current user (0600 on Unix; on Windows the
/// per-user state directory already carries a user-only ACL).
fn write_private(path: &Path, bytes: &[u8]) -> Result<bool> {
    ensure_parent(path)?;
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    match options.open(path) {
        Ok(mut file) => {
            use std::io::Write;
            file.write_all(bytes)?;
            file.flush()?;
            Ok(true)
        }
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => Ok(false),
        Err(e) => Err(e).with_context(|| format!("create {}", path.display())),
    }
}

pub fn random_hex(bytes: usize) -> Result<String> {
    let mut buf = vec![0_u8; bytes];
    getrandom::fill(&mut buf).map_err(|e| anyhow::anyhow!("OS entropy unavailable: {e}"))?;
    Ok(buf.iter().map(|b| format!("{b:02x}")).collect())
}

/// The audit MAC key, generated on first use.
pub fn load_or_create_key() -> Result<PathBuf> {
    let path = key_path()?;
    let fresh = write_private(&path, random_hex(32)?.as_bytes())?;
    let raw = std::fs::read_to_string(&path)
        .with_context(|| format!("read MAC key {}", path.display()))?;
    if raw.trim().len() < 32 {
        if fresh {
            bail!("generated MAC key is malformed at {}", path.display());
        }
        // An empty/partial file from an interrupted first run: rewrite it.
        std::fs::write(&path, random_hex(32)?)?;
    }
    Ok(path)
}

/// The daemon token, generated on first use. Both the daemon and its local proxy
/// read this same file, so the handshake needs no user action.
pub fn load_or_create_token() -> Result<String> {
    let path = token_path()?;
    write_private(&path, random_hex(32)?.as_bytes())?;
    let raw = std::fs::read_to_string(&path)
        .with_context(|| format!("read daemon token {}", path.display()))?;
    let token = raw.trim().to_string();
    if token.len() < 32 {
        let regenerated = random_hex(32)?;
        std::fs::write(&path, &regenerated)?;
        return Ok(regenerated);
    }
    Ok(token)
}
