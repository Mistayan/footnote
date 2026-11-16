# llama.cpp Vulkan speed grid

Frozen before grid results. Extend `LLAMACPP-RUNTIMES.md` on the same RX 6800
using Jina v5 nano Q8_0 and the already downloaded b11901 and b12421 Vulkan
servers. Compare flash attention on/off and microbatch sizes 512, 2048 and 8192;
other settings remain the earlier protocol's eight slots, context and logical
batch size 8192, last-token pooling, and GPU layers 99. Run configurations
sequentially after other benchmark jobs stop, not concurrently with model
screening or indexing. Document any other observed load; this is not a claim of
an idle system unless independently verified.

Use the same frozen local documentation passages and queries for all cells,
one warmup, 100 individually timed queries and 256 passages per cell. Repeat
each cell twice and preserve individual rows, server logs, hardware and input
hashes. Compare the first 100 document vectors against the first cell; record
minimum cosine and any errors before interpreting speed. Never overwrite an
earlier run. This is a diagnostic on one model and machine, not an automatic
product setting change; quality and compatibility need separate confirmation.

## Input-length amendment, 16 November

The first grid exposed an HTTP 500 at microbatch 512: one passage used 514
tokens, exceeding the physical batch. Its failures and partial larger-batch
rows are preserved in `bench/work/speed-grid-20261115/`; they are not mixed with
the rerun. Before the rerun, clip every passage to at most 400 UTF-8 bytes
without splitting a character, keeping the same 256 passages and 100 queries
for every cell. This gives headroom for the document prefix and special tokens.
The rerun has a new output directory, hashes and fresh measurements for all
cells. Report the failure if an input still exceeds the runtime's token limit.

## Corrected grid results

All 24 runs completed: two repeats for each of 12 runtime/flash/microbatch
combinations. Each repeat had 100 individual queries and 256 passages clipped
to 400 UTF-8 bytes. Ranges below cover the six runs per runtime/flash pair;
query p95 is per repeat, not a pooled percentile.

| Runtime | Flash | Query p95 range (ms) | Passages/s range | Minimum cosine vs first cell |
| --- | --- | ---: | ---: | ---: |
| b11901 Vulkan | off | 20.2–24.6 | 230–254 | 0.999814 |
| b11901 Vulkan | on | 19.8–24.1 | 223–241 | 0.999749 |
| b12421 Vulkan | off | 20.3–24.5 | 212–259 | 0.999737 |
| b12421 Vulkan | on | 20.3–22.6 | 195–246 | 0.999607 |

The ranges overlap and two repeats do not establish a reliable winner. Several
settings fall below the earlier 0.9999 vector-cosine requirement, so these
results do not justify enabling a new indexing configuration. CPU samples
before the run were about 4.6–10.0%; the machine was not certified idle. This
short-passage workload is different from `LLAMACPP-RUNTIMES.md` and its absolute
passage rates are not directly comparable. Inputs, all individual rows, logs,
binary hashes, host observations and runner/helper snapshots are under
`bench/work/speed-grid-20261116-v2/`; helper SHA-256
`373751bb214b45c720a00cb4379eb97c9a94e0a86a2e03b0e15c4c67ce41f02d`.
