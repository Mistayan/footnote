//! Bounded, HTTP-only Spider crawl for DOCS-CRAWL; outputs the same files as Footnote's crawler.
use anyhow::{Context, Result, bail};
use spider::{tokio, website::Website};
use std::{collections::BTreeMap, path::PathBuf, time::Instant};
use url::Url;

#[tokio::main]
async fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 6 {
        bail!("usage: spider-probe START OUTPUT PAGE_LIMIT ALLOW_REGEX EXCLUDE_REGEX_OR_DASH");
    }
    let start = Url::parse(&args[1])?;
    let out = PathBuf::from(&args[2]);
    let max: u32 = args[3].parse()?;
    if max == 0 || max > 500 || out.exists() {
        bail!("page limit must be 1..500 and output must not already exist");
    }
    std::fs::create_dir_all(&out)?;
    let mut site = Website::new(start.as_str());
    site.with_limit(max)
        .with_concurrency_limit(Some(2))
        .with_respect_robots_txt(true)
        .with_delay(100)
        .with_request_timeout(Some(std::time::Duration::from_secs(30)))
        .with_user_agent(Some("FootnoteDocs/0.1 (+https://github.com/bobcat88/footnote; benchmark)"))
        .with_whitelist_url(Some(vec![args[4].clone().into()]));
    if args[5] != "-" {
        site.with_blacklist_url(Some(vec![args[5].clone().into()]));
    }
    let began = Instant::now();
    site.scrape().await;
    let pages = site.get_pages().context("Spider did not return pages")?;
    let mut urls = BTreeMap::new();
    let (mut skipped, mut bytes) = (0usize, 0usize);
    for page in pages {
        if !page.status_code.is_success() || page.get_html_bytes_u8().len() > 8 * 1024 * 1024 {
            skipped += 1;
            continue;
        }
        let url = Url::parse(page.get_url())?;
        let body = page.get_html();
        let text = if url.path().ends_with(".md") || url.path().ends_with(".txt") {
            body
        } else {
            let main = dom_smoothie::Readability::new(body.as_str(), Some(url.as_str()), None)
                .ok().and_then(|mut r| r.parse().ok()).map(|a| a.content.to_string())
                .filter(|c| c.len() > 200).unwrap_or(body);
            htmd::HtmlToMarkdown::builder()
                .skip_tags(vec!["script", "style", "nav", "footer", "noscript", "svg"])
                .build().convert(&main).unwrap_or_default()
        };
        if text.trim().len() < 50 { skipped += 1; continue; }
        let file = format!("{}.md", urls.len() + 1);
        std::fs::write(out.join(&file), &text)?;
        urls.insert(file, url.to_string());
        bytes += text.len();
    }
    std::fs::write(out.join("urls.json"), serde_json::to_vec_pretty(&urls)?)?;
    println!("{}", serde_json::json!({"pages": urls.len(), "returned": pages.len(), "skipped": skipped,
        "bytes": bytes, "seconds": began.elapsed().as_secs_f64(), "robots": true, "max_concurrency": 2,
        "page_limit": max, "start": start.as_str(), "allow": args[4], "exclude": args[5]}));
    Ok(())
}
