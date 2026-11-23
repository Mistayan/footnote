# Daemon resident memory by component, before and after (#517)

Measured 23 November 2026: the daemon's idle working set falls from 222 MB to 24 MB with the configured jina-v5-nano, and from 223 MB to 45 MB with the default pair; recall rankings are unchanged.

Machine: Intel Core Ultra 7 270K Plus, 24 logical CPUs, Windows 11. **Not idle**: other agents were building and testing at
the same time (24 to 99 % CPU before a run, logged per run in [daemon-ram/results.json](daemon-ram/results.json)). Memory
figures repeat within 1 MB from run to run. Latency figures are noisy and are read only as "not worse", never as a speed claim.

Builds, all `cargo build --release --locked --features llama` (the release feature set):

| Build | Commit | What it adds |
|---|---|---|
| base | `e0a13be` (origin/main) | before this work |
| b2 | `ae5f8e0` | spans at run time, memory database searched with its configured models, GGUF model freed on unload |
| b3 | `df18b20` | b2 + each ONNX session made on first use |

## Workload

[daemon_ram.py](daemon_ram.py), the same for every build. Isolated state folder (never the user's): a copy of the real memory
database (514 memories, vectors from bekko-a8m, gte-small and jina-v5-nano), copies of the three installed model folders,
`memory.json` naming the configured model(s), metrics on. One daemon (`serve --mcp --daemon --idle-seconds 20`) and one agent
session (`footnote mcp`) held open throughout, as an agent keeps it. The daemon's working set and private bytes are read after
each phase:

1. **started**: daemon up, one keyword probe.
2. **lexical**: 20 keyword recalls through the daemon.
3. **hook**: 20 hook recalls (`memory-recall --resident --model <configured>`, what the prompt hook sends).
4. **agents**: 20 + 40 `footnote_recall` calls from the agent session (the agents' tool).
5. **idle**: no request for `idle_seconds`, so the models are unloaded.
6. **reload**: the 20 hook recalls again. The model loads again, and the rankings must equal phase 3.

```
python -I bench/experiments/daemon_ram.py <footnote.exe> <label> <memory.db copy> %LOCALAPPDATA%/footnote/models <out> --configured jina-v5-nano
python -I bench/experiments/daemon_ram.py <footnote.exe> <label> <memory.db copy> %LOCALAPPDATA%/footnote/models <out> --configured bekko-a8m,gte-small
```

Two configurations: the maintainer's (**jina**, jina-v5-nano only, a GGUF model through llama.cpp) and the shipped default
(**pair**, bekko-a8m + gte-small, ONNX). Each build ran twice per configuration, base and b3 alternated (pair four times).

## Result: working set per phase, MB (working set / private)

| Phase | jina, base | jina, b3 | pair, base | pair, b3 |
|---|---:|---:|---:|---:|
| started | 16.6 / 5.0 | 16.6 / 5.0 | 16.7 / 5.2 | 16.8 / 5.3 |
| lexical | 17.1 / 5.3 | 17.2 / 5.3 | 17.2 / 5.5 | 17.2 / 5.4 |
| hook | 200.6 / 147.4 | 201.1 / 147.7 | 449.6 / 432.3 | 287.6 / 270.2 |
| agents | **631.3 / 572.9** | **201.3 / 147.8** | 624.8 / 566.1 | 288.1 / 270.3 |
| idle (after unload) | **221.9 / 91.6** | **23.9 / 10.6** | **221.1 / 85.6** | **44.3 / 24.8** |
| reload | 400.1 / 232.2 | 202.9 / 149.8 | 633.1 / 504.0 | 297.4 / 285.4 |

Run 1 shown; run 2 is within 1 MB on every row except pair idle (base 224.6 / 99.7, b3 44.8 / 27.4). All runs are in
[daemon-ram/results.json](daemon-ram/results.json).

What each row shows:

- **The agents' tool loaded models nobody configured.** With jina-v5-nano configured, `footnote_recall` on the memory database
  used every installed model that once gave it vectors. That added bekko-a8m and gte-small, +430 MB. Fixed: a memory database
  is searched with the models `memory.json` names, as the hook does (`app::search_models`).
- **The idle unload kept the GGUF weights.** The llama.cpp model was leaked on purpose (`Box::leak`) so its context could borrow
  it, so `semantic::unload()` freed only the context. Each unload and reload leaked another copy: base reload is 400 MB, and
  the 508 MB seen on 22 Nov after a day of running fits that. Fixed: `llama::Gguf` owns the model and frees it after the
  context.
- **ONNX models held two sessions each**, one for queries and one for passages, each with its own copy of the weights. A daemon
  that only answers recalls never uses the passage session. Fixed: each session is made on first use from `model.onnx`,
  hashed again. Pair: 450 to 288 MB while loaded.
- **What stays after unload with the pair** (44 MB vs 24 MB): the ONNX Runtime environment and its thread pools, which live
  for the process.

## Breakdown by component (one `footnote embed` process per model, b2 + memtrace patch)

[daemon_ram_components.py](daemon_ram_components.py) with a diagnostic build
([daemon-ram/memtrace.patch](daemon-ram/memtrace.patch), applied on `ae5f8e0`): the encoder pauses at each load step and the
process's memory is read; llama.cpp's own log gives its buffer sizes. Private MB added by each step:

| Component | bekko-a8m (ONNX) | gte-small (ONNX) | jina-v5-nano (GGUF) |
|---|---:|---:|---:|
| Model files read and hashed (dropped after load) | 157 | 33 | n/a (hashed, then mapped by llama.cpp) |
| Tokenizer | 66 | 6 | 61 (model load, vocabulary included; weights mapped from the 215 MB file) |
| Query session (weights + graph) | 141 | 57 | n/a |
| Passage session (second copy of the weights) | 128 | 38 | n/a |
| Context compute buffer | n/a | n/a | 53 (llama.cpp log), +75 private at context creation |
| Arena growth over 20 queries or passages | 4 to 5 | 4 to 5 | 6 |
| Process private after load and 20 texts (empty process: 4) | 344 | 110 | 145 |

- **Model weights** dominate: ONNX copies them into each session; llama.cpp maps the GGUF file, so they show in the working set
  but not as private bytes.
- **ONNX Runtime arena:** 4 to 5 MB for these workloads. The arena is not where the memory goes, so arena and thread settings
  were left unchanged.
- **Search index and SQLite caches:** +0.5 MB (phase lexical), on 514 memories.
- **llama.cpp context:** sized for 1,024 tokens (`CTX`) while jina-v5-nano's `max_length` is 512. Sizing it to the model would
  save about 26 MB while loaded. Not done: it would also lower the largest input accepted today (a re-tokenized cut text can
  exceed `max_length` by a few tokens). Left as a finding.

## Idle target

**Set from this report: at most 50 MB working set once the daemon has unloaded its models after `idle_seconds`, for every model
configuration.** It is the floor that a process with ONNX Runtime initialized can reach.

**Met:** jina 23.9 and 23.7 MB, pair 44.3, 44.8, 44.8 and 45.0 MB (base: 221 to 225 MB).

Set after the first measurement, not before, because the breakdown above was needed to know what a daemon without models holds.

## Recall latency and quality

**Quality: unchanged.** The hook's recall path is the one the recall benchmark measures
([MEMORY-RECALL-SWITCH.md](MEMORY-RECALL-SWITCH.md)). Its frozen questions are git-ignored and no longer on this machine, so
identity was checked instead of rerunning them:

- Vectors from base and b3 are **bit-identical**: 3 models × queries and passages × 20 texts
  ([daemon_ram_vectors.py](daemon_ram_vectors.py), `max_abs_diff` 0.0).
- Hook recall rankings (top 3 memory ids, 20 queries) are **identical** between base and b3 in all 4 runs. After unload and
  reload they are identical to before.
- The agents' `footnote_recall` rankings **change by design** in the jina configuration: it now uses the configured model
  instead of the three-model blend. In the pair configuration, base also loaded jina-v5-nano. This tool's ranking against
  labelled questions was not measured.

**Latency: not worse.** Whole process per hook call, through the warm daemon.

| Measure, ms | base | b3 |
|---|---:|---:|
| jina: hook recall p50 / p95 (2 runs × 40 calls) | 27.7 / 34.6, 29.7 / 54.1 | 26.9 / 30.3, 28.0 / 31.5 |
| jina: agents' `footnote_recall`, in session, p50 / p95 | 15.2 / 16.9, 16.2 / 18.8 | 10.1 / 11.5, 10.0 / 11.8 |
| pair: hook recall p50 / p95, 3 rounds alternated, metrics off and on (median of 6 × 40 calls) | 27.4 / 30.6 | 27.4 / 32.4 |
| pair: agents' `footnote_recall`, in session, p50 (4 runs) | 15.7 to 17.7 | 11.7 to 12.3 |

The pair rows come from [daemon_ram_latency.py](daemon_ram_latency.py) (raw output in
[daemon-ram/latency-ab.txt](daemon-ram/latency-ab.txt)). That rerun was made because b3's pair runs in the RAM workload landed on
CPU spikes (56 to 99 %, hook p50 40 to 243 ms). Alternated on the same minutes, base, b2 and b3 all give p50 27 to 31 ms, and
p95 varies 28 to 51 ms for every build alike. Spans on (`memory.metrics`) cost nothing measurable.

## Spans (#518 part)

`metrics.jsonl` again holds daemon, MCP and CLI steps when `memory.metrics` is on. The workload above wrote `cli.mcp`,
`cli.memory-recall`, `daemon.initialize`, `daemon.tools/call`, `mcp.footnote_recall`, `mcp.footnote_memory_recall`,
`encoder.load`, `encoder.query`, `model.identity`, `search.keywords`, `search.query_vector` and `search.vectors`.
`footnote status` lists steps that failed at least 3 times in the last 24 hours.

## Limits

- One machine, not idle; one memory database (514 memories).
- Windows only (process memory counters).
- Recall quality checked as identity on the hook path, not rerun on labelled questions.
- The three changes were chosen from the memory breakdown, not from span totals by time. Picking the three hottest paths by
  time needs spans from real use, which this work turns back on.
