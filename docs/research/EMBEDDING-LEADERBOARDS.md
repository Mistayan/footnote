# Embedding model leaderboards: reference

Snapshot taken 14 November 2026 from the MTEB leaderboard (https://huggingface.co/spaces/mteb/leaderboard, model pages at
https://mteb-leaderboard.hf.space). Scores change as models are added; re-read the live board before choosing.

Use: a shortlist of candidates to measure on Footnote's own corpora, never a verdict on its own. Footnote adopts a model only by
its own benchmark rule (`bench/experiments/LLAMACPP-MODELS.md`).

## Which board for which corpus

| Corpus | Board | Why |
|---|---|---|
| Mostly one language | that language's board, e.g. `MTEB(fra, v1)` (retrieval column) and `RTEB(fra, beta)` | ranks models on that language only |
| Several languages | `MTEB(Multilingual, v2)`, "performance per language" tab, filtered to the client's languages | a high multilingual mean can hide a weak language |
| A domain | `RTEB(Law)`, `RTEB(Health)`, `RTEB(fin)`, `RTEB(Code)` | domain wording differs from web text |

## How to read it

- **Zero-shot %:** share of the board's tasks the model was not trained on. Below 100 %, its score is partly measured on data it
  has seen. Footnote saw this on SciFact: EmbeddingGemma 2 scored 0.95 nDCG@10 on SciFact's training split.
- **RTEB** keeps part of its data private, so it is harder to train on than MTEB. Prefer it when both exist.
- **Memory** is the full-precision weight size. A GGUF file at Q8_0 is about 1.1 bytes per parameter, Q4 about 0.6:
  an 8B model needs about 8.5 GB at Q8_0, so it fits a 16 GB GPU.
- **Speed is the real cost of large models.** Encoding time grows with parameters. Footnote measured Qwen3-Embedding-4B at
  1,451 s for SciFact dev on an RX 6800 (Vulkan), against 241 s for the shipped pair on the CPU. A large model pays off for a
  corpus built once and queried for months, where quality matters more than ingestion time, as it often does for a company;
  less for a corpus that changes daily.

## French, 14 November 2026 (open-weight models)

`RTEB(fra, beta)`, mean over tasks (top 5 overall are closed API models: voyage-4-large 69.20, Cohere embed v5 pro 65.51):

| Rank | Model | Parameters | Score | Note |
|---|---|---|---|---|
| 5 | nvidia/Nemotron-3-Embed-8B | 8.0B | 64.79 | licence openmdw-1.1 |
| 6 | Octen/Octen-Embedding-4B | 4.0B | 64.62 | Apache 2.0; fine-tuned Qwen3-Embedding-4B (53.07) |
| 9 | nlpai-lab/KURE-v3 | 1.1B | 62.05 | built for Korean |
| 10 | nvidia/NV-Embed-v2 | 7.8B | 61.46 | non-commercial |
| 16 | Qwen/Qwen3-Embedding-8B | 7.6B | 59.51 | Apache 2.0 |
| 24 | nvidia/Nemotron-3-Embed-1B | 1.1B | 56.78 | |
| 28 | google/embeddinggemma-300m | 308M | 55.03 | |
| 37 | Qwen/Qwen3-Embedding-4B | 4.0B | 53.07 | |
| 38 | Snowflake/snowflake-arctic-embed-l-v2.0 | 568M | 53.02 | |

`MTEB(fra, v1)`, retrieval column:

| Rank | Model | Parameters | Zero-shot | Retrieval |
|---|---|---|---|---|
| 1 | codefuse-ai/F2LLM-v2-14B | 14.0B | 80 % | 72.49 |
| 5 | Qwen/Qwen3-Embedding-8B | 7.6B | 100 % | 71.81 |
| 2 | codefuse-ai/F2LLM-v2-8B | 7.6B | 80 % | 71.39 |
| 3 | codefuse-ai/F2LLM-v2-4B | 4.0B | 80 % | 69.09 |
| 7 | Qwen/Qwen3-Embedding-4B | 4.0B | 100 % | 68.49 |
| 9 | codefuse-ai/F2LLM-v2-1.7B | 1.7B | 80 % | 64.24 |
| 13 | codefuse-ai/F2LLM-v2-0.6B | 596M | 80 % | 60.04 |
| 11 | microsoft/harrier-oss-v1-0.6b | 596M | 96 % | 59.40 |
| 19 | Qwen/Qwen3-Embedding-0.6B | 596M | 100 % | 58.50 |
| 21 | microsoft/harrier-oss-v1-270m | 268M | 96 % | 56.36 |
| 39 | hotchpotch/bekko-embedding-v1-a25m | 123M | 96 % | 53.56 |

Also high but too large for a 16 GB GPU or too slow to be practical here: BAAI/bge-multilingual-gemma2 (9.2B, 34 GB full precision,
about 10 GB at Q8_0), nvidia/llama-embed-nemotron-8b (28 GB full precision), microsoft/harrier-oss-v1-27b (top of several boards;
about 16 GB even at 4-bit).

## How the boards compared with Footnote's own runs so far

Qwen3-Embedding-0.6B ranks below the 4B on the boards (58.50 against 68.49 on MTEB fra retrieval), and Footnote measured it at
+0.069 nDCG@10 over the shipped pair on Alloprof dev. On SciFact dev the 4B gained +0.028, no more than Jina v5 nano on the CPU.
Board gaps between sizes do not carry over one to one to a given corpus; that is why every candidate is measured here.
