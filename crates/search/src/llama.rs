//! GGUF embedding models through llama.cpp, compiled in (`--features llama`). Test 6 (bench/experiments/LLAMACPP-INPROCESS.md):
//! called in-process, Jina v5 nano encodes a query in about 26 ms at p95, the same vectors as `llama-server`.
//!
//! Recipe, the one the bench lab used: prefix, cut to `max_length - 4` tokens (tokenize without special tokens, keep the first ones,
//! detokenize), tokenize again with the model's special tokens, one sequence per call, the model's pooling, L2 normalization.
use anyhow::{Context, Result, anyhow, bail};
use llama_cpp_2::context::LlamaContext;
use llama_cpp_2::context::params::{LlamaContextParams, LlamaPoolingType};
use llama_cpp_2::llama_backend::LlamaBackend;
use llama_cpp_2::llama_batch::LlamaBatch;
use llama_cpp_2::model::LlamaModel;
use llama_cpp_2::model::params::LlamaModelParams;
use std::{mem::ManuallyDrop, num::NonZeroU32, path::Path, ptr::NonNull, sync::OnceLock};

const CTX: u32 = 1024;

/// A loaded GGUF model and its context. It owns both: the context borrows the model, so the model is kept behind a pointer and
/// freed after the context in `Drop`. A resident daemon drops encoders after `idle_seconds` unused (#515); the model was leaked
/// before, which kept its weights (about 200 MB for Jina v5 nano) resident for the life of the process (#517).
pub struct Gguf {
    /// Borrows `*model`; dropped first.
    ctx: ManuallyDrop<LlamaContext<'static>>,
    /// From `Box::into_raw` in `load`, freed once in `Drop`.
    model: NonNull<LlamaModel>,
    max_len: usize,
    pub dimension: usize,
}

// SAFETY: `LlamaModel` is Send and Sync and `LlamaContext` is Send (llama-cpp-2); the model pointer is owned by this value alone.
unsafe impl Send for Gguf {}

impl Drop for Gguf {
    fn drop(&mut self) {
        // SAFETY: the context is the model's only borrower and goes first; the pointer came from `Box::into_raw` and is freed
        // only here.
        unsafe {
            ManuallyDrop::drop(&mut self.ctx);
            drop(Box::from_raw(self.model.as_ptr()));
        }
    }
}

fn backend() -> Result<&'static LlamaBackend> {
    static B: OnceLock<Result<LlamaBackend, String>> = OnceLock::new();
    B.get_or_init(|| {
        let mut b = LlamaBackend::init().map_err(|e| e.to_string())?;
        b.void_logs(); // llama.cpp would otherwise print to stderr on every call
        Ok(b)
    })
    .as_ref()
    .map_err(|e| anyhow!("llama.cpp backend: {e}"))
}

/// What a GGUF file declares about itself, to import it as an embedding model (#556).
pub struct GgufInfo {
    pub name: String,
    /// "mean", "cls" or "last": the pooling `Gguf::load` takes.
    pub pooling: String,
    pub dimension: usize,
    pub context: usize,
}

/// Read a GGUF's metadata (loads the weights, on the CPU). Refuses a file without an embedding pooling type: a chat model or a
/// reranker would otherwise import fine and fail at the first recall.
pub fn inspect(path: &Path) -> Result<GgufInfo> {
    let model = LlamaModel::load_from_file(
        backend()?,
        path,
        &LlamaModelParams::default().with_n_gpu_layers(0),
    )
    .map_err(|e| anyhow!("not a GGUF model llama.cpp can load: {e}"))?;
    let meta = |key: &str| model.meta_val_str(key).ok();
    let arch = meta("general.architecture").context("GGUF without general.architecture")?;
    let pooling = match meta(&format!("{arch}.pooling_type")).as_deref() {
        Some("1") => "mean",
        Some("2") => "cls",
        Some("3") => "last",
        _ => bail!(
            "{arch} model declares no embedding pooling: not an embedding model (or one llama.cpp cannot pool)"
        ),
    };
    Ok(GgufInfo {
        name: meta("general.name").unwrap_or_default(),
        pooling: pooling.into(),
        dimension: usize::try_from(model.n_embd_out()).context("embedding width")?,
        context: meta(&format!("{arch}.context_length"))
            .and_then(|c| c.parse().ok())
            .unwrap_or(512),
    })
}

impl Gguf {
    /// `pooling` is the manifest's: "last" or "mean". The file must already be verified by the caller.
    pub fn load(path: &Path, pooling: &str, max_len: usize) -> Result<Self> {
        let pooling = match pooling {
            "last" => LlamaPoolingType::Last,
            "mean" => LlamaPoolingType::Mean,
            "cls" => LlamaPoolingType::Cls,
            _ => bail!("unsupported pooling for a GGUF model"),
        };
        if !(8..=CTX as usize).contains(&max_len) {
            bail!("unsupported max_length for a GGUF model");
        }
        let b = backend()?;
        let owned = Box::new(
            LlamaModel::load_from_file(b, path, &LlamaModelParams::default().with_n_gpu_layers(0))
                .map_err(|e| anyhow!("load GGUF model: {e}"))?,
        );
        let ptr = NonNull::from(Box::leak(owned));
        // SAFETY: the model lives until `Gguf::drop`, which frees the context first; on an error below it is freed here.
        let model: &'static LlamaModel = unsafe { ptr.as_ref() };
        let free = || {
            // SAFETY: nothing borrows the model yet (no context was made); the pointer came from `Box::leak` above.
            drop(unsafe { Box::from_raw(ptr.as_ptr()) });
        };
        let threads = crate::encoder::bulk_threads() as i32;
        let params = LlamaContextParams::default()
            .with_n_ctx(NonZeroU32::new(CTX))
            .with_n_batch(CTX)
            .with_n_ubatch(CTX)
            .with_n_threads(threads)
            .with_n_threads_batch(threads)
            .with_embeddings(true)
            .with_pooling_type(pooling);
        let dimension = match usize::try_from(model.n_embd_out()) {
            Ok(d) => d,
            Err(e) => {
                free();
                return Err(e).context("embedding width");
            }
        };
        let ctx = match model.new_context(b, params) {
            Ok(ctx) => ctx,
            Err(e) => {
                free();
                bail!("llama.cpp context: {e}");
            }
        };
        Ok(Self {
            ctx: ManuallyDrop::new(ctx),
            model: ptr,
            max_len,
            dimension,
        })
    }

    fn model(&self) -> &LlamaModel {
        // SAFETY: owned by `self` and freed only in `drop`.
        unsafe { self.model.as_ref() }
    }

    /// One unit vector per text (`text` already carries its prefix) and whether it was cut at `max_length`.
    pub fn embed(&mut self, text: &str) -> Result<(Vec<f64>, bool)> {
        let vocab = self.model().vocab();
        let mut cut = false;
        let mut text = text.as_bytes().to_vec();
        if text.len() >= self.max_len - 4 {
            // every token covers at least one byte, so a shorter text always fits
            let plain = vocab.tokenize(&text, false, false);
            if plain.len() > self.max_len - 4 {
                text = vocab.detokenize(&plain[..self.max_len - 4], false, false);
                cut = true;
            }
        }
        let tokens = vocab.tokenize(&text, true, true);
        if tokens.is_empty() || tokens.len() > CTX as usize {
            bail!("embedding input bound exceeded");
        }
        let mut batch = LlamaBatch::new(tokens.len(), 1);
        batch
            .add_sequence(&tokens, 0, true)
            .map_err(|e| anyhow!("{e}"))?;
        self.ctx.clear_kv_cache();
        // encoder-only models (Jina v5 nano) take encode(); decoder models (Qwen3, Gemma) take decode()
        if self.ctx.encode(&mut batch).is_err() {
            self.ctx
                .decode(&mut batch)
                .map_err(|e| anyhow!("llama.cpp decode: {e}"))?;
        }
        let v = self
            .ctx
            .embeddings_seq_ith(0)
            .map_err(|_| anyhow!("no pooled embedding"))?;
        if v.len() != self.dimension {
            bail!("invalid embedding output");
        }
        let norm = v
            .iter()
            .map(|x| (*x as f64).powi(2))
            .sum::<f64>()
            .sqrt()
            .max(1e-12);
        let out: Vec<f64> = v.iter().map(|x| *x as f64 / norm).collect();
        if out.iter().any(|a| !a.is_finite()) {
            bail!("invalid embedding output");
        }
        Ok((out, cut))
    }
}
