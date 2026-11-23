//! Embedding model manager: list, install, use, remove, recommend (P1 item 9).
//!
//! `models install` is the only command that reaches the network: it fetches public model files pinned to a Hugging Face commit
//! and checks them against pinned SHA-256 hashes. The manifest it writes is byte-identical to the one the former Python script
//! wrote, because a model's identity is the hash of its manifest (vectors computed before stay valid).
use anyhow::{Context, Result, bail, ensure};
use serde_json::{Value, json};
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
};

struct Recipe {
    name: &'static str,
    repo: &'static str,
    revision: &'static str,
    /// The model file in the repository: `.onnx` (with `tokenizer.json`), or `.gguf` (llama.cpp, tokenizer inside).
    file: &'static str,
    /// What `install` downloads, in bytes (model file plus tokenizer at the pinned revision, from the Hugging Face API).
    download_bytes: u64,
    query_prefix: &'static str,
    passage_prefix: &'static str,
    max_length: u32,
    pad_token: &'static str,
    quantization: &'static str,
    /// Pinned (file, sha256) of every downloaded file; a download that does not match is removed.
    sha256: &'static [(&'static str, &'static str)],
    role: &'static str,
    /// Written into the manifest and shown on install when it restricts use; empty for the permissive ONNX models.
    license: &'static str,
}

impl Recipe {
    fn gguf(&self) -> bool {
        self.file.ends_with(".gguf")
    }
}

const RECIPES: &[Recipe] = &[
    Recipe {
        name: "bekko-a8m",
        download_bytes: 164462521,
        repo: "hotchpotch/bekko-embedding-v1-a8m",
        revision: "c721113d59a1d91b447450324f51c4b3332c924a",
        file: "onnx/model.onnx",
        query_prefix: "",
        passage_prefix: "",
        max_length: 512,
        pad_token: "<pad>",
        quantization: "none (fp32)",
        sha256: &[
            (
                "model.onnx",
                "96d8cc6199e96357b21b2fb12f6d7ffd2d4abc7b182fe94b5468fbd6dc819af7",
            ),
            (
                "tokenizer.json",
                "8bd47075711f75a143d1b78e01a41cc65c1c591b00d3cfeffc23db07adce1392",
            ),
        ],
        role: "default pair, multilingual half",
        license: "MIT",
    },
    Recipe {
        name: "gte-small",
        download_bytes: 34726087,
        repo: "Xenova/gte-small",
        revision: "5927d1727bb12db490052a1b33265ad78058de08",
        file: "onnx/model_quantized.onnx",
        query_prefix: "",
        passage_prefix: "",
        max_length: 512,
        pad_token: "[PAD]",
        quantization: "onnx-dynamic-int8",
        sha256: &[
            (
                "model.onnx",
                "18dec105109b6004369799ca4761fb8fb413c64172c02147bcfac186b5c5f6cb",
            ),
            (
                "tokenizer.json",
                "da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0",
            ),
        ],
        role: "default pair, English half",
        license: "MIT",
    },
    Recipe {
        name: "e5-small",
        download_bytes: 135390915,
        repo: "Xenova/multilingual-e5-small",
        revision: "761b726dd34fb83930e26aab4e9ac3899aa1fa78",
        file: "onnx/model_quantized.onnx",
        query_prefix: "query: ",
        passage_prefix: "passage: ",
        max_length: 512,
        pad_token: "<pad>",
        quantization: "onnx-dynamic-int8",
        sha256: &[
            (
                "model.onnx",
                "f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193",
            ),
            (
                "tokenizer.json",
                "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
            ),
        ],
        role: "earlier model, tests and comparison",
        license: "MIT",
    },
    Recipe {
        name: "minilm",
        download_bytes: 135391039,
        repo: "Xenova/paraphrase-multilingual-MiniLM-L12-v2",
        revision: "2c4055b12046f11709e9df2c122e59ffbdc2f900",
        file: "onnx/model_quantized.onnx",
        query_prefix: "",
        passage_prefix: "",
        max_length: 128,
        pad_token: "<pad>",
        quantization: "onnx-dynamic-int8",
        sha256: &[
            (
                "model.onnx",
                "66fc00f5f29afcaff34092e1bdd20008ca3918265a82fb9695a551e510cc4ebc",
            ),
            (
                "tokenizer.json",
                "b60b6b43406a48bf3638526314f3d232d97058bc93472ff2de930d43686fa441",
            ),
        ],
        role: "earlier model, tests and comparison",
        license: "Apache-2.0",
    },
    Recipe {
        name: "jina-v5-nano",
        download_bytes: 232883776,
        repo: "jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF",
        revision: "59cfaceeeb7d738c404659435af4c0da74d06c96",
        file: "v5-nano-retrieval-Q8_0.gguf",
        query_prefix: "Query: ",
        passage_prefix: "Document: ",
        max_length: 512,
        pad_token: "",
        quantization: "Q8_0",
        sha256: &[(
            "model.gguf",
            "86b6e6279e9b9e71389f02a082764a2ac2b15a50e37482c26f98d69092f12442",
        )],
        role: "French or mixed corpora, opt-in",
        license: "CC-BY-NC-4.0 (no commercial use)",
    },
];
const DEFAULT_PAIR: [&str; 2] = ["bekko-a8m", "gte-small"];

fn recipe(name: &str) -> Result<&'static Recipe> {
    RECIPES
        .iter()
        .find(|r| r.name == name)
        .with_context(|| format!("unknown model `{name}`; `footnote models list` shows them"))
}

pub fn models_dir(state: &Path) -> PathBuf {
    state.join("models")
}

/// Models the memory hook uses (memory.json `models`), as written there.
pub(crate) fn in_use(state: &Path) -> Result<Vec<String>> {
    let s = footnote_core::config::product_settings(state, "memory")?;
    Ok(s["models"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|m| m.as_str().map(|p| p.replace('\\', "/")))
        .collect())
}

fn same_model(path: &str, dir: &Path) -> bool {
    let dir = dir.to_string_lossy().replace('\\', "/");
    path.trim_end_matches('/') == dir.trim_end_matches('/')
}

pub fn list(state: &Path) -> Result<Value> {
    let used = in_use(state)?;
    let rows: Vec<Value> = RECIPES
        .iter()
        .map(|r| {
            let dir = models_dir(state).join(r.name);
            let installed = dir.join("manifest.json").exists();
            let bytes: u64 = ["model.onnx", "tokenizer.json", "model.gguf"]
                .iter()
                .filter_map(|f| fs::metadata(dir.join(f)).ok())
                .map(|m| m.len())
                .sum();
            json!({"name": r.name, "role": r.role, "installed": installed, "path": installed.then(|| dir.clone()),
                "bytes": installed.then_some(bytes), "download_bytes": r.download_bytes, "used_by_memory": used.iter().any(|u| same_model(u, &dir)),
                "source": format!("{}@{}", r.repo, &r.revision[..12]),
                "license": (!r.license.is_empty()).then_some(r.license)})
        })
        .collect();
    // Models imported from a GGUF file (#556): any other folder of the models folder with a manifest.
    let mut rows = rows;
    for dir in fs::read_dir(models_dir(state))
        .into_iter()
        .flatten()
        .flatten()
        .map(|e| e.path())
    {
        let name = dir
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_default();
        if !dir.join("manifest.json").exists() || recipe(&name).is_ok() {
            continue;
        }
        let bytes = fs::metadata(dir.join("model.gguf")).map_or(0, |m| m.len());
        let facts = imported_facts(&dir);
        rows.push(json!({"name": name, "role": "imported GGUF", "installed": true, "imported": true, "path": dir,
            "bytes": bytes, "download_bytes": null, "used_by_memory": used.iter().any(|u| same_model(u, &dir)),
            "source": "imported", "license": facts["license"], "family": facts["family"],
            "dimension": facts["dimension"], "prefixes": facts["prefixes"]}));
    }
    // Models the hook uses from elsewhere (for example a development checkout) are reported too.
    let elsewhere: Vec<&String> = used
        .iter()
        .filter(|u| {
            !rows.iter().any(|r| {
                r["path"]
                    .as_str()
                    .is_some_and(|p| same_model(u, Path::new(p)))
            })
        })
        .collect();
    Ok(
        json!({"models": rows, "memory_uses_from_elsewhere": elsewhere, "folder": models_dir(state), "llama": cfg!(feature = "llama")}),
    )
}

pub(crate) fn agent() -> ureq::Agent {
    use ureq::tls::{RootCerts, TlsConfig, TlsProvider};
    ureq::Agent::config_builder()
        .tls_config(
            TlsConfig::builder()
                .provider(TlsProvider::NativeTls)
                .root_certs(RootCerts::PlatformVerifier) // system roots, so company TLS proxies work (as in crawl.rs)
                .build(),
        )
        .build()
        .into()
}

/// Stream `url` into `to`, reporting bytes against the size the server announces.
pub(crate) fn download(url: &str, to: &Path, job: &mut footnote_core::jobs::Job) -> Result<()> {
    use std::io::Write;
    let response = agent()
        .get(url)
        .call()
        .with_context(|| format!("download {url}"))?;
    let total = response
        .headers()
        .get("content-length")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.parse::<u64>().ok());
    let mut body = response.into_body();
    let mut reader = body.as_reader();
    let mut out = fs::File::create(to)?;
    let (mut buf, mut done) = (vec![0u8; 1 << 16], 0u64);
    loop {
        let n = reader
            .read(&mut buf)
            .with_context(|| format!("download {url}"))?;
        if n == 0 {
            break;
        }
        out.write_all(&buf[..n])?;
        done += n as u64;
        job.progress(done, total);
    }
    job.progress(done, total.or(Some(done)));
    Ok(())
}

pub(crate) fn sha256_file(path: &Path) -> Result<String> {
    use sha2::{Digest, Sha256};
    let mut f = fs::File::open(path)?;
    let mut h = Sha256::new();
    let mut buf = vec![0u8; 1 << 20];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        h.update(&buf[..n]);
    }
    Ok(format!("{:x}", h.finalize()))
}

/// The manifest exactly as the former Python script wrote it (`json.dumps(indent=2)` plus a newline, in text mode, so CRLF on
/// Windows): a model's identity is the hash of these bytes.
fn manifest_text(r: &Recipe, files: &[(&str, String, u64, String)]) -> String {
    let s = |v: &str| serde_json::to_string(v).expect("string");
    let entries: Vec<String> = files
        .iter()
        .map(|(local, sha, bytes, url)| {
            format!(
                "    {}: {{\n      \"sha256\": {},\n      \"bytes\": {bytes},\n      \"url\": {}\n    }}",
                s(local),
                s(sha),
                s(url)
            )
        })
        .collect();
    if r.gguf() {
        // Byte-identical to the manifest the benchmark lab wrote for test 6 (LF on every platform), so vectors stay valid.
        // shortcut: pooling and width are Jina v5 nano's, generalise when a second GGUF model is offered.
        return format!(
            "{{
  \"repository\": {},
  \"revision\": {},
  \"license\": {},
  \"runtime\": \"llama.cpp\",
  \"files\": {{
{}
  }},
  \"pooling\": \"last\",
  \"query_prefix\": {},
  \"passage_prefix\": {},
  \"max_length\": {},
  \"dimension\": 768,
  \"quantization\": {}
}}
",
            s(r.repo),
            s(r.revision),
            s(r.license),
            entries.join(
                ",
"
            ),
            s(r.query_prefix),
            s(r.passage_prefix),
            r.max_length,
            s(r.quantization)
        );
    }
    let text = format!(
        "{{\n  \"repository\": {},\n  \"revision\": {},\n  \"files\": {{\n{}\n  }},\n  \"pooling\": \"attention-mask-mean-l2\",\n  \"query_prefix\": {},\n  \"passage_prefix\": {},\n  \"max_length\": {},\n  \"pad_token\": {},\n  \"dimension\": 384,\n  \"quantization\": {}\n}}\n",
        s(r.repo),
        s(r.revision),
        entries.join(",\n"),
        s(r.query_prefix),
        s(r.passage_prefix),
        r.max_length,
        s(r.pad_token),
        s(r.quantization)
    );
    if cfg!(windows) {
        text.replace('\n', "\r\n")
    } else {
        text
    }
}

pub fn install(state: &Path, names: &[String]) -> Result<Value> {
    let mut done = Vec::new();
    for name in names {
        let r = recipe(name)?;
        if r.gguf() && !cfg!(feature = "llama") {
            bail!("`{name}` runs through llama.cpp, which this build of Footnote does not include");
        }
        let dir = models_dir(state).join(r.name);
        ignore_models(state)?;
        let mut files = Vec::new();
        let wanted: &[(&str, &str)] = if r.gguf() {
            &[(r.file, "model.gguf")]
        } else {
            &[("tokenizer.json", "tokenizer.json"), (r.file, "model.onnx")]
        };
        for &(remote, local) in wanted {
            let path = dir.join(local);
            let url = format!(
                "https://huggingface.co/{}/resolve/{}/{remote}",
                r.repo, r.revision
            );
            let pinned = r.sha256.iter().find(|(f, _)| *f == local).map(|p| p.1);
            let digest = fetch(state, r.name, &path, &url, pinned)?;
            files.push((local, digest, fs::metadata(&path)?.len(), url));
        }
        fs::write(dir.join("manifest.json"), manifest_text(r, &files))?;
        done.push(json!({"name": r.name, "path": dir, "license": (!r.license.is_empty()).then_some(r.license)}));
    }
    Ok(json!({"installed": done}))
}

/// Hundreds of MB that must never reach a repository, even if the state folder ends up inside a synced git folder.
fn ignore_models(state: &Path) -> Result<()> {
    let ignore = models_dir(state).join(".gitignore");
    if !ignore.exists() {
        fs::create_dir_all(models_dir(state))?;
        fs::write(
            &ignore,
            "# Downloaded models: never commit them.
*
",
        )?;
    }
    Ok(())
}

/// Download `url` to `path` unless present, then check its sha256 against `pinned` (a mismatching file is removed).
fn fetch(state: &Path, name: &str, path: &Path, url: &str, pinned: Option<&str>) -> Result<String> {
    let file = path
        .file_name()
        .map(|f| f.to_string_lossy().into_owned())
        .unwrap_or_default();
    if !path.exists() {
        fs::create_dir_all(path.parent().context("model file path")?)?;
        let mut partial = path.as_os_str().to_owned();
        partial.push(".partial");
        let partial = PathBuf::from(partial);
        let mut job = footnote_core::jobs::Job::start(
            state,
            "models.install",
            &format!("{name} {file}"),
            "bytes",
        )?;
        let done = download(url, &partial, &mut job);
        job.finish(&done);
        done?;
        fs::rename(&partial, path)?;
    }
    let digest = sha256_file(path)?;
    if let Some(pinned) = pinned
        && digest != pinned
    {
        fs::remove_file(path)?;
        bail!("{name}/{file}: sha256 {digest} does not match the pinned {pinned}; file removed");
    }
    Ok(digest)
}

/// Point the memory hook at these installed models. Vectors for the new models are computed at the next session start.
pub fn use_models(state: &Path, names: &[String]) -> Result<Value> {
    let mut paths = Vec::new();
    for name in names {
        ensure!(
            recipe(name).is_ok() || valid_name(name),
            "unknown model `{name}`; `footnote models list` shows them"
        );
        let dir = models_dir(state).join(name);
        if !dir.join("manifest.json").exists() {
            bail!("`{name}` is not installed; run `footnote models install {name}` first");
        }
        // #515: configuring a model this build cannot load leaves recall on keywords and new memories without vectors.
        ensure!(
            cfg!(feature = "llama") || !dir.join("model.gguf").exists(),
            "`{name}` runs through llama.cpp, which this build of Footnote does not include; install a release build (or build with `--features llama`) first"
        );
        paths.push(dir.to_string_lossy().replace('\\', "/"));
    }
    if paths.is_empty() || paths.len() > 3 {
        bail!("give one to three models");
    }
    footnote_core::config::set_value(state, "memory", "models", json!(paths))?;
    Ok(
        json!({"memory_models": paths, "note": "vectors these models do not have yet are computed in the background at the next session start (none when only the folder changed)"}),
    )
}

/// An imported model's folder name: lowercase ASCII, digits, `-`, `_` and `.`, never a path.
fn valid_name(name: &str) -> bool {
    (1..=64).contains(&name.len())
        && !name.starts_with('.')
        && name
            .chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || matches!(c, '-' | '_' | '.'))
}

/// The folder name for an imported file: its stem, lowercased, other characters as `-`.
fn import_name(file: &Path) -> String {
    let stem = file
        .file_stem()
        .map(|s| s.to_string_lossy().to_lowercase())
        .unwrap_or_default();
    let name: String = stem
        .chars()
        .map(|c| {
            if c.is_ascii_lowercase() || c.is_ascii_digit() || matches!(c, '_' | '.') {
                c
            } else {
                '-'
            }
        })
        .collect();
    name.trim_matches(|c| c == '-' || c == '.')
        .chars()
        .take(64)
        .collect()
}

/// Query and passage prefixes for the model families Footnote knows: the catalogue's (Jina v5, E5) and the GGUF candidates
/// its lab measured with these prefixes (bench/experiments/LLAMACPP-MODELS.md, C1 and C2). A family matches when all its
/// tokens are words of the file's name or the model's declared name. Any other model gets no prefixes, and its card says so.
struct Family {
    name: &'static str,
    tokens: &'static [&'static str],
    query_prefix: &'static str,
    passage_prefix: &'static str,
}

const FAMILIES: &[Family] = &[
    Family {
        name: "jina-v5",
        tokens: &["jina", "v5"],
        query_prefix: "Query: ",
        passage_prefix: "Document: ",
    },
    Family {
        name: "e5",
        tokens: &["e5"],
        query_prefix: "query: ",
        passage_prefix: "passage: ",
    },
    Family {
        name: "embeddinggemma",
        tokens: &["embeddinggemma"],
        query_prefix: "task: search result | query: ",
        passage_prefix: "title: none | text: ",
    },
    Family {
        name: "qwen3-embedding",
        tokens: &["qwen3", "embedding"],
        query_prefix: "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: ",
        passage_prefix: "",
    },
];

/// The known family of a model with these names (file stem, declared name), if any.
fn family(names: &[&str]) -> Option<&'static Family> {
    let words: Vec<String> = names
        .iter()
        .flat_map(|n| n.split(|c: char| !c.is_ascii_alphanumeric()))
        .map(str::to_ascii_lowercase)
        .collect();
    FAMILIES
        .iter()
        .find(|f| f.tokens.iter().all(|t| words.iter().any(|w| w == t)))
}

/// Copy a GGUF embedding model into the models folder with a manifest, so `models use` can pick it (#556). The original file
/// stays where it is. Refused, with the reason, by a build without llama.cpp and for a file that is not an embedding model.
pub fn import(state: &Path, file: &Path) -> Result<Value> {
    ensure!(
        cfg!(feature = "llama"),
        "this build of Footnote has no llama.cpp, so it cannot run a GGUF model; install a release build (or build with `--features llama`) first"
    );
    import_checked(state, file, &load_check)
}

/// The last check before copying: llama.cpp loads the weights and gives the embedding width it will produce.
#[cfg(feature = "llama")]
fn load_check(file: &Path) -> Result<Option<usize>> {
    Ok(Some(footnote_search::llama::inspect(file)?.dimension))
}
#[cfg(not(feature = "llama"))]
fn load_check(_: &Path) -> Result<Option<usize>> {
    bail!("this build of Footnote has no llama.cpp")
}

/// `import` after the build check; `load` is llama.cpp's check (tests pass one that accepts a synthetic header).
fn import_checked(
    state: &Path,
    file: &Path,
    load: &dyn Fn(&Path) -> Result<Option<usize>>,
) -> Result<Value> {
    ensure!(
        file.extension()
            .is_some_and(|e| e.eq_ignore_ascii_case("gguf")),
        "{} is not a .gguf file",
        file.display()
    );
    ensure!(
        fs::metadata(file)
            .with_context(|| format!("cannot read {}", file.display()))?
            .is_file(),
        "not a file"
    );
    let info = crate::gguf::read(file)?
        .embedding()
        .with_context(|| format!("{} cannot be used for search", file.display()))?;
    let name = import_name(file);
    ensure!(
        valid_name(&name),
        "cannot name a model after {}",
        file.display()
    );
    ensure!(
        recipe(&name).is_err(),
        "`{name}` is a catalogue model; install it with `footnote models install {name}`"
    );
    let dir = models_dir(state).join(&name);
    ensure!(!dir.exists(), "a model named `{name}` is already installed");
    let dimension = load(file)?.unwrap_or(info.dimension);
    let stem = file
        .file_stem()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_default();
    let fam = family(&[&stem, &info.name]);
    ignore_models(state)?;
    fs::create_dir_all(&dir)?;
    let copied = (|| -> Result<(String, u64)> {
        let partial = dir.join("model.gguf.partial");
        let bytes = fs::copy(file, &partial)?;
        fs::rename(&partial, dir.join("model.gguf"))?;
        Ok((sha256_file(&dir.join("model.gguf"))?, bytes))
    })();
    let (sha, bytes) = match copied {
        Ok(v) => v,
        Err(e) => {
            let _ = fs::remove_dir_all(&dir); // no half-imported model left behind
            return Err(e.context(format!("copy {} into the models folder", file.display())));
        }
    };
    let manifest = json!({
        "repository": "imported", "revision": "", "license": info.license, "source": file, "name": info.name,
        "architecture": info.architecture, "family": fam.map_or("", |f| f.name),
        "runtime": "llama.cpp", "files": {"model.gguf": {"sha256": sha, "bytes": bytes}},
        "pooling": info.pooling, "query_prefix": fam.map_or("", |f| f.query_prefix),
        "passage_prefix": fam.map_or("", |f| f.passage_prefix),
        "max_length": info.context.clamp(8, 512), "dimension": dimension, "quantization": "",
    });
    fs::write(
        dir.join("manifest.json"),
        serde_json::to_string_pretty(&manifest)? + "\n",
    )?;
    let prefixes = match fam {
        Some(f) => format!(
            "It uses the {} family's query and passage prefixes.",
            f.name
        ),
        None => "No query or passage prefixes are known for it.".into(),
    };
    let license = if info.license.is_empty() {
        "Its licence is unknown: check the model card before use at work.".to_string()
    } else {
        format!("The file declares the licence {}.", info.license)
    };
    Ok(
        json!({"imported": true, "name": name, "path": dir, "bytes": bytes, "dimension": dimension, "pooling": info.pooling,
        "family": fam.map(|f| f.name), "license": (!info.license.is_empty()).then_some(&info.license),
        "note": format!("`footnote models use {name}` makes Footnote Memory use it; its vectors are computed at the next session start. {prefixes} {license}")}),
    )
}

/// What an imported model's manifest says about it, for `models list`.
fn imported_facts(dir: &Path) -> Value {
    let m: Value = fs::read_to_string(dir.join("manifest.json"))
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_default();
    let text = |k: &str| m[k].as_str().filter(|s| !s.is_empty()).map(str::to_owned);
    json!({"license": text("license"), "family": text("family"), "dimension": m["dimension"],
        "prefixes": text("query_prefix").is_some() || text("passage_prefix").is_some()})
}

pub fn remove(state: &Path, name: &str) -> Result<Value> {
    ensure!(
        recipe(name).is_ok() || valid_name(name),
        "unknown model `{name}`; `footnote models list` shows them"
    );
    let dir = models_dir(state).join(name);
    if in_use(state)?.iter().any(|u| same_model(u, &dir)) {
        bail!("`{name}` is used by Footnote Memory; switch with `footnote models use` first");
    }
    if !dir.exists() {
        return Ok(json!({"removed": false, "name": name}));
    }
    footnote_core::no_links(&dir)?;
    fs::remove_dir_all(&dir)?;
    Ok(json!({"removed": true, "name": name}))
}

/// French share of a corpus sample from function words: an estimate, not a language detector.
fn corpus_language(db: &Path) -> Result<Value> {
    let c = crate::app::open(db, false)?;
    let mut s = c.prepare("SELECT text FROM chunks ORDER BY id LIMIT 400")?;
    let texts: Vec<String> = s
        .query_map([], |r| r.get(0))?
        .collect::<rusqlite::Result<_>>()?;
    let (mut fr, mut en) = (0usize, 0usize);
    for t in &texts {
        for w in t
            .split(|ch: char| !ch.is_alphabetic())
            .map(str::to_lowercase)
        {
            match w.as_str() {
                "le" | "la" | "les" | "des" | "est" | "une" | "pour" | "que" | "dans" | "avec"
                | "sur" | "pas" => fr += 1,
                "the" | "and" | "is" | "of" | "to" | "for" | "that" | "with" | "on" | "not"
                | "are" | "this" => en += 1,
                _ => {}
            }
        }
    }
    let share = if fr + en == 0 {
        0.0
    } else {
        fr as f64 / (fr + en) as f64
    };
    let label = if fr + en < 50 {
        "too little text"
    } else if share >= 0.8 {
        "French"
    } else if share > 0.2 {
        "mixed French and English"
    } else {
        "English"
    };
    Ok(
        json!({"estimate": label, "french_share": (share * 100.0).round() / 100.0, "chunks_sampled": texts.len()}),
    )
}

/// Recommendation from Footnote's own measured results only; where nothing was measured, it says so.
pub fn recommend(db: Option<&Path>) -> Result<Value> {
    let hardware = crate::hardware::detect();
    let language = db.map(corpus_language).transpose()?;
    let french = language.as_ref().is_some_and(|l| {
        matches!(
            l["estimate"].as_str(),
            Some("French" | "mixed French and English")
        )
    });
    let mut reasons = vec![json!(
        "The default pair (bekko-a8m + gte-small) is the shipped default, chosen with benchmark protocol v1 (bench/experiments/RESULTS.md)."
    )];
    if french {
        reasons.push(json!(
            "French or mixed corpus: Jina v5 nano scored +0.08 to +0.10 nDCG@10 over the pair on held-out Alloprof and mix-fr-en (bench/experiments/LLAMACPP-INPROCESS.md). On an idle machine it adds about 6 ms at p50 and 26 ms at p95 per search; the database is about 2.5 times larger. Licence CC-BY-NC-4.0: no commercial use. Install with `footnote models install jina-v5-nano` (builds that include llama.cpp)."
        ));
    }
    if hardware["gpus"].as_array().is_some_and(|g| !g.is_empty()) {
        reasons.push(json!(
            "GPU found but not used for search: on the Radeon RX 6800, single queries through DirectML were 10 to 34 times slower than the CPU; only batch indexing with fp32 bekko-a8m gained (3.2 times) (bench/experiments/GPU-ENCODING.md)."
        ));
    }
    Ok(json!({
        "hardware": hardware,
        "corpus_language": language,
        "recommended": DEFAULT_PAIR,
        "consider": if french { json!(["jina-v5-nano"]) } else { json!([]) },
        "reasons": reasons,
    }))
}

#[cfg(test)]
mod tests {
    use std::path::Path;

    #[test]
    fn imported_names_are_folder_safe() {
        assert_eq!(
            super::import_name(Path::new("D:/m/Qwen3-Embedding-0.6B-Q8_0.gguf")),
            "qwen3-embedding-0.6b-q8_0"
        );
        assert_eq!(super::import_name(Path::new("../..gguf")), "");
        for bad in ["", "..", ".hidden", "a/b", "a\\b", "Upper", &"x".repeat(65)] {
            assert!(!super::valid_name(bad), "{bad}");
        }
        assert!(super::valid_name("bge-m3-q8_0"));
    }

    /// An imported model shows in the list, can be used and then removed; a bad name or a non-GGUF file is refused.
    #[test]
    fn an_imported_model_is_listed_used_and_removed() {
        let t = tempfile::tempdir().unwrap();
        let state = t.path();
        let dir = super::models_dir(state).join("my-embed");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("manifest.json"), "{}").unwrap();
        std::fs::write(dir.join("model.gguf"), b"1234").unwrap();
        let list = super::list(state).unwrap();
        let row = list["models"]
            .as_array()
            .unwrap()
            .iter()
            .find(|m| m["name"] == "my-embed")
            .unwrap()
            .clone();
        assert_eq!(
            (row["imported"].clone(), row["bytes"].clone()),
            (serde_json::json!(true), serde_json::json!(4))
        );
        let used = super::use_models(state, &["my-embed".into()]);
        if !cfg!(feature = "llama") {
            // #515: a GGUF model is refused by a build that cannot load it; the rest needs it configured.
            assert!(used.unwrap_err().to_string().contains("llama.cpp"));
            return;
        }
        used.unwrap();
        assert!(
            super::list(state).unwrap()["memory_uses_from_elsewhere"]
                .as_array()
                .unwrap()
                .is_empty()
        );
        assert!(
            super::remove(state, "my-embed").is_err(),
            "removed while in use"
        );
        assert!(super::use_models(state, &["../outside".into()]).is_err());
        assert!(super::import(state, &t.path().join("notes.txt")).is_err());
    }

    fn embedding_gguf(arch: &str, name: &str, license: Option<&str>) -> Vec<u8> {
        use crate::gguf::Meta;
        let mut keys = vec![
            ("general.architecture".to_string(), Meta::Str(arch.into())),
            ("general.name".to_string(), Meta::Str(name.into())),
            (format!("{arch}.pooling_type"), Meta::Int(3)),
            (format!("{arch}.embedding_length"), Meta::Int(1024)),
            (format!("{arch}.context_length"), Meta::Int(32768)),
        ];
        if let Some(l) = license {
            keys.push(("general.license".into(), Meta::Str(l.into())));
        }
        let keys: Vec<(&str, Meta)> = keys.iter().map(|(k, v)| (k.as_str(), v.clone())).collect();
        crate::gguf::synthetic(&keys)
    }

    /// #556: a build without llama.cpp refuses an import with the reason, before reading the file.
    #[cfg(not(feature = "llama"))]
    #[test]
    fn a_build_without_llama_refuses_an_import() {
        let t = tempfile::tempdir().unwrap();
        let file = t.path().join("tiny.gguf");
        std::fs::write(&file, embedding_gguf("qwen3", "Tiny", None)).unwrap();
        let err = super::import(&t.path().join("state"), &file)
            .unwrap_err()
            .to_string();
        assert!(err.contains("no llama.cpp"), "{err}");
        assert!(!super::models_dir(&t.path().join("state")).exists());
    }

    /// #556: with llama.cpp, a file whose weights it cannot load is refused and nothing is left in the models folder.
    #[cfg(feature = "llama")]
    #[test]
    fn llama_refuses_a_header_without_weights() {
        let t = tempfile::tempdir().unwrap();
        let file = t.path().join("tiny.gguf");
        std::fs::write(&file, embedding_gguf("qwen3", "Tiny", None)).unwrap();
        assert!(super::import(t.path(), &file).is_err());
        assert!(!super::models_dir(t.path()).join("tiny").exists());
    }

    /// #556: a chat model or reranker is refused before anything is copied.
    #[test]
    fn a_gguf_that_is_not_an_embedding_model_is_refused() {
        use crate::gguf::Meta;
        let t = tempfile::tempdir().unwrap();
        let chat = t.path().join("chat-7b.gguf");
        std::fs::write(
            &chat,
            crate::gguf::synthetic(&[
                ("general.architecture", Meta::Str("llama".into())),
                ("llama.embedding_length", Meta::Int(4096)),
            ]),
        )
        .unwrap();
        let err = format!(
            "{:#}",
            super::import_checked(t.path(), &chat, &|_| Ok(None)).unwrap_err()
        );
        assert!(err.contains("not an embedding model"), "{err}");
        let fake = t.path().join("fake.gguf");
        std::fs::write(&fake, b"not a model").unwrap();
        assert!(super::import_checked(t.path(), &fake, &|_| Ok(None)).is_err());
        assert!(!super::models_dir(t.path()).join("chat-7b").exists());
        assert!(!super::models_dir(t.path()).join("fake").exists());
    }

    /// #556: an embedding GGUF is copied (the original stays), with a manifest llama.cpp can load, the family's prefixes and
    /// an unknown licence reported as such; a second import of the same name is refused.
    #[test]
    fn an_embedding_gguf_is_copied_with_its_manifest() {
        let t = tempfile::tempdir().unwrap();
        let state = t.path().join("state");
        let file = t.path().join("Qwen3-Embedding-Tiny-Q8_0.gguf");
        let bytes = embedding_gguf("qwen3", "Qwen3 Embedding Tiny", None);
        std::fs::write(&file, &bytes).unwrap();
        let out = super::import_checked(&state, &file, &|_| Ok(None)).unwrap();
        assert!(file.exists(), "the original stays where it is");
        let dir = super::models_dir(&state).join("qwen3-embedding-tiny-q8_0");
        assert_eq!(out["name"], "qwen3-embedding-tiny-q8_0");
        assert_eq!(std::fs::read(dir.join("model.gguf")).unwrap(), bytes);
        let m: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(dir.join("manifest.json")).unwrap())
                .unwrap();
        assert_eq!(
            (
                &m["runtime"],
                &m["pooling"],
                &m["dimension"],
                &m["max_length"],
                &m["family"]
            ),
            (
                &serde_json::json!("llama.cpp"),
                &serde_json::json!("last"),
                &serde_json::json!(1024),
                &serde_json::json!(512),
                &serde_json::json!("qwen3-embedding")
            )
        );
        assert_eq!(
            m["files"]["model.gguf"]["sha256"].as_str().unwrap(),
            super::sha256_file(&file).unwrap()
        );
        assert!(m["query_prefix"].as_str().unwrap().ends_with("Query: "));
        assert!(out["note"].as_str().unwrap().contains("licence is unknown"));
        let row = super::list(&state).unwrap()["models"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["name"] == "qwen3-embedding-tiny-q8_0")
            .unwrap()
            .clone();
        assert_eq!(
            (&row["license"], &row["prefixes"], &row["dimension"]),
            (
                &serde_json::Value::Null,
                &serde_json::json!(true),
                &serde_json::json!(1024)
            )
        );
        let again = super::import_checked(&state, &file, &|_| Ok(None)).unwrap_err();
        assert!(again.to_string().contains("already installed"));

        // an unknown family gets no prefixes; a declared licence is kept
        let other = t.path().join("my-embed.gguf");
        std::fs::write(
            &other,
            embedding_gguf("bert", "My Embed", Some("apache-2.0")),
        )
        .unwrap();
        super::import_checked(&state, &other, &|_| Ok(Some(384))).unwrap();
        let m: serde_json::Value = serde_json::from_str(
            &std::fs::read_to_string(super::models_dir(&state).join("my-embed/manifest.json"))
                .unwrap(),
        )
        .unwrap();
        assert_eq!(
            (&m["query_prefix"], &m["license"], &m["dimension"]),
            (
                &serde_json::json!(""),
                &serde_json::json!("apache-2.0"),
                &serde_json::json!(384)
            )
        );
    }

    #[test]
    fn known_families_match_on_whole_words() {
        let name = |n: &[&str]| super::family(n).map(|f| f.name);
        assert_eq!(
            name(&["v5-nano-retrieval-Q8_0", "Jina Embeddings V5 Text Nano"]),
            Some("jina-v5")
        );
        assert_eq!(name(&["multilingual-e5-small-q8_0", ""]), Some("e5"));
        assert_eq!(
            name(&["embeddinggemma-300M-Q8_0", ""]),
            Some("embeddinggemma")
        );
        assert_eq!(
            name(&["Qwen3-Embedding-0.6B-Q8_0", ""]),
            Some("qwen3-embedding")
        );
        assert_eq!(name(&["bge-m3-q8_0", "be5t"]), None);
    }

    /// Same bytes as the manifest the lab wrote for test 6, so a model's identity (the manifest hash) does not change.
    #[test]
    fn nano_manifest_matches_the_benchmarked_one() {
        let r = super::recipe("jina-v5-nano").unwrap();
        let url = "https://huggingface.co/jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF/resolve/59cfaceeeb7d738c404659435af4c0da74d06c96/v5-nano-retrieval-Q8_0.gguf";
        let files = [(
            "model.gguf",
            r.sha256[0].1.to_string(),
            232883776,
            url.to_string(),
        )];
        let expected = r#"{
  "repository": "jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF",
  "revision": "59cfaceeeb7d738c404659435af4c0da74d06c96",
  "license": "CC-BY-NC-4.0 (no commercial use)",
  "runtime": "llama.cpp",
  "files": {
    "model.gguf": {
      "sha256": "86b6e6279e9b9e71389f02a082764a2ac2b15a50e37482c26f98d69092f12442",
      "bytes": 232883776,
      "url": "https://huggingface.co/jinaai/jina-embeddings-v5-text-nano-retrieval-GGUF/resolve/59cfaceeeb7d738c404659435af4c0da74d06c96/v5-nano-retrieval-Q8_0.gguf"
    }
  },
  "pooling": "last",
  "query_prefix": "Query: ",
  "passage_prefix": "Document: ",
  "max_length": 512,
  "dimension": 768,
  "quantization": "Q8_0"
}
"#;
        assert_eq!(
            super::manifest_text(r, &files),
            expected.replace("\r\n", "\n")
        );
    }
}
