//! `footnote docs refresh`: unchanged sites cost no re-indexing, and only changed, removed and new pages are touched.
use assert_cmd::Command;
use serde_json::Value;
use std::{
    collections::HashMap,
    io::{Read, Write},
    net::TcpListener,
    sync::{
        Arc, Mutex,
        atomic::{AtomicUsize, Ordering},
    },
    thread,
};

type Site = Arc<Mutex<HashMap<String, String>>>;

fn page(title: &str, body: &str, links: &[&str]) -> String {
    let a: String = links
        .iter()
        .map(|l| format!("<a href=\"{l}\">x</a> "))
        .collect();
    format!("<html><body><main><h1>{title}</h1><p>{body}</p>{a}</main></body></html>")
}

/// A local docs site with ETags. Returns its port, how many full (200) bodies it has served, and every path requested.
fn serve(site: Site) -> (u16, Arc<AtomicUsize>, Arc<Mutex<Vec<String>>>) {
    let l = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = l.local_addr().unwrap().port();
    let full = Arc::new(AtomicUsize::new(0));
    let served = full.clone();
    let paths: Arc<Mutex<Vec<String>>> = Arc::default();
    let asked = paths.clone();
    thread::spawn(move || {
        for mut c in l.incoming().flatten() {
            let (site, served, asked) = (site.clone(), served.clone(), asked.clone());
            thread::spawn(move || {
                let mut buf = [0u8; 4096];
                let n = c.read(&mut buf).unwrap_or(0);
                let req = String::from_utf8_lossy(&buf[..n]).to_string();
                let path = req.split_whitespace().nth(1).unwrap_or("/").to_string();
                asked.lock().unwrap().push(path.clone());
                let body = site.lock().unwrap().get(&path).cloned();
                let reply = match body {
                    None => {
                        "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                            .into()
                    }
                    Some(b) => {
                        let etag = format!(
                            "\"{:x}\"",
                            b.len() * 31 + b.bytes().map(u64::from).sum::<u64>() as usize
                        );
                        if req
                            .to_lowercase()
                            .contains(&format!("if-none-match: {etag}"))
                        {
                            format!(
                                "HTTP/1.1 304 Not Modified\r\nETag: {etag}\r\nConnection: close\r\n\r\n"
                            )
                        } else {
                            served.fetch_add(1, Ordering::SeqCst);
                            format!(
                                "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nETag: {etag}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{b}",
                                b.len()
                            )
                        }
                    }
                };
                let _ = c.write_all(reply.as_bytes());
            });
        }
    });
    (port, full, paths)
}

#[test]
fn refresh_touches_only_what_changed() {
    let t = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let state = t.path().join("state");
    let run = |args: &[&str]| -> Value {
        let out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
            .env("FOOTNOTE_STATE_DIR", &state)
            .args(args)
            .output()
            .unwrap();
        assert!(out.status.success(), "{out:?}");
        serde_json::from_slice(&out.stdout).unwrap()
    };
    let filler =
        "Connections are reused from the pool and returned when the request ends. ".repeat(30);
    let site: Site = Arc::default();
    let set = |path: &str, html: String| {
        site.lock().unwrap().insert(path.into(), html);
    };
    set("/docs/", page("Home", &filler, &["/docs/a", "/docs/b"]));
    set("/docs/a", page("Alpha", &filler, &["/docs/"]));
    set(
        "/docs/b",
        page(
            "Beta",
            &format!("The zebra setting is off. {filler}"),
            &["/docs/"],
        ),
    );
    let (port, full, _) = serve(site.clone());
    let url = format!("http://127.0.0.1:{port}/docs/");

    let added = run(&["docs", "add", &url, "--no-embed", "--site", "mock"]);
    assert_eq!(added["index"]["indexed"], 3, "{added}");
    let db = added["db"].as_str().unwrap().to_string();
    let chunks = |needle: &str| -> i64 {
        rusqlite::Connection::open(&db)
            .unwrap()
            .query_row(
                "SELECT count(*) FROM chunks c JOIN sources s ON s.id=c.source_id WHERE s.status='indexed' AND c.text LIKE ?1",
                [format!("%{needle}%")],
                |r| r.get(0),
            )
            .unwrap()
    };
    let refresh = || run(&["docs", "refresh", "mock", "--no-embed"])["refreshed"][0].clone();

    // Unchanged: every page answers 304, nothing is re-indexed.
    let before = full.load(Ordering::SeqCst);
    let r = refresh();
    assert_eq!(
        r["summary"], "3 unchanged, 0 changed, 0 added, 0 removed",
        "{r}"
    );
    assert_eq!(
        full.load(Ordering::SeqCst),
        before,
        "no page body was downloaded again"
    );

    // b changes materially, a gets a spelling fix (cosmetic), and b's new link finds the new page c.
    set(
        "/docs/b",
        page(
            "Beta",
            &format!("The zebra setting is on by default now. {filler}"),
            &["/docs/", "/docs/c"],
        ),
    );
    set(
        "/docs/a",
        page(
            "Alpha",
            &filler.replacen("reused", "re-used", 1),
            &["/docs/"],
        ),
    );
    set(
        "/docs/c",
        page("Gamma", &format!("The giraffe flag is new. {filler}"), &[]),
    );
    let r = refresh();
    assert_eq!(
        r["summary"], "1 unchanged, 1 changed, 1 added, 0 removed",
        "{r}"
    );
    assert_eq!(r["cosmetic_skipped"], 1, "{r}");
    assert_eq!(chunks("zebra setting is on by default"), 1);
    assert_eq!(chunks("zebra setting is off"), 0);
    assert_eq!(chunks("giraffe flag"), 1);

    // Punctuation only: cosmetic, the indexed text stays.
    set(
        "/docs/c",
        page("Gamma", &format!("The giraffe flag is new! {filler}"), &[]),
    );
    let r = refresh();
    assert_eq!(r["cosmetic_skipped"], 1, "{r}");
    assert_eq!(r["changed"], 0, "{r}");

    // A removed page leaves the index.
    site.lock().unwrap().remove("/docs/c");
    let r = refresh();
    assert_eq!(r["removed"], 1, "{r}");
    assert_eq!(chunks("giraffe flag"), 0);
    assert_eq!(r["pages"], 3, "{r}");
}

#[test]
fn a_page_found_empty_is_not_fetched_again_until_its_wait_is_over() {
    let t = tempfile::tempdir_in(env!("CARGO_TARGET_TMPDIR")).unwrap();
    let state = t.path().join("state");
    let run = |args: &[&str]| -> Value {
        let out = Command::new(assert_cmd::cargo::cargo_bin!("footnote"))
            .env("FOOTNOTE_STATE_DIR", &state)
            .args(args)
            .output()
            .unwrap();
        assert!(out.status.success(), "{out:?}");
        serde_json::from_slice(&out.stdout).unwrap()
    };
    let filler =
        "Connections are reused from the pool and returned when the request ends. ".repeat(30);
    let site: Site = Arc::default();
    let (port, _, paths) = serve(site.clone());
    let base = format!("http://127.0.0.1:{port}");
    {
        let mut s = site.lock().unwrap();
        s.insert("/docs/".into(), page("Home", &filler, &["/docs/a"]));
        s.insert("/docs/a".into(), page("Alpha", &filler, &["/docs/"]));
        // Listed in the sitemap, linked from nowhere, and empty: a redirect stub.
        s.insert("/docs/stub".into(), page("Moved", "", &[]));
        s.insert(
            "/sitemap.xml".into(),
            format!(
                "<urlset><url><loc>{base}/docs/</loc></url><url><loc>{base}/docs/a</loc></url>                 <url><loc>{base}/docs/stub</loc></url></urlset>"
            ),
        );
    }
    let added = run(&[
        "docs",
        "add",
        &format!("{base}/docs/"),
        "--no-embed",
        "--site",
        "mock",
    ]);
    assert_eq!(added["index"]["indexed"], 2, "{added}");
    let stub_hits = || {
        paths
            .lock()
            .unwrap()
            .iter()
            .filter(|p| *p == "/docs/stub")
            .count()
    };
    let refresh = || run(&["docs", "refresh", "mock", "--no-embed"])["refreshed"][0].clone();

    // The first refresh fetches the stub and finds it empty; the second does not ask for it.
    let before = stub_hits();
    refresh();
    let after_first = stub_hits();
    assert_eq!(
        after_first,
        before + 1,
        "the first refresh fetches the stub"
    );
    let r = refresh();
    assert_eq!(r["added"], 0, "{r}");
    assert_eq!(
        stub_hits(),
        after_first,
        "the empty page was requested again"
    );

    // Thirty days on, the stub is fetched again, and picked up now that it has content.
    let side = std::path::Path::new(added["db"].as_str().unwrap())
        .with_extension("pages")
        .join("refresh.json");
    let mut v: Value = serde_json::from_slice(&std::fs::read(&side).unwrap()).unwrap();
    let key = v["empty"]
        .as_object()
        .unwrap()
        .keys()
        .next()
        .unwrap()
        .clone();
    v["empty"][&key] = Value::from(v["empty"][&key].as_u64().unwrap() - 31 * 24 * 3600);
    std::fs::write(&side, serde_json::to_vec(&v).unwrap()).unwrap();
    site.lock().unwrap().insert(
        "/docs/stub".into(),
        page("Stub", &format!("The okapi page moved here. {filler}"), &[]),
    );
    let r = refresh();
    assert_eq!(stub_hits(), after_first + 1, "{r}");
    assert_eq!(r["added"], 1, "{r}");
    let v: Value = serde_json::from_slice(&std::fs::read(&side).unwrap()).unwrap();
    assert!(v.get("empty").is_none(), "{v}");
}
