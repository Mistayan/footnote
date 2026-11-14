"""Where does the shipped-like lab stack lose relevant documents? Dev split only (tuning data), never heldout.

    bench/.labenv/Scripts/python.exe -I bench/experiments/miss_analysis.py --datasets scifact,nfcorpus,alloprof,mix-fr-en

For every judged-relevant document: its rank in the fused ranking, in the lexical arm alone and in the dense arm alone (top 100 each).
Slices by query language and length. Also the per-query oracle that picks the better of fused, lexical and dense: an upper bound on
what any query routing could gain, not an achievable result. Writes bench/experiments/MISS-ANALYSIS.md and bench/work/miss-analysis.json.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path[:0] = [str(BENCH), str(BENCH / "lab")]
import fetch  # noqa: E402
import metrics  # noqa: E402

# Same base as bench/experiments/run_models2.sh: the shipped pair, z-score convex fusion at alpha 0.55, whole documents.
BASE = {"dense": {"model": "bekko-a8m", "extra": {"model": "gte-small", "weight": 0.5}}, "lexical": {"k1": 1.2, "tokenizer": {"stem": "en"}},
        "fusion": {"kind": "cc", "norm": "zscore", "alpha": 0.55}, "chunker": {"kind": "whole"}}
ARMS = {"fused": {}, "lexical": {"fusion": {"kind": "lexical"}}, "dense": {"fusion": {"kind": "dense"}}}
DEPTH = 100


def bucket(rank: int | None) -> str:
    if rank is None:
        return "not in top 100"
    return "top 10" if rank <= 10 else "11-20" if rank <= 20 else "21-100"


def length(text: str) -> str:
    n = len(text.split())
    return "1-4 words" if n <= 4 else "5-12 words" if n <= 12 else "13+ words"


def summarize(records: list[dict]) -> dict:
    """records: one per relevant document, with ranks per arm (None = absent from top 100)."""
    out = collections.Counter()
    for r in records:
        out["fused " + bucket(r["fused"])] += 1
        if r["fused"] is None or r["fused"] > 10:
            lex, den = (r[a] is not None and r[a] <= 10 for a in ("lexical", "dense"))
            out["missed: lexical top 10 only" if lex and not den else "missed: dense top 10 only" if den and not lex
                else "missed: both arms top 10" if lex else "missed: neither arm top 10"] += 1
    return dict(out)


def main() -> None:
    import lab  # noqa: PLC0415
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datasets", default="scifact,nfcorpus,alloprof,mix-fr-en")
    args = ap.parse_args()
    report, lines = {}, ["# Miss analysis, dev split", "", "Shipped-like lab stack (bekko-a8m + gte-small, z-score convex fusion, alpha 0.55, whole documents). "
                         "Counts are relevant documents. Dev data only: this chooses experiments, it proves nothing.", ""]
    for ds in args.datasets.split(","):
        corpus, queries, qrels = fetch.load(ds, "dev")
        queries = {q: t for q, t in queries.items() if q in qrels and any(v > 0 for v in qrels[q].values())}
        runs = {}
        for arm, override in ARMS.items():
            eng = lab.LabEngine(f"miss-{arm}", lab.merge(lab.merge(lab.DEFAULT, BASE), override))
            eng.prepare(ds, corpus)
            eng.warm_queries(list(queries.values()))
            runs[arm] = {q: metrics.dedupe(eng.search(q, t, DEPTH))[:DEPTH] for q, t in queries.items()}
        records, ndcg, oracle = [], collections.defaultdict(list), []
        for q, text in queries.items():
            per = {arm: metrics.ndcg_at_k(runs[arm][q], qrels[q], 10) for arm in ARMS}
            for arm, v in per.items():
                ndcg[arm].append(v)
            oracle.append(max(per.values()))
            for doc, grade in qrels[q].items():
                if grade > 0:
                    rec = {arm: (runs[arm][q].index(doc) + 1 if doc in runs[arm][q] else None) for arm in ARMS}
                    records.append(rec | {"lang": lab.lang_of(text), "length": length(text)})
        mean = {arm: round(sum(v) / len(v), 4) for arm, v in ndcg.items()}
        slices = {f"{key}={val}": summarize([r for r in records if r[key] == val])
                  for key in ("lang", "length") for val in sorted({r[key] for r in records})}
        report[ds] = {"queries": len(queries), "relevant": len(records), "ndcg@10": mean, "oracle_best_arm_ndcg@10": round(sum(oracle) / len(oracle), 4),
                      "all": summarize(records), "slices": slices}
        lines += [f"## {ds}: {len(queries)} queries, {len(records)} relevant documents", "",
                  f"nDCG@10 fused {mean['fused']}, lexical only {mean['lexical']}, dense only {mean['dense']}; "
                  f"per-query best-arm oracle {report[ds]['oracle_best_arm_ndcg@10']} (upper bound, not achievable).", "",
                  "| Slice | " + " | ".join(sorted(report[ds]["all"])) + " |", "|---|" + "---:|" * len(report[ds]["all"])]
        for name, counts in [("all", report[ds]["all"]), *slices.items()]:
            lines.append(f"| {name} | " + " | ".join(str(counts.get(k, 0)) for k in sorted(report[ds]["all"])) + " |")
        lines.append("")
    (BENCH / "work" / "miss-analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (HERE / "MISS-ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
