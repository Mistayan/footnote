# Compact source qualification: less noise, uncertain recall gain

Measured 15 November 2026. Frozen recipe and criteria:
[MEMORY-QUALIFICATION.md](MEMORY-QUALIFICATION.md).

This is a **development-only** experiment on the same 244 LongMemEval-S databases: 231 answerable
queries, 13 dataset abstentions and 244 cross-database negatives. The existing baseline and full
source-context controls were reused only after verifying identical code, data, binary and model
identities. Each variant contains the same 7,235 memory identities summed over the databases.

## What qualification means here

The compact variant prepends one source-derived `Subject: ...` line to the original statement,
with no more than 80 additional characters. For preferences it uses a same-turn neighbouring
sentence; for fixes it prefers the preceding user's first sentence. It never sees the benchmark
query or labels while qualifying a memory. Of 7,235 statements, 6,981 received a qualifier.

This is an inexpensive source-fragment approximation, **not an agent-written autonomous memory,
an entity extractor or a new tag/filter system**. Failure of this recipe cannot establish that
better agent-written qualification would fail. The benchmark histories and old extractor are
English; French agent-written memories remain untested.

## Quality and retained text

| Development measure | Original statement | Full source context | Compact qualifier |
|---|---:|---:|---:|
| Raw hybrid any@3 | 121/231 = 52.38% | 139/231 = 60.17% | 127/231 = 54.98% |
| Raw keyword any@3 | 79/231 = 34.20% | 105/231 = 45.45% | 87/231 = 37.66% |
| Hybrid any@3 with old cutoff | 60/231 = 25.97% | 85/231 = 36.80% | 68/231 = 29.44% |
| Negative injections with old cutoff | 51/257 = 19.84% | 54/257 = 21.01% | 40/257 = 15.56% |
| True dataset abstention injections | 4/13 | 6/13 | 3/13 |
| Cross-database negative injections | 47/244 | 48/244 | 37/244 |
| Retained text characters | 672,636 | 1,802,775 | 1,148,470 |
| Text relative to original | 1.00x | 2.68x | 1.71x |

The compact variant gains **2.60 percentage points** of raw hybrid recall over the original.
Paired bootstrap 95% interval: **[-0.87, +6.06] points**, 10,000 samples by question family,
seed 20261115. The interval crosses zero. It retains only one third of the full-context raw recall
gain, below the frozen 75% target. Both recall criteria fail. The text-budget and noise criteria pass.

The fixed old cutoff is 2.341051842888992. It was not retuned for either enriched representation,
so the lower injection rates are diagnostic observations, not a calibrated production guarantee.
In particular, three versus four errors among 13 true abstentions is too small a change to certify
an improvement. Cross-database absence of answer-session IDs is also not semantic irrelevance proof.

## Actual on-disk control

The first ten fixed-order databases were rebuilt in all three variants. They contain 290 memories
in total. Sizes below are sums of actual file bytes, including SQLite and any WAL/SHM plus derived
Tantivy files, after commands and inspection connections close. Shared models and process state
are excluded. These are small-database observations, not estimates at large scale.

| File bytes, ten databases | Original | Full context | Compact qualifier |
|---|---:|---:|---:|
| SQLite including sidecars | 1,794,048 | 1,994,752 | 1,851,392 |
| Tantivy | 159,246 | 203,510 | 184,027 |
| Total store + index | 1,953,294 | 2,198,262 | 2,035,419 |
| Total relative to original | 1.000x | 1.125x | 1.042x |
| Vector payload within SQLite | 225,040 | 225,040 | 225,040 |

Thus the earlier **2.68x text** figure did not mean a 2.68x complete database. In this fixed small
sample, full context costs about **12.5%** more store/index bytes and the compact qualifier about
**4.2%**. Vector payload size is unchanged, as expected from the same memory count and dimensions.
SQLite page granularity and index overhead matter on these small databases. No idle-machine query
latency, peak RAM or encoder token/truncation measurement is claimed by this parallel collection.

## Decision

Do not replace the current representation with this compact prefix recipe. It does not meet its
frozen development recall criteria, despite the lower text volume and observed injection rate.
Keep the fuller source-context result as a development candidate; its disk cost in this sample is
far smaller than a text-only accounting suggested, but it worsened true abstention injections.

The next representation test should evaluate genuinely self-contained agent-written statements:
explicit subject, applicable project, technical stack/platform only when supported, and the reason
or condition needed to interpret the fact. Compare those against unchanged source evidence on new
French/English examples with answer-level judgments and hard no-answer cases. Do not infer that this
experiment validates tags, strict metadata filtering, a new database backend or automatic injection.

## Evidence and checks

- Collector: [memory_qualification.py](memory_qualification.py).
- Tests: [test_memory_qualification.py](test_memory_qualification.py); 16 memory-benchmark tests pass.
- Raw records: `bench/work/memory-qualification-dev-v1.jsonl`.
- Input identities and exact database IDs: `bench/work/memory-qualification-dev-v1.manifest.json`.
- Analysis: `bench/work/memory-qualification-dev-v1.analysis.json`.
- The collector rejects input changes on resume, missing numeric scores and changed stored counts.
  It writes only complete cases and removes its isolated temporary databases after measurement.
- `git diff --check` passes. Existing product source changes were preserved; no schema, hook prompt,
  installed MCP binary, user-memory database, dependency, commit or push was changed for this trial.
