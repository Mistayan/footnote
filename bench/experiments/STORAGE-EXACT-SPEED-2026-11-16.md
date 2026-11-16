# Exact vector candidate speed: bounded comparison

Frozen before measurement. Use the 17,053 frozen mix-fr-en chunks and first
100 frozen query vectors of `matched-inputs`, verify their hashes, compare exact
dot-product top-10 IDs and preserve all results. Test three configurations:

1. The existing float32 NumPy matrix resident in the Python benchmark process.
2. Qdrant 1.20.1 server on localhost, exact search, the same vectors and IDs.
3. PostgreSQL 16.14 with pgvector 0.8.3 on localhost, exact sequential scan,
   ordering equal distances by chunk ID.

Preload each store before measurement; no model encoding or ingestion is in
the query timing. Warm each method, run three rounds of the 100 queries, and
record individual samples, p50/p95, returned IDs, top-10 overlap, versions,
input/code hashes and server logs. Timings include client/server transport for
the two servers, whereas NumPy is in-process; this distinction is part of the
comparison. Run when other benchmark jobs have stopped and document observed
background load; do not call the machine idle without evidence. No ANN index,
hybrid fusion, parallel users, product daemon, durability, storage footprint or
build time is evaluated. Ties and floating-point rounding may change IDs without
changing the underlying score; investigate before interpreting recall.

The harness was smoke-tested on the separate 109-chunk Syntec fixture while a
model benchmark was active: all three methods returned the same top-10 sets for
all 300 calls. Those smoke-test timings are deliberately excluded from the
comparison. The mixed-corpus measurement has not yet run.

## Result (16 November, 05:11, `bench/work/storage/exact-speed-mix-20261116`)

17,053 chunks, 100 queries, 3 rounds; every method returned the same top-10 IDs on every call (overlap 1.0).

| Method | p50 | p95 |
|---|---|---|
| NumPy float32, in process | 1.34 ms | 1.63 ms |
| PostgreSQL 16.14 + pgvector 0.8.3, sequential scan | 7.87 ms | 8.43 ms |
| Qdrant 1.20.1 server, exact | 16.20 ms | 24.19 ms |

- Same answers; in-process exact scan is about 6 times faster than pgvector and 12 times faster than Qdrant at this size, most
  of the gap being transport and server overhead (both servers on localhost).
- Background load before the run: CPU 4.9 to 9.5 % over 5 s, no benchmark process running; not certified idle.
- At this scale an external store buys no query speed; its case is size beyond one machine's memory, sharing and operations.
