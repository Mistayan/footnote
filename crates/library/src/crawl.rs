//! Documentation crawler (backlog item 14; study: docs/research/DOCS-INGESTION-STUDY.md). Cheapest discovery first: the site's
//! `llms.txt`, its sitemap, then links within the start URL's path. Each page's main content (Readability) becomes Markdown in
//! `<out>/<n>.md`; `<out>/urls.json` maps every file to its URL. Polite by construction: robots.txt, one request at a time,
//! an identifying user agent. JavaScript is not run.
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};
use std::{
    collections::{HashSet, VecDeque},
    fs,
    path::Path,
    time::Duration,
};
use ureq::ResponseExt;
use url::Url;

const AGENT: &str =
    "FootnoteDocs/0.1 (+https://github.com/bobcat88/footnote; local documentation index)";
const MAX_BYTES: u64 = 8 * 1024 * 1024;

pub struct Options<'a> {
    pub start: &'a str,
    pub max_pages: usize,
    /// Pages whose URL matches are skipped (for example translated mirrors).
    pub exclude: Option<regex::Regex>,
}

fn agent() -> ureq::Agent {
    use ureq::tls::{RootCerts, TlsConfig, TlsProvider};
    // System roots, not ureq's bundled Mozilla list: fastapi.tiangolo.com fails against the bundle, and companies add their own roots.
    ureq::Agent::config_builder()
        .tls_config(
            TlsConfig::builder()
                .provider(TlsProvider::NativeTls)
                .root_certs(RootCerts::PlatformVerifier)
                .build(),
        )
        .timeout_global(Some(Duration::from_secs(30)))
        .user_agent(AGENT)
        .http_status_as_error(false)
        .build()
        .into()
}

/// Body and final URL (after redirects) of a successful text response.
fn get(agent: &ureq::Agent, url: &Url) -> Option<(String, Url, String)> {
    let mut r = agent.get(url.as_str()).call().ok()?;
    if !r.status().is_success() {
        return None;
    }
    let kind = r
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_ascii_lowercase();
    let last = r
        .get_uri()
        .to_string()
        .parse::<Url>()
        .unwrap_or_else(|_| url.clone());
    let body = r
        .body_mut()
        .with_config()
        .limit(MAX_BYTES)
        .read_to_string()
        .ok()?;
    Some((body, last, kind))
}

/// Same host, under the start path, http(s), no fragment, not excluded.
fn in_scope(u: &Url, start: &Url, exclude: &Option<regex::Regex>) -> bool {
    // "/3/" and "/docs" keep their folder; "/guide/index.html" keeps "/guide".
    let p = start.path();
    let last = p.rsplit('/').next().unwrap_or("");
    let dir = if p.ends_with('/') || !last.contains('.') {
        p.trim_end_matches('/')
    } else {
        p.rsplit_once('/').map_or("", |(d, _)| d)
    };
    matches!(u.scheme(), "http" | "https")
        && u.host_str() == start.host_str()
        && (u.path() == dir || u.path().starts_with(&format!("{dir}/"))) // "/3" must not take "/3.11/"
        && !exclude.as_ref().is_some_and(|re| re.is_match(u.as_str()))
}

fn normalize(mut u: Url) -> Url {
    u.set_fragment(None);
    u.set_query(None);
    u
}

/// One key per page whatever its form: `/guide/features`, `/guide/features/`, `.md`, `.html` and `/index.html` are the same page.
fn page_key(u: &Url) -> String {
    let s = u.as_str().trim_end_matches('/');
    let s = s
        .strip_suffix(".md")
        .or_else(|| s.strip_suffix(".html"))
        .unwrap_or(s);
    s.strip_suffix("/index").unwrap_or(s).to_string()
}

/// Links of an HTML page or of an llms.txt (Markdown links), resolved against `base`.
fn links(text: &str, base: &Url) -> Vec<Url> {
    static HREF: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re = HREF.get_or_init(|| {
        regex::Regex::new(r#"(?:href=["']([^"'#][^"']*)["']|\]\((https?://[^)\s]+|/[^)\s]*)\))"#)
            .expect("valid pattern")
    });
    re.captures_iter(text)
        .filter_map(|c| c.get(1).or_else(|| c.get(2)))
        .filter_map(|m| base.join(m.as_str()).ok())
        .map(normalize)
        .collect()
}

/// Page URLs listed by the sitemap (`<loc>` entries; nested sitemap indexes are followed once).
fn sitemap(agent: &ureq::Agent, root: &Url) -> Vec<Url> {
    let loc = regex::Regex::new(r"<loc>\s*([^<\s]+)\s*</loc>").expect("valid pattern");
    let mut out = Vec::new();
    let Some((xml, _, _)) = root.join("/sitemap.xml").ok().and_then(|u| get(agent, &u)) else {
        return out;
    };
    for c in loc.captures_iter(&xml) {
        let Ok(u) = Url::parse(&c[1]) else { continue };
        if u.path().ends_with(".xml") {
            if let Some((inner, _, _)) = get(agent, &u) {
                out.extend(
                    loc.captures_iter(&inner)
                        .filter_map(|c| Url::parse(&c[1]).ok()),
                );
            }
        } else {
            out.push(u);
        }
    }
    out.into_iter().map(normalize).collect()
}

/// Main content as Markdown: Readability first, the whole body when it finds nothing.
fn markdown(html: &str, url: &Url) -> String {
    let main = dom_smoothie::Readability::new(html, Some(url.as_str()), None)
        .ok()
        .and_then(|mut r| r.parse().ok())
        .map(|a| a.content.to_string())
        .filter(|c| c.len() > 200)
        .unwrap_or_else(|| html.to_string());
    htmd::HtmlToMarkdown::builder()
        .skip_tags(vec!["script", "style", "nav", "footer", "noscript", "svg"])
        .build()
        .convert(&main)
        .unwrap_or_default()
}

pub fn crawl(out: &Path, o: &Options, progress: &mut dyn FnMut(u64, u64)) -> Result<Value> {
    let start = normalize(Url::parse(o.start).context("start URL")?);
    if !matches!(start.scheme(), "http" | "https") {
        bail!("only http and https URLs can be crawled");
    }
    fs::create_dir_all(out)?;
    let agent = agent();
    // The scope follows a redirect to another host (vitejs.dev/guide/ answers from vite.dev/guide/; docs.pydantic.dev/latest/
    // from pydantic.dev/docs/validation/latest/) but not one within the site: tailwindcss.com/docs redirects to one page,
    // /docs/installation/using-vite, and the scope must stay /docs.
    let start = match get(&agent, &start) {
        Some((_, last, _)) if last.host_str() != start.host_str() => normalize(last),
        _ => start,
    };
    let robots = start
        .join("/robots.txt")
        .ok()
        .and_then(|u| get(&agent, &u))
        .filter(|(_, _, kind)| !kind.contains("html")) // some sites answer a missing robots.txt with an HTML page
        .and_then(|(txt, _, _)| texting_robots::Robot::new("FootnoteDocs", txt.as_bytes()).ok());
    let allowed = |u: &Url| robots.as_ref().is_none_or(|r| r.allowed(u.as_str()));

    // Discovery: llms.txt beside the start page and at the root, then the sitemap, then the start page itself.
    let mut seeds = Vec::new();
    let mut via_llms = 0;
    for llms in [start.join("llms.txt"), start.join("/llms.txt")]
        .into_iter()
        .flatten()
    {
        if let Some((txt, _, kind)) = get(&agent, &llms)
            && !kind.contains("html")
        {
            let found = links(&txt, &llms);
            via_llms += found.len();
            seeds.extend(found);
        }
    }
    let from_sitemap = sitemap(&agent, &start);
    let via_sitemap = from_sitemap.len();
    seeds.push(start.clone());
    seeds.extend(from_sitemap);

    let mut queue: VecDeque<Url> = VecDeque::new();
    let mut seen: HashSet<String> = HashSet::new();
    let mut written: HashSet<String> = HashSet::new(); // page keys already saved (llms.txt `.md` first, then HTML)
    for u in seeds {
        if in_scope(&u, &start, &o.exclude) && seen.insert(u.to_string()) {
            queue.push_back(u);
        }
    }
    let (mut pages, mut bytes, mut skipped) = (0usize, 0u64, 0usize);
    let mut urls = serde_json::Map::new();
    while let Some(u) = queue.pop_front() {
        if pages >= o.max_pages {
            break;
        }
        if !allowed(&u) {
            skipped += 1;
            continue;
        }
        let Some((body, last, kind)) = get(&agent, &u) else {
            skipped += 1;
            continue;
        };
        let last = normalize(last);
        if last != u && (!in_scope(&last, &start, &o.exclude) || !seen.insert(last.to_string())) {
            continue; // a redirect out of scope or to a page already taken
        }
        let text = if kind.contains("html") {
            for l in links(&body, &last) {
                if in_scope(&l, &start, &o.exclude) && seen.insert(l.to_string()) {
                    queue.push_back(l);
                }
            }
            markdown(&body, &last)
        } else if kind.contains("markdown") || kind.contains("text/plain") {
            body
        } else {
            continue;
        };
        if text.trim().len() < 50 {
            skipped += 1; // empty main content: probably rendered by JavaScript
            continue;
        }
        if !written.insert(page_key(&last)) {
            continue; // the same page in another form (Markdown and HTML both listed)
        }
        pages += 1;
        bytes += text.len() as u64;
        let file = format!("{pages}.md");
        fs::write(out.join(&file), &text)?;
        urls.insert(file, json!(last.as_str()));
        progress(pages as u64, bytes);
    }
    fs::write(out.join("urls.json"), serde_json::to_string_pretty(&urls)?)?;
    Ok(
        json!({"pages": pages, "bytes": bytes, "skipped": skipped, "queued_left": queue.len(),
        "discovered": {"llms_txt": via_llms, "sitemap": via_sitemap}, "out": out, "robots_txt": robots.is_some()}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scope_keeps_the_start_folder_only() {
        let u = |s: &str| Url::parse(s).unwrap();
        let start = u("https://docs.python.org/3/");
        assert!(in_scope(
            &u("https://docs.python.org/3/library/os.html"),
            &start,
            &None
        ));
        assert!(!in_scope(
            &u("https://docs.python.org/3.11/"),
            &start,
            &None
        ));
        assert!(!in_scope(&u("https://example.com/3/x"), &start, &None));
        let page = u("https://vite.dev/guide/index.html");
        assert!(in_scope(
            &u("https://vite.dev/guide/features"),
            &page,
            &None
        ));
        let fr = Some(regex::Regex::new("/fr/").unwrap());
        assert!(!in_scope(
            &u("https://docs.python.org/3/fr/x.html"),
            &start,
            &fr
        ));
    }

    #[test]
    fn page_forms_share_one_key() {
        let k = |s: &str| page_key(&Url::parse(s).unwrap());
        let a = k("https://vite.dev/guide/features");
        for other in [
            "https://vite.dev/guide/features.md",
            "https://vite.dev/guide/features/",
            "https://vite.dev/guide/features.html",
        ] {
            assert_eq!(k(other), a);
        }
        assert_eq!(
            k("https://vite.dev/guide/index.html"),
            k("https://vite.dev/guide/")
        );
        assert_ne!(k("https://vite.dev/guide/cli"), a);
    }

    #[test]
    fn links_from_html_and_llms_txt() {
        let base = Url::parse("https://vite.dev/guide/").unwrap();
        let found = links(
            r#"<a href="features#x">a</a> [b](/config/) [c](https://vite.dev/guide/cli.md)"#,
            &base,
        );
        let found: Vec<_> = found.iter().map(Url::as_str).collect();
        assert_eq!(
            found,
            [
                "https://vite.dev/guide/features",
                "https://vite.dev/config/",
                "https://vite.dev/guide/cli.md"
            ]
        );
    }
}
