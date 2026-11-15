//! Long steps (model downloads, indexing) report their progress in `<state dir>/jobs/<id>.json`, so every window and command
//! can follow them, whoever started them: the launcher, the command line or an agent. A job whose process died before it
//! finished is reported as interrupted, so a progress bar never hangs.
use anyhow::Result;
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

const KEEP_FINISHED: u64 = 7 * 24 * 3600 * 1000;

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_millis() as u64)
}

pub struct Job {
    path: PathBuf,
    v: Value,
    last: Instant,
}

impl Job {
    /// `unit`: what `done` and `total` count ("bytes", "files").
    pub fn start(state: &Path, kind: &str, label: &str, unit: &str) -> Result<Self> {
        let dir = state.join("jobs");
        crate::state::ensure_private_dir(&dir)?;
        let id = format!(
            "{}-{}-{}",
            now_ms(),
            std::process::id(),
            label.replace(|c: char| !c.is_ascii_alphanumeric(), "-")
        );
        let mut job = Self {
            path: dir.join(format!("{id}.json")),
            v: json!({"id": id, "kind": kind, "label": label, "unit": unit, "pid": std::process::id(), "state": "running",
                "done": 0, "total": null, "started": now_ms(), "updated": now_ms()}),
            last: Instant::now(),
        };
        job.write();
        Ok(job)
    }

    /// Record progress; written at most four times a second.
    pub fn progress(&mut self, done: u64, total: Option<u64>) {
        self.v["done"] = json!(done);
        self.v["total"] = json!(total);
        if self.last.elapsed() >= Duration::from_millis(250) {
            self.last = Instant::now();
            self.write();
        }
    }

    pub fn finish<T>(mut self, result: &Result<T>) {
        match result {
            Ok(_) => self.v["state"] = json!("done"),
            Err(e) => {
                self.v["state"] = json!("failed");
                self.v["error"] = json!(format!("{e:#}"));
            }
        }
        self.write();
    }

    fn write(&mut self) {
        self.v["updated"] = json!(now_ms());
        // Beside, then rename: a reader never sees half a file. Progress is best effort: it never fails the job itself.
        let tmp = self.path.with_extension("tmp");
        if std::fs::write(&tmp, self.v.to_string()).is_ok() {
            let _ = std::fs::rename(&tmp, &self.path);
        }
    }
}

/// `footnote jobs`: running and recent jobs, newest first; finished ones older than a week are removed.
pub fn list(state: &Path) -> Result<Value> {
    let dir = state.join("jobs");
    let mut jobs = Vec::new();
    for entry in std::fs::read_dir(&dir).into_iter().flatten().flatten() {
        let path = entry.path();
        if path.extension().is_none_or(|e| e != "json") {
            continue;
        }
        let Ok(mut v) = std::fs::read(&path)
            .map_err(anyhow::Error::from)
            .and_then(|b| Ok(serde_json::from_slice::<Value>(&b)?))
        else {
            continue;
        };
        if v["state"] == "running" && !alive(v["pid"].as_u64().unwrap_or(0) as u32) {
            v["state"] = json!("interrupted");
        }
        if v["state"] != "running"
            && now_ms().saturating_sub(v["updated"].as_u64().unwrap_or(0)) > KEEP_FINISHED
        {
            let _ = std::fs::remove_file(&path);
            continue;
        }
        jobs.push(v);
    }
    jobs.sort_by_key(|v| std::cmp::Reverse(v["started"].as_u64().unwrap_or(0)));
    Ok(json!({"jobs": jobs}))
}

#[cfg(windows)]
fn alive(pid: u32) -> bool {
    use windows_sys::Win32::Foundation::{CloseHandle, STILL_ACTIVE};
    use windows_sys::Win32::System::Threading::{
        GetExitCodeProcess, OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION,
    };
    unsafe {
        let h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
        if h.is_null() {
            return false;
        }
        let mut code = 0u32;
        let ok = GetExitCodeProcess(h, &mut code) != 0;
        CloseHandle(h);
        ok && code == STILL_ACTIVE as u32
    }
}

#[cfg(not(windows))]
fn alive(pid: u32) -> bool {
    // Signal 0 checks existence without touching the process.
    std::process::Command::new("kill")
        .args(["-0", &pid.to_string()])
        .stderr(std::process::Stdio::null())
        .status()
        .is_ok_and(|s| s.success())
}
