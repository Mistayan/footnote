# llama.cpp runtimes on the Radeon RX 6800

15 November 2026. Backlog P3 (llama.cpp speed grid, runtime versions). Reported, not judged. Script:
`llamacpp_runtimes.py`; output `bench/work/overnight/llamacpp-runtimes.json`.

Jina v5 nano Q8_0 through `llama-server` (last-token pooling, 8 slots, 8,192 context on the GPU). 200 single queries one at a
time, then 493 passages from this repository's docs in requests of 16. The three runtimes ran back to back under the same
conditions. Release zips checked against their sha256 (Vulkan a5ca8df1..., ROCm 5883932a...).

| Runtime | Query p50 | Query p95 | Passages/s | Min cosine vs b11901 |
|---|---|---|---|---|
| b11901 Vulkan (current) | 15.8 ms | 27.9 ms | 86.5 | 1 |
| b12421 Vulkan | 12.9 ms (−18 %) | 19.4 ms (−30 %) | 82.2 (−5 %) | 0.9997 |
| b12421 ROCm/HIP | 15.7 ms | 29.2 ms | 17.4 (−80 %) | 0.9998 |

- b12421 Vulkan answers single queries faster, indexes about as fast, and gives the same vectors within 0.9997.
- ROCm brings nothing on this card and indexes five times slower: dropped.
- The product compiles its own llama.cpp (`llama-cpp-2`); these figures inform which version that crate should track, they do not
  change the product by themselves.
