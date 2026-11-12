"""Validation gate for a model config: reproduce the published MTEB nDCG@10 (dense only, whole-document) within a tolerance.

    bench/.labenv/Scripts/python.exe -I bench/lab/check_model.py e5-small-multi syntec
    bench/.labenv/Scripts/python.exe -I bench/lab/check_model.py bge-small-en scifact --tol 0.03

A model that fails here has a wrong pooling, prefix or tokenizer in models.MODELS and must not be used in any experiment. Tolerance covers
int8 quantization and library differences (published scores are fp32 sentence-transformers). The result is appended to lab/model_checks.jsonl.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import lab  # noqa: E402
import metrics  # noqa: E402
import models  # noqa: E402

TASK = {"scifact": "SciFact", "nfcorpus": "NFCorpus", "syntec": "SyntecRetrieval", "alloprof": "AlloprofRetrieval"}


def published(model: str, dataset: str) -> float | None:
    anchors = json.loads((HERE.parent / "anchors.json").read_text(encoding="utf-8"))
    vals = [a["scores_test"][0]["ndcg_at_10"] for a in anchors["mteb"]
            if a["model"] == models.MODELS[model]["mteb"] and a["task"] == TASK[dataset] and a["scores_test"]]
    return max(vals) if vals else None  # several revisions may exist: take the best published


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", choices=sorted(models.MODELS))
    ap.add_argument("dataset", choices=sorted(TASK))
    ap.add_argument("--tol", type=float, default=0.03)
    args = ap.parse_args()
    corpus, queries, qrels = fetch.load(args.dataset)
    eng = lab.LabEngine("check", {"chunker": {"kind": "whole"}, "lexical": {"on": False},
                                  "dense": {"on": True, "model": args.model}, "fusion": {"kind": "dense"}})
    t = time.perf_counter()
    info = eng.prepare(args.dataset, corpus)
    rankings = {q: eng.search(q, text, 20) for q, text in queries.items()}
    score = metrics.evaluate(rankings, qrels)["ndcg@10"]
    ref = published(args.model, args.dataset)
    ok = ref is not None and abs(score - ref) <= args.tol
    row = {"model": args.model, "dataset": args.dataset, "ndcg@10": round(score, 5), "published": ref,
           "delta": None if ref is None else round(score - ref, 5), "tolerance": args.tol, "pass": ok,
           "max_len": eng._enc.max_len, "seconds": round(time.perf_counter() - t, 1), "embed_ms": round(info["embed_ms"])}
    print(json.dumps(row))
    with (HERE / "model_checks.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
