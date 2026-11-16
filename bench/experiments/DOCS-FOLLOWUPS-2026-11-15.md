# Documentation retrieval follow-ups

Prepared 15 November 2026, after the `DOCS-VS-GROUNDED.md` and grouped-result
analyses, before the follow-up runs. The 59 questions and Grounded Docs answers
were already observed: these are diagnostic experiments, not independent
held-out confirmation or a replacement for the original pre-registered verdict.

## Page diversity on identical pages

Use the unchanged Grounded Docs run1 page exports, dataset, five Footnote
databases, and the original Grounded Docs hybrid answers. Query Footnote with
the installed default pair using `--limit 5 --per-source 1`, separately in
hybrid and lexical mode. Each exported file corresponds to one stored page;
the cap is per file path, not a general guarantee of URL-level deduplication.
Compare to the uncapped original top five and to the earlier exploratory top-20
client-side grouping. Record the executable, source files, dataset, model
manifests and database hashes; save all raw ranked URLs and per-query metrics.
Run every query twice and compare ranked results, without claiming reproducible
scores if either pass fails or differs. Eight independent CLI processes are a
quality-throughput setting, not a multi-user load test.

Use the same paired bootstrap as the original: 10,000 query resamples, seed
20261115, nDCG@5 difference and 95% interval. Also report MRR, Recall@5,
Hit@3 and results per library. The original comparator was built on an earlier
crawl and any unavailable or non-reproducible input is a blocker, not a zero.

## Same-model diagnostic

Compare Footnote and Grounded Docs on the identical exported text with the same
EmbeddingGemma 300M GGUF file. Record exact model hash, tokenization, prompt,
pooling, normalization, chunking, runtime, and query/document truncation on
both sides. Equal weights alone do not isolate the ranking algorithm: if any
recipe detail differs or cannot be established, report it as a same-weights
comparison with the remaining confounders. Use separate databases and keep the
original artifacts. Do not use these previously observed queries to claim a
fresh, independent test.

## Concurrency diagnostic

Use persistent, already-warmed agent-facing servers and explicit independent
clients. Test 1, 5, 10, 20 and 40 simultaneous requests, identical query mix,
fixed warm-up and duration at each level. Separate the measured scenario of
multiple clients sharing one server from multiple servers sharing a database.
Report successful and failed requests, throughput, p50/p95/p99 end-to-end
latency, server process RSS and CPU, and model-memory duplication; record the
environment and whether the computer is otherwise idle. A client count is not
a production-user count, and extrapolation to 1,000 users needs further data.
Use a private benchmark database and owned processes; never stop existing MCP
servers. If idle or a chosen topology cannot be verified, label the run as
diagnostic and do not claim idle-machine latency.

## Crawl protocol limitations discovered during takeover

The failed first minimal run is preserved in `bench/work/crawl/minimal-coverage.out`.
The repaired minimal run starts in a fresh folder. The current runner does not
cache raw HTTP responses for cross-variant replay, despite that requirement in
`DOCS-CRAWL.md`; skipped pages also combine several causes, not just missing
JavaScript. Record coverage as a preliminary observation. A spider comparison
needs independently documented fetches, timing and limits, and cannot be called
a same-response extraction comparison. Do not silently change the earlier
protocol or the original run's verdict.
