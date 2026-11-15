//! Test 6: embed queries one at a time with llama.cpp in-process (no server), timing each call.
//!
//! llama_inproc <runtime dir> <model.gguf> <threads> <queries file, NUL-separated> <output .jsonl>
//!
//! Structs mirror `include/llama.h` of build b11901 (commit 5320c87ff), the build the DLLs come from. The layout is
//! checked at start against the library's own defaults; a mismatch aborts.
use std::ffi::{c_char, c_void, CString};
use std::io::Write;
use std::time::Instant;

#[repr(C)]
#[derive(Clone, Copy)]
struct ModelParams {
    devices: *mut c_void,
    tensor_buft_overrides: *const c_void,
    n_gpu_layers: i32,
    split_mode: i32,
    load_mode: i32,
    lazy_mode: i32,
    main_gpu: i32,
    tensor_split: *const f32,
    progress_callback: *const c_void,
    progress_callback_user_data: *mut c_void,
    kv_overrides: *const c_void,
    vocab_only: bool,
    check_tensors: bool,
    use_extra_bufts: bool,
    no_host: bool,
    no_alloc: bool,
    load_mtp: bool,
}

#[repr(C)]
#[derive(Clone, Copy)]
struct ContextParams {
    n_ctx: u32,
    n_batch: u32,
    n_ubatch: u32,
    n_seq_max: u32,
    n_rs_seq: u32,
    n_outputs_max: u32,
    n_outputs_max_per_seq: u32,
    n_threads: i32,
    n_threads_batch: i32,
    ctx_type: i32,
    rope_scaling_type: i32,
    pooling_type: i32,
    attention_type: i32,
    flash_attn_type: i32,
    rope_freq_base: f32,
    rope_freq_scale: f32,
    yarn_ext_factor: f32,
    yarn_attn_factor: f32,
    yarn_beta_fast: f32,
    yarn_beta_slow: f32,
    yarn_orig_ctx: u32,
    defrag_thold: f32,
    cb_eval: *const c_void,
    cb_eval_user_data: *mut c_void,
    type_k: i32,
    type_v: i32,
    moe_cache_size: usize,
    abort_callback: *const c_void,
    abort_callback_data: *mut c_void,
    embeddings: bool,
    offload_kqv: bool,
    no_perf: bool,
    op_offload: bool,
    swa_full: bool,
    kv_unified: bool,
    samplers: *mut c_void,
    n_samplers: usize,
    ctx_other: *mut c_void,
}

#[repr(C)]
struct Batch {
    n_tokens: i32,
    token: *mut i32,
    embd: *mut f32,
    pos: *mut i32,
    n_seq_id: *mut i32,
    seq_id: *mut *mut i32,
    logits: *mut i8,
}

#[link(name = "kernel32")]
extern "system" {
    fn LoadLibraryW(name: *const u16) -> *mut c_void;
    fn GetProcAddress(module: *mut c_void, name: *const c_char) -> *mut c_void;
    fn SetDllDirectoryW(path: *const u16) -> i32;
}

extern "C" fn quiet(_level: i32, _text: *const c_char, _user: *mut c_void) {}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(Some(0)).collect()
}

unsafe fn sym<T>(lib: *mut c_void, name: &str) -> T {
    let c = CString::new(name).unwrap();
    let p = GetProcAddress(lib, c.as_ptr());
    assert!(!p.is_null(), "missing symbol {name}");
    std::mem::transmute_copy(&p)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 6, "usage: llama_inproc <runtime dir> <model.gguf> <threads> <queries> <out.jsonl>");
    let (dir, model_path, threads) = (&args[1], &args[2], args[3].parse::<i32>().unwrap());
    let raw = std::fs::read(&args[4]).unwrap();
    let queries: Vec<&[u8]> = raw.split(|b| *b == 0).filter(|q| !q.is_empty()).collect();
    unsafe {
        assert!(SetDllDirectoryW(wide(dir).as_ptr()) != 0);
        let ggml = LoadLibraryW(wide(&format!("{dir}\\ggml.dll")).as_ptr());
        let llama = LoadLibraryW(wide(&format!("{dir}\\llama.dll")).as_ptr());
        assert!(!ggml.is_null() && !llama.is_null(), "cannot load ggml.dll / llama.dll from {dir}");
        let load_all: extern "C" fn(*const c_char) = sym(ggml, "ggml_backend_load_all_from_path");
        let backend_init: extern "C" fn() = sym(llama, "llama_backend_init");
        let model_defaults: extern "C" fn() -> ModelParams = sym(llama, "llama_model_default_params");
        let ctx_defaults: extern "C" fn() -> ContextParams = sym(llama, "llama_context_default_params");
        let load_model: extern "C" fn(*const c_char, ModelParams) -> *mut c_void = sym(llama, "llama_model_load_from_file");
        let init_ctx: extern "C" fn(*mut c_void, ContextParams) -> *mut c_void = sym(llama, "llama_init_from_model");
        let get_vocab: extern "C" fn(*const c_void) -> *const c_void = sym(llama, "llama_model_get_vocab");
        let n_embd: extern "C" fn(*const c_void) -> i32 = sym(llama, "llama_model_n_embd");
        let tokenize: extern "C" fn(*const c_void, *const c_char, i32, *mut i32, i32, bool, bool) -> i32 =
            sym(llama, "llama_tokenize");
        let get_memory: extern "C" fn(*const c_void) -> *mut c_void = sym(llama, "llama_get_memory");
        let memory_clear: extern "C" fn(*mut c_void, bool) = sym(llama, "llama_memory_clear");
        let batch_one: extern "C" fn(*mut i32, i32) -> Batch = sym(llama, "llama_batch_get_one");
        let encode: extern "C" fn(*mut c_void, Batch) -> i32 = sym(llama, "llama_encode"); // nano is non-causal: decode() would fall back to encode() and log each call
        let embeddings_seq: extern "C" fn(*mut c_void, i32) -> *const f32 = sym(llama, "llama_get_embeddings_seq");

        let log_set: extern "C" fn(extern "C" fn(i32, *const c_char, *mut c_void), *mut c_void) = sym(llama, "llama_log_set");
        log_set(quiet, std::ptr::null_mut()); // the product would not print a line per query either
        let dir_c = CString::new(dir.as_str()).unwrap();
        load_all(dir_c.as_ptr());
        backend_init();

        // layout check: these are llama.cpp's documented defaults; any shift in the mirrored structs breaks them
        let mut cp = ctx_defaults();
        assert!(cp.n_ctx == 512 && cp.n_batch == 2048 && cp.n_ubatch == 512 && cp.n_seq_max == 1, "context params layout");
        assert!(!cp.embeddings && cp.offload_kqv && cp.ctx_other.is_null() && cp.n_samplers == 0, "context params tail layout");
        let mut mp = model_defaults();
        assert!(mp.devices.is_null() && !mp.vocab_only && mp.kv_overrides.is_null(), "model params layout");

        mp.n_gpu_layers = 0; // like the test 5 query server (-ngl 0)
        let path = CString::new(model_path.as_str()).unwrap();
        let model = load_model(path.as_ptr(), mp);
        assert!(!model.is_null(), "model load failed");
        cp.n_ctx = 1024; // the test 5 server gave each slot 1024 tokens
        cp.n_batch = 1024;
        cp.n_ubatch = 1024;
        cp.n_threads = threads;
        cp.n_threads_batch = threads;
        cp.embeddings = true;
        cp.pooling_type = 3; // LLAMA_POOLING_TYPE_LAST, as `--pooling last`
        let ctx = init_ctx(model, cp);
        assert!(!ctx.is_null(), "context init failed");
        let vocab = get_vocab(model);
        let dim = n_embd(model) as usize;
        let memory = get_memory(ctx);

        let mut out = std::io::BufWriter::new(std::fs::File::create(&args[5]).unwrap());
        let mut tokens = vec![0i32; 2048];
        let mut embed = |text: &[u8]| -> Vec<f32> {
            let n = tokenize(vocab, text.as_ptr() as *const c_char, text.len() as i32, tokens.as_mut_ptr(), tokens.len() as i32, true, true);
            assert!(n > 0, "tokenize failed ({n})");
            if !memory.is_null() {
                memory_clear(memory, true);
            }
            assert_eq!(encode(ctx, batch_one(tokens.as_mut_ptr(), n)), 0, "encode failed");
            let v = embeddings_seq(ctx, 0);
            assert!(!v.is_null(), "no pooled embedding");
            std::slice::from_raw_parts(v, dim).to_vec()
        };
        for q in queries.iter().take(3) {
            embed(&[b"Query: ".as_slice(), q].concat());
        }
        for q in &queries {
            let text = [b"Query: ".as_slice(), q].concat();
            let t0 = Instant::now();
            let v = embed(&text);
            let ms = t0.elapsed().as_secs_f64() * 1000.0;
            let vec: Vec<String> = v.iter().map(|x| format!("{x}")).collect();
            writeln!(out, "{{\"ms\":{ms},\"vec\":[{}]}}", vec.join(",")).unwrap();
        }
    }
}
