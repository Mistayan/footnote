# Qwen3-Embedding-4B single-terminal-token recheck

Planned before this rerun. The earlier `LLAMACPP-MODELS.md` Qwen3-4B
measurements used a lab suffix even though llama-server adds the GGUF terminal
token. Keep those receipts and test the standard single-token input using a new
model name and cache, the same official GGUF hash, b11901 Vulkan, GPU layers 99,
same M2 hybrid, and the same Alloprof and SciFact dev queries. The corrected
runner is `qwen4_single_token.py`; rows are append-only in
`bench/sweeps/qwen4-single-token-20261116.jsonl`. Compare to the recorded pair
and to the earlier double-token recipe only as a tuning diagnostic. Both corpora
have already informed model selection; no held-out claim or release change
follows. Timings require a separate quiet-machine measurement.
