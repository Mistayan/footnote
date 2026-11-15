# Source context improves development recall, with an abstention caveat

Measured 15 November 2026. Protocol: [MEMORY-CONTEXT.md](MEMORY-CONTEXT.md).
This is development evidence on previously used LongMemEval-S histories. No new held-out
confirmation or production activation is claimed.

## What changed

The same historical memory statements were stored in two isolated variants. The contextualized
variant adds bounded neighbouring source sentences and, for assistant fixes, the preceding user
turn. It has no access to evaluation questions or answers. Original statements, kinds, scopes,
source sessions and memory counts are preserved. Models, binary and retrieval settings are identical.

244 development databases were evaluated twice, with one original query and one cross-database
negative each: 976 query/variant evaluations, each in keyword and hybrid modes. Of the original
queries, 231 are answerable and 13 are dataset abstentions. There are 244 additional cross-database
negatives. Each variant stored 7,235 memories summed over these databases; this is not a count of
unique sessions or of the user's personal memories.

## Results

| Development metric | Statement alone | With source context |
|---|---:|---:|
| Keyword any@3, answerable | 79/231 = 34.20% | 105/231 = 45.45% |
| Hybrid any@3, before cutoff | 121/231 = 52.38% | 139/231 = 60.17% |
| Hybrid any@3, previous fixed cutoff | 60/231 = 25.97% | 85/231 = 36.80% |
| Negative injection, previous fixed cutoff | 51/257 = 19.84% | 54/257 = 21.01% |
| Dataset abstention injection, same cutoff | 4/13 = 30.77% | 6/13 = 46.15% |
| Cross-database negative injection, same cutoff | 47/244 = 19.26% | 48/244 = 19.67% |
| Keyword negative injection, no cutoff | 257/257 | 257/257 |
| Stored text characters, summed | 672,636 | 1,802,775 |

The main raw-hybrid gain is **+7.79 percentage points**, paired bootstrap 95% interval
**[+3.46, +12.12]**, 10,000 resamples by question family, seed 20261115. It meets the frozen
development criterion for considering a new independent confirmation: lower bound above zero,
aggregate gated negative injection up by no more than five points. The aggregate negative increase
is +1.17 points. This must not conceal the small abstention subgroup's increase of two cases.

The previous cutoff, 2.341051842888992, was kept unchanged. It was fitted to the old development
negative scores, so these gated numbers are diagnostics, not calibration or acceptance for the new
representation. Keyword's negative injection is also high without abstention: retaining keyword
hits unconditionally would not solve that problem.

Context changed 96.79% of stored statements and increased retained text by about 2.68 times.
That is a character count, not a measurement of tokens, RAM, model latency or total database size.
Parallel collection cannot establish idle-machine latency.

## Checks and evidence

- The baseline matches the earlier collection's query identities and hit counts across all 244
  databases and 488 queries. Relevance flags match on answerable queries; numeric scores differ
  by at most 1.56e-7. Both variants stored identical counts.
- Eleven targeted tests pass across the context collector, historical collector and cutoff analysis.
  They check source bounds, original identity deduplication, preservation of the original sentence,
  earlier-turn-only context, UTF-8 bounds and known bootstrap outcomes. `git diff --check` passes.
- Raw: `bench/work/memory-context-dev-v1.jsonl`.
- Frozen inputs: `bench/work/memory-context-dev-v1.manifest.json` records code, protocol, model,
  binary and source-data SHA-256 identities, plus the exact question IDs.
- Analysis: `bench/work/memory-context-dev-v1.analysis.json`.
- Implementation: [memory_context.py](memory_context.py); tests: [test_memory_context.py](test_memory_context.py).

## Decision and next test

Keep bounded source context as a development candidate. This experiment supports retaining enough
information to make a memory understandable; it does not prove a change in database architecture
is needed. Both lexical and hybrid recall improve. It also does not isolate semantic disambiguation
from retaining additional facts in the neighbouring text.

The next confirmation should use new French and English agent-written memories with explicit
source-grounded answer judgments and difficult no-answer questions. Freeze the source-only writing
rule and development-only relevance rule before opening those results. Include latency, encoding
truncation, token overhead and false injections. The graph, model and storage should remain fixed
so any improvement can be attributed to representation.

Do not automatically activate the current contextualization or the old cutoff: the 13-question
abstention subgroup is too small for certification and deteriorated in this run. The production hook,
installed MCP binary and personal memory store were not modified by this experiment.
