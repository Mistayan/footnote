# A3 screening: intermediate results

The six stage-A runs are complete. Protocol: [A3-SCREEN-2026-11-15.md](A3-SCREEN-2026-11-15.md).
The append-only rows are in `bench/sweeps/a3-20261115.jsonl` and the input
hashes in `bench/work/a3v2-inputs-20261115.json`. The earlier double-terminal
attempt was stopped before it produced a row; model names and caches changed.

| Dataset, dev | Third-party Q8 candidate | nDCG@10 | Recall@10 | Shipped pair nDCG@10 |
| --- | --- | ---: | ---: | ---: |
| Alloprof, 692 queries | Harrier 0.6B | 0.54012 | 0.72688 | 0.50357 |
| Alloprof, 692 queries | F2LLM v2 1.7B | 0.59400 | 0.78179 | 0.50357 |
| Alloprof, 692 queries | Octen 4B | 0.63163 | 0.84538 | 0.50357 |
| SciFact, 809 queries | Harrier 0.6B | 0.78106 | 0.89330 | 0.76240 |
| SciFact, 809 queries | F2LLM v2 1.7B | 0.75732 | 0.88187 | 0.76240 |
| SciFact, 809 queries | Octen 4B | 0.78674 | 0.90144 | 0.76240 |

The baselines are the existing `research:llamacpp` rows with the same query
counts. This is a development-set screen, not held-out validation. Models,
tokenization and runtimes differ from the shipped pair. The elapsed time was
measured while another indexing process ran for most cells and is not an idle
performance result. Octen's SciFact run was resumed separately after interruption.
All three exceed the +0.01 screening threshold on at least one corpus; F2LLM
does not exceed it on SciFact. This is not the stage-B or held-out decision.
