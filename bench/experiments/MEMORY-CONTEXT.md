# Context around a memory: development experiment

Frozen on 15 November 2026 before collecting contextualized recall results.

Question: does bounded context copied from the source conversation improve the retrieval of the
same memories, with the same binary, two embedding models, lexical engine and fusion?

## Frozen method

- Use only the previous LongMemEval-S **development** partition, grouped by question ID without
  the `_abs` suffix. The previously examined held-out partition is excluded. This experiment is
  development evidence, not a fresh confirmation and not authorization for automatic injection.
- Keep the historical extractor's statements, ten-per-session cap, order, kinds and scopes.
  Deduplicate on the original `(kind, scope, text)` before either variant is stored, so the two
  variants retain the same memory identities and source sessions. Record actual stored counts.
- Baseline: original statement alone. Context: the immediately previous and next sentence in the
  same turn, each capped at 240 characters. For an assistant fix, also include the most recent
  earlier user turn's first 240 characters. Keep the original statement intact. No later turn,
  question, answer, answer-session label or retrieval output enters contextualization.
- Context can add facts from the same source turn. Consequently this experiment measures the
  combined effect of retained source information and disambiguation, not just embedding quality.
  Source context is data and may itself contain instructions; this experiment does not activate
  the text in an agent or alter the live memory store.
- Recall the original query, and one deterministic cross-database negative with disjoint answer
  sessions, in lexical and hybrid modes. The negative query belongs to the development partition.
  Also report the dataset's `_abs` questions separately from cross-database negatives.
- Main metrics: raw hybrid any@3, lexical any@3, and negative injection. Report the previous fixed
  cutoff 2.341051842888992 as a secondary diagnostic, without retuning it after enrichment.
- Main comparison: contextualized hybrid minus baseline hybrid on answerable development
  questions, paired bootstrap by question family, 10,000 samples, seed 20261115.
- Promising for a new independent confirmation only if the raw hybrid gain's 95% interval is
  above zero and gated negative injection increases by at most five percentage points.
  Do not select a different context length or recipe from this run.

## Reproduction

`rtk proxy python bench/experiments/memory_context.py collect --output bench/work/memory-context-dev-v1.jsonl --workers 4`

`rtk proxy python bench/experiments/memory_context.py analyse bench/work/memory-context-dev-v1.jsonl`

The collector records hashes for its code, reused helper, protocol, binary, corpus and model files.
It saves one complete paired record per database, refuses changed inputs on resume, and creates
only isolated temporary databases. Parallel collection is not an idle-machine latency benchmark.

Limitations inherited from the baseline: heuristic extraction rather than agent-written memories;
source-session membership is a relevance proxy, and absent answer-session IDs do not prove semantic
irrelevance. A future confirmation needs source-grounded answer judgments and representative French
and English agent-written memories. This run does not change the hook or the memory schema.
