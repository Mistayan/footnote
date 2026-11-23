//! Change scan cost bench (issue #549, `bench/experiments/SCAN-COST-2026-11-23.md`).
//!
//! `cargo run --release -p footnote-library --example scan_cost -- <command> ...`
//!
//! - `seed SHARE DB`: write the `sources` rows a completed index leaves (SHA-256, status `indexed`, an extractor string
//!   the index accepts), without extracting anything.
//! - `run SHARE DB [default|full|no-verify]`: time one unchanged re-scan through `footnote_library::index`.
//! - `split SHARE DB`: today's loop with a timer around each step (walk and metadata, read, hash, database).
//! - `coldread SHARE`: read every file once with the OS cache bypassed (Windows only).
//!
//! Every command prints one JSON line.
use anyhow::{Context, Result, bail};
use footnote_core::{bounded_read, hash};
use footnote_library::{Scan, index_with};
use rusqlite::{Connection, OptionalExtension, params};
use serde_json::json;
use std::{
    path::{Path, PathBuf},
    time::{Duration, Instant},
};
use walkdir::WalkDir;

const EXTS: [&str; 9] = [
    "md", "txt", "pdf", "png", "jpg", "jpeg", "webp", "tiff", "bmp",
];
const HELPER: &str = include_str!("../../../tools/extract.py");

fn files(root: &Path) -> Result<Vec<PathBuf>> {
    let mut out = Vec::new();
    for e in WalkDir::new(root).sort_by_file_name().follow_links(false) {
        let e = e?;
        let ext = e
            .path()
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_lowercase();
        if e.file_type().is_file() && EXTS.contains(&ext.as_str()) {
            out.push(e.into_path());
        }
    }
    Ok(out)
}

fn ext_of(p: &Path) -> String {
    p.extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_lowercase()
}

fn seed(share: &Path, db: &Path) -> Result<serde_json::Value> {
    if db.exists() {
        bail!("{} exists", db.display());
    }
    let root = std::fs::canonicalize(share)?;
    let root_s = root.to_string_lossy().to_string();
    let mut c = footnote_search::store::open(db, true)?;
    let helper = format!(
        "seeded;helper-sha256={};chunker-v2",
        hash(HELPER.as_bytes())
    );
    let tx = c.transaction()?;
    let t = Instant::now();
    let mut n = 0_u64;
    let mut bytes = 0_u64;
    for p in files(&root)? {
        let data = std::fs::read(&p)?;
        bytes += data.len() as u64;
        let ex = if ["md", "txt"].contains(&ext_of(&p).as_str()) {
            footnote_library::UTF8_EXTRACTOR
        } else {
            helper.as_str()
        };
        tx.execute(
            "INSERT INTO sources(root,path,sha256,revision,status,extractor) VALUES(?1,?2,?3,1,'indexed',?4)",
            params![root_s, p.to_string_lossy(), hash(&data), ex],
        )?;
        n += 1;
    }
    tx.commit()?;
    Ok(json!({"cmd":"seed","files":n,"bytes":bytes,"ms":t.elapsed().as_millis()}))
}

fn run(share: &Path, db: &Path, arm: &str) -> Result<serde_json::Value> {
    let mut c = footnote_search::store::open(db, true)?;
    let allow = [share.to_path_buf()];
    let t = Instant::now();
    let out = match arm {
        "default" => {
            footnote_library::index(&mut c, share, &allow, 10_000_000, 1 << 30, &mut |_, _| {})?
        }
        "full" | "no-verify" => {
            let scan = if arm == "full" {
                Scan::Full
            } else {
                Scan::Precheck { verify_every: None }
            };
            index_with(
                &mut c,
                share,
                &allow,
                10_000_000,
                1 << 30,
                scan,
                &mut |_, _| {},
            )?
        }
        other => bail!("unknown arm {other}"),
    };
    let ms = t.elapsed().as_secs_f64() * 1000.0;
    Ok(json!({"cmd":"run","arm":arm,"ms":ms,"result":out}))
}

/// Today's unchanged path step by step: the same walk filter, `bounded_read`, `hash` and lookup as `index()`.
fn split(share: &Path, db: &Path) -> Result<serde_json::Value> {
    let mut c: Connection = footnote_search::store::open(db, true)?;
    let root = std::fs::canonicalize(share)?;
    let tx = c.transaction_with_behavior(rusqlite::TransactionBehavior::Immediate)?;
    let (mut read, mut hashing, mut dbt) = (Duration::ZERO, Duration::ZERO, Duration::ZERO);
    let (mut n, mut bytes, mut unchanged) = (0_u64, 0_u64, 0_u64);
    let start = Instant::now();
    for entry in WalkDir::new(&root)
        .sort_by_file_name()
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| e.path() == root || !footnote_core::is_link(e.path()))
    {
        let e = entry?;
        if !e.file_type().is_file() || !EXTS.contains(&ext_of(e.path()).as_str()) {
            continue;
        }
        let path = e.path().to_string_lossy().to_string();
        let t = Instant::now();
        let data = bounded_read(e.path())?;
        read += t.elapsed();
        bytes += data.len() as u64;
        let t = Instant::now();
        let sha = hash(&data);
        hashing += t.elapsed();
        let t = Instant::now();
        let old: Option<String> = tx
            .query_row(
                "SELECT sha256 FROM sources WHERE path=?1 AND status='indexed'",
                [&path],
                |r| r.get(0),
            )
            .optional()?;
        dbt += t.elapsed();
        n += 1;
        if old.as_deref() == Some(sha.as_str()) {
            unchanged += 1;
        }
    }
    let total = start.elapsed();
    tx.rollback()?;
    let ms = |d: Duration| d.as_secs_f64() * 1000.0;
    Ok(
        json!({"cmd":"split","files":n,"bytes":bytes,"unchanged":unchanged,"total_ms":ms(total),
        "walk_ms":ms(total - read - hashing - dbt),"read_ms":ms(read),"hash_ms":ms(hashing),"db_ms":ms(dbt)}),
    )
}

#[cfg(windows)]
fn coldread(share: &Path) -> Result<serde_json::Value> {
    use std::io::Read;
    use std::os::windows::fs::OpenOptionsExt;
    const FILE_FLAG_NO_BUFFERING: u32 = 0x2000_0000;
    const BUF: usize = 1 << 20;
    let mut raw = vec![0_u8; BUF + 4096];
    let off = raw.as_ptr().align_offset(4096);
    let buf = &mut raw[off..off + BUF];
    let list = files(&std::fs::canonicalize(share)?)?;
    let t = Instant::now();
    let mut bytes = 0_u64;
    for p in &list {
        let mut f = std::fs::OpenOptions::new()
            .read(true)
            .custom_flags(FILE_FLAG_NO_BUFFERING)
            .open(p)
            .with_context(|| p.display().to_string())?;
        loop {
            let k = f.read(buf)?;
            if k == 0 {
                break;
            }
            bytes += k as u64;
        }
    }
    let s = t.elapsed().as_secs_f64();
    Ok(
        json!({"cmd":"coldread","files":list.len(),"bytes":bytes,"ms":s*1000.0,"mib_s":bytes as f64/1048576.0/s}),
    )
}

#[cfg(not(windows))]
fn coldread(_: &Path) -> Result<serde_json::Value> {
    bail!("coldread is Windows only")
}

fn main() -> Result<()> {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let arg =
        |i: usize| -> Result<PathBuf> { Ok(PathBuf::from(a.get(i).context("missing argument")?)) };
    let out = match a.first().map(String::as_str) {
        Some("seed") => seed(&arg(1)?, &arg(2)?)?,
        Some("run") => run(
            &arg(1)?,
            &arg(2)?,
            a.get(3).map_or("default", String::as_str),
        )?,
        Some("split") => split(&arg(1)?, &arg(2)?)?,
        Some("coldread") => coldread(&arg(1)?)?,
        _ => bail!("usage: scan_cost seed|run|split|coldread SHARE [DB] [ARM]"),
    };
    println!("{out}");
    Ok(())
}
