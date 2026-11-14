# LongMemEval-S: Footnote against ICM

Run 14 November 2026, 01:54 to 03:05, quiet machine. All 500 questions (including the 30 abstention-tagged ones), user turns only, no dates, one fresh index per question, gold = `answer_session_ids`. Tools and protocol: [ICM-SUITE.md](ICM-SUITE.md). Scorer: `longmem_score.py`, which reproduces ICM's published numbers exactly from their own artifact.

| System | any@5 | all@5 | any@10 | all@10 | nDCG@10 (distinct sessions) |
|---|---:|---:|---:|---:|---:|
| **Footnote**, shipped binary (`target/release/footnote.exe`), local run | **0.978** | **0.908** | **0.992** | **0.970** | **0.939** |
| ICM 0.11.5 keyword-only (`--no-embeddings`), local run, same machine | 0.952 | 0.820 | 0.968 | 0.882 | 0.875 |
| ICM v2 hybrid, vendor-published artifact (other machine and version) | 0.974 | 0.886 | 0.986 | 0.948 | 0.926 |

Paired bootstrap, 95 % intervals, ICM minus Footnote:

| Comparison | any@5 | all@5 | any@10 | all@10 | nDCG@10 |
|---|---|---|---|---|---|
| ICM keyword, local | −0.026 [−0.042, −0.012] | −0.088 [−0.116, −0.060] | −0.024 [−0.040, −0.010] | −0.088 [−0.114, −0.062] | −0.064 [−0.080, −0.048] |
| ICM hybrid, published | −0.004 [−0.012, +0.004] | −0.022 [−0.044, 0.000] | −0.006 [−0.016, +0.002] | −0.022 [−0.040, −0.004] | −0.013 [−0.023, −0.002] |

Reading:
- Against ICM's keyword mode, run here under identical conditions, Footnote is better on every metric.
- Against ICM's published hybrid (its default, with multilingual E5-large), Footnote is better on all@10 and nDCG@10 and tied on any@5, all@5 (upper bound exactly 0) and any@10. This compares a local run with a vendor run on different hardware and software: it supports "at least on par with ICM's published result", not a controlled win. A local hybrid ICM run is still to do.
- Ingestion differs by design: Footnote splits each session into chunks and maps them back to sessions; ICM stores mostly one memory per session. Footnote's adapter requests at most 20 results, ICM's 50 raw units.

Raw outputs: `bench/work/lme500-footnote.json`, `bench/work/lme500-icm.json`, `bench/work/lme500-paired.json`, `bench/work/lme500-vs-icm-published.json`.
