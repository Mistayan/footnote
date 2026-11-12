"""Summarize bench/sweeps/<sweep>.jsonl as leaderboards (markdown). Read-only.

    python bench/sweep_report.py models            # one table per dataset, best first, with the gap to the best row
    python bench/sweep_report.py fusion --tag en   # filter on the free tag stored at run time

Rows with an `error` are listed at the end: a failure is a result.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sweep")
    ap.add_argument("--tag")
    ap.add_argument("--split")
    ap.add_argument("--top", type=int, default=0, help="show only the best N rows per dataset")
    args = ap.parse_args()
    rows = [json.loads(l) for l in (HERE / "sweeps" / f"{args.sweep}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.tag is not None:  # prefix match, so `--tag en2` selects `en2:gte-small`, `en2:bekko-a8m`...
        rows = [r for r in rows if r.get("tag", "").startswith(args.tag)]
    if args.split:
        rows = [r for r in rows if r["split"] == args.split]
    by_ds: dict[str, list] = collections.defaultdict(list)
    errors = []
    for r in rows:
        (errors if "error" in r else by_ds[f"{r['dataset']} ({r['split']})"]).append(r)
    for ds, items in by_ds.items():
        items.sort(key=lambda r: -r["ndcg@10"])
        best = items[0]["ndcg@10"]
        print(f"\n### {ds}  ({items[0]['queries']} queries)\n\n| Config | nDCG@10 | Recall@10 | MRR@10 | vs best | Chunks | Embed s |\n|---|---|---|---|---|---|---|")
        for r in (items[: args.top] if args.top else items):
            print(f"| {(r.get('tag') + ' · ') if r.get('tag') else ''}{r['label']} | {r['ndcg@10']:.4f} | {r['recall@10']:.4f} | {r['mrr@10']:.4f} | {r['ndcg@10'] - best:+.4f} | {r['chunks']} | {r['embed_ms'] // 1000} |")
    if errors:
        print("\n### Failures\n")
        for r in errors:
            print(f"- {r['dataset']} / {r['label']}: {r['error']}")


if __name__ == "__main__":
    main()
