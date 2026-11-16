# PostgreSQL + pgvector: isolated comparison preparation

Written before execution. Provision PostgreSQL and pgvector in an isolated
conda-forge environment under `bench/work/storage/`, without a Windows service.
Pin package versions, preserve resolved package records and hashes, use a fresh
local data directory and bind the temporary server to localhost. Stop only the
process started by the experiment. No existing database or installation is used.

First validate exact negative inner-product nearest neighbors against the same
hash-verified Syntec vectors and queries used by the SQLite/LanceDB component
comparison. Preserve IDs, float32 vector values and the query subset; verify
neighbor differences and ties. Then compare hybrid candidates with the same
Tantivy index and CC fusion, with a declared pool size and unchanged input.
Archive raw results and code. Record what component still depends on SQLite.
One-model results, partial queries, index/build timings under load, and exact
search are not evidence of full production parity, scale, or ANN behavior.

Documentation: [pgvector operators](https://github.com/pgvector/pgvector#querying),
[PostgreSQL Windows distributions](https://www.postgresql.org/download/windows/).

## Results

The isolated conda-forge environment contains PostgreSQL 16.14 and pgvector
0.8.3; the resolved environment is preserved in
`bench/work/storage/postgres-pgvector-env-explicit.txt`. A localhost-only
three-vector fixture passed exact inner-product search and a metadata filter.
The server was stopped after each experiment.

For each of Syntec, NFCorpus, SciFact, Alloprof and mix-fr-en, the first 100
frozen queries were run twice against all frozen chunks. Using pgvector exact
inner-product candidates, the shared Tantivy index and CC fusion, all 500 top-20
document rankings matched the existing SQLite/NumPy control; both pgvector
passes agreed. pgvector ordered equal distances by chunk ID. Result JSON,
rankings, input hashes and source snapshots are retained under
`bench/work/storage/postgres-*-hybrid-check/`.

The PostgreSQL table contained the vectors, text and document IDs, but the
hybrid diagnostic fetched document IDs from the existing SQLite control to keep
the rest of the retrieval path identical. Consequently this is **not** a full
PostgreSQL system-of-record comparison. Only 100 queries per corpus were used;
ANN, performance, transactions, crash recovery, concurrent users and full
storage footprints remain to be tested before any migration decision.
