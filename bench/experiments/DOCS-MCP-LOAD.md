# MCP concurrency diagnostic

Frozen 15 November 2026, before the measured run. Implements the two scenarios
in [DOCS-FOLLOWUPS-2026-11-15.md](DOCS-FOLLOWUPS-2026-11-15.md).

- A copy of the existing React database and Tantivy index, with both default
  models. Original dataset's React questions, shuffled with seed 20261115.
- At each level (1, 5, 10, 20, 40), start that many persistent MCP sessions,
  then three warm-up searches and 30 measured searches per client. Each client
  waits for its previous response before sending another. Queries are rotated
  deterministically; all scenarios use the same mix. Clients warm one at a
  time to avoid a transient model-loading spike; stop if available physical
  memory falls below 5 GiB.
- Shared: one private daemon, each client a separate stdio proxy. Verify daemon
  readiness and reject any proxy that falls back to serving in-process.
  Standalone: one in-process MCP server per client, all reading the same copy.
- Measure complete JSON-RPC `footnote_recall` calls, hybrid, top 5, per-source
  cap 1. Report successful throughput, failures, per-call p50/p95/p99, total
  wall time, aggregate Windows working set, CPU core-seconds, and individual
  requests. The working-set sum double-counts pages shared between processes.
  Thirty observations at level 1 make its p95/p99 particularly unstable.
- Repeatability, saturation trends and failures are descriptive, not a claim
  about actual company users or about 1,000-user cost. Machine-idle status must
  be reported honestly; background processes and heat may affect latency.
- All processes and the database are created specifically for this test.
  Stop only the PIDs started by this test, never the user's existing MCP server.

The optional `--smoke` run uses two calls per client at levels 1 and 2 to
validate the harness. It is not part of the measured results.
