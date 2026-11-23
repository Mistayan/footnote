# Lean hook decisions and coverage on 23 November 2026

The same 6,770 completed shell calls yielded 3,539 eligible rewrites under the hook's rules. The old prefix heuristic counted 2,648.

## Coverage

Both Windows binaries scanned the same seven-day window and matched 6,770 calls across 371 transcript files. The revised report accounts for commands the generic wrapper handles and rejects calls the actual rewrite planner leaves alone, including unsafe pipelines and redirects. These counts measure eligibility on the recorded calls. Actual rewrite rates come from `hook_decisions.by_agent` in `footnote gain`.

| Agent | Completed calls | Eligible under the hook rules | Uncovered |
|---|---:|---:|---:|
| Claude Code | 5,979 | 3,040 | 2,939 |
| Antigravity | 790 | 499 | 291 |
| Codex | 1 | 0 | 1 |
| Total | 6,770 | 3,539 | 3,231 |

The Codex row describes the transcript files this run could match. It is too small to estimate Codex's rewrite coverage.

## Hook latency

A quiet-machine run with 180 paired debug-build invocations measured 3% CPU load before and 15% after. Each pair used the same synthetic event, alternating among a Codex Git rewrite, a Claude Code pipeline the hook passes through, and an Antigravity shell command it passes through. The order of the binaries within each pair was randomized. Warm-ups are excluded from timing.

| Windows hook invocation | p50 | p95 |
|---|---:|---:|
| Main before the change | 10.024 ms | 11.140 ms |
| With the decision log | 9.828 ms | 10.739 ms |

The paired median change was −0.174 ms (95% bootstrap interval −0.255 to −0.097 ms). A Codex-only comparison within the patched binary measured +0.178 ms of median logging overhead. Its p95 fluctuated across runs. For the full hook, skipping executable lookup on passes offset the append in this workload. Each call makes one append with no file synchronization. The ledger rotates at 512 KiB and keeps one older segment.

```powershell
footnote gain --days 7 --missed
python bench/lean_hook_decisions.py --footnote $patched --before $before --pairs 180
python bench/lean_hook_decisions.py --footnote $patched --pairs 120
```

[Timing and coverage receipt](../receipts/20261123-lean-hook-decisions.json)
