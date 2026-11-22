//! `footnote docs refresh [library]`: keep cached documentation fresh without crawling it again (#310).
//!
//! A crawled entry keeps its pages beside the database (`<version>.pages/`, with `refresh.json`: per page the fetched URL and
//! its validators). Refresh asks each page with a conditional request (ETag, Last-Modified, else a hash of the body), so an
//! unchanged site costs one small request per page and no re-indexing. A changed page is judged; a material one is rewritten and
//! the folder is indexed again (the indexer already skips unchanged files, drops removed ones and re-chunks changed ones), the
//! keyword index first and the embeddings afterwards through the usual `docs.embed` job, which embeds only chunks without a vector.
//! New pages come from the links of changed pages and the sitemap, up to the entry's original page cap.
//!
//! The judge: `ChangeJudge` decides "material or cosmetic" for a changed page; cosmetic leaves the indexed text and its
//! embeddings alone (the new validators are kept, so the page is not fetched in full again, and the next judgement still
//! compares against what is indexed, so small changes add up). The default, `TokenDiff`, is deterministic and offline. A
//! Haiku-class model can be plugged in by implementing `ChangeJudge` and passing it to `refresh`: it only answers true or false for
//! a pair of texts and never writes index content. It is not wired to any API key or flag, and `model_calls` in the report is 0.
//! Entries made before this existed, from a folder (`--from`) or installed from a bundle have no page data and are skipped.
use crate::docs::{self, Add};
use anyhow::{Result, bail};
use footnote_library::crawl::{self, Client, Recheck, Validators};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::Path;

/// Decides whether a changed page is worth re-indexing and re-embedding.
pub trait ChangeJudge {
    fn is_material(&self, old: &str, new: &str) -> bool;
}

/// Most changed words a cosmetic change may have (a typo fix, a renamed link), however long the page: "off" turning into "on by
/// default now" is 5 words of a long page and must not be skipped.
const TYPO_WORDS: i64 = 4;

/// Cosmetic when the share of changed words is below the threshold, at most `TYPO_WORDS` words changed, no changed word holds a
/// digit (a number, version or limit that moved is never cosmetic), and no word changed place: "run A, do not run B" and "do not
/// run A, run B" have the same words, not the same meaning (#431). Words compare case- and punctuation-insensitively, so
/// reflowed text is no change.
pub struct TokenDiff(pub f64);

impl Default for TokenDiff {
    fn default() -> Self {
        TokenDiff(0.01)
    }
}

/// Above this many cells, the reorder check gives up and calls the change material: re-indexing a page is cheap, keeping a
/// stale one is not. Pages that differ by a few words in one place stay far below it once the common start and end are cut.
const ORDER_CELLS: usize = 4_000_000;

fn words(s: &str) -> Vec<String> {
    s.split_whitespace()
        .map(|w| {
            w.trim_matches(|c: char| !c.is_alphanumeric())
                .to_lowercase()
        })
        .filter(|w| !w.is_empty())
        .collect()
}

fn counts(words: &[String]) -> HashMap<&str, i64> {
    let mut m = HashMap::new();
    for w in words {
        *m.entry(w.as_str()).or_insert(0) += 1;
    }
    m
}

/// Whether some words changed place: an ordered diff needs more edits than the word counts explain (`moved`). A typo fix is one
/// word out and one in either way; a reordering needs edits although no count changed.
fn reordered(a: &[String], b: &[String], moved: i64) -> bool {
    let start = a.iter().zip(b).take_while(|(x, y)| x == y).count();
    let (a, b) = (&a[start..], &b[start..]);
    let end = a
        .iter()
        .rev()
        .zip(b.iter().rev())
        .take_while(|(x, y)| x == y)
        .count();
    let (a, b) = (&a[..a.len() - end], &b[..b.len() - end]);
    if a.is_empty() || b.is_empty() {
        return false; // only insertions or only deletions: the counts already tell
    }
    if a.len() * b.len() > ORDER_CELLS {
        return true;
    }
    // Longest common subsequence, two rows.
    let mut prev = vec![0usize; b.len() + 1];
    let mut row = vec![0usize; b.len() + 1];
    for x in a {
        for (j, y) in b.iter().enumerate() {
            row[j + 1] = if x == y {
                prev[j] + 1
            } else {
                row[j].max(prev[j + 1])
            };
        }
        std::mem::swap(&mut prev, &mut row);
    }
    let edits = a.len() + b.len() - 2 * prev[b.len()];
    edits as i64 > moved
}

impl ChangeJudge for TokenDiff {
    fn is_material(&self, old: &str, new: &str) -> bool {
        let (wa, wb) = (words(old), words(new));
        let (a, b) = (counts(&wa), counts(&wb));
        let total = (wa.len() + wb.len()) as i64;
        let mut moved = 0;
        for w in a.keys().chain(b.keys()).collect::<HashSet<_>>() {
            let d = (a.get(w).unwrap_or(&0) - b.get(w).unwrap_or(&0)).abs();
            if d > 0 && w.chars().any(|c| c.is_ascii_digit()) {
                return true;
            }
            moved += d;
        }
        if total > 0 && (moved > TYPO_WORDS || moved as f64 / total as f64 >= self.0) {
            return true;
        }
        reordered(&wa, &wb, moved)
    }
}

#[derive(Serialize, Deserialize)]
pub(crate) struct PageRec {
    pub url: String,
    pub validators: Validators,
}

#[derive(Serialize, Deserialize)]
pub(crate) struct Sidecar {
    pub scope: String,
    pub max_pages: usize,
    pub pages: BTreeMap<String, PageRec>,
    #[serde(default)]
    pub refreshed_unix: u64,
    /// Pages a refresh fetched and found empty (page key -> when, Unix seconds), skipped until `RETRY_EMPTY` has passed.
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub empty: BTreeMap<String, u64>,
}

/// How long a page found empty is skipped before a refresh fetches it again, in case it gained content: 30 days.
const RETRY_EMPTY: u64 = 30 * 24 * 3600;

fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_secs())
}

impl Sidecar {
    /// The page keys the entry already holds (see `crawl::key_of`), and the pages found empty less than `RETRY_EMPTY` ago.
    pub fn known(&self) -> HashSet<String> {
        let now = now();
        self.pages
            .values()
            .filter_map(|p| crawl::key_of(&p.url))
            .chain(
                self.empty
                    .iter()
                    .filter(|(_, at)| now.saturating_sub(**at) < RETRY_EMPTY)
                    .map(|(k, _)| k.clone()),
            )
            .collect()
    }

    /// Remember the pages just found empty, and forget those whose wait is over (they were fetched again if listed).
    fn remember_empty(&mut self, keys: Vec<String>, now: u64) {
        self.empty
            .retain(|_, at| now.saturating_sub(*at) < RETRY_EMPTY);
        self.empty.extend(keys.into_iter().map(|k| (k, now)));
    }

    /// Write newly found pages beside the entry's others; returns how many.
    pub fn add(&mut self, dir: &Path, found: Vec<crawl::Found>) -> Result<usize> {
        let mut n = self
            .pages
            .keys()
            .filter_map(|f| f.strip_suffix(".md")?.parse::<usize>().ok())
            .max()
            .unwrap_or(0);
        let added = found.len();
        for f in found {
            n += 1;
            std::fs::write(dir.join(format!("{n}.md")), &f.text)?;
            self.pages.insert(
                format!("{n}.md"),
                PageRec {
                    url: f.url.to_string(),
                    validators: f.validators,
                },
            );
        }
        Ok(added)
    }
}

/// Index the entry's page folder again (changed pages are re-chunked, removed ones dropped), keywords only.
pub(crate) fn reindex(db: &Path, dir: &Path) -> Result<()> {
    let mut c = crate::app::open(db, true)?;
    footnote_library::index(
        &mut c,
        dir,
        std::slice::from_ref(&dir.to_path_buf()),
        100_000,
        2_048,
        &mut |_, _| {},
    )?;
    let _ = crate::lexical::sync(&c); // a failure only means searches fall back to FTS5, as for `add`
    Ok(())
}

pub fn run(state: &Path, library: Option<&str>, judge: &dyn ChangeJudge, a: &Add) -> Result<Value> {
    let site = library.map(|l| docs::safe("library", l)).transpose()?;
    let wanted: Vec<_> = docs::entries(state)
        .into_iter()
        .filter(|e| site.as_ref().is_none_or(|s| &e.0 == s))
        .collect();
    if let Some(l) = library
        && wanted.is_empty()
    {
        bail!("{l} is not in the docs cache (see `footnote docs list`)");
    }
    let client = Client::default();
    let (mut rows, mut touched) = (Vec::new(), Vec::new());
    for (site, version, db) in wanted {
        match one(&client, judge, &db) {
            Ok(mut v) => {
                if v["changed"].as_u64().unwrap_or(0)
                    + v["added"].as_u64().unwrap_or(0)
                    + v["removed"].as_u64().unwrap_or(0)
                    > 0
                {
                    touched.push(db);
                }
                v["site"] = json!(site);
                v["version"] = json!(version);
                rows.push(v);
            }
            Err(e) => {
                rows.push(json!({"site": site, "version": version, "error": format!("{e:#}")}))
            }
        }
    }
    let embedding = docs::embed_missing(state, &touched, a)?;
    Ok(json!({"refreshed": rows, "embedding": embedding, "model_calls": 0}))
}

fn one(client: &Client, judge: &dyn ChangeJudge, db: &Path) -> Result<Value> {
    let dir = db.with_extension("pages");
    let Ok(bytes) = std::fs::read(dir.join("refresh.json")) else {
        return Ok(json!({
            "skipped": "no page data (added before refresh existed, from a folder, or installed from a bundle); run `docs add` for it again"
        }));
    };
    let mut side: Sidecar = serde_json::from_slice(&bytes)?;
    let (mut same, mut changed, mut cosmetic, mut removed, mut unreachable) = (0, 0, 0, 0, 0);
    let mut seeds = Vec::new();
    for file in side.pages.keys().cloned().collect::<Vec<_>>() {
        let rec = &side.pages[&file];
        match client.recheck(&rec.url, &rec.validators) {
            Recheck::Same(v) => {
                same += 1;
                if let Some(entry) = side.pages.get_mut(&file) {
                    entry.validators = v;
                }
            }
            Recheck::Changed(text, v, links) => {
                seeds.extend(links);
                let old = std::fs::read_to_string(dir.join(&file)).unwrap_or_default();
                if let Some(entry) = side.pages.get_mut(&file) {
                    entry.validators = v;
                }
                if judge.is_material(&old, &text) {
                    std::fs::write(dir.join(&file), text)?;
                    changed += 1;
                } else {
                    cosmetic += 1;
                }
            }
            Recheck::Gone => {
                let _ = std::fs::remove_file(dir.join(&file));
                side.pages.remove(&file);
                removed += 1;
            }
            Recheck::Unreachable | _ => unreachable += 1,
        }
    }
    let known = side.known();
    let room = side.max_pages.saturating_sub(side.pages.len());
    let (found, empty) = if room > 0 {
        client.find_new(&side.scope, &known, seeds, room)
    } else {
        (Vec::new(), Vec::new())
    };
    let added = side.add(&dir, found)?;
    if changed + removed + added > 0 {
        reindex(db, &dir)?;
    }
    side.refreshed_unix = now();
    side.remember_empty(empty, side.refreshed_unix);
    std::fs::write(dir.join("refresh.json"), serde_json::to_vec_pretty(&side)?)?;
    Ok(json!({
        "summary": format!("{same} unchanged, {changed} changed, {added} added, {removed} removed"),
        "unchanged": same, "changed": changed, "added": added, "removed": removed,
        "cosmetic_skipped": cosmetic, "unreachable": unreachable, "pages": side.pages.len(),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_judge_skips_typos_and_reflow_but_not_numbers_or_new_text() {
        let base = "Connections are reused from the pool. ".repeat(30)
            + "The colour of the badge is blue.";
        let judge = TokenDiff::default();
        assert!(!judge.is_material(&base, &base.replace("colour", "color")));
        assert!(!judge.is_material(&base, &base.replace(". ", ".\n").to_uppercase()));
        assert!(judge.is_material(&base, &base.replace("blue", "blue 42")));
        assert!(judge.is_material(
            &base,
            &(base.clone() + " A whole new paragraph about timeouts and retries follows.")
        ));
    }

    #[test]
    fn reordered_words_are_material_even_on_a_long_page() {
        let filler = "Connections are reused from the pool. ".repeat(200);
        let page = |rule: &str| format!("{filler}{rule} {filler}");
        let judge = TokenDiff::default();
        // Same words, same counts, other meaning (#431).
        assert!(judge.is_material(
            &page("Run the migration, do not run the backup."),
            &page("Do not run the migration, run the backup.")
        ));
        assert!(judge.is_material(
            &page("Allow reads, deny writes."),
            &page("Deny reads, allow writes.")
        ));
        // Reflowed text, same order: still no change.
        let rule = page("Run the migration, do not run the backup.");
        assert!(!judge.is_material(&rule, &rule.replace(", ", ",\n").replace(". ", ".\n\n")));
        // A typo fix in the middle is not a reordering.
        assert!(!judge.is_material(
            &page("The colour of the badge is blue."),
            &page("The color of the badge is blue.")
        ));
    }
}
