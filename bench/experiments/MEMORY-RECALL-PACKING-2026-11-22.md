# Memory recall packing: dual relevance floors, pointer packing and compact subagent context (#356)

Written 22 November 2026, before any measurement for this experiment was collected. Continues [MEMORY-ABSTENTION.md](MEMORY-ABSTENTION.md) and [MEMORY-CUTOFF.md](MEMORY-CUTOFF.md).

## Why

1. **Dual relevance floors (`cos_floor`, `inject_floor`):** [MEMORY-CUTOFF.md](MEMORY-CUTOFF.md) showed that a single threshold on query-relative `fusion_score` alone fails on held-out LongMemEval-S (any@3 fell from 31.80 % to 26.78 %). [MEMORY-ABSTENTION.md](MEMORY-ABSTENTION.md) showed a cross-encoder reranker (`mmarco-mMiniLMv2-L12-H384-v1`) also failed on dev (93.4 % no-answer injection at -4.8 pp any@3). Exposing the mean raw dense cosine (`dense_cosine`) alongside `fusion_score` costs zero extra model inference (it is already computed inside `Dense::blend` in `crates/search/src/semantic.rs`) and allows testing a dual-floor gate (`dense_cosine >= cos_floor` AND `fusion_score >= inject_floor`).
2. **Pointer packing:** Today `src/hook.rs` injects up to `recall_limit` (4) memories at up to 200 characters each (~200 tokens). Rendering only the top-K (`K = 2`) hits at 200 characters and secondary hits as compact one-line pointers (60-character preview + `[id N]` for `footnote_get <id>`) inside a strict character budget (`600` chars ≈ 150 tokens) can trim per-prompt token overhead without dropping any recalled memory ID.
3. **Compact `"binding"` subagent pack:** Delegated subagents currently inherit the full `SessionStart` pack (up to 3,000 chars ≈ 750 tokens, including facts, fixes, and session summaries) plus standing prose. A `"binding"` mode (`pack_binding`, preferences only, capped at 800 chars ≈ 200 tokens) gives delegated workers hard rules and constraints without redundant session prose.

## Data and splits

- **Dual relevance floors & pointer packing:** LongMemEval-S cleaned (`longmemeval_s_cleaned.json`), exact same deterministic question-family split (`sha256(family) % 2`: `dev` vs `heldout`), same positive + `_abs` + cross-database negative structure as [MEMORY-ABSTENTION.md](MEMORY-ABSTENTION.md) and [memory_cutoff_collect.py](memory_cutoff_collect.py), default model pair (`bekko-a8m` + `gte-small`), `recall_limit = 4`, built from this branch's release binary.
- **Binding subagent pack:** Deterministic multi-kind memory fixture (global preferences, project preferences, project facts, fixes, and session summaries totaling > 3,000 chars) comparing `full` (`3,000` chars) vs `binding` (`800` chars).

## Decision rule (fixed before any measurement)

1. **Dual relevance floors (`cos_floor`, `inject_floor`):**
   - **Dev only:** evaluate a deterministic grid of `(cos_floor, inject_floor)` pairs over dev hit quantiles (plus single-axis ablations) and select the pair that minimizes no-answer injection rate while keeping answerable `any@4` within **≤ 5.0 percentage points** of ungated hybrid `any@4` on dev.
   - **Held-out, once, with `(cos_floor, inject_floor)` frozen:** passes ONLY if BOTH hold:
     - no-answer injection rate ≤ **50.0 %** (`_abs` and cross-database negatives combined; each also reported separately);
     - answerable `any@4` within **≤ 5.0 percentage points** of ungated hybrid `any@4` (paired bootstrap 95 % CI, 10,000 resamples, seed `20261122`, by question family).
   - **Adoption rule:** default shipped hook settings (`cos_floor = None`, `inject_floor = None`) change ONLY if the held-out gate passes. Otherwise dual floors remain opt-in settings in `memory.json`, disabled by default.
2. **Pointer packing (`top_k = 2` @ 200 chars, secondary @ 60 chars, cap 600 chars):**
   - Measured on the same held-out hits (no tuning): reports mean injected chars and estimated tokens (`chars / 4`) per prompt vs flat 4×200 baseline, and `any@4` (whether a relevant memory ID remains present in the injected text).
   - **Adoption rule:** opt-in setting (`pointer_packing: false` by default) unless it reduces injected tokens by ≥ 25 % on multi-hit prompts with 0.0 pp drop in `any@4`.
3. **Binding subagent pack (`subagent_context: "binding"`, 800-char cap):**
   - Must stay ≤ **250 estimated tokens** (≤ 1,000 rendered chars) while retaining 100 % of binding preferences that fit within the 800-char text budget and excluding session/fact prose.

## Not in scope

- Changing the embedding models or fusion formula (`ALPHA = 0.55`).
- Enabling an abstention cutoff by default without passing the held-out gate.
- LLM answer-quality grading or paid API benchmark runs.

## Result (22 November 2026): dual floors and pointer packing stay opt-in; binding pack passes

Runner: [memory_recall_packing.py](memory_recall_packing.py); raw JSONL in git-ignored `bench/work/recall-packing/` (LongMemEval-S cleaned, default model pair `bekko-a8m` + `gte-small`, `recall_limit = 4`, release binary from this branch).

### 1. Dual relevance floors (`cos_floor`, `inject_floor`)

Dev split (244 question families: 231 answerable, 257 no-answer) selected `cos_floor = 0.479774` and `inject_floor = 0.817429` (dev `any@4` 0.550 → 0.502, -4.76 pp; no-answer injection 100 % → 72.0 %; mean tokens/prompt 169.5 → 79.3).

Held-out split, evaluated once with those floors frozen (256 question families: 239 answerable, 273 no-answer; paired bootstrap 95 % CI, 10,000 resamples, seed `20261122`):

| Held-out measure | Ungated (`recall_limit=4`) | Dual floors (frozen) | Pointer packing (`top_k=2`, 600 chars) |
|---|---:|---:|---:|
| `any@4` (answerable, n=239) | 0.448 | 0.393 (-5.44 pp; CI [-8.44, -2.88]) | 0.448 (0.00 pp) |
| No-answer injection (n=273) | 100.0 % | **70.3 %** (CI [-35.3, -24.4] pp) | 100.0 % |
| `_abs` / `cross` injection | 100.0 % / 100.0 % | 70.6 % / 70.3 % | 100.0 % / 100.0 % |
| Mean chars / prompt | 670.7 | 295.2 (-56.0 %) | 586.2 (-12.6 %) |
| Mean est. tokens / prompt (`chars/4`) | 167.7 | 73.8 | 146.5 |

- **Dual floors decision:** **fails** the held-out gate (no-answer injection 70.3 % > 50.0 % ceiling, and `any@4` drop 5.44 pp > 5.0 pp ceiling). Although dual floors beat the cross-encoder reranker from [MEMORY-ABSTENTION.md](MEMORY-ABSTENTION.md) (70.3 % vs 93.4 % no-answer injection) at zero extra inference cost, defaults stay `cos_floor = None` and `inject_floor = None` (opt-in in `memory.json`).
- **Pointer packing decision:** preserves 100 % of `any@4` (0.00 pp drop) and cuts injected tokens by 12.6 % on LongMemEval's short extracted sentences (~100 chars avg; larger savings on longer agent-written memories). Below the 25 % default-enable bar, so `pointer_packing` stays `false` by default (opt-in in `memory.json`).

### 2. Compact `"binding"` subagent pack

Deterministic multi-kind fixture (4 preferences + 15 facts/fixes/sessions > 3,000 chars):

| Mode | Memories | Text chars | Est. tokens (`chars/4`) | All preferences? | Reduction vs full |
|---|---:|---:|---:|---|---:|
| `full` (`--max-chars 3000`) | 19 | 2,585 | 646.2 | no | — |
| `binding` (`--binding --max-chars 800`) | 4 | 294 | **73.5** | yes (100 %) | **-88.6 %** |

- **Binding pack decision:** **passes** (73.5 est. tokens ≤ 250 target, 100 % binding preferences retained, zero session/fact prose). Exposed via `footnote memory-pack --binding`, `subagent_context: "binding"` in `memory.json`, `event.subagent = true`, or `FOOTNOTE_SUBAGENT=1`.

