#!/usr/bin/env python3
"""Timed runs of the change scan cost bench (issue #549, bench/experiments/SCAN-COST-2026-11-23.md).

Usage: python run_rounds.py SHARE WORKDIR BIN_A BIN_B OUT.jsonl [--rounds 5] [--hashbench EXE] [--coldread]

BIN_A is the `scan_cost` example built from origin/main (arm a, today's `index()`); BIN_B is the same example built
from the frozen commit (arms b = default pre-check with rolling re-verify, b-noverify, full). Seeds one database
with BIN_B, copies it per arm, runs one discarded warm-up per arm (for b it is the first run after an upgrade, which
records the stamps: reported, not discarded silently), then ROUNDS rounds with the arm order rotated, the CPU load
sampled for 10 s before each round (Windows), the split of today's loop 5 times, BLAKE3 against SHA-256, and one
uncached read pass. Appends every raw result to OUT.jsonl.
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import time

PS_CPU = ("(1..10 | ForEach-Object { (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor "
          "-Filter \"Name='_Total'\").PercentProcessorTime; Start-Sleep -Milliseconds 900 } "
          "| Measure-Object -Average).Average")


def cpu():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", PS_CPU], capture_output=True, text=True, check=True)
    return float(out.stdout.strip().replace(",", "."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("share")
    ap.add_argument("work")
    ap.add_argument("bin_a")
    ap.add_argument("bin_b")
    ap.add_argument("out")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--hashbench")
    ap.add_argument("--coldread", action="store_true")
    a = ap.parse_args()
    work = pathlib.Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    log = open(a.out, "a", encoding="utf-8")

    def emit(rec):
        rec["t"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        log.write(json.dumps(rec) + "\n")
        log.flush()
        print(json.dumps(rec), flush=True)
        return rec

    def call(*args):
        out = subprocess.run(list(map(str, args)), capture_output=True, text=True)
        if out.returncode != 0:
            return {"error": out.stderr.strip()[-2000:], "args": list(map(str, args))}
        return json.loads(out.stdout.strip().splitlines()[-1])

    def load(phase):
        for attempt in range(4):
            c = cpu()
            if c <= 30 or attempt == 3:
                return emit({"phase": phase, "cpu_pct": c, "flagged": c > 30, "attempt": attempt})
            time.sleep(60)

    seed_db = work / "seed.db"
    if not seed_db.exists():
        emit({"phase": "seed", **call(a.bin_b, "seed", a.share, seed_db)})
    arms = {"a": (a.bin_a, "default"), "b": (a.bin_b, "default"), "b-noverify": (a.bin_b, "no-verify"),
            "full": (a.bin_b, "full")}
    for arm in arms:
        shutil.copyfile(seed_db, work / f"{arm}.db")
    load("warm-up")
    for arm, (exe, mode) in arms.items():
        emit({"phase": "warm-up", **call(exe, "run", a.share, work / f"{arm}.db", mode), "arm": arm})
    names = list(arms)
    for r in range(a.rounds):
        load(f"round {r + 1}")
        for arm in names[r % len(names):] + names[: r % len(names)]:
            exe, mode = arms[arm]
            emit({"phase": f"round {r + 1}", **call(exe, "run", a.share, work / f"{arm}.db", mode), "arm": arm})
    load("split")
    for i in range(5):
        emit({"phase": "split", "i": i + 1, **call(a.bin_a, "split", a.share, work / "a.db")})
    if a.hashbench:
        load("hashbench")
        out = subprocess.run([a.hashbench, a.share, "3"], capture_output=True, text=True, check=True)
        for line in out.stdout.strip().splitlines():
            emit({"phase": "hashbench", **json.loads(line)})
    if a.coldread:
        load("coldread")
        emit({"phase": "coldread", **call(a.bin_a, "coldread", a.share)})


if __name__ == "__main__":
    main()
