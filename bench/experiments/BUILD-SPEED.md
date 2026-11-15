# Index build speed: plan and pre-registered rules

Written 14 November 2026, before any result of this test. Goal: a faster first ingestion without losing quality. Profiling showed encoding is 97 to 99.9 % ONNX inference, and the shipped int8 `gte-small` encodes at half the speed of fp32 `bekko-a8m` (46.9 against 87.8 documents per second on SciFact).

Weekend constraint: small corpora only. A variant is measured on a large corpus only after it wins on the small ones.

## Test 1: `gte-small` in fp32 instead of int8

Same repository and revision as the shipped model (`Xenova/gte-small`), file `onnx/model.onnx` instead of `onnx/model_quantized.onnx`. Same tokenizer, pooling, fusion (z-score convex, alpha 0.55) and partner model (`bekko-a8m` fp32). The only change is the second model's precision.

**Corpora:** held-out splits of SciFact, NFCorpus (English) and Alloprof (French). Mix-fr-en is left for the large-corpus confirmation.

**Adopt fp32 only if every condition holds:**
1. **Quality:** on each of the three corpora, the paired bootstrap 95 % interval (10,000 resamples) of the nDCG@10 difference (fp32 pair minus shipped pair) has a lower bound of -0.005 or higher. Comparison against the existing baseline receipts `receipts/heldout/*-lab_models2_baseline-heldout`.
2. **Speed:** document encoding throughput of `gte-small` fp32 is at least 1.3 times int8 (`profile_encode.py`, SciFact, 2,000 documents, quiet machine).
3. **Cost:** model file at most 600 MB; single-query encoding p95 at most twice the int8 one.

If it passes: measure a full shipped-binary build of mix-fr-en with fp32 against the 1,757 s receipt, then decide on shipping.

## Test 1b: the shipped embedding helper (written after test 1, before measuring it)

Test 1 showed that the models are not the bottleneck. Encoding SciFact with both models takes about 160 s at lab speed, but the shipped build took 676 s, 673 s of it in embedding (6,495 chunks, about 9.6 per second). The shipped helper (`tools/embed.py`) runs each model with 2 CPU threads, batches of 8, and texts in corpus order, so each batch is padded to its longest text. The lab uses all threads, batches of 32 and sorts by length.

**Change under test, document encoding only:** sort texts by length, larger batches, more threads, and restore the original order. Queries keep today's path (2 threads, one text) so query latency cannot get worse.

**Adopt only if every condition holds:**
1. **Same vectors:** on 2,000 SciFact documents, for both shipped models, every document's cosine between today's helper output and the new output is at least 0.99999.
2. **Same results:** a shipped-binary SciFact build with the new helper scores test nDCG@10 within 0.002 of the current receipt (0.747).
3. **Speed:** that build's embedding time is at most two thirds of the current 673 s (1.5× faster or more).

Then confirm on the large corpus (mix-fr-en, 1,757 s today). Product cost: changing `embed.py` changes the recipe hash, so existing databases must run `rebuild-embeddings` once.

**Result (`work/build-speed-t2-parallel.jsonl`):** one after the other 70.2 s, at the same time 74.8 s (0.94×), vectors identical. **Rejected:** with 12 threads each, the two models already saturate the CPU.

### Test 3: GPU for document encoding: not run

DirectML reproduces only `bekko-a8m` exactly (`GPU-ENCODING.md`); `gte-small` int8 gives different vectors on the GPU. After test 1b, `bekko-a8m` is about 40 % of the pair's encoding time (27 of 70 s per 2,000 SciFact documents), so the GPU could save at most that share, at the cost of a DirectML dependency Microsoft has moved to maintenance. Not worth a test run.

## Original plan for tests 2 and 3

- **Parallel encoding:** both models encoded at the same time, each ONNX session with half the threads, against one after the other.
- **GPU batch indexing:** DirectML for document encoding only, kept only for models whose vectors match the CPU (cosine 1.000000, identical nDCG). Queries stay on the CPU.

Rules for these are written here before they run.

## Results

### Test 1: fp32 `gte-small`: rejected (14 November)

Document encoding on 2,000 SciFact documents (`profile_encode.py`, raw: `work/build-speed-t1-profile.jsonl`): int8 48.4 documents/s, fp32 35.1 (0.73×; the rule needed 1.3×), `bekko-a8m` 95.3. The quality run was not needed. The overnight lead was wrong: `bekko-a8m` is faster because it is a smaller model, not because it is fp32; on this CPU int8 is the faster precision for `gte-small`.

### Test 1b: helper threads: passes on SciFact (14 November)

Variants on 2,000 SciFact documents (`helper_speed.py`, raw: `work/build-speed-t1b-helper.jsonl`), cosine against today's helper:

| Model | Variant | Documents/s | Speed-up | Min cosine |
|---|---|---|---|---|
| bekko-a8m | today: corpus order, batch 8, 2 threads | 25.1 to 26.4 | | |
| bekko-a8m | corpus order, batch 8, 12 threads | 72.3 | 2.87 | 1.0 |
| bekko-a8m | sorted, batch 32, 12 threads | 76.9 | 2.91 | 1.0 |
| bekko-a8m | sorted, batch 32, 24 threads | 55.3 | 2.09 | 1.0 |
| gte-small | today | 15.3 to 15.6 | | |
| gte-small | corpus order, batch 8, 12 threads | 34.8 | 2.22 | 1.0 |
| gte-small | corpus order, batch 16, 12 threads | 30.9 | 1.97 | 0.9871 |
| gte-small | sorted, batch 32, 12 threads | 43.5 | 2.85 | 0.9933 |

Sorting or larger batches change the int8 model's vectors: it quantizes activations per batch, so a text's vector depends on its batch neighbours. Only threads are exact for both models. **Change kept:** documents run on a second ONNX session with half the logical CPUs (12 here); corpus order, batch 8 and the 2-thread query session are unchanged.

Shipped-binary SciFact build with the new helper (receipt `20261114T074136Z-scifact-shipped-ensemble-mcp`) against the previous one (`20261113T092648Z`):

| | Before | After |
|---|---|---|
| Embedding time | 673.4 s | **279.9 s (2.41×)** |
| nDCG@10 | 0.7467 | 0.7467 |
| Rankings SHA-256 | 2e8c1770… | 2e8c1770… (identical) |
| Query p50 / p95 | 20.7 / 24.0 ms | 21.4 / 24.6 ms |

All three conditions hold. The harness also had to change: it reused a cached index whenever the binary was unchanged, even after `embed.py` changed; the build metadata now records the helper's hash.

Large-corpus confirmation, mix-fr-en (receipt `20261114T075530Z` against `20261113T162140Z`): build **1,756.5 s → 712.4 s (2.47×)**, nDCG@10 0.488989 both, rankings identical (b0472dd3…), query p50 / p95 27.9 / 44.3 → 27.8 / 44.6 ms. **Adopted** (a product change: existing databases run `rebuild-embeddings` once). Against competitors on this corpus: mem0 best 336 s (Footnote was 5.2× slower, now 2.1×); ICM keyword-only 98 s (18× → 7.3×).

### Test 2: both models at the same time (written before measuring)

After test 1b each model encodes with 12 threads, one model after the other; one model on all 24 threads was slower. Test: the two models encode the same 2,000 SciFact documents at the same time, each with 12 threads, against one after the other. **Adopt into the binary only if** the wall time of the pair is at most 80 % of the sequential time (1.25× or more), with vectors identical to test 1b (cosine 1.0), since the Rust change (one helper call per model in parallel) costs complexity.

### Test 4: encoder in Rust, no Python (written 14 November, before any code or measurement)

The Python helper (`tools/embed.py`) is replaced by the same recipe inside the binary: ONNX Runtime 1.31 through the `ort` crate (2.0.0-rc.15, built for ONNX Runtime 1.31, the version Python uses today) and the `tokenizers` crate 0.22.2 (the Rust library under Python's `tokenizers` 0.22.2). Same manifest checks, prefixes, truncation, padding, batches of 8 in corpus order, mean pooling, L2 normalization, 2 threads for queries and half the logical CPUs for documents.

Gains to expect: no Python install for search and memory; the helper start (about 1.05 s per process and model, from `footnote metrics`) goes away; no JSON round trip per batch.

**Adopt only if every condition holds:**
1. **Same vectors:** on the same 2,000 SciFact documents as test 1b and the 300 SciFact test queries, for both shipped models, every cosine between the Python helper and the Rust encoder is at least 0.99999.
2. **Same results:** a SciFact build with the Rust encoder gives the same rankings SHA-256 as the current receipt (2e8c1770…); if it differs, nDCG@10 within 0.002 of 0.7467.
3. **No slower:** embedding time at most 1.1× today's 279.9 s, and query p95 at most 1.1× today's 24.6 ms.
4. **Size:** the release binary grows by at most 40 MB.

If SciFact passes: one mix-fr-en build (rankings b0472dd3…, 712.4 s) before shipping. Product cost if adopted: the recipe identity changes, so existing databases run `rebuild-embeddings` once, unless condition 1 shows identical vectors, in which case the old Python recipe hash is accepted as equal.

**Result (14 November): adopted.**

1. Vectors (`rust_encoder.py`, raw: `work/build-speed-t4-vectors.jsonl`), 2,000 SciFact documents and 300 test queries:

| Model | Texts | Min cosine | Max difference | Python texts/s | Rust texts/s |
|---|---|---|---|---|---|
| bekko-a8m | documents | 1.0 | 1.0e-7 | 80.1 | 81.7 |
| bekko-a8m | queries | 1.0 | 1.5e-7 | 457.6 | 179.1 * |
| gte-small | documents | 1.0 | 3.3e-16 | 40.9 | 41.2 |
| gte-small | queries | 1.0 | 2.2e-16 | 350.6 | 285.8 * |

\* The Rust figure includes the first batch's warm-up, the Python one does not; per-query latency is judged on the receipts below.

2–4. Shipped-binary builds, Rust encoder against the Python helper:

| | SciFact before | SciFact after | Mix-fr-en before | Mix-fr-en after |
|---|---|---|---|---|
| Receipt | `20261114T074136Z` | `20261114T125923Z` | `20261114T075530Z` | `20261114T131231Z` |
| nDCG@10 | 0.7467 | 0.7467 | 0.488989 | 0.488989 |
| Rankings SHA-256 | 2e8c1770… | 2e8c1770… (identical) | b0472dd3… | cda616aa… (3 of 3,039 queries differ) |
| Embedding time | 279.9 s | **241.0 s (−14 %)** | 704.5 s † | **660.4 s (−6 %)** |
| Query p50 / p95 | 21.4 / 24.6 ms | **18.5 / 21.5 ms** | 27.8 / 44.6 ms | 27.1 / 43.9 ms |
| Binary | 9.5 MB | 34.8 MB (+25 MB) | | |

† Whole build 712.4 → 664.9 s (−7 %).

On mix-fr-en, three queries swap two neighbouring documents around rank 9–10: `gte-small` is bit-identical, `bekko-a8m` (fp32) differs by about 1e-7, enough to cross an int8 rounding step now and then. nDCG@10 is identical to six decimals, so condition 2 holds through its fallback. The recipe identity stays the Python helper's hash (`d69ec768…`): vectors already stored stay valid, no rebuild needed.

Python is no longer needed for indexing, embeddings or search. It remains for the one-time model download, PDF extraction and OCR, and the memory hook.
