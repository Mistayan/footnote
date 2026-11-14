"""Paired bootstrap comparison of two reportable runs on the same dataset and split.

    python bench/compare.py scifact lab_bm25-product-like shipped-lexical          # latest receipts by engine id
    python bench/compare.py alloprof receipts/<a>.rankings.json.gz receipts/<b>.rankings.json.gz --split heldout

Reports mean nDCG@10 for each system, the paired difference and a 95 percent bootstrap interval (10,000 resamples of queries, fixed seed).
The interval excludes zero only when the gain is consistent across queries, which is the standard the decision rules require.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import metrics  # noqa: E402


def load_rankings(spec: str, dataset: str) -> dict[str, list[str]]:
    path = Path(spec)
    if not path.exists():  # an engine id: take the latest non-partial test receipt
        matches = sorted(p for p in (HERE / "receipts").glob(f"*-{dataset}-{spec}.rankings.json.gz"))
        if not matches:
            raise SystemExit(f"no receipt for {dataset}/{spec}")
        path = matches[-1]
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def per_query(rankings: dict, qrels: dict) -> dict[str, float]:
    return {q: metrics.ndcg_at_k(metrics.dedupe(rankings.get(q, [])), qrels[q], 10)
            for q in qrels if any(v > 0 for v in qrels[q].values())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--split", default="test")
    ap.add_argument("--resamples", type=int, default=10000)
    args = ap.parse_args()
    _, queries, qrels = fetch.load(args.dataset, args.split)
    pa, pb = (per_query(load_rankings(x, args.dataset), qrels) for x in (args.a, args.b))
    qs = sorted(set(pa) & set(pb))
    diffs = [pb[q] - pa[q] for q in qs]
    rng = random.Random(20261111)
    means = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(args.resamples))
    lo, hi = means[int(0.025 * args.resamples)], means[int(0.975 * args.resamples)]
    mean_a, mean_b = sum(pa[q] for q in qs) / len(qs), sum(pb[q] for q in qs) / len(qs)
    verdict = "B better" if lo > 0 else "A better" if hi < 0 else "no consistent difference"
    print(f"{args.dataset} ({args.split}), {len(qs)} queries\n  A = {args.a}: nDCG@10 {mean_a:.4f}\n  B = {args.b}: nDCG@10 {mean_b:.4f}\n"
          f"  B - A = {mean_b - mean_a:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  -> {verdict}")
    for label, spec in (("A", args.a), ("B", args.b)):
        problem = unreproducible(spec)
        if problem:
            print(f"  WARNING {label}: {problem}; this interval cannot support a reproducible-superiority claim")
    return 0


def unreproducible(spec: str) -> str | None:
    """Why the receipt next to a rankings file fails its determinism check, or None if it passed or has no receipt."""
    receipt = Path(spec.replace(".rankings.json.gz", ".json"))
    if not spec.endswith(".rankings.json.gz") or not receipt.exists():
        return None
    det = json.loads(receipt.read_text(encoding="utf-8")).get("determinism", {})
    if not det.get("checked"):
        return f"{receipt.name} has no determinism check"
    if not det.get("identical_rankings"):
        return f"{receipt.name} is not reproducible (rankings not identical when {det.get('queries_checked', '?')} queries were repeated)"
    return None


if __name__ == "__main__":
    raise SystemExit(main())
