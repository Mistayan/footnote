//! Opt-in observability: timings, failures and unfinished steps, one JSON line each in `<state dir>/metrics.jsonl`.
//!
//! On when the memory settings hold `"metrics": true` (option `memory.metrics`, the same switch as the hook's own timings),
//! when `FOOTNOTE_METRICS=1`, or always in a build with `--features metrics`. Off, a span costs one cached flag read: no clock
//! read, no allocation, no write. A long-running process (the daemon) re-reads the switch at most once a minute (#517).
//!
//! Lines: `{"t":<unix ms>,"pid":..,"start":"cli.index"}` when a long step begins; `{"t":..,"pid":..,"span":"search.hybrid",
//! "ms":12.3,"ok":true}` when a step ends. A step that returned an error, or panicked, has `"ok":false`; a step with a start
//! line and no end line from the same process stopped (killed, hung or crashed). `footnote metrics` summarizes the file and
//! `footnote status` lists steps that failed again and again lately.

use serde_json::{Value, json};
use std::{
    fs::{File, OpenOptions},
    io::{Read, Seek, SeekFrom, Write},
    path::Path,
    sync::{
        Mutex, OnceLock,
        atomic::{AtomicU8, AtomicU64, Ordering},
    },
    time::{Instant, SystemTime, UNIX_EPOCH},
};

/// Time an expression that returns a `Result`, recording whether it succeeded. The name is only built when metrics are on.
#[macro_export]
macro_rules! timed {
    ($name:expr, $body:expr) => {{
        let __span = $crate::metrics::Span::begin(|| $name);
        let __result = $body;
        if let Some(__span) = __span {
            __span.finish(__result.is_ok());
        }
        __result
    }};
}
/// Mark the start of a long step, so a step that never finishes is visible.
#[macro_export]
macro_rules! started {
    ($name:expr) => {{
        if $crate::metrics::enabled() {
            $crate::metrics::start($name);
        }
    }};
}
pub use crate::{started, timed};

/// How often a running process re-reads the switch, in seconds.
const RECHECK_SECS: u64 = 60;
/// 0: not read yet, 1: off, 2: on.
static ON: AtomicU8 = AtomicU8::new(0);
static CHECKED_AT: AtomicU64 = AtomicU64::new(0);

fn unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_millis() as u64)
}

/// Metrics are on for this process. Cheap: the settings file is read once, then again at most once a minute.
#[must_use]
pub fn enabled() -> bool {
    if cfg!(feature = "metrics") {
        return true;
    }
    let now = unix_ms() / 1000;
    let state = ON.load(Ordering::Relaxed);
    if state != 0 && now.saturating_sub(CHECKED_AT.load(Ordering::Relaxed)) < RECHECK_SECS {
        return state == 2;
    }
    let on = read_switch();
    ON.store(if on { 2 } else { 1 }, Ordering::Relaxed);
    CHECKED_AT.store(now, Ordering::Relaxed);
    on
}

fn read_switch() -> bool {
    match std::env::var("FOOTNOTE_METRICS").as_deref() {
        Ok("1" | "true") => return true,
        Ok("0" | "false") => return false,
        _ => {}
    }
    crate::state::state_dir()
        .and_then(|state| crate::config::product_settings(&state, "memory"))
        .is_ok_and(|v| v["metrics"].as_bool().unwrap_or(false))
}

static SINK: OnceLock<Option<Mutex<File>>> = OnceLock::new();

fn write(mut v: Value) {
    let sink = SINK.get_or_init(|| {
        // Started by `cargo test` without its own state folder: never write into the user's real metrics file.
        if std::env::var_os("CARGO_MANIFEST_DIR").is_some()
            && std::env::var_os("FOOTNOTE_STATE_DIR").is_none()
        {
            return None;
        }
        let dir = crate::state::state_dir().ok()?;
        std::fs::create_dir_all(&dir).ok()?;
        let f = OpenOptions::new()
            .create(true)
            .append(true)
            .open(dir.join("metrics.jsonl"));
        f.ok().map(Mutex::new)
    });
    v["t"] = json!(unix_ms());
    v["pid"] = json!(std::process::id());
    if let Some(Ok(mut f)) = sink.as_ref().map(|m| m.lock()) {
        // One write per line (see state::append_line); observability never breaks the operation it observes.
        let _ = f.write_all(format!("{v}\n").as_bytes());
    }
}

pub fn start(name: impl Into<String>) {
    write(json!({"start": name.into()}));
}

/// One timed step. Dropped without [`Span::finish`] (a panic unwinding through it), it records `"ok":false`.
pub struct Span {
    name: String,
    at: Instant,
    done: bool,
}
impl Span {
    /// A span when metrics are on; the name closure only runs then.
    pub fn begin<S: Into<String>>(name: impl FnOnce() -> S) -> Option<Self> {
        enabled().then(|| Self::new(name()))
    }
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            at: Instant::now(),
            done: false,
        }
    }
    pub fn finish(mut self, ok: bool) {
        self.record(ok);
    }
    fn record(&mut self, ok: bool) {
        self.done = true;
        let ms = (self.at.elapsed().as_secs_f64() * 1e6).round() / 1e3;
        write(json!({"span": std::mem::take(&mut self.name), "ms": ms, "ok": ok}));
    }
}
impl Drop for Span {
    fn drop(&mut self) {
        if !self.done {
            self.record(false);
        }
    }
}

/// `footnote metrics`: per step, how many, failures, p50, p95 and max milliseconds; then steps that started and never ended.
pub fn summary(top: usize) -> anyhow::Result<Value> {
    use std::collections::{BTreeMap, HashMap};
    let path = crate::state::state_dir()?.join("metrics.jsonl");
    let text = std::fs::read_to_string(&path).unwrap_or_default();
    let mut spans: BTreeMap<String, (Vec<f64>, usize)> = BTreeMap::new();
    let mut open: HashMap<(u64, String), Vec<u64>> = HashMap::new();
    for line in text.lines() {
        let Ok(v) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        let pid = v["pid"].as_u64().unwrap_or(0);
        if let Some(name) = v["start"].as_str() {
            open.entry((pid, name.to_string()))
                .or_default()
                .push(v["t"].as_u64().unwrap_or(0));
        } else if let Some(name) = v["span"].as_str() {
            let e = spans.entry(name.to_string()).or_default();
            e.0.push(v["ms"].as_f64().unwrap_or(0.0));
            e.1 += usize::from(!v["ok"].as_bool().unwrap_or(true));
            if let Some(starts) = open.get_mut(&(pid, name.to_string())) {
                starts.pop();
            }
        }
    }
    let pct = |s: &[f64], p: f64| s[((s.len() - 1) as f64 * p).round() as usize];
    let mut rows: Vec<Value> = spans
        .into_iter()
        .map(|(name, (mut ms, failed))| {
            ms.sort_by(f64::total_cmp);
            json!({"step": name, "count": ms.len(), "failed": failed, "p50_ms": pct(&ms, 0.5),
                "p95_ms": pct(&ms, 0.95), "max_ms": pct(&ms, 1.0), "total_s": (ms.iter().sum::<f64>() / 10.0).round() / 100.0})
        })
        .collect();
    rows.sort_by(|a, b| {
        b["total_s"]
            .as_f64()
            .unwrap_or(0.0)
            .total_cmp(&a["total_s"].as_f64().unwrap_or(0.0))
    });
    rows.truncate(top);
    let mut unfinished: Vec<Value> = open
        .into_iter()
        .flat_map(|((pid, name), ts)| {
            ts.into_iter()
                .map(move |t| json!({"step": name, "pid": pid, "started": t}))
        })
        .collect();
    unfinished.sort_by_key(|v| std::cmp::Reverse(v["started"].as_u64().unwrap_or(0)));
    unfinished.truncate(top);
    Ok(
        json!({"file": path, "on": enabled(), "steps": rows, "unfinished": unfinished,
        "failing": failing(&state_metrics(&path), unix_ms(), FAILING_WINDOW_MS, FAILING_MIN),
        "note": "a step in `unfinished` started and never recorded an end in the same process: killed, hung or crashed (or still running)"}),
    )
}

/// Window and count past which a step's failures are reported: three in the last 24 hours.
pub const FAILING_WINDOW_MS: u64 = 24 * 3600 * 1000;
pub const FAILING_MIN: usize = 3;
/// Only the end of a long metrics file is read for the failure report.
const TAIL_BYTES: u64 = 2 * 1024 * 1024;

/// The last [`TAIL_BYTES`] of the metrics file (whole lines only); empty when there is none.
fn state_metrics(path: &Path) -> String {
    let Ok(mut f) = File::open(path) else {
        return String::new();
    };
    let len = f.metadata().map_or(0, |m| m.len());
    let from = len.saturating_sub(TAIL_BYTES);
    if f.seek(SeekFrom::Start(from)).is_err() {
        return String::new();
    }
    let mut bytes = Vec::new();
    if f.read_to_end(&mut bytes).is_err() {
        return String::new();
    }
    let mut text = String::from_utf8_lossy(&bytes).into_owned();
    if from > 0 {
        // The first line was cut in the middle.
        text = text
            .split_once('\n')
            .map_or_else(String::new, |(_, rest)| rest.to_string());
    }
    text
}

/// Steps that failed at least `min` times since `now_ms - window_ms`: name, failures, runs, last failure. Most failures first.
#[must_use]
pub fn failing(text: &str, now_ms: u64, window_ms: u64, min: usize) -> Vec<Value> {
    use std::collections::BTreeMap;
    let since = now_ms.saturating_sub(window_ms);
    // name -> (runs, failed, last failure)
    let mut steps: BTreeMap<&str, (usize, usize, u64)> = BTreeMap::new();
    let rows: Vec<Value> = text
        .lines()
        .filter(|l| l.contains("\"span\""))
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect();
    for v in &rows {
        let (Some(name), Some(t)) = (v["span"].as_str(), v["t"].as_u64()) else {
            continue;
        };
        if t < since {
            continue;
        }
        let e = steps.entry(name).or_default();
        e.0 += 1;
        if v["ok"] == false {
            e.1 += 1;
            e.2 = e.2.max(t);
        }
    }
    let mut out: Vec<Value> = steps
        .into_iter()
        .filter(|(_, (_, failed, _))| *failed >= min)
        .map(|(name, (runs, failed, last))| {
            json!({"step": name, "failed": failed, "runs": runs, "last_failure": last})
        })
        .collect();
    out.sort_by_key(|v| std::cmp::Reverse(v["failed"].as_u64().unwrap_or(0)));
    out
}

/// Steps failing again and again in the last 24 hours, from `<state>/metrics.jsonl` (`footnote status`).
#[must_use]
pub fn recent_failures(state: &Path) -> Vec<Value> {
    failing(
        &state_metrics(&state.join("metrics.jsonl")),
        unix_ms(),
        FAILING_WINDOW_MS,
        FAILING_MIN,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(span: &str, t: u64, ok: bool) -> String {
        json!({"span": span, "t": t, "ok": ok, "ms": 1.0, "pid": 1}).to_string()
    }

    #[test]
    fn repeated_recent_failures_are_reported_and_old_or_rare_ones_are_not() {
        let now = 10 * FAILING_WINDOW_MS;
        let old = now - FAILING_WINDOW_MS - 1;
        let mut lines = vec![
            "not json".to_string(),
            json!({"start": "hook.embed", "t": now, "pid": 1}).to_string(),
        ];
        lines.extend((0..5).map(|i| row("hook.embed", now - i, false)));
        lines.push(row("hook.embed", now - 10, true));
        lines.extend((0..2).map(|i| row("mcp.footnote_recall", now - i, false)));
        lines.extend((0..9).map(|_| row("cli.index", old, false)));
        let out = failing(&lines.join("\n"), now, FAILING_WINDOW_MS, FAILING_MIN);
        assert_eq!(
            out,
            vec![json!({"step": "hook.embed", "failed": 5, "runs": 6, "last_failure": now})]
        );
    }

    #[test]
    fn a_long_file_is_read_from_its_tail_on_a_line_boundary() {
        let t = tempfile::tempdir().unwrap();
        let path = t.path().join("metrics.jsonl");
        let filler = row("old.step", 1, true) + "\n";
        let mut text = filler.repeat((TAIL_BYTES as usize / filler.len()) + 10);
        text.push_str(&row("new.step", 2, false));
        std::fs::write(&path, &text).unwrap();
        let tail = state_metrics(&path);
        assert!(tail.len() as u64 <= TAIL_BYTES);
        assert!(
            tail.lines()
                .all(|l| serde_json::from_str::<Value>(l).is_ok())
        );
        assert!(tail.ends_with(&row("new.step", 2, false)));
    }

    #[test]
    fn a_dropped_span_records_a_failure() {
        // Only the bookkeeping: the sink is off under `cargo test` without FOOTNOTE_STATE_DIR.
        let mut s = Span::new("x");
        s.record(true);
        assert!(s.done);
        let d = Span::new("y");
        drop(d); // records ok:false; must not panic
    }
}
