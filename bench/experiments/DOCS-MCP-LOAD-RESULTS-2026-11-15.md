# MCP concurrency: first diagnostic

15 November 2026. Protocol: [DOCS-MCP-LOAD.md](DOCS-MCP-LOAD.md). A private
copy of the React documentation database, the default two models, and 12
repeated React queries. Each level ran once after warming every session; each
client issued 30 consecutive hybrid searches. There were no failed requests.

| Concurrent clients | Shared daemon: requests/s | Shared p95 ms | Shared working-set sum MiB | Separate servers: requests/s | Separate p95 ms | Separate working-set sum MiB |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 73.8 | 14.7 | 461 | 81.0 | 13.4 | 452 |
| 5 | 268.6 | 22.1 | 519 | 311.6 | 17.9 | 2,262 |
| 10 | 285.4 | 39.3 | 589 | 495.7 | 22.6 | 4,513 |
| 20 | 267.1 | 83.9 | 725 | 740.2 | 31.3 | 9,032 |
| 40 | 286.0 | 148.1 | 1,000 | 712.9 | 74.8 | 18,053 |

In this short closed-loop workload, the shared daemon reaches a throughput
plateau while p95 increases with more clients. Separate servers use much more
aggregate process working set and sustain higher throughput here. This does not
establish a causal bottleneck: model locks, SQLite, CPU scheduling and transport
need profiling. The Windows working-set sum counts pages shared across processes
more than once, so it is not actual physical RAM consumed. It includes the
daemon/proxies for shared and all server processes for separate servers.

Each level lasted only about 0.4–4.2 seconds after warm-up, and the system was
not certified idle (an 11% total CPU reading was observed before the run).
These are therefore diagnostic numbers, not a production capacity, 1,000-user
cost or idle-machine latency claim. A longer repeated run, monitored background
load, private-memory accounting and realistic request arrival rates would be
needed for those decisions. At level 1, the percentiles use only 30 observations.

Inputs, per-request latencies/errors, resource samples, and exact runner and
protocol snapshots are in `bench/work/gd/mcp-load-20261115/`. Only the test's
own daemon and client PIDs were stopped. An earlier smoke run is retained
separately and is not included in the numbers above.
