"""Retrieval metrics, fixed by protocol v1. Stdlib only.

nDCG uses linear gain (gain = relevance label) and a log2 discount, with the ideal DCG built from the
positive qrels, which is what pytrec_eval's `ndcg_cut` computes for BEIR. Queries without any positive
qrel are not scored (BEIR convention). A ranking shorter than k is scored as is (missing slots count zero).
"""
from __future__ import annotations

import math


def _positives(qrels: dict[str, int]) -> dict[str, int]:
    return {d: r for d, r in qrels.items() if r > 0}


def dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranking: list[str], qrels: dict[str, int], k: int) -> float:
    pos = _positives(qrels)
    if not pos:
        raise ValueError("query has no positive judgment")
    gains = [float(pos.get(d, 0)) for d in ranking[:k]]
    ideal = sorted(pos.values(), reverse=True)[:k]
    return dcg(gains) / dcg([float(g) for g in ideal])


def recall_at_k(ranking: list[str], qrels: dict[str, int], k: int) -> float:
    pos = _positives(qrels)
    if not pos:
        raise ValueError("query has no positive judgment")
    return len(set(ranking[:k]) & set(pos)) / len(pos)


def mrr_at_k(ranking: list[str], qrels: dict[str, int], k: int) -> float:
    pos = _positives(qrels)
    if not pos:
        raise ValueError("query has no positive judgment")
    for i, d in enumerate(ranking[:k]):
        if d in pos:
            return 1.0 / (i + 1)
    return 0.0


def dedupe(ranking: list[str]) -> list[str]:
    """Keep the first occurrence of each document (several chunks of one document collapse to its best rank)."""
    seen: set[str] = set()
    out: list[str] = []
    for d in ranking:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def evaluate(rankings: dict[str, list[str]], qrels: dict[str, dict[str, int]]) -> dict:
    """Mean metrics over every query that has a positive judgment. Unanswered queries score zero."""
    scored = [q for q, r in qrels.items() if any(v > 0 for v in r.values())]
    if not scored:
        raise ValueError("no query with a positive judgment")
    out: dict[str, float] = {}
    def mean(fn) -> float:
        return sum(fn(dedupe(rankings.get(q, [])), qrels[q]) for q in scored) / len(scored)
    out["ndcg@10"] = mean(lambda r, j: ndcg_at_k(r, j, 10))
    for k in (5, 10, 20):
        out[f"recall@{k}"] = mean(lambda r, j, k=k: recall_at_k(r, j, k))
    out["mrr@10"] = mean(lambda r, j: mrr_at_k(r, j, 10))
    out["queries_scored"] = len(scored)
    out["queries_empty"] = sum(1 for q in scored if not rankings.get(q))
    return out


def recall_any_all_at_k(ranking: list[str], qrels: dict[str, int], k: int) -> tuple[float, float]:
    """LongMemEval retrieval metrics: (any = at least one answer session in the top k, all = every answer session in the top k)."""
    pos = set(_positives(qrels))
    if not pos:
        raise ValueError("query has no positive judgment")
    hit = pos & set(ranking[:k])
    return float(bool(hit)), float(hit == pos)
