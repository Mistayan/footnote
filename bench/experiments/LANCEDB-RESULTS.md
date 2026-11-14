# Matched backend results

Complete receipts: 20/20. Missing: 0. Receipt window starts at 20261113T070000Z.

Identical exported chunks and a8m vectors; exact retrieval with precomputed query embeddings. Encoding is excluded from every latency. These are component controls, not the production two-model pipeline.

| Dataset | Engine | nDCG@10 | R@10 | p50 ms | p95 ms | Build s | Store MiB | Tantivy within store MiB | Models/cache MiB | Determinism queries |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| syntec | matched-sqlite-tantivy | 0.821 | 0.960 | 0.41 | 0.50 | 0.1 | 0.45 | 0.04 | n/a | 100 |
| syntec | matched-lance-rrf | 0.808 | 0.960 | 6.04 | 7.62 | 1.5 | 0.31 | 0.00 | n/a | 100 |
| syntec | matched-lance-cc | 0.828 | 0.970 | 6.12 | 7.70 | 0.5 | 0.31 | 0.00 | n/a | 100 |
| syntec | matched-lance-tantivy | 0.821 | 0.960 | 2.37 | 2.89 | 0.5 | 0.26 | 0.04 | n/a | 100 |
| nfcorpus | matched-sqlite-tantivy | 0.345 | 0.164 | 1.09 | 1.29 | 0.3 | 18.62 | 0.94 | n/a | 200 |
| nfcorpus | matched-lance-rrf | 0.346 | 0.167 | 9.96 | 11.44 | 0.7 | 11.85 | 0.00 | n/a | 200 |
| nfcorpus | matched-lance-cc | 0.345 | 0.164 | 9.60 | 10.82 | 0.8 | 11.89 | 0.00 | n/a | 200 |
| nfcorpus | matched-lance-tantivy | 0.345 | 0.164 | 3.06 | 3.82 | 0.8 | 11.23 | 0.94 | n/a | 200 |
| scifact | matched-sqlite-tantivy | 0.732 | 0.858 | 1.34 | 1.57 | 0.5 | 26.29 | 1.27 | n/a | 200 |
| scifact | matched-lance-rrf | 0.723 | 0.852 | 13.51 | 15.36 | 0.8 | 16.50 | 0.00 | n/a | 200 |
| scifact | matched-lance-cc | 0.732 | 0.858 | 12.85 | 13.83 | 0.8 | 16.44 | 0.00 | n/a | 200 |
| scifact | matched-lance-tantivy | 0.732 | 0.858 | 3.63 | 4.34 | 0.9 | 15.62 | 1.27 | n/a | 200 |
| alloprof | matched-sqlite-tantivy | 0.462 | 0.638 | 1.39 | 1.64 | 0.5 | 23.81 | 1.41 | n/a | 200 |
| alloprof | matched-lance-rrf | 0.451 | 0.641 | 12.64 | 14.92 | 0.9 | 16.34 | 0.00 | n/a | 200 |
| alloprof | matched-lance-cc | 0.462 | 0.638 | 12.98 | 15.22 | 0.9 | 16.42 | 0.00 | n/a | 200 |
| alloprof | matched-lance-tantivy | 0.462 | 0.638 | 3.57 | 4.33 | 1.0 | 15.27 | 1.41 | n/a | 200 |
| mix-fr-en | matched-sqlite-tantivy | 0.476 | 0.609 | 2.29 | 2.66 | 1.3 | 69.18 | 3.65 | n/a | 200 |
| mix-fr-en | matched-lance-rrf | 0.463 | 0.604 | 21.19 | 23.95 | 1.2 | 45.08 | 0.00 | n/a | 200 |
| mix-fr-en | matched-lance-cc | 0.476 | 0.608 | 21.30 | 23.84 | 1.2 | 45.14 | 0.00 | n/a | 200 |
| mix-fr-en | matched-lance-tantivy | 0.476 | 0.609 | 4.97 | 5.81 | 1.9 | 42.97 | 3.65 | n/a | 200 |

Store includes the backend index; do not add it twice. Model/cache files are separate, may contain shared downloads, and exclude the Python environment and executable. Unknown sizes are n/a. Native FTS is included in LanceDB store bytes. Common frozen input artifacts are excluded. Builds are measured as recorded, without a cold filesystem-cache guarantee.

Receipt provenance:

- [20261113T232749Z-syntec-matched-sqlite-tantivy.json](../receipts/20261113T232749Z-syntec-matched-sqlite-tantivy.json), 100 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232752Z-syntec-matched-lance-rrf.json](../receipts/20261113T232752Z-syntec-matched-lance-rrf.json), 100 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232754Z-syntec-matched-lance-cc.json](../receipts/20261113T232754Z-syntec-matched-lance-cc.json), 100 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232755Z-syntec-matched-lance-tantivy.json](../receipts/20261113T232755Z-syntec-matched-lance-tantivy.json), 100 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232758Z-nfcorpus-matched-sqlite-tantivy.json](../receipts/20261113T232758Z-nfcorpus-matched-sqlite-tantivy.json), 323 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232804Z-nfcorpus-matched-lance-rrf.json](../receipts/20261113T232804Z-nfcorpus-matched-lance-rrf.json), 323 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232811Z-nfcorpus-matched-lance-cc.json](../receipts/20261113T232811Z-nfcorpus-matched-lance-cc.json), 323 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232814Z-nfcorpus-matched-lance-tantivy.json](../receipts/20261113T232814Z-nfcorpus-matched-lance-tantivy.json), 323 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232817Z-scifact-matched-sqlite-tantivy.json](../receipts/20261113T232817Z-scifact-matched-sqlite-tantivy.json), 300 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232825Z-scifact-matched-lance-rrf.json](../receipts/20261113T232825Z-scifact-matched-lance-rrf.json), 300 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232833Z-scifact-matched-lance-cc.json](../receipts/20261113T232833Z-scifact-matched-lance-cc.json), 300 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232836Z-scifact-matched-lance-tantivy.json](../receipts/20261113T232836Z-scifact-matched-lance-tantivy.json), 300 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232845Z-alloprof-matched-sqlite-tantivy.json](../receipts/20261113T232845Z-alloprof-matched-sqlite-tantivy.json), 2316 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232919Z-alloprof-matched-lance-rrf.json](../receipts/20261113T232919Z-alloprof-matched-lance-rrf.json), 2316 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T232953Z-alloprof-matched-lance-cc.json](../receipts/20261113T232953Z-alloprof-matched-lance-cc.json), 2316 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T233004Z-alloprof-matched-lance-tantivy.json](../receipts/20261113T233004Z-alloprof-matched-lance-tantivy.json), 2316 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T233019Z-mix-fr-en-matched-sqlite-tantivy.json](../receipts/20261113T233019Z-mix-fr-en-matched-sqlite-tantivy.json), 3039 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T233131Z-mix-fr-en-matched-lance-rrf.json](../receipts/20261113T233131Z-mix-fr-en-matched-lance-rrf.json), 3039 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T233242Z-mix-fr-en-matched-lance-cc.json](../receipts/20261113T233242Z-mix-fr-en-matched-lance-cc.json), 3039 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
- [20261113T233301Z-mix-fr-en-matched-lance-tantivy.json](../receipts/20261113T233301Z-mix-fr-en-matched-lance-tantivy.json), 3039 scored queries; latency: resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch.
