# Final multilingual confirmation — fresh single-exposure run

**Status: actual execution complete; independent semantic judgment pending. No 80% or 90% acceptance claim.**

Run: `artifacts/final-multilingual-confirmation/fresh-c6cfd7b5ae4149e7b9f76484e52bf863/`

## Independent-review handoff

Send **only** these files to a new independent reviewer:

- `blind-packet.json` — 52 shuffled top-one records, including refused and no-answer requests; exact query, full actual presented evidence, original URL/version/language/hash and excerpt offsets; no scores, acceptance flags, gold, expected IDs or query IDs.
- `RUBRIC.json` — complete-answer, version/scope and explicit source-edition criteria; pass/fail/uncertain plus verbatim support and rationale.

Freeze reviewer verdicts before revealing:

- `mapping-DO-NOT-SEND.json` — blinded ID → original request, accepted status, answerability and language direction.
- `gold-DO-NOT-SEND.json` — pre-inference source answer statements, exact selected quotes/offsets, semantic criteria, version and corpuswide eligible/excluded source editions.
- `actual-records-DO-NOT-SEND.jsonl` — all 52 live selected-method requests, raw dense/Qdrant candidates, lexical branch, contributions, reranked scores, ordered top-five actual evidence and timing.
- `exact-ID-diagnostic-DO-NOT-SEND.json` — exact selected-parent-ID hits **only**, explicitly not semantic correctness; unselected passages remain unjudged, not wrong.

Final milestone numerator must be independently judged **accepted-correct / all 40 answerable**. Rejections count as misses. Report accepted precision, answerable coverage and no-answer false acceptance separately. A judged point estimate on this small, clustered public-source corpus is not general certification or private-vault validation.

## Fresh frozen inputs

Six genuine official Python 3.13 source pages: `json`, `dataclasses`, and `asyncio-queue`, each in the English and French official editions. Exact original HTML bytes, normalized text and source-byte receipts are retained under `sources/`, `source-receipts.json`, and `network-receipts.json`. All seven fetches (six corpus sources plus official license) succeeded; no fabricated or substitute documents, no failed network path. Python's official license page is retained as `sources/python-license.raw` and `.txt`; PSF v2 documentation terms and additional 0BSD example-code terms are recorded before freezing.

- 40 answerable questions, **10 in each EN→EN, EN→FR, FR→EN, FR→FR direction**, covering distinct API/condition facts, not bilingual duplicate questions about the same fact.
- 12 no-answer questions: 10 unsupported near-miss APIs/options/guarantees and two explicitly unavailable private facts. No private source was accessed.
- Every answerable query explicitly requests its required documentation edition. Any genuinely answering passage in an eligible corpus source can receive semantic credit; selected quote IDs are incomplete diagnostics only.
- French-edition documents contain some upstream untranslated English paragraphs. These directions are **official source-edition directions**, not a claim that every French-page evidence sentence is French. Original upstream typos/source-link errors are not repaired.
- 135 uniform parent blocks, width 1800 Unicode codepoints, stride 900, no title enrichment or gold-derived boundaries; 500 source-wide token slices at cap96/overlap24.

`freeze.json` and `protocol.json` bind original source bytes, normalized corpus, source gold, requests, rubric, both configurations, code and actual local model/server hashes before ranking. `code-freeze/` contains 16 byte-identical code/test copies. Model artifact hashes include the existing MiniLM encoder and mMARCO reranker; no model downloads, new dependencies or shared-environment changes.

## Unchanged method and transport

The candidate overrides **only constructor corpus/transport binding**. It directly inherits `evidence_completion.experiment.Session.constrained`, `CorpusIdentitySession.index`, and `IdentitySearchSession.search`; evidence is produced by the unchanged `evidence_completion.core.get_evidence` and generic request parser.

Frozen selected configuration: source-wide cap96/overlap24; actual Qdrant ANN point400, parent100, ef512; FTS10; RRF60; pool20; resident pinned mMARCO512 longest-first CPU2/1 batch4; original cutoff **2.5**; exact-source sentence/paragraph/fenced-code/REPL completion bounded at **2500 characters**; explicit source-language filtering before acquisition and again at presentation.

Both baseline and selected configurations were frozen. Full baseline52 inference was omitted as optional; no baseline quality comparison is claimed. A neutral label-free live request proved exact selected-no-constraint versus inherited identity **pool, ranking and scores** parity (`mechanical-parity.json`). Old development21 replay was not performed, and no old per-query failures/results were opened. Function identity and the neutral check are not mislabeled as historical21 parity.

## Preliminary structural results only

| Measure | Actual result |
|---|---:|
| Selected live requests | 52/52 |
| Answerable accepted | 37/40 |
| Answerable rejected | 3/40 |
| Answerable coverage | 92.5% |
| No-answer accepted (false accepts under frozen corpus absence gold) | 4/12 |
| No-answer false-acceptance rate | 33.33% |
| Full top-five snippets verified against original normalized offsets and hashes | 260 |
| Structurally incomplete / over-budget completions | 0 |
| Independent semantic correct count / P@1 | **Pending** |

Coverage is not accuracy. The four accepted no-answer requests are an observed limitation at the unchanged cutoff, not grounds for recalibrating this exposed set. No fresh ranking, cutoff, source boundary or gold modifications followed exposure.

Actual resident Qdrant server: 500/500 indexed points, green status; loopback-only owned storage/process; server vector readback retained. Complete measured run wall time: 84.142 seconds. Cleanup records owned PID24500/port65211 exited/closed. Windows `Popen.terminate` is forced termination, not graceful durability acceptance. Independent post-run process and socket probes confirmed cleanup. No existing service was stopped.

## Verification and replay boundaries

The artifact manifest hashes evidence outputs, frozen code copies, readback and cleanup. Frozen source/code/model inputs were reverified after all requests. All snippets retain exact original-source codepoint offsets, raw and normalized hashes, excerpt hash and source applicability. The final packet contains all52 actual top-one records; mapping IDs are a bijection.

Commands:

```bash
python -m unittest discover -s tests -p 'test_final_multilingual_confirmation*.py' -v
```

The runner is runnable as:

```bash
python tools/final_multilingual_confirmation/runner.py NEW_PREPARED_OWNED_SNAPSHOT
```

It refuses to run an already frozen directory, preventing silent overwrite/re-exposure. Source preparation and authoring are `fetch.py` then `gold.py`; do not interpret regenerating this now-exposed test as another fresh confirmation. The frozen first run is the delivered result; no tuning is authorized on it.

Only new `tools/final_multilingual_confirmation/*`, `tests/test_final_multilingual_confirmation*.py`, this document and the unique artifact directory were created. Incumbent source/config files remain hash-verified unchanged. No staging, commits, push, vault, private data, global configuration or shared dependency changes.
