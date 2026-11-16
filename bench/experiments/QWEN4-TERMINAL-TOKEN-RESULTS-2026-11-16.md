# Qwen3-4B terminal-token recheck

Protocol: [QWEN4-TERMINAL-TOKEN-2026-11-16.md](QWEN4-TERMINAL-TOKEN-2026-11-16.md).
The Alloprof dev run completed with a single terminal token: nDCG@10 **0.62092**,
recall@10 **0.82659**, 692 queries. The recorded double-token run scored 0.6180
nDCG@10 on that corpus; both numbers are development results, not independent
confirmation. SciFact dev completed at nDCG@10 **0.78681**, recall@10
**0.89866**, 809 queries; its previous double-token nDCG@10 was 0.79008. The
change in token handling therefore moved the observed scores in opposite
directions on the two reused dev sets. Neither run is a new held-out test.
Raw append-only rows and
input hashes are in `bench/sweeps/qwen4-single-token-20261116.jsonl` and
`bench/work/qwen4-single-token-inputs-20261116.json`.
