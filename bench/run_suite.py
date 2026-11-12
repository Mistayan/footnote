"""Run the whole protocol-v1 matrix. Resumable: a (dataset, engine) pair with a complete receipt for the same binary and the same
metrics.py is skipped. Order is cheapest first so interrupted runs still leave useful receipts.

    python bench/run_suite.py                 # everything missing
    python bench/run_suite.py --only lexical  # lexical engines only
    python bench/run_suite.py --list          # show what would run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engines  # noqa: E402

IR = ["syntec", "scifact", "nfcorpus", "alloprof"]
LEXICAL = ["shipped-lexical", "bm25-or-lexical"]
HYBRID = ["shipped-hybrid", "shipped-hybrid-e5"]


def done(dataset: str, engine: str) -> bool:
    import run
    exe, harness = engines.sha256_file(engines.EXE), run.harness_hash()
    for f in (HERE / "receipts").glob(f"*-{dataset}-{engine}.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r["engine"]["versions"]["binary_sha256"] == exe and r["code"].get("harness_sha256") == harness and not r["partial"]:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["lexical", "hybrid"])
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    ens = {"lexical": LEXICAL, "hybrid": HYBRID, None: LEXICAL + HYBRID}[args.only]
    jobs = [("run.py", d, e) for e in ens for d in IR] + [("run_lme.py", None, e) for e in ens]
    for script, dataset, engine in jobs:
        name = dataset or "longmemeval_s"
        if done(name, engine):
            print(f"skip  {name} / {engine} (receipt exists)")
            continue
        print(f"{'would run' if args.list else 'run'}  {name} / {engine}", flush=True)
        if args.list:
            continue
        cmd = [sys.executable, "-I", str(HERE / script)] + ([dataset, engine] if dataset else [engine])
        if subprocess.run(cmd).returncode != 0:
            print(f"FAILED {name} / {engine}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
