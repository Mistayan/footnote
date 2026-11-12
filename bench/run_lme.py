"""LongMemEval-S, retrieval only (no LLM): can the engine put the evidence session in the top k of one question's haystack?

    python bench/run_lme.py bm25-or-lexical --questions 30

One small index per question (about 47 sessions of one user's chat history), queried twice for the determinism check, then deleted.
Abstention questions (`_abs`) have no evidence session and are not scored. Metrics follow the LongMemEval paper:
recall_any@k and recall_all@k at session level, plus nDCG@10.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import json
import shutil
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engines  # noqa: E402
import fetch  # noqa: E402
import metrics  # noqa: E402
import run as base  # noqa: E402


def session_text(turns: list[dict]) -> str:
    return "\n\n".join(f"{t['role']}: {t['content']}" for t in turns)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("engine", help="product engine or lab:<name>")
    ap.add_argument("--split", choices=["test", "dev", "heldout"], default="test")
    ap.add_argument("--lab-json", help="inline lab config (JSON)")
    ap.add_argument("--questions", type=int, help="score only the first N scoreable questions (receipt is marked partial)")
    args = ap.parse_args()

    questions = [q for q in fetch.load_longmemeval() if not q["question_id"].endswith("_abs")]
    if args.split != "test":
        questions = [q for q in questions if fetch.is_dev(q["question_id"]) == (args.split == "dev")]
    partial = bool(args.questions and args.questions < len(questions))
    if partial:
        questions = questions[: args.questions]
    engine = base.get_engine(args.engine, args.lab_json)
    if hasattr(engine, "_cache_embeddings"):
        engine._cache_embeddings = False  # one-off haystacks: do not fill the disk cache
    rankings: dict[str, list[str]] = {}
    qrels: dict[str, dict[str, int]] = {}
    types: dict[str, str] = {}
    build_ms, search_ms, deterministic = [], [], True
    for i, q in enumerate(questions, 1):
        qid = q["question_id"]
        corpus = {sid: ("", session_text(turns)) for sid, turns in zip(q["haystack_session_ids"], q["haystack_sessions"])}
        qrels[qid] = {sid: 1 for sid in q["answer_session_ids"]}
        types[qid] = q["question_type"]
        t = time.perf_counter()
        engine.prepare(f"lme/{qid}", corpus)
        build_ms.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        first = metrics.dedupe(engine.search(qid, q["question"], base.K))[: base.K]
        search_ms.append((time.perf_counter() - t) * 1000)
        if set(first) - set(corpus):  # integrity: ids must come from this question's own haystack
            raise RuntimeError(f"{qid}: ids outside the haystack returned: {sorted(set(first) - set(corpus))[:3]}")
        again = metrics.dedupe(engine.search(qid, q["question"], base.K))[: base.K]
        deterministic &= first == again
        rankings[qid] = first
        engine.close()
        shutil.rmtree(engines.WORK / "lme" / qid, ignore_errors=True)  # lab engines keep the index in memory and have no folder
        if i % 25 == 0 or i == len(questions):
            print(f"  {i}/{len(questions)} questions", flush=True)

    def mean(fn) -> float:
        return sum(fn(rankings[q], qrels[q]) for q in qrels) / len(qrels)

    scores = {"ndcg@10": mean(lambda r, j: metrics.ndcg_at_k(r, j, 10)), "queries_scored": len(qrels)}
    for k in (5, 10):
        scores[f"recall_any@{k}"] = mean(lambda r, j, k=k: metrics.recall_any_all_at_k(r, j, k)[0])
        scores[f"recall_all@{k}"] = mean(lambda r, j, k=k: metrics.recall_any_all_at_k(r, j, k)[1])
    by_type: dict[str, list[float]] = collections.defaultdict(list)
    for q in qrels:
        by_type[types[q]].append(metrics.recall_any_all_at_k(rankings[q], qrels[q], 5)[0])
    scores["recall_any@5_by_type"] = {t: {"n": len(v), "value": round(sum(v) / len(v), 4)} for t, v in sorted(by_type.items())}
    now = dt.datetime.now(dt.timezone.utc)
    name = f"{now.strftime('%Y%m%dT%H%M%SZ')}-longmemeval_s-{engine.id.replace(':', '_')}{'' if args.split == 'test' else '-' + args.split}{'-partial' if partial else ''}"
    lock = fetch.read_lock()["longmemeval_s"]
    receipt = {
        "protocol": base.PROTOCOL, "timestamp_utc": now.isoformat(timespec="seconds"), "partial": partial,
        "task": "longmemeval-retrieval-only (session level, no LLM)",
        "dataset": {"id": "longmemeval_s", "split": args.split, "revision": lock["rev"], "files": lock["files"], "questions": len(qrels),
                    "excluded": "abstention questions (_abs)"},
        "engine": {"id": engine.id, "config": engine.config, "versions": engine.versions()},
        "code": {"commit": base.git("rev-parse", "HEAD"), "dirty": bool(base.git("status", "--porcelain", "--", "src", "bench")),
                 "metrics_sha256": hashlib.sha256((base.HERE / "metrics.py").read_bytes()).hexdigest(),
                 "harness_sha256": base.harness_hash()},
        "machine": base.machine(),
        "build": {"per_question_ms_p50": round(statistics.median(build_ms), 1), "per_question_ms_p95": round(base.pct(build_ms, .95), 1)},
        "metrics": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in scores.items()},
        "latency_ms": {"scope": engine.latency_scope, "p50": round(statistics.median(search_ms), 2),
                       "p95": round(base.pct(search_ms, .95), 2), "queries": len(search_ms)},
        "determinism": {"checked": True, "queries_checked": len(qrels), "identical_rankings": deterministic,
                        "rankings_sha256": base.rankings_hash(rankings)},
    }
    folder = base.RECEIPTS if args.split == "test" else base.RECEIPTS / args.split
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    if path.exists():
        raise SystemExit(f"{path} exists; receipts are immutable")
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with gzip.open(folder / f"{name}.rankings.json.gz", "wt", encoding="utf-8") as f:
        json.dump({q: rankings[q] for q in sorted(rankings)}, f, separators=(",", ":"))
    m = receipt["metrics"]
    print(f"\n{name}\n  recall_any@5={m['recall_any@5']} @10={m['recall_any@10']}  recall_all@5={m['recall_all@5']} "
          f"@10={m['recall_all@10']}  nDCG@10={m['ndcg@10']}\n  by type (any@5): {m['recall_any@5_by_type']}\n  "
          f"search p50={receipt['latency_ms']['p50']} ms  deterministic={deterministic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
