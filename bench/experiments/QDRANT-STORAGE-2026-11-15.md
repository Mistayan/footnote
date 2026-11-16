# Qdrant server: preparation for a matched storage comparison

Planned before any new comparison. Use the official Windows x64 Qdrant 1.20.1
release as an isolated localhost process with its data under `bench/work/`.
Official asset SHA-256: `cdbcf8831a19b40785af300d10b762501fb3ff796f1a3c8d7fa142c67f76ad62`.
No system service or Docker installation is required. Source: [official release](https://github.com/qdrant/qdrant/releases/tag/v1.20.1).

Use the same frozen chunks, vectors, query vectors, IDs and judged queries as
the matched SQLite/Tantivy and LanceDB experiment where possible. Test exact
dense search before any approximate index and check identical-neighbor overlap,
IDs and filter semantics on a tiny fixture first. Document the Qdrant version,
its configuration, files, process and measurements. Preserve earlier receipts.
The previous Python client's local brute-force mode is not the Qdrant server or
Qdrant Edge. Do not present their performance as interchangeable. Query latency,
throughput, build time and storage must be measured on an otherwise quiet machine
and with equivalent contents; hybrid differences and single-model results do not
by themselves justify a migration. Multi-user operation is a separate test.

Preparation completed: the official archive was SHA-256 verified and extracted
under the isolated work directory. `qdrant_server_smoke.py` started the server
on localhost, inserted three vectors, checked exact neighbors plus a payload
filter (`[1, 3]`), and stopped its process. This is a tiny functional fixture,
not a storage, quality or performance comparison.

`qdrant_exact_check.py` additionally loaded the existing hash-verified Syntec
matched inputs, with 109 chunks and 100 frozen query vectors. Exact dot-product
top-10 IDs matched the NumPy reference for all 100 queries (mean and minimum
overlap 1.0). The receipt is under `bench/work/storage/qdrant-1.20.1/`.
This establishes agreement for this small dense fixture only; it excludes the
hybrid ranking and makes no timing, scaling or production-readiness claim.

Expanded check, 16 November: the first 100 frozen queries per corpus were used
against all frozen chunks, exact dot product, top 10. SciFact (6,495 chunks),
Alloprof (5,850) and mix-fr-en (17,053) each had 100% ID overlap in this run.
NFCorpus (4,599) had mean overlap 99.9%, minimum 90%. A separate NFCorpus rerun
had three 9/10 overlaps: in each case the differing IDs have byte-identical
vectors but belong to different documents. Ties at the cutoff can therefore
change selected IDs, and the two Qdrant runs selected different tied members.
Exact scores alone do not ensure repeatable document lists; a matched hybrid
test needs a declared tie-handling policy and enough candidates to handle ties.
Per-run input hashes, server logs, results and runner snapshots are retained in
`bench/work/storage/qdrant-1.20.1/`. No latency was measured under idle conditions.

Next diagnostic, fixed before execution: first 100 query IDs from each frozen
matched input, the same separate Tantivy index and CC fusion as the existing
SQLite control, but fetch exact dense candidates from Qdrant. Compare rankings
twice and calculate existing judged metrics. Keep differences at the candidate
pool cutoff visible; do not change the pool after seeing results. This is a
component diagnostic, not a full held-out study or migration benchmark.

Result: on 100 frozen queries for each of Syntec, NFCorpus, SciFact, Alloprof
and mix-fr-en, all 500 top-20 document rankings matched the SQLite/resident
NumPy control; the two Qdrant passes also agreed. The nDCG@10 and other judged
metrics were therefore identical on these subsets. The standalone top-10 tie
finding above still applies: these particular hybrid results do not prove ties
are generally stable. Qdrant provided only the 100 exact dense candidates;
the existing SQLite store still supplied document IDs, while Tantivy and CC
fusion were shared. Thus this is **not** a full Qdrant-backed storage, write,
scaling or latency comparison. Results, rankings and runner snapshots are in
the five `*-hybrid-check` directories under `bench/work/storage/qdrant-1.20.1/`.
