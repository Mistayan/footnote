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
use std::{num::NonZeroU32, path::Path, sync::OnceLock};

const CTX: u32 = 1024;

pub struct Gguf {
    // shortcut: the model is leaked so the context can borrow it for 'static; an encoder lives for the process, so this leaks only
    // when a model directory is replaced while the process runs. Upgrade to an owning wrapper if models are swapped often.
    model: &'static LlamaModel,
    ctx: LlamaContext<'static>,
    max_len: usize,
    pub dimension: usize,
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

impl Gguf {
    /// `pooling` is the manifest's: "last" or "mean". The file must already be verified by the caller.
    pub fn load(path: &Path, pooling: &str, max_len: usize) -> Result<Self> {
        let pooling = match pooling {
            "last" => LlamaPoolingType::Last,
            "mean" => LlamaPoolingType::Mean,
            _ => bail!("unsupported pooling for a GGUF model"),
        };
        if !(8..=CTX as usize).contains(&max_len) {
            bail!("unsupported max_length for a GGUF model");
        }
        let b = backend()?;
        let model: &'static LlamaModel = Box::leak(Box::new(
            LlamaModel::load_from_file(b, path, &LlamaModelParams::default().with_n_gpu_layers(0))
                .map_err(|e| anyhow!("load GGUF model: {e}"))?,
        ));
        let threads = (std::thread::available_parallelism().map_or(4, |n| n.get()) / 2).max(1) as i32;
        let params = LlamaContextParams::default()
            .with_n_ctx(NonZeroU32::new(CTX))
            .with_n_batch(CTX)
            .with_n_ubatch(CTX)
            .with_n_threads(threads)
            .with_n_threads_batch(threads)
            .with_embeddings(true)
            .with_pooling_type(pooling);
        let ctx = model.new_context(b, params).map_err(|e| anyhow!("llama.cpp context: {e}"))?;
        let dimension = usize::try_from(model.n_embd_out()).context("embedding width")?;
        Ok(Self { model, ctx, max_len, dimension })
    }

    /// One unit vector per text (`text` already carries its prefix) and whether it was cut at `max_length`.
    pub fn embed(&mut self, text: &str) -> Result<(Vec<f64>, bool)> {
        let vocab = self.model.vocab();
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
        batch.add_sequence(&tokens, 0, true).map_err(|e| anyhow!("{e}"))?;
        self.ctx.clear_kv_cache();
        // encoder-only models (Jina v5 nano) take encode(); decoder models (Qwen3, Gemma) take decode()
        if self.ctx.encode(&mut batch).is_err() {
            self.ctx.decode(&mut batch).map_err(|e| anyhow!("llama.cpp decode: {e}"))?;
        }
        let v = self.ctx.embeddings_seq_ith(0).map_err(|_| anyhow!("no pooled embedding"))?;
        if v.len() != self.dimension {
            bail!("invalid embedding output");
        }
        let norm = v.iter().map(|x| (*x as f64).powi(2)).sum::<f64>().sqrt().max(1e-12);
        let out: Vec<f64> = v.iter().map(|x| *x as f64 / norm).collect();
        if out.iter().any(|a| !a.is_finite()) {
            bail!("invalid embedding output");
        }
        Ok((out, cut))
    }
}
