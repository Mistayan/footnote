//! Text embeddings inside the binary: the recipe the Python helper (`tools/embed.py`) used, without Python.
//!
//! A model directory holds `manifest.json`, `model.onnx` and `tokenizer.json`. The model and tokenizer are hashed and checked against
//! the manifest, then loaded from the very bytes that were hashed (no window to swap a file between check and load). Recipe: optional
//! prefix, truncation at `max_length`, padding to the longest text of a batch of 8 in the given order, attention-mask mean pooling,
//! L2 normalization. Queries run on a 2-thread session (one short text, low steady latency); documents on a second session with half
//! the logical CPUs. Same graph and batches, so both give the same vectors (bench/experiments/BUILD-SPEED.md, tests 1b and 4).
//!
//! A manifest with `"runtime": "llama.cpp"` holds `model.gguf` instead (llama.rs, builds with `--features llama` only).
use anyhow::{Context, Result, anyhow, bail};
use ort::session::{Session, SessionInputValue};
use ort::value::Tensor;
use serde::Deserialize;
use std::{borrow::Cow, collections::HashMap, path::Path, sync::OnceLock};
use tokenizers::{PaddingParams, Tokenizer, TruncationParams};

pub const DIM: usize = 384;
const MAX_TEXT_BYTES: usize = 64_000;
const MAX_TEXTS: usize = 10_000;
/// Texts per inference call. The int8 model quantizes activations per batch, so this is part of the recipe: changing it changes vectors.
const ONNX_BATCH: usize = 8;

#[derive(Deserialize)]
struct FileEntry {
    sha256: String,
}
#[derive(Deserialize)]
struct Manifest {
    files: HashMap<String, FileEntry>,
    pooling: String,
    query_prefix: String,
    passage_prefix: String,
    max_length: usize,
    dimension: usize,
    pad_token: Option<String>,
    #[serde(default = "onnx")]
    runtime: String,
}
fn onnx() -> String {
    "onnx".into()
}

pub struct Encoded {
    pub vectors: Vec<Vec<f64>>,
    pub truncated_at_limit: usize,
}

pub struct Encoder {
    m: Manifest,
    /// SHA-256 of `manifest.json`: the model identity stored next to every vector.
    pub model_sha256: String,
    backend: Backend,
}
enum Backend {
    Onnx {
        tokenizer: Tokenizer,
        query: Session,
        bulk: Session,
    },
    #[cfg(feature = "llama")]
    Llama(crate::llama::Gguf),
}

/// The model files a manifest of this runtime must list and hash.
pub fn files(runtime: &str) -> &'static [&'static str] {
    if runtime == "llama.cpp" {
        &["model.gguf"]
    } else {
        &["model.onnx", "tokenizer.json"]
    }
}

/// Hash every model file against the manifest; returns the verified bytes.
fn verified(model: &Path, m: &Manifest) -> Result<HashMap<&'static str, Vec<u8>>> {
    let mut out = HashMap::new();
    for &name in files(&m.runtime) {
        let path = model.join(name);
        footnote_core::no_links(&path)?;
        let bytes = std::fs::read(&path).with_context(|| format!("read {name}"))?;
        let expected = &m
            .files
            .get(name)
            .context("manifest lists no hash for a model file")?
            .sha256;
        if &footnote_core::hash(&bytes) != expected {
            bail!("model artifact hash mismatch: {name}");
        }
        out.insert(name, bytes);
    }
    Ok(out)
}

fn err(e: impl std::fmt::Display) -> anyhow::Error {
    anyhow!("{e}")
}

impl Encoder {
    pub fn load(model: &Path) -> Result<Self> {
        let manifest_bytes = footnote_core::bounded_read(&model.join("manifest.json"))?;
        let m: Manifest = serde_json::from_slice(&manifest_bytes).context("embedding manifest")?;
        if m.runtime == "llama.cpp" {
            return Self::load_gguf(model, m, &manifest_bytes);
        }
        if m.runtime != "onnx" {
            bail!("unsupported embedding runtime: {}", m.runtime);
        }
        if m.pooling != "attention-mask-mean-l2"
            || !(1..=512).contains(&m.max_length)
            || m.dimension != DIM
        {
            bail!("unsupported embedding recipe");
        }
        let verified = verified(model, &m)?;
        let mut tokenizer = Tokenizer::from_bytes(&verified["tokenizer.json"]).map_err(err)?;
        tokenizer
            .with_truncation(Some(TruncationParams {
                max_length: m.max_length,
                ..Default::default()
            }))
            .map_err(err)?;
        let pad_token = m.pad_token.clone().unwrap_or_else(|| "<pad>".into());
        let pad_id = tokenizer
            .token_to_id(&pad_token)
            .with_context(|| format!("pad token not in vocabulary: {pad_token}"))?;
        tokenizer.with_padding(Some(PaddingParams {
            pad_id,
            pad_token,
            ..Default::default()
        }));
        let cpus = std::thread::available_parallelism().map_or(4, |n| n.get());
        // ONNX Runtime allows one environment per process, shared by every model.
        static ENV: OnceLock<Result<ort::environment::Environment, String>> = OnceLock::new();
        let env = ENV
            .get_or_init(|| {
                ort::init()
                    .with_telemetry(false)
                    .build()
                    .map_err(|e| e.to_string())
            })
            .as_ref()
            .map_err(err)?;
        let session = |threads: usize| -> Result<Session> {
            Session::builder(env)
                .map_err(err)?
                .with_intra_threads(threads)
                .map_err(err)?
                .with_inter_threads(1)
                .map_err(err)?
                .commit_from_memory(&verified["model.onnx"])
                .map_err(err)
        };
        Ok(Self {
            model_sha256: footnote_core::hash(&manifest_bytes),
            backend: Backend::Onnx {
                query: session(2)?,
                bulk: session((cpus / 2).max(2))?,
                tokenizer,
            },
            m,
        })
    }

    #[cfg(feature = "llama")]
    fn load_gguf(model: &Path, m: Manifest, manifest_bytes: &[u8]) -> Result<Self> {
        drop(verified(model, &m)?);
        // shortcut: llama.cpp reads the file again after the hash check (it takes a path, not bytes), so a file swapped in that
        // window is not caught; the model directory is the user's own. Upgrade by loading from a verified copy if that changes.
        let g = crate::llama::Gguf::load(&model.join("model.gguf"), &m.pooling, m.max_length)?;
        if g.dimension != m.dimension {
            bail!("unsupported embedding recipe");
        }
        Ok(Self {
            model_sha256: footnote_core::hash(manifest_bytes),
            backend: Backend::Llama(g),
            m,
        })
    }
    #[cfg(not(feature = "llama"))]
    fn load_gguf(_: &Path, _: Manifest, _: &[u8]) -> Result<Self> {
        bail!("this build has no llama.cpp support; rebuild with --features llama")
    }

    pub fn dimension(&self) -> usize {
        self.m.dimension
    }

    pub fn encode(&mut self, texts: &[String], kind: &str) -> Result<Encoded> {
        let prefix = match kind {
            "query" => &self.m.query_prefix,
            "passage" => &self.m.passage_prefix,
            _ => bail!("kind must be query or passage"),
        };
        if texts.is_empty()
            || texts.len() > MAX_TEXTS
            || texts.iter().any(|t| t.len() > MAX_TEXT_BYTES)
        {
            bail!("embedding input bound exceeded");
        }
        let (tokenizer, query, bulk) = match &mut self.backend {
            Backend::Onnx {
                tokenizer,
                query,
                bulk,
            } => (tokenizer, query, bulk),
            #[cfg(feature = "llama")]
            Backend::Llama(g) => {
                let (mut vectors, mut truncated) = (Vec::with_capacity(texts.len()), 0);
                for t in texts {
                    let (v, cut) = g.embed(&format!("{prefix}{t}"))?;
                    truncated += usize::from(cut);
                    vectors.push(v);
                }
                return Ok(Encoded {
                    vectors,
                    truncated_at_limit: truncated,
                });
            }
        };
        let session = if kind == "passage" { bulk } else { query };
        let names: Vec<String> = session
            .inputs()
            .iter()
            .map(|i| i.name().to_string())
            .collect();
        let (mut vectors, mut truncated) = (Vec::with_capacity(texts.len()), 0);
        for part in texts.chunks(ONNX_BATCH) {
            let tokens = tokenizer
                .encode_batch(part.iter().map(|t| format!("{prefix}{t}")).collect(), true)
                .map_err(err)?;
            let (rows, len) = (tokens.len(), tokens[0].get_ids().len());
            let ids: Vec<i64> = tokens
                .iter()
                .flat_map(|t| t.get_ids().iter().map(|&x| x as i64))
                .collect();
            let mask: Vec<i64> = tokens
                .iter()
                .flat_map(|t| t.get_attention_mask().iter().map(|&x| x as i64))
                .collect();
            let lengths: Vec<i64> = mask.chunks(len).map(|r| r.iter().sum()).collect();
            truncated += lengths
                .iter()
                .filter(|&&n| n as usize >= self.m.max_length)
                .count();
            let mut inputs: Vec<(Cow<str>, SessionInputValue)> = Vec::new();
            for name in &names {
                let data = match name.as_str() {
                    "input_ids" => ids.clone(),
                    "attention_mask" => mask.clone(),
                    "token_type_ids" => vec![0; ids.len()],
                    other => bail!("unexpected model input: {other}"),
                };
                inputs.push((
                    name.clone().into(),
                    Tensor::from_array(([rows, len], data)).map_err(err)?.into(),
                ));
            }
            let out = session.run(inputs).map_err(err)?;
            let (shape, hidden) = out[0].try_extract_tensor::<f32>().map_err(err)?;
            if shape.len() != 3
                || shape[0] as usize != rows
                || shape[1] as usize != len
                || shape[2] as usize != DIM
            {
                bail!("invalid embedding output");
            }
            // Mean over real tokens, then L2, in f64 like the Python helper (numpy upcasts f32 * int64).
            for (r, n) in lengths.iter().enumerate() {
                let mut v = vec![0f64; DIM];
                for t in 0..len {
                    if mask[r * len + t] != 0 {
                        let row = &hidden[(r * len + t) * DIM..][..DIM];
                        v.iter_mut().zip(row).for_each(|(a, &x)| *a += x as f64);
                    }
                }
                v.iter_mut().for_each(|a| *a /= *n as f64);
                let norm = v.iter().map(|a| a * a).sum::<f64>().sqrt().max(1e-12);
                v.iter_mut().for_each(|a| *a /= norm);
                if v.iter().any(|a| !a.is_finite()) {
                    bail!("invalid embedding output");
                }
                vectors.push(v);
            }
        }
        Ok(Encoded {
            vectors,
            truncated_at_limit: truncated,
        })
    }
}
