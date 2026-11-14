# Head-to-head retrieval results

Complete receipts: 26/27. Missing: 1. Receipt window starts at 20261113T070000Z.

Same documents, queries and scoring; each product keeps its own models, chunking and ranking. This is a configured retrieval comparison, not an isolated database test. mem0 LLM extraction and Cognee graph retrieval are excluded.

| Dataset | Engine | nDCG@10 | R@10 | p50 ms | p95 ms | Build s | Store MiB | Index within store MiB | Models/cache MiB | Determinism queries |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| syntec | shipped-ensemble-mcp | 0.795 | 0.950 | 12.85 | 15.82 | 12.5 | 0.75 | 0.10 | 189.96 | 100 |
| syntec | mem0 | 0.727 | 0.870 | 7.84 | 14.97 | 3.3 | 0.94 | 0.77 | 191.58 | 100 |
| syntec | mem0-multilingual | 0.745 | 0.920 | 6.89 | 13.92 | 5.8 | 0.94 | 0.77 | 912.95 | 100 |
| syntec | cognee | 0.553 | 0.790 | 147.98 | 274.57 | 14.3 | 9.27 | 2.47 | 912.95 | 100 |
| syntec | cognee-lexical | 0.700 | 0.850 | 74.23 | 85.83 | 18.2 | 9.10 | 2.47 | 912.95 | 100 |
| syntec | cognee-multilingual | 0.682 | 0.900 | 218.14 | 371.00 | 21.9 | 10.90 | 2.75 | 912.95 | 100 |
| nfcorpus | shipped-ensemble-mcp | 0.368 | 0.183 | 15.73 | 17.92 | 475.5 | 28.60 | 2.37 | 189.96 | 200 |
| nfcorpus | mem0 | 0.357 | 0.168 | 80.93 | 109.72 | 177.6 | 40.57 | 32.53 | 912.95 | 200 |
| nfcorpus | mem0-multilingual | 0.296 | 0.134 | 90.86 | 112.43 | 104.3 | 40.57 | 32.54 | 912.95 | 200 |
| nfcorpus | cognee | 0.338 | 0.163 | 480.20 | 508.99 | 1938.8 | 1724.50 | 1645.43 | 912.95 | 200 |
| nfcorpus | cognee-lexical | 0.311 | 0.152 | 369.91 | 830.30 | 1967.0 | 1722.45 | 1645.43 | 912.95 | unchecked/failed |
| nfcorpus | cognee-multilingual | 0.251 | 0.114 | 488.99 | 523.55 | 2214.1 | 1828.81 | 1664.11 | 912.95 | 200 |
| scifact | shipped-ensemble-mcp | 0.747 | 0.887 | 20.66 | 24.00 | 676.5 | 38.58 | 3.13 | 189.96 | 200 |
| scifact | mem0 | 0.729 | 0.845 | 132.10 | 163.84 | 282.3 | 56.32 | 45.52 | 912.95 | 200 |
| scifact | mem0-multilingual | 0.555 | 0.727 | 128.36 | 160.96 | 161.5 | 56.31 | 45.52 | 912.95 | 200 |
| scifact | cognee | 0.719 | 0.845 | 525.39 | 553.09 | 3387.2 | 3421.42 | 3312.28 | 912.95 | 200 |
| scifact | cognee-lexical | 0.664 | 0.777 | 476.68 | 961.41 | 3429.0 | 3420.97 | 3312.28 | 912.95 | 200 |
| scifact | cognee-multilingual | 0.573 | 0.700 | 539.12 | 567.47 | 3860.7 | 3559.33 | 3338.90 | 912.95 | 200 |
| alloprof | shipped-ensemble-mcp | 0.478 | 0.660 | 22.39 | 38.59 | 636.9 | 43.16 | 3.47 | 189.96 | 200 |
| alloprof | mem0 | 0.360 | 0.524 | 98.67 | 128.55 | 209.3 | 47.23 | 36.34 | 912.95 | 200 |
| alloprof | mem0-multilingual | 0.354 | 0.530 | 99.74 | 128.78 | 86.9 | 47.21 | 36.31 | 912.95 | 200 |
| alloprof | cognee | 0.289 | 0.430 | 446.07 | 473.54 | 1618.0 | 968.43 | 840.77 | 912.95 | 200 |
| alloprof | cognee-lexical | 0.305 | 0.453 | 652.55 | 1128.30 | 1607.5 | 964.02 | 840.77 | 912.95 | 200 |
| alloprof | cognee-multilingual | 0.297 | 0.468 | 473.49 | 514.59 | 1841.2 | 1170.58 | 900.92 | 912.95 | 200 |
| mix-fr-en | shipped-ensemble-mcp | 0.489 | 0.624 | 27.86 | 44.34 | 1756.5 | 110.40 | 8.63 | 189.96 | 200 |
| mix-fr-en | mem0-multilingual | 0.343 | 0.480 | 287.27 | 354.38 | 335.6 | 145.07 | 115.21 | 912.95 | 200 |

Store includes the backend index; do not add it twice. Model/cache files are separate, may contain shared downloads, and exclude the Python environment and executable. Unknown sizes are n/a. Latency includes Footnote MCP transport; competitors use in-process calls. Builds are measured as recorded, without a cold filesystem-cache guarantee.

Missing receipts, still pending or failed:

- mix-fr-en/cognee-multilingual

Receipt provenance:

- [20261113T070259Z-syntec-shipped-ensemble-mcp.json](../receipts/20261113T070259Z-syntec-shipped-ensemble-mcp.json), 100 scored queries; latency: one resident `mcp` session (models loaded once, helpers resident): JSON-RPC over stdio, per-query wall time.
- [20261113T070305Z-syntec-mem0.json](../receipts/20261113T070305Z-syntec-mem0.json), 100 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T070313Z-syntec-mem0-multilingual.json](../receipts/20261113T070313Z-syntec-mem0-multilingual.json), 100 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T070403Z-syntec-cognee.json](../receipts/20261113T070403Z-syntec-cognee.json), 100 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T070447Z-syntec-cognee-lexical.json](../receipts/20261113T070447Z-syntec-cognee-lexical.json), 100 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T070558Z-syntec-cognee-multilingual.json](../receipts/20261113T070558Z-syntec-cognee-multilingual.json), 100 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T071411Z-nfcorpus-shipped-ensemble-mcp.json](../receipts/20261113T071411Z-nfcorpus-shipped-ensemble-mcp.json), 323 scored queries; latency: one resident `mcp` session (models loaded once, helpers resident): JSON-RPC over stdio, per-query wall time.
- [20261113T071753Z-nfcorpus-mem0.json](../receipts/20261113T071753Z-nfcorpus-mem0.json), 323 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T072026Z-nfcorpus-mem0-multilingual.json](../receipts/20261113T072026Z-nfcorpus-mem0-multilingual.json), 323 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T075702Z-nfcorpus-cognee.json](../receipts/20261113T075702Z-nfcorpus-cognee.json), 323 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T083346Z-nfcorpus-cognee-lexical.json](../receipts/20261113T083346Z-nfcorpus-cognee-lexical.json), 323 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T091511Z-nfcorpus-cognee-multilingual.json](../receipts/20261113T091511Z-nfcorpus-cognee-multilingual.json), 323 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T092648Z-scifact-shipped-ensemble-mcp.json](../receipts/20261113T092648Z-scifact-shipped-ensemble-mcp.json), 300 scored queries; latency: one resident `mcp` session (models loaded once, helpers resident): JSON-RPC over stdio, per-query wall time.
- [20261113T093238Z-scifact-mem0.json](../receipts/20261113T093238Z-scifact-mem0.json), 300 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T093624Z-scifact-mem0-multilingual.json](../receipts/20261113T093624Z-scifact-mem0-multilingual.json), 300 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T103721Z-scifact-cognee.json](../receipts/20261113T103721Z-scifact-cognee.json), 300 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T113943Z-scifact-cognee-lexical.json](../receipts/20261113T113943Z-scifact-cognee-lexical.json), 300 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T124851Z-scifact-cognee-multilingual.json](../receipts/20261113T124851Z-scifact-cognee-multilingual.json), 300 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T130039Z-alloprof-shipped-ensemble-mcp.json](../receipts/20261113T130039Z-alloprof-shipped-ensemble-mcp.json), 2316 scored queries; latency: one resident `mcp` session (models loaded once, helpers resident): JSON-RPC over stdio, per-query wall time.
- [20261113T130823Z-alloprof-mem0.json](../receipts/20261113T130823Z-alloprof-mem0.json), 2316 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T131406Z-alloprof-mem0-multilingual.json](../receipts/20261113T131406Z-alloprof-mem0-multilingual.json), 2316 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
- [20261113T135959Z-alloprof-cognee.json](../receipts/20261113T135959Z-alloprof-cognee.json), 2316 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T145930Z-alloprof-cognee-lexical.json](../receipts/20261113T145930Z-alloprof-cognee-lexical.json), 2316 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T155038Z-alloprof-cognee-multilingual.json](../receipts/20261113T155038Z-alloprof-cognee-multilingual.json), 2316 scored queries; latency: in-process Python call to cognee.search (async, one event loop for the run; embedder loaded once; no LLM).
- [20261113T162140Z-mix-fr-en-shipped-ensemble-mcp.json](../receipts/20261113T162140Z-mix-fr-en-shipped-ensemble-mcp.json), 3039 scored queries; latency: one resident `mcp` session (models loaded once, helpers resident): JSON-RPC over stdio, per-query wall time.
- [20261113T164258Z-mix-fr-en-mem0-multilingual.json](../receipts/20261113T164258Z-mix-fr-en-mem0-multilingual.json), 3039 scored queries; latency: in-process Python call to mem0 Memory.search (embedder loaded once, Qdrant local mode, no LLM).
