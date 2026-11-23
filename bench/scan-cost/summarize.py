#!/usr/bin/env python3
"""Summarise run_rounds.py output (issue #549): medians per arm, the split of (a), hash bench and cold read.

Usage: python summarize.py results.jsonl
"""
import json
import statistics
import sys


def main():
    rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
    out = {}
    runs = {}
    for r in rows:
        if "arm" in r and r.get("arm") == "default":
            # The first log (23 Nov) let the example's own "arm" overwrite the runner's: (a) is today's binary, which
            # has no "hashed" field; (b) is the new binary in its default mode.
            r["arm"] = "b" if "hashed" in r.get("result", {}) else "a"
        if r.get("phase", "").startswith("round") and "arm" in r:
            runs.setdefault(r["arm"], []).append(r)
    for arm, rs in runs.items():
        ok = [r for r in rs if "ms" in r]
        ms = [r["ms"] for r in ok]
        out[arm] = {"n": len(ok), "errors": len(rs) - len(ok), "median_ms": round(statistics.median(ms)),
                    "min_ms": round(min(ms)), "max_ms": round(max(ms)),
                    "hashed_median": statistics.median([r["result"].get("hashed", -1) for r in ok]),
                    "unchanged": sorted({r["result"]["unchanged"] for r in ok})}
    out["round_ms"] = {arm: [round(r["ms"]) for r in rs if "ms" in r] for arm, rs in runs.items()}
    out["warm-up"] = {r["arm"]: {"ms": round(r.get("ms", -1)), "hashed": r.get("result", {}).get("hashed"),
                                 "error": r.get("error")} for r in rows if r.get("phase") == "warm-up" and "arm" in r}
    split = [r for r in rows if r.get("phase") == "split" and "total_ms" in r]
    if split:
        out["split_median_ms"] = {k: round(statistics.median(r[k] for r in split))
                                  for k in ["total_ms", "walk_ms", "read_ms", "hash_ms", "db_ms"]}
    hb = [r for r in rows if r.get("phase") == "hashbench" and "sha256_ms" in r]
    if hb:
        out["hashbench_median"] = {k: statistics.median(r[k] for r in hb)
                                   for k in ["sha256_ms", "blake3_ms", "blake3_rayon_ms", "sha256_gib_s",
                                             "blake3_gib_s", "blake3_rayon_gib_s"]}
    out["coldread"] = [r for r in rows if r.get("phase") == "coldread" and "cmd" in r]
    out["seed"] = [r for r in rows if r.get("phase") == "seed"]
    out["load"] = [(r["phase"], r["cpu_pct"], r["flagged"]) for r in rows if "cpu_pct" in r]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
