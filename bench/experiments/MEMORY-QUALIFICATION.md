# Compact source qualification: development experiment

Frozen on 15 November 2026, before compact-qualification inference.

This tests a cheap, source-bound qualification of the existing memory statements, rather than a
tag filtering system or an LLM rewrite. The original statement is kept intact. The code sees only
its source conversation when qualifying it, never the evaluation query, gold or retrieval output.

## Fixed recipe

- Reuse exactly the 244 development databases from MEMORY-CONTEXT.md and their deterministic
  negative queries. Previously examined held-out data remains excluded.
- A preference uses its preceding sentence in the same user turn, or the following sentence if
  none precedes it. A fix uses the first sentence of the most recent earlier user turn, falling
  back to a same-turn neighbour if there is no earlier user context.
- Prepend one `Subject: ...` line containing a source fragment. The total extra text including
  the label and newline is at most 80 characters. Cut at a word boundary where possible. Do not
  add keywords, infer stack/platform, write new claims or concatenate several context paragraphs.
  A missing source qualifier leaves the statement unchanged.
- This simple first test does not claim to identify the best topic or rewrite a memory like an
  agent would. Technical entities can help only when present in the chosen source fragment.
- Original memory identities, order, kinds, scopes and sessions are preserved. Same binary,
  embedding models, lexical engine, fusion, queries and top-3 result limit as the previous run.

## Controls and criteria

- Baseline and full-context controls come from the immutable previous JSONL and manifest. Verify
  their binary/model/data/helper identities against current inputs; reject changed inputs.
- Report raw lexical and hybrid any@3, the previous fixed-cutoff diagnostic, cross-database
  negatives and true dataset abstentions separately. Do not fit a new cutoff.
- A useful development candidate must retain at least 75% of the prior full-context hybrid gain,
  have a positive paired-bootstrap lower bound versus baseline, keep stored text at most 1.75
  times baseline, and increase neither true-abstention injection count nor aggregate negative
  injection by more than five percentage points. For true abstentions require no increase.
  These are development checks, not approval to activate automatic injection.
- Main interval: paired raw-hybrid difference by question family, 10,000 bootstrap samples,
  seed 20261115. No recipe or budget change after reading the results.
- Disk control: for the first ten database IDs in the fixed ordering, rebuild baseline, full
  context and compact qualification. Record SQLite plus WAL/SHM and derived Tantivy file bytes
  separately. Exclude shared model files and per-process state; also report vector payload bytes.
  This small-database sample is not a large-scale footprint or idle-machine latency benchmark.

## Run

`rtk proxy python bench/experiments/memory_qualification.py collect --output bench/work/memory-qualification-dev-v1.jsonl --workers 4`

`rtk proxy python bench/experiments/memory_qualification.py analyse bench/work/memory-qualification-dev-v1.jsonl`

The collector checkpoints complete cases, fingerprints every input, refuses changed-input resumes
and uses temporary databases only. No live memory schema, SAVE prompt or MCP installation changes.
Inherited limits: historical heuristic extraction, English benchmark conversations, source-session
membership as a proxy for answer relevance, only 13 true abstentions, and development data already
used for prior experiments. New agent-written French/English memories remain necessary for confirmation.
