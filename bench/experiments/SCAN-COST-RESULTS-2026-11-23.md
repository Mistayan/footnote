# Change scan cost on large shares: results (issue #549)

Result: on 50,000 files (19.6 GiB), an unchanged re-scan takes 22.8 s today and 3.3 s with the size and modification time pre-check (6.9x faster, rolling re-verify included); reading is 72% of today's cost and SHA-256 18%, so BLAKE3 would save about 2% once the pre-check ships and is not needed.

Decision rule: [SCAN-COST-2026-11-23.md](SCAN-COST-2026-11-23.md), committed before any timed run (`bf18394`, `56f4fba` before the rebase onto `main`). Code
frozen at `e225987` (`acc6634` before the rebase; the timed binaries were built from it) before the held-out share was generated. Raw rows:
[`bench/scan-cost/results-2026-11-23.jsonl`](../scan-cost/results-2026-11-23.jsonl), summarised by
[`summarize.py`](../scan-cost/summarize.py); harness in [`bench/scan-cost/`](../scan-cost/) and
`crates/library/examples/scan_cost.rs`.

## Setup as run

- **Machine:** Intel Core Ultra 7 270K Plus, 24 logical CPUs, 47.6 GiB, Windows 11 Pro 10.0.28000. Share on C:
  (Crucial P2 NVMe, 500 GB), 82 GB free before the run. Windows Defender real-time protection off.
- **Load:** not an idle machine: other agents were working (T3 Code, a Footnote daemon). CPU sampled 10 s before each
  block: 14% average (peak 29%) before development; 7.1% warm-up, 4.9 / 7.0 / 7.0 / 27.6 / 8.8% before rounds 1 to 5,
  6.9% split, 21.8% hash bench, 4.3% cold read. No block crossed the 30% flag. The slowest run of every arm falls in
  rounds 4 and 5; medians are used.
- **Held-out share:** `make_share.py --files 50000 --gib 20 --seed 549`: 50,000 files, 21,033,806,361 bytes
  (19.59 GiB, 2% under the 20 GiB target), 19,859 pdf, 7,354 png, 7,556 jpg, 10,184 md, 5,047 txt; largest file
  16.6 MB. Generated in 456 s, deleted after the run. Database seeded in 13.6 s.
- **Development share:** 2,000 files, 0.79 GiB, seed 1, used to write and check the code before the freeze.

## Unchanged re-scan, held-out share, warm cache

One discarded warm-up per arm, then 5 rounds with the arm order rotated. `index()` end to end, release build.

| Arm | Median | Min | Max | Files hashed per run | vs (a) |
|---|---:|---:|---:|---:|---:|
| (a) today (`origin/main`) | 22.8 s | 21.9 s | 27.0 s | 50,000 | 1.00 |
| (b) pre-check, rolling re-verify every 16 runs (new default) | **3.30 s** | 3.19 s | 5.49 s | 3,125 | **0.14** |
| (b) pre-check, no re-verify | 1.81 s | 1.78 s | 3.00 s | 0 | 0.08 |
| `Scan::Full` (new code, hashes everything) | 24.9 s | 23.3 s | 31.7 s | 50,000 | 1.09 |

- **First run after the upgrade** records the stamps, so it hashes every file: 25.5 s (warm-up of (b)), the cost of
  one run of (a). The no-verify and full warm-ups took 23.3 s and 23.8 s.
- **What survives the fallbacks:** rolling re-verify keeps 93% of the gain of (b) without it ((22.8 - 3.30) /
  (22.8 - 1.81)). A full scan keeps none, by design, and is 9% slower than (a): it also writes the stamps and takes
  one extra metadata call per file.
- (b) without re-verify costs 36 µs per file: the walk, one metadata call and one indexed lookup.

## Split of (a), today's loop

Instrumented copy of today's loop (same walk filter, `bounded_read`, `hash`, lookup), 5 runs, median.

| Step | Time | Share |
|---|---:|---:|
| Read (`bounded_read`) | 18.9 s | 72% |
| SHA-256 | 4.67 s | 18% |
| Walk and metadata | 2.11 s | 8% |
| Database lookup | 0.47 s | 2% |
| Total | 26.2 s | |

The split's total is 15% above (a)'s end-to-end median (26.2 s against 22.8 s), at the edge of the rule's 15%
tolerance; the per-step timers and the later run time (after the rounds) are the likely cause. Reading at about
1 GiB/s with the share in RAM shows that `bounded_read` itself is costly (two metadata calls, a link check on every
ancestor folder, a growing buffer); it is untouched here because (b) skips it.

## Cold read (estimate)

One pass with the OS cache bypassed: 69.4 s for 19.59 GiB, 289 MiB/s. Replacing the warm read time by the uncached one,
in proportion to the bytes each arm reads:

| Arm | Warm (measured) | Cold (estimated) | vs (a) |
|---|---:|---:|---:|
| (a) today | 22.8 s | about 73 s | 1.00 |
| (b) with rolling re-verify | 3.30 s | about 6.5 s | 0.09 |

The metadata calls of (b) are assumed to stay warm. A network share reads far slower than a local NVMe drive, so the
gap there is larger still. On the development share, uncached reads ran at only 33 to 64 MiB/s while other agents wrote
to the same drive: the cold figures vary a lot with what else uses the disk.

## (c) BLAKE3 against SHA-256

`hashbench` on the held-out share, files in memory, 3 runs, median (bench only; the engine does not depend on BLAKE3).

| Algorithm | Time for 19.59 GiB | Throughput |
|---|---:|---:|
| SHA-256 (`sha2` 0.10.9, CPU SHA instructions) | 4.40 s | 4.45 GiB/s |
| BLAKE3 1.8.7, one thread | 3.31 s | 5.92 GiB/s |
| BLAKE3 1.8.7, multi-threaded per file (`update_rayon`) | 3.10 s | 6.33 GiB/s |

Most files are a few hundred KB, too small for one file's hash to spread over many cores; the CPU's SHA instructions
keep SHA-256 close. Estimated end-to-end effect (the arm's SHA-256 time scaled by the BLAKE3 / SHA-256 ratio, 0.75 one
thread):

- **(b), the adopted mode:** it hashes 1/16 of the bytes, about 0.29 s of SHA-256; BLAKE3 saves about 0.07 s of 3.30 s,
  **2%**. Rule threshold: 25%. **Not recommended.**
- **Full re-hash (first index, full scan), information only:** about 1.2 s of 22.8 s, 5%.

## Decision

1. **Gates:** the 8 tests in `crates/library/src/scan_tests.rs` pass on Windows: new size; same size with a new
   modification time; a same-size rewrite inside the racy window; a future modification time; an extractor change; a
   file deleted then restored; equivalence of the database with a full scan after two rounds of mixed edits; the trust
   rule itself. The restored-timestamp rewrite is missed by (b) alone on Windows, as the rule expects, and caught by
   `Scan::Full` and by rolling re-verify. On Unix the change time catches it at once; that branch was not run here
   (no Linux or macOS machine, open in the PR).
2. **(b) ships for every edition:** 3.30 s against 22.8 s is 0.14 of (a), well under the 0.5 threshold. It changes no
   stored hash.
3. **Fallbacks:** rolling re-verify keeps 93% of the gain; a full scan keeps none and is available as `Scan::Full`
   in the library. It is not yet a command-line flag (`--rehash`): that is a follow-up, because this story stayed
   inside the library crate.
4. **(c) is not needed:** 2% in the adopted mode against a 25% threshold. Stored hashes stay SHA-256 in both editions,
   so no `blake3:` prefix is introduced.

## Failures and limits

- **Harness bug, fixed after the run:** the example's own `"arm": "default"` overwrote the runner's arm name, so arms (a)
  and (b) were logged under the same name. They are told apart without ambiguity: today's binary has no `hashed` field
  in its result. `summarize.py` does this and `run_rounds.py` now writes the runner's name last. No run was lost.
- Scale: 19.59 GiB rather than 20 (the size generator stops within 2% of its target), with all 50,000 files planned.
  No scale cut was needed for disk space.
- The seeded database has no chunks; the unchanged path never reads them, but a real corpus database is larger.
- Only the library scan is timed. The command line also syncs the lexical index after `index`, which is not measured.
- One machine, a local drive, not idle (see Load). A real file share over SMB was not measured.
- Unix branches (change time in the stamp) are covered by the gate tests but were not run on this Windows machine.
