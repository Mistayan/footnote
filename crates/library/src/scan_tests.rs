//! Correctness gates of the size and modification time pre-check (#549,
//! `bench/experiments/SCAN-COST-2026-11-23.md`, decision rule 1).
use super::*;
use std::time::{Duration, SystemTime};

const NO_VERIFY: Scan = Scan::Precheck { verify_every: None };
const DAY: Duration = Duration::from_secs(86_400);

struct Share {
    dir: tempfile::TempDir,
    root: PathBuf,
}

fn share() -> Share {
    let dir = tempfile::tempdir().unwrap();
    let root = dir.path().join("share");
    fs::create_dir(&root).unwrap();
    Share { dir, root }
}

fn set_mtime(p: &Path, t: SystemTime) {
    fs::OpenOptions::new()
        .write(true)
        .open(p)
        .unwrap()
        .set_modified(t)
        .unwrap();
}

/// Rewrite a file and put its old modification time back, as `touch -r` or some sync tools do.
fn rewrite_keeping_mtime(p: &Path, text: &str) {
    let before = fs::metadata(p).unwrap().modified().unwrap();
    fs::write(p, text).unwrap();
    set_mtime(p, before);
}

impl Share {
    /// Write `name` with a modification time `age` in the past (`None`: now, the racy case).
    fn write(&self, name: &str, text: &str, age: Option<Duration>) -> PathBuf {
        let p = self.root.join(name);
        fs::write(&p, text).unwrap();
        if let Some(age) = age {
            set_mtime(&p, SystemTime::now() - age);
        }
        p
    }

    fn open(&self, db: &str) -> Connection {
        footnote_search::store::open(&self.dir.path().join(db), true).unwrap()
    }

    fn index(&self, db: &str, scan: Scan) -> Value {
        index_with(
            &mut self.open(db),
            &self.root,
            std::slice::from_ref(&self.root),
            10_000,
            1_024,
            scan,
            &mut |_, _| {},
        )
        .unwrap()
    }

    /// Everything a scan decides, comparable between two databases of the same share.
    fn state(&self, db: &str) -> Vec<String> {
        let c = self.open(db);
        let rows = |sql: &str| -> Vec<String> {
            let mut s = c.prepare(sql).unwrap();
            s.query_map([], |r| r.get(0))
                .unwrap()
                .collect::<rusqlite::Result<_>>()
                .unwrap()
        };
        let mut out = rows(
            "SELECT path||'|'||sha256||'|'||status||'|'||revision||'|'||extractor FROM sources ORDER BY path",
        );
        out.extend(rows(
            "SELECT s.path||'|'||k.line||'|'||k.heading||'|'||k.text FROM chunks k JOIN sources s ON s.id=k.source_id ORDER BY s.path,k.line",
        ));
        out.extend(rows("SELECT 'fts '||count(*) FROM search_fts"));
        out
    }
}

fn counts(v: &Value, keys: &[&str]) -> Vec<u64> {
    keys.iter().map(|k| v[*k].as_u64().unwrap()).collect()
}

#[test]
fn precheck_skips_settled_files_and_hashes_changed_ones() {
    let s = share();
    let a = s.write("a.md", "# A\nalpha one\n", Some(DAY));
    let b = s.write("b.md", "# B\nbravo two\n", Some(DAY));
    s.write("c.txt", "charlie\n", Some(DAY));
    let first = s.index("k.db", Scan::default());
    assert_eq!(counts(&first, &["indexed", "hashed"]), [3, 3], "{first}");
    let again = s.index("k.db", NO_VERIFY);
    assert_eq!(counts(&again, &["unchanged", "hashed"]), [3, 0], "{again}");
    // New size, old modification time kept: the size alone gives it away.
    rewrite_keeping_mtime(&a, "# A\nalpha one, longer\n");
    // Same size, newer modification time.
    let old = fs::metadata(&b).unwrap().modified().unwrap();
    fs::write(&b, "# B\nbravo 2!2\n").unwrap();
    set_mtime(&b, old + Duration::from_secs(1));
    let v = s.index("k.db", NO_VERIFY);
    assert_eq!(
        counts(&v, &["indexed", "unchanged", "hashed"]),
        [2, 1, 2],
        "{v}"
    );
    let c = s.open("k.db");
    let mut q = c.prepare("SELECT path,sha256 FROM sources").unwrap();
    let rows: Vec<(String, String)> = q
        .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))
        .unwrap()
        .collect::<rusqlite::Result<_>>()
        .unwrap();
    assert_eq!(rows.len(), 3);
    for (p, sha) in rows {
        assert_eq!(sha, hash(&fs::read(&p).unwrap()), "{p}");
    }
}

#[test]
fn same_size_rewrite_inside_the_racy_window_is_hashed_again() {
    let s = share();
    let a = s.write("a.md", "# A\nfirst\n", None);
    s.index("k.db", Scan::default());
    rewrite_keeping_mtime(&a, "# A\nsecnd\n");
    let v = s.index("k.db", NO_VERIFY);
    assert_eq!(counts(&v, &["indexed", "hashed"]), [1, 1], "{v}");
}

#[test]
fn future_modification_time_is_never_trusted() {
    let s = share();
    let a = s.write("a.md", "# A\nfirst\n", None);
    set_mtime(&a, SystemTime::now() + DAY);
    s.index("k.db", Scan::default());
    rewrite_keeping_mtime(&a, "# A\nsecnd\n");
    assert_eq!(s.index("k.db", NO_VERIFY)["indexed"], 1);
}

#[test]
fn extractor_change_reextracts_even_when_the_stat_matches() {
    let s = share();
    s.write("a.md", "# A\nfirst\n", Some(DAY));
    s.index("k.db", Scan::default());
    s.open("k.db")
        .execute("UPDATE sources SET extractor='utf8-v1'", [])
        .unwrap();
    assert_eq!(s.index("k.db", NO_VERIFY)["indexed"], 1);
}

#[test]
fn deleted_then_restored_file_is_indexed_again() {
    let s = share();
    let a = s.write("a.md", "# A\nfirst\n", Some(DAY));
    let when = fs::metadata(&a).unwrap().modified().unwrap();
    s.index("k.db", Scan::default());
    fs::remove_file(&a).unwrap();
    assert_eq!(s.index("k.db", NO_VERIFY)["deleted"], 1);
    fs::write(&a, "# A\nfirst\n").unwrap();
    set_mtime(&a, when);
    assert_eq!(s.index("k.db", NO_VERIFY)["indexed"], 1);
    assert!(s.state("k.db")[0].contains("|indexed|"));
}

#[test]
fn restored_timestamp_rewrite_is_caught_by_full_scan_and_rolling_verify() {
    let s = share();
    let a = s.write("a.md", "# A\nfirst\n", Some(DAY));
    let b = s.write("b.md", "# B\nfirst\n", Some(DAY));
    s.index("k.db", Scan::default());
    rewrite_keeping_mtime(&a, "# A\nsecnd\n");
    rewrite_keeping_mtime(&b, "# B\nsecnd\n");
    let gap = s.index("k.db", NO_VERIFY);
    if cfg!(unix) {
        // The change time moved, and `touch -r` cannot set it back: no gap on Unix.
        assert_eq!(gap["indexed"], 2, "{gap}");
        return;
    }
    // The accepted gap (decision rule): same size, old modification time restored.
    assert_eq!(gap["indexed"], 0, "{gap}");
    assert_eq!(s.index("k.db", Scan::Full)["indexed"], 2);
    // Rolling re-verify: with n = 2, each file is hashed in exactly one of any two consecutive runs.
    rewrite_keeping_mtime(&a, "# A\nthird\n");
    rewrite_keeping_mtime(&b, "# B\nthird\n");
    let every2 = Scan::Precheck {
        verify_every: NonZeroU32::new(2),
    };
    let runs = [s.index("k.db", every2), s.index("k.db", every2)];
    let found = counts(&runs[0], &["indexed"])[0] + counts(&runs[1], &["indexed"])[0];
    assert_eq!(found, 2, "{runs:?}");
}

#[test]
fn precheck_matches_a_full_scan_after_mixed_edits() {
    let s = share();
    let path = |i: usize| s.root.join(format!("f{i:02}.md"));
    for i in 0..30 {
        s.write(
            &format!("f{i:02}.md"),
            &format!("# F{i}\nbody {i}\n"),
            Some(DAY),
        );
    }
    for _ in 0..2 {
        s.index("p.db", Scan::default());
        s.index("f.db", Scan::Full);
    }
    for round in 0..2 {
        let r = round * 10;
        for i in r..r + 3 {
            // Bigger, old modification time kept.
            rewrite_keeping_mtime(
                &path(i),
                &format!("# F{i}\nbody {i} grown in round {round}\n"),
            );
        }
        for i in r + 3..r + 6 {
            // Same size, new modification time.
            let text = fs::read_to_string(path(i)).unwrap().replace("body", "BODY");
            fs::write(path(i), text).unwrap();
            set_mtime(&path(i), SystemTime::now() - DAY / 2);
        }
        for i in r + 6..r + 8 {
            fs::remove_file(path(i)).unwrap();
        }
        for i in 0..2 {
            s.write(&format!("new{round}{i}.md"), "# New\nadded\n", Some(DAY));
        }
        // A fresh file, and one touched without a content change.
        s.write(&format!("fresh{round}.md"), "# Fresh\nnow\n", None);
        set_mtime(&path(r + 8), SystemTime::now() - DAY / 3);
        let (p, f) = (s.index("p.db", NO_VERIFY), s.index("f.db", Scan::Full));
        let keys = ["indexed", "unchanged", "deleted", "failed"];
        assert_eq!(counts(&p, &keys), counts(&f, &keys), "{p} vs {f}");
        assert!(p["hashed"].as_u64() < f["hashed"].as_u64(), "{p} vs {f}");
        assert_eq!(s.state("p.db"), s.state("f.db"), "round {round}");
    }
}

#[test]
fn stat_trust_rule() {
    let st = |size, mtime_ns| Stamp {
        size,
        mtime_ns,
        aux_ns: 7,
    };
    let at = 10 * SETTLE_NS;
    let settled = Some(st(5, at - SETTLE_NS));
    let rec = Some((st(5, at - SETTLE_NS), at));
    assert!(stat_trusted(NO_VERIFY, settled, rec, 1, 1));
    assert!(!stat_trusted(Scan::Full, settled, rec, 1, 1));
    assert!(!stat_trusted(
        NO_VERIFY,
        Some(st(6, at - SETTLE_NS)),
        rec,
        1,
        1
    ));
    assert!(!stat_trusted(NO_VERIFY, None, rec, 1, 1));
    assert!(!stat_trusted(NO_VERIFY, settled, None, 1, 1));
    let racy = Some(st(5, at - SETTLE_NS + 1));
    assert!(!stat_trusted(NO_VERIFY, racy, racy.map(|r| (r, at)), 1, 1));
    let n4 = Scan::Precheck {
        verify_every: NonZeroU32::new(4),
    };
    let due: Vec<i64> = (0..8)
        .filter(|run| !stat_trusted(n4, settled, rec, 3, *run))
        .collect();
    assert_eq!(due, [1, 5]);
}
