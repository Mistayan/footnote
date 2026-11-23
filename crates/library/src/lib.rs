//! Footnote Library: document corpora. Extraction and folder indexing (ADR 0001); documentation crawling comes later.
use anyhow::{Result, bail};
use footnote_core::{bounded_read, hash, is_link, no_links};
use footnote_search::store::{is_memory_db, text_chunks};
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::{Value, json};
use std::{
    fs,
    num::NonZeroU32,
    path::{Path, PathBuf},
};
use walkdir::WalkDir;

pub mod crawl;
pub mod extract;
pub mod miss;
#[cfg(test)]
mod scan_tests;

use footnote_core::metrics;

fn excluded(p: &Path) -> bool {
    p.components().any(|c| {
        let name = c.as_os_str().to_string_lossy().to_lowercase();
        name.starts_with('.')
            || [
                "node_modules",
                "target",
                "private",
                "secrets",
                "credentials",
                "optimization-registry",
            ]
            .contains(&name.as_str())
            || name.contains("secret")
            || name.contains("credential")
    })
}

/// How [`index_with`] decides that a file has not changed since it was last hashed (#549).
#[non_exhaustive]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Scan {
    /// Read and hash every file, as before #549. Catches a rewrite that kept its size and restored its old timestamp.
    Full,
    /// Skip the read and hash of a file whose size and timestamps match the ones recorded when it was last hashed. The
    /// stored SHA-256 stays the source of truth: anything that does not match is read and hashed. With `verify_every`,
    /// each run also hashes the files whose `(source id + run) mod n = 0`, so every file is re-verified at least once
    /// every `n` runs.
    Precheck { verify_every: Option<NonZeroU32> },
}

impl Default for Scan {
    fn default() -> Self {
        Scan::Precheck {
            verify_every: NonZeroU32::new(VERIFY_EVERY),
        }
    }
}

/// Rolling re-verify period of the default scan (bench/experiments/SCAN-COST-2026-11-23.md).
const VERIFY_EVERY: u32 = 16;
/// A recorded stat is trusted only if the file's modification time was at least this much older than the start of the
/// scan that hashed it. Covers coarse timestamps (FAT: 2 s), a second write inside the same tick, and a file server
/// whose clock is behind ours by up to Kerberos's default 5-minute tolerance. Younger files are hashed on every run.
const SETTLE_NS: i64 = 600 * 1_000_000_000;

/// Size and timestamps of a file, compared with the ones recorded when it was last hashed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Stamp {
    size: i64,
    mtime_ns: i64,
    /// Unix: the change time, which `touch -r` cannot set back. Windows: the creation time. Elsewhere 0.
    aux_ns: i64,
}

fn epoch_ns(t: std::time::SystemTime) -> Option<i64> {
    match t.duration_since(std::time::UNIX_EPOCH) {
        Ok(d) => i64::try_from(d.as_nanos()).ok(),
        Err(e) => i64::try_from(e.duration().as_nanos()).ok().map(|n| -n),
    }
}

fn stamp(m: &fs::Metadata) -> Option<Stamp> {
    #[cfg(unix)]
    let aux_ns = {
        use std::os::unix::fs::MetadataExt;
        m.ctime()
            .checked_mul(1_000_000_000)?
            .checked_add(m.ctime_nsec())?
    };
    #[cfg(windows)]
    let aux_ns = {
        use std::os::windows::fs::MetadataExt;
        i64::try_from(m.creation_time()).ok()?
    };
    #[cfg(not(any(unix, windows)))]
    let aux_ns = 0;
    Some(Stamp {
        size: i64::try_from(m.len()).ok()?,
        mtime_ns: epoch_ns(m.modified().ok()?)?,
        aux_ns,
    })
}

/// True when a file can be treated as unchanged without reading it: its stamp equals the recorded one, the recorded
/// modification time had settled when it was hashed, and this run is not the file's re-verify turn.
#[must_use]
fn stat_trusted(
    scan: Scan,
    now: Option<Stamp>,
    recorded: Option<(Stamp, i64)>,
    id: i64,
    run: i64,
) -> bool {
    let Scan::Precheck { verify_every } = scan else {
        return false;
    };
    let (Some(now), Some((rec, hashed_at))) = (now, recorded) else {
        return false;
    };
    let due = verify_every.is_some_and(|n| (id + run).rem_euclid(i64::from(n.get())) == 0);
    now == rec && rec.mtime_ns.saturating_add(SETTLE_NS) <= hashed_at && !due
}

/// What the database knows about a path from its last index.
struct Known {
    id: i64,
    sha256: String,
    extractor: String,
    /// The stamp recorded when the file was last hashed, and when that scan started.
    recorded: Option<(Stamp, i64)>,
}

const STAT_TABLES: &str = "CREATE TABLE IF NOT EXISTS source_stats(source_id INTEGER PRIMARY KEY,size INTEGER NOT NULL,mtime_ns INTEGER NOT NULL,aux_ns INTEGER NOT NULL,hashed_at_ns INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS index_runs(root TEXT PRIMARY KEY,runs INTEGER NOT NULL);";

/// Index a folder with the default change scan ([`Scan::default`]).
pub fn index(
    c: &mut Connection,
    root: &Path,
    allow: &[PathBuf],
    max_files: usize,
    max_mib: u64,
    progress: &mut dyn FnMut(u64, u64),
) -> Result<Value> {
    index_with(
        c,
        root,
        allow,
        max_files,
        max_mib,
        Scan::default(),
        progress,
    )
}

pub fn index_with(
    c: &mut Connection,
    root: &Path,
    allow: &[PathBuf],
    max_files: usize,
    max_mib: u64,
    scan: Scan,
    progress: &mut dyn FnMut(u64, u64),
) -> Result<Value> {
    no_links(root)?;
    let root = fs::canonicalize(root)?;
    if !root.is_dir() {
        bail!("root must be a directory");
    }
    let mut allowed = false;
    for p in allow {
        no_links(p)?;
        if root.starts_with(fs::canonicalize(p)?) {
            allowed = true;
        }
    }
    if !allowed {
        bail!("root is outside explicit allowlist");
    }
    if is_memory_db(c)? {
        bail!("this is an agent memory database; index documents into a separate corpus database");
    }
    let root_s = root.to_string_lossy().to_string();
    let mut seen = std::collections::HashSet::new();
    let mut indexed = 0;
    let mut unchanged = 0;
    let mut failed = 0;
    let mut failures = Vec::new();
    let mut total_bytes = 0_u64;
    let mut hashed = 0_u64;
    let scan_start = epoch_ns(std::time::SystemTime::now()).unwrap_or(i64::MIN);
    let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    tx.execute_batch(STAT_TABLES)?;
    let run: i64 = tx.query_row(
        "INSERT INTO index_runs(root,runs) VALUES(?1,1) ON CONFLICT(root) DO UPDATE SET runs=runs+1 RETURNING runs",
        [&root_s],
        |r| r.get(0),
    )?;
    // Sorted: the same files get the same ids on every platform (NTFS lists by name, Linux file systems do not).
    for entry in WalkDir::new(&root)
        .sort_by_file_name()
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| {
            e.path() == root
                || (!excluded(e.path().strip_prefix(&root).unwrap_or(e.path()))
                    && !is_link(e.path()))
        })
    {
        let e = entry?;
        if !e.file_type().is_file() {
            continue;
        }
        let ext = e
            .path()
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_lowercase();
        if ![
            "md", "txt", "pdf", "png", "jpg", "jpeg", "webp", "tiff", "bmp",
        ]
        .contains(&ext.as_str())
        {
            continue;
        }
        let path = e.path().to_string_lossy().to_string();
        seen.insert(path.clone());
        if seen.len() > max_files {
            bail!("index file limit exceeded ({max_files}); raise it with --max-files");
        }
        // Taken before the read: if the file changes after this, the next run sees a newer stamp and hashes it again.
        let meta = fs::symlink_metadata(e.path())?;
        let now = stamp(&meta);
        let old: Option<Known> = tx
            .prepare_cached(
                "SELECT s.id,s.sha256,s.extractor,t.size,t.mtime_ns,t.aux_ns,t.hashed_at_ns FROM sources s LEFT JOIN source_stats t ON t.source_id=s.id WHERE s.path=?1 AND s.status='indexed'",
            )?
            .query_row([&path], |r| {
                let recorded = match (r.get(3)?, r.get(4)?, r.get(5)?, r.get(6)?) {
                    (Some(size), Some(mtime_ns), Some(aux_ns), Some(at)) => Some((
                        Stamp {
                            size,
                            mtime_ns,
                            aux_ns,
                        },
                        at,
                    )),
                    _ => None,
                };
                Ok(Known {
                    id: r.get(0)?,
                    sha256: r.get(1)?,
                    extractor: r.get(2)?,
                    recorded,
                })
            })
            .optional()?;
        let current = |ex: &str| {
            if ["md", "txt"].contains(&ext.as_str()) {
                ex == "utf8-v2"
            } else {
                ex.contains(extract::helper_hash()) && ex.contains("chunker-v2")
            }
        };
        if let Some(k) = &old
            && current(&k.extractor)
            && stat_trusted(scan, now, k.recorded, k.id, run)
        {
            total_bytes += meta.len();
            progress(seen.len() as u64, total_bytes);
            if total_bytes > max_mib * 1024 * 1024 {
                bail!("index scan byte limit exceeded ({max_mib} MiB); raise it with --max-mib");
            }
            unchanged += 1;
            continue;
        }
        let bytes = bounded_read(e.path())?;
        total_bytes += bytes.len() as u64;
        progress(seen.len() as u64, total_bytes);
        if total_bytes > max_mib * 1024 * 1024 {
            bail!("index scan byte limit exceeded ({max_mib} MiB); raise it with --max-mib");
        }
        let sha = hash(&bytes);
        hashed += 1;
        let record = |id: i64| -> Result<()> {
            if let Some(s) = now {
                tx.prepare_cached("INSERT INTO source_stats(source_id,size,mtime_ns,aux_ns,hashed_at_ns) VALUES(?1,?2,?3,?4,?5) ON CONFLICT(source_id) DO UPDATE SET size=excluded.size,mtime_ns=excluded.mtime_ns,aux_ns=excluded.aux_ns,hashed_at_ns=excluded.hashed_at_ns")?
                    .execute(params![id, s.size, s.mtime_ns, s.aux_ns, scan_start])?;
            } else {
                // No usable stamp: forget the old one, so it can never vouch for this content.
                tx.prepare_cached("DELETE FROM source_stats WHERE source_id=?1")?
                    .execute([id])?;
            }
            Ok(())
        };
        if let Some(k) = &old
            && k.sha256 == sha
            && current(&k.extractor)
        {
            record(k.id)?;
            unchanged += 1;
            continue;
        }
        let extraction = if ["md", "txt"].contains(&ext.as_str()) {
            match String::from_utf8(bytes) {
                Ok(text) if text.len() <= 1_000_000 => crate::extract::Extraction {
                    status: if text.trim().is_empty() {
                        "empty"
                    } else {
                        "indexed"
                    }
                    .into(),
                    extractor: "utf8-v2".into(),
                    pages: vec![crate::extract::Page { page: 0, text }],
                },
                _ => crate::extract::Extraction {
                    status: "failed".into(),
                    extractor: "utf8-v2".into(),
                    pages: vec![],
                },
            }
        } else {
            crate::metrics::timed!("index.extract", crate::extract::extract(&bytes, &ext))
                .unwrap_or_else(|_| crate::extract::Extraction {
                    status: "unsupported_or_failed".into(),
                    extractor: "local-extractor-unavailable".into(),
                    pages: vec![],
                })
        };
        if extraction.status != "indexed" {
            failed += 1;
            if failures.len() < 20 {
                failures.push(json!({"path":path,"status":extraction.status}));
            }
        }
        tx.execute("INSERT INTO sources(root,path,sha256,revision,status,extractor) VALUES(?1,?2,?3,1,?4,?5) ON CONFLICT(path) DO UPDATE SET root=excluded.root,sha256=excluded.sha256,revision=sources.revision+1,status=excluded.status,extractor=excluded.extractor",params![root_s,path,sha,extraction.status,extraction.extractor])?;
        let id: i64 = tx.query_row("SELECT id FROM sources WHERE path=?1", [&path], |r| {
            r.get(0)
        })?;
        record(id)?;
        tx.execute(
            "DELETE FROM search_fts WHERE rowid IN (SELECT id FROM chunks WHERE source_id=?1)",
            [id],
        )?;
        tx.execute("DELETE FROM chunks WHERE source_id=?1", [id])?;
        if extraction.status == "indexed" {
            for p in extraction.pages {
                text_chunks(
                    &tx,
                    id,
                    &p.text,
                    if p.page == 0 { None } else { Some(p.page) },
                )?;
            }
            indexed += 1;
        }
    }
    let paths: Vec<(i64, String)> = {
        let mut s =
            tx.prepare("SELECT id,path FROM sources WHERE root=?1 AND status!='deleted'")?;
        s.query_map([&root_s], |r| Ok((r.get(0)?, r.get(1)?)))?
            .collect::<rusqlite::Result<_>>()?
    };
    let mut deleted = 0;
    for (id, p) in paths {
        if !seen.contains(&p) {
            tx.execute(
                "UPDATE sources SET status='deleted',revision=revision+1 WHERE id=?1",
                [id],
            )?;
            tx.execute(
                "DELETE FROM search_fts WHERE rowid IN (SELECT id FROM chunks WHERE source_id=?1)",
                [id],
            )?;
            deleted += 1;
        }
    }
    tx.commit()?;
    Ok(
        json!({"indexed":indexed,"unchanged":unchanged,"deleted":deleted,"failed":failed,"failures":failures,"hashed":hashed}),
    )
}
