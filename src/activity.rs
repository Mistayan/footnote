//! `footnote activity`: what memory did, day by day (the launcher's Activity screen; the visibility principle).
//! Saves come from the memory database and `save` events in the hook's activity log; sessions and prompts given memories
//! come from the hook's activity log, which holds ids, counts and projects only, never what was asked.
use anyhow::Result;
use serde_json::{Value, json};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

/// Recalls listed in `recent`, newest first.
const RECENT: usize = 20;

/// Record a memory save (`t` in ms and `n` live memories stored) in `<state>/memory-hook/activity.jsonl` so
/// `footnote activity` can report saves per hour (#635). Skipped for ad-hoc `--db` databases outside the state folder.
pub(crate) fn log_save(db: &Path, report: &Value) {
    let n = report["stored"].as_array().map_or(0, |a| {
        a.iter().filter(|r| r["pending_review"] != true).count()
    });
    if n == 0 {
        return;
    }
    let Ok(state) = crate::state::state_dir() else {
        return;
    };
    let is_state_db = std::env::var_os("FOOTNOTE_STATE_DIR").is_some()
        || crate::status::memory_db(&state)
            .is_ok_and(|mem| std::path::absolute(db).ok() == std::path::absolute(&mem).ok());
    if !is_state_db {
        return;
    }
    let on = footnote_core::config::product_settings(&state, "memory")
        .map_or(true, |v| v["activity"].as_bool().unwrap_or(true));
    if !on {
        return;
    }
    let dir = state.join("memory-hook");
    if crate::state::ensure_private_dir(&dir).is_err() {
        return;
    }
    crate::hook::append_activity(
        &dir,
        &json!({
            "t": footnote_core::audit::now_ms(),
            "event": "save",
            "n": n,
        }),
    );
}

#[derive(Default)]
struct LocalDay {
    saved_db: i64,
    recalls: u64,
    sessions: u64,
    hours: [(u64, u64); 24],
}

pub fn activity(days: u16) -> Result<Value> {
    let state = crate::state::state_dir()?;
    let settings = footnote_core::config::product_settings(&state, "memory")?;
    let db = settings["db"]
        .as_str()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| state.join("memory.db"));
    let now_utc = time::OffsetDateTime::now_utc();
    let today = now_utc.date();
    let first = today - time::Duration::days(i64::from(days) - 1);
    let offset = time::UtcOffset::current_local_offset().unwrap_or(time::UtcOffset::UTC);
    let local_today = now_utc.to_offset(offset).date();
    let local_first = local_today - time::Duration::days(6);

    let mut by_day: BTreeMap<String, Value> = BTreeMap::new();
    for d in 0..days {
        let date = (first + time::Duration::days(i64::from(d))).to_string();
        by_day.insert(
            date.clone(),
            json!({
                "date": date,
                "saved": 0,
                "sessions": 0,
                "prompts_given_memories": 0,
                "recall_misses": 0,
                "recall_skips": 0,
            }),
        );
    }
    let mut week: BTreeMap<String, LocalDay> = BTreeMap::new();
    for d in 0..7 {
        let date = (local_first + time::Duration::days(d)).to_string();
        week.insert(date, LocalDay::default());
    }

    let conn = if db.exists() {
        Some(crate::app::open(&db, false)?)
    } else {
        None
    };
    if let Some(c) = &conn {
        let earliest = first.min(local_first).to_string();
        let mut s = c.prepare(
            "SELECT m.observed_at, count(*) FROM memories m JOIN sources s ON s.id=m.source_id WHERE s.status='indexed' AND m.observed_at >= ?1 GROUP BY m.observed_at",
        )?;
        for row in s.query_map([earliest], |r| {
            Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)?))
        })? {
            let (date, n) = row?;
            if let Some(day) = by_day.get_mut(&date) {
                day["saved"] = json!(n);
            }
            if let Some(w) = week.get_mut(&date) {
                w.saved_db = n;
            }
        }
    }

    let utc_since = (first.midnight().assume_utc().unix_timestamp() * 1000).max(0) as u64;
    let local_since = (local_first
        .midnight()
        .assume_offset(offset)
        .unix_timestamp()
        * 1000)
        .max(0) as u64;
    let since_ms = utc_since.min(local_since);
    let mut used: HashMap<i64, u64> = HashMap::new();
    let mut recent: Vec<Value> = Vec::new();
    let (mut total_hits, mut total_misses, mut total_skips) = (0u64, 0u64, 0u64);
    let log = std::fs::read_to_string(state.join("memory-hook/activity.jsonl")).unwrap_or_default();
    for v in log
        .lines()
        .filter_map(|l| serde_json::from_str::<Value>(l).ok())
    {
        let Some(t) = v["t"].as_u64().filter(|t| *t >= since_ms) else {
            continue;
        };
        let Ok(dt) = time::OffsetDateTime::from_unix_timestamp((t / 1000) as i64) else {
            continue;
        };
        if t >= local_since {
            let local = dt.to_offset(offset);
            let ldate = local.date().to_string();
            let h = usize::from(local.hour());
            if let Some(w) = week.get_mut(&ldate) {
                match v["event"].as_str() {
                    Some("save") => w.hours[h].0 += v["n"].as_u64().unwrap_or(1),
                    Some("recall") => {
                        w.hours[h].1 += 1;
                        w.recalls += 1;
                    }
                    Some("pack") => w.sessions += 1,
                    _ => {}
                }
            }
        }
        if t < utc_since {
            continue;
        }
        let date = dt.date().to_string();
        let Some(day) = by_day.get_mut(&date) else {
            continue;
        };
        match v["event"].as_str() {
            Some("pack") => {
                recent.push(
                    json!({"t": t, "event": v["event"], "project": v["project"], "ids": v["ids"]}),
                );
                day["sessions"] = json!(day["sessions"].as_u64().unwrap_or(0) + 1);
            }
            Some("recall") => {
                recent.push(
                    json!({"t": t, "event": v["event"], "project": v["project"], "ids": v["ids"]}),
                );
                day["prompts_given_memories"] =
                    json!(day["prompts_given_memories"].as_u64().unwrap_or(0) + 1);
                total_hits += 1;
            }
            Some("recall_miss") => {
                day["recall_misses"] = json!(day["recall_misses"].as_u64().unwrap_or(0) + 1);
                total_misses += 1;
                continue;
            }
            Some("recall_skip") => {
                day["recall_skips"] = json!(day["recall_skips"].as_u64().unwrap_or(0) + 1);
                total_skips += 1;
                continue;
            }
            _ => continue,
        }
        for id in v["ids"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_i64)
        {
            *used.entry(id).or_default() += 1;
        }
    }

    let hours: Vec<Value> = week
        .into_iter()
        .map(|(date, w)| {
            let hourly_saved: u64 = w.hours.iter().map(|(s, _)| *s).sum();
            let cells: Vec<Value> = w
                .hours
                .iter()
                .map(|(s, r)| json!({"saved": s, "recalls": r}))
                .collect();
            if let Some(day) = by_day.get_mut(&date) {
                day["hours"] = json!(cells);
            }
            let saved = if w.saved_db > 0 {
                w.saved_db as u64
            } else {
                hourly_saved
            };
            json!({
                "date": date,
                "saved": saved,
                "recalls": w.recalls,
                "sessions": w.sessions,
                "hours": cells,
            })
        })
        .collect();

    // The newest recalls first, each with what reached the agent (never the prompt, which is not recorded).
    recent.reverse();
    recent.truncate(RECENT);
    let about = |id: i64| {
        conn.as_ref().and_then(|c| {
            c.query_row(
                "SELECT m.kind, m.scope, m.observed_at, c.text FROM chunks c JOIN sources s ON s.id=c.source_id JOIN memories m ON m.source_id=s.id WHERE c.id=?1",
                [id],
                |r| Ok(json!({"id": id, "kind": r.get::<_, String>(0)?, "scope": r.get::<_, String>(1)?, "observed_at": r.get::<_, String>(2)?,
                    "text": r.get::<_, String>(3)?.chars().take(120).collect::<String>()})),
            )
            .ok()
        })
        .unwrap_or_else(|| json!({"id": id, "gone": true}))
    };
    for r in &mut recent {
        let ids: Vec<i64> = r["ids"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_i64)
            .collect();
        r["memories"] = json!(ids.into_iter().map(about).collect::<Vec<_>>());
    }
    let mut top: Vec<(i64, u64)> = used.into_iter().collect();
    top.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    top.truncate(10);
    let mut most_used = Vec::new();
    for (id, times) in top {
        let memory = conn.as_ref().and_then(|c| {
            c.query_row(
                "SELECT m.kind, m.scope, c.text FROM chunks c JOIN sources s ON s.id=c.source_id JOIN memories m ON m.source_id=s.id WHERE c.id=?1",
                [id],
                |r| Ok(json!({"kind": r.get::<_, String>(0)?, "scope": r.get::<_, String>(1)?, "text": r.get::<_, String>(2)?.chars().take(160).collect::<String>()})),
            )
            .ok()
        });
        most_used.push(json!({"id": id, "times": times, "memory": memory}));
    }
    Ok(json!({
        "days": by_day.into_values().collect::<Vec<_>>(),
        "hours": hours,
        "most_used": most_used,
        "recent": recent,
        "recall": {"hits": total_hits, "misses": total_misses, "skips": total_skips},
        "activity_log": settings["activity"].as_bool().unwrap_or(true),
        "note": "dates in UTC; saves by the date the agent observed; prompt text is never recorded",
    }))
}
