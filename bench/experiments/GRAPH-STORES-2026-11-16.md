# Graph stores: Windows preparation

Omnigraph 0.15.0 (commit `373834b4c1c4b29cf0ddd64bee9565f98c60cc26`)
was downloaded from its official Windows release and the archive SHA-256
verified as `4e605c1a1f99eeeddddcb37fe7e4653b8f575a0612c638aa5bc2b9bc039528a0`.
An isolated local graph, a linted schema and parameterized query were used to
insert three vectors. Filtering to Rust returned the expected two records in
the expected order. Source fixture: `omnigraph-fixture/`; data remain under
`bench/work/storage/omnigraph-0.15.0/`.

Omnigraph's `nearest` reports squared L2 distance. The prior matched storage
experiments use dot product, and their decoded vectors are not exactly unit
length, so their rankings cannot be assumed equivalent. A diagnostic can map
each passage vector `x` to `[x, sqrt(R² - ||x||²)]` and each query `q` to
`[q, 0]`, with fixed `R²` greater than all squared passage norms. Squared L2
then equals `R² + ||q||² - 2(x·q)` in exact arithmetic; float rounding and ties
still need checking. This adds a dimension and is a diagnostic transformation,
not a native dot-product comparison. Preserve inputs, transformed data,
queries, code, scores, ranking differences and versions; do not claim a speed
comparison from separate CLI invocations.

On Syntec's 109 frozen chunks and 100 frozen queries, the transformed 385-D
vectors produced the same ordered top-10 chunk IDs as the NumPy dot-product
control for all queries. The engine reported exhaustive search. This verifies
only that small exact dense case, not hybrid ranking or performance. Input
hashes, transformed data, per-query parameters, rankings, binary hash and source
snapshot are in `bench/work/storage/omnigraph-0.15.0/syntec-transformed-main-check/`.

The first attempt to create a review branch on a local Windows graph failed
with `Invalid table location` and `outcome_unknown`; a separate `file:///D:/`
branch-creation probe failed similarly. Listing both graphs afterwards showed
only `main`. The failed graph and runner are preserved; the test used a fresh,
disposable local graph on `main`. This is a reproduction on this machine, not
a claim that every Windows Omnigraph setup has the same issue.

Before expanding the diagnostic: use the same transformation, exact scan and
first 100 frozen query vectors on NFCorpus, SciFact, Alloprof and mix-fr-en.
Record both ordered and set overlap with NumPy; tied vectors may change an
arbitrary top-10 boundary. No engine, latency or hybrid-system conclusion follows
from this transformed, single-vector-component experiment.

Result: on all five corpora, the sets of the first ten chunks matched the NumPy
control for all 500 queries. Ordered lists matched for 498; on two NFCorpus
queries, two byte-identical vectors from different chunks were swapped. The
other 498 ordered lists matched. The mixed corpus initially exceeded Omnigraph's
8,192 keyed-entity limit per load; its error reported no effect. A fresh graph
loaded the 17,053 chunks in batches of at most 4,096. Failed and successful
inputs, runner snapshots, results and rankings are preserved separately under
`bench/work/storage/omnigraph-0.15.0/`. This does not test hybrid relevance,
native dot product, concurrent operation, performance or storage footprint.
For all five transformed data files, the first 384 float32 components were
also checked against the original frozen vectors and matched exactly.

Planned before the hybrid diagnostic: use the already frozen transformed
graphs and query vectors for the first 100 queries per corpus, request 100
exhaustive L2 candidates, convert distance back to a dot-product score with
`(R² + ||q||² - distance) / 2`, and use the existing Tantivy/CC/SQLite control
for the rest. Compare the top-20 document rankings twice. Differences from
rounding or ties count as differences; this is a transformed, single-model
component test, not a native metric or performance comparison.

Result: the 500 top-20 document rankings on the five 100-query subsets matched
the SQLite/NumPy control, and two Omnigraph passes agreed. The system still
used the existing SQLite control for document IDs, Tantivy for lexical ranking
and the shared CC fusion; Omnigraph provided only transformed exact L2
candidates. Rankings, hashes and source snapshots are under the five
`*-hybrid-check` work directories. This is not an Omnigraph-native hybrid or
system-of-record benchmark, and the separate tie and Windows branch findings
above remain relevant.

HelixDB 3.7.0's official Windows CLI was downloaded and its SHA-256 verified as
`442bf2953b1f3fc4267f93d987ad3c2c991371a6d28d1262c118afc5a67e1037`.
Its `start` command manages a container image. Docker is not installed on
this machine and no WSL distribution was listed, so a HelixDB engine benchmark
has not run. The CLI binary alone does not establish engine behavior.
An isolated fixture was scaffolded without installing agent skills; its
`helix.toml` selects the Docker runtime and image `ghcr.io/helixdb/helixdb:v0.0.16`.
WSL itself reports version 3.0.5. The official Docker Desktop 4.99.0 installer
was downloaded and its SHA-256 checked against the winget manifest
(`a5e299131c9c53d60f3f752b162078945eb5faf6eedcf0be20a214c6e6cea444`);
it has not been installed or started yet.

The documentation also offers an embedded runtime. The official Windows Python
wheels `helix-db==0.3.3` and `helix-db-embedded==0.3.3` were installed only
under `bench/work/storage/helix-python/`, with telemetry disabled in the test
process. An in-memory graph passed a three-vector Euclidean-search fixture.
The installed native runtime DLL SHA-256 is
`af3396db57d95e84a02ec56f999751c325e02fadb4fdd9c322b7d48dabedbb76`.
Index creation is asynchronous: the first attempt searched too early and got
`index_not_found`; waiting for the operation to succeed fixed the fixture.
This is an embedded runtime, not the containerized server or persistent storage.

Separately, `helix_disk_smoke.py` created a three-vector embedded disk database,
waited for its index, closed the writer, reopened a read-only handle and checked
the expected vector order. This validates one clean reopen only; it does not
test crash recovery, multi-user access or a persistent-server deployment.

Before the next diagnostic: use the same Syntec vectors transformed from dot
product to Euclidean space, create a Helix vector index, wait for it to become
active, insert all 109 vectors, verify visibility, and compare the first 100
queries with the exact NumPy top 10 twice. Record recall and repeat differences;
Helix's indexed search is approximate, not an exact scan. No speed, hybrid,
server or durability claim follows from the in-memory run.

The Syntec diagnostic returned the same top-10 sets as NumPy for all 100
queries in both passes. Before expanding: load the four remaining frozen
corpora into separate in-memory engines, build and wait for each vector index,
then run the same first 100 transformed queries twice. Report overlap, any
errors and repeat differences; do not infer persistent-server performance.

| Corpus | Chunks | Mean top-10 overlap | Minimum overlap |
| --- | ---: | ---: | ---: |
| Syntec | 109 | 100.0% | 100% |
| NFCorpus | 4,599 | 99.3% | 80% |
| SciFact | 6,495 | 99.5% | 90% |
| Alloprof | 5,850 | 99.6% | 90% |
| mix-fr-en | 17,053 | 98.5% | 80% |

Each row covers 100 frozen queries, searched twice against one in-memory index;
both passes returned identical orders. The lowest overlaps are per query, not
dataset-wide scores. On NFCorpus, some missed neighbors had strictly greater
dot-product scores than the returned alternatives, so ties alone do not explain
the differences. The index was built after insertion and reached `succeeded`;
the stored node count was checked. Results, rankings and runner snapshots are
under `bench/work/storage/helixdb-3.7.0/embedded-*-check/`. These figures are
nearest-neighbor overlap, not judged nDCG or end-to-end hybrid recall, and do
not establish behavior of the Helix server or of larger corpora.

Next, fixed before execution: for each corpus, rebuild one in-memory Helix
index from those same transformed vectors and request 100 indexed candidates
for each of the first 100 queries. Convert Helix's fixture-verified squared
Euclidean distance back to dot-product scores, then use the same Tantivy,
SQLite ID lookup and CC fusion as the control. Compare document rankings and
judged metrics twice. This measures an approximate candidate component; it is
not a native Helix hybrid, durable storage, latency or service benchmark.

| Corpus | Control nDCG@10 | Helix candidates nDCG@10 | Different top-20 lists / 100 |
| --- | ---: | ---: | ---: |
| Syntec | 0.82068 | 0.82068 | 0 |
| NFCorpus | 0.39235 | 0.39211 | 39 |
| SciFact | 0.76855 | 0.76617 | 44 |
| Alloprof | 0.46893 | 0.46893 | 52 |
| mix-fr-en | 0.47373 | 0.47129 | 59 |

For these subsets, 194 of 500 ordered top-20 lists differed and both Helix
passes agreed within each single built index. Mean nDCG@10 differences were
small in these particular queries, but unchanged aggregate nDCG does not mean
individual document lists agree. No confidence interval or held-out conclusion
is implied. Ranked outputs, inputs and source snapshots are stored under
`bench/work/storage/helixdb-3.7.0/embedded-*-hybrid-check/`.

After observing the first 100 per corpus, the follow-up uses every remaining
query in the same frozen public test splits for NFCorpus, SciFact, Alloprof and
mix-fr-en. Syntec has only 100 queries. Rebuild one in-memory index per corpus,
keep the same 100-candidate transformed-L2/CC protocol and two passes, and
preserve all rankings. These test splits have already been used elsewhere in
the project; the expanded check is not a fresh independent holdout.

| Remaining test queries | Count | Control nDCG@10 | Helix nDCG@10 | Difference, post-hoc paired 95% interval | Different top-20 lists |
| --- | ---: | ---: | ---: | ---: | ---: |
| NFCorpus | 223 | 0.32344 | 0.32264 | -0.00081 [-0.00288, +0.00099] | 111 |
| SciFact | 200 | 0.71362 | 0.71519 | +0.00157 [-0.00010, +0.00474] | 93 |
| Alloprof | 2,216 | 0.46188 | 0.46074 | -0.00113 [-0.00297, +0.00041] | 1,277 |
| mix-fr-en | 2,939 | 0.47575 | 0.47323 | -0.00251 [-0.00417, -0.00111] | 1,886 |

Intervals use a paired query bootstrap (10,000 resamples, seed 20261116),
calculated after observing the first-100 diagnostics. Both Helix passes agreed
within each newly built index. The intervals characterize this reused test
sample and do not establish independent generalization or a production verdict.
Raw rankings, source snapshots and the bootstrap receipt are in
`bench/work/storage/helixdb-3.7.0/`.

Sources: [Omnigraph](https://github.com/ModernRelay/omnigraph),
[Omnigraph releases](https://github.com/ModernRelay/omnigraph/releases/tag/v0.15.0),
[HelixDB releases](https://github.com/HelixDB/helix-db/releases/tag/v3.7.0).
