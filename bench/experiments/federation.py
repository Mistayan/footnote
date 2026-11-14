"""Federation test (docs/FEDERATION-DESIGN.md, section 6): one corpus split into N team indexes behind a router, against one index.

    bench/.labenv/Scripts/python.exe -I bench/experiments/federation.py --dataset mix-fr-en --output bench/work/federation-mix.json

Same lab configuration as the shipped pair and the same stored vectors. The only difference is the split: every index keeps
its own keyword statistics (word rarity, average length). Vector scores and their normalisation are the single index's, which
a router reproduces exactly from per-index totals. Speed: the slowest index's work plus the merge, against one index.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BENCH), str(BENCH / "lab"), str(Path(__file__).resolve().parent)]
import fetch  # noqa: E402
import metrics  # noqa: E402
from lab import Bm25, LabEngine, doc_scores, fuse  # noqa: E402

BASE = "M0 shipped pair: bekko-a8m + gte-small"


def shipped_cfg(dataset: str) -> dict:
    rows = [json.loads(x) for x in (BENCH / "sweeps/models2.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if r["dataset"] == dataset and r["split"] == "dev" and r["label"] == BASE][-1]["cfg"]


def random_split(doc_ids: list[str], n: int) -> np.ndarray:
    return np.array([int(hashlib.sha256(d.encode()).hexdigest(), 16) % n for d in doc_ids])


def topic_split(doc_vectors: np.ndarray, n: int, seed: int = 20261114, rounds: int = 25) -> np.ndarray:
    """K-means on document vectors: indexes grouped by subject (and, in a mixed corpus, mostly by language)."""
    rng = np.random.default_rng(seed)
    centers = doc_vectors[rng.choice(len(doc_vectors), n, replace=False)]
    for _ in range(rounds):
        label = np.argmax(doc_vectors @ centers.T, axis=1)
        for k in range(n):
            members = doc_vectors[label == k]
            if len(members):
                c = members.mean(axis=0)
                centers[k] = c / max(float(np.linalg.norm(c)), 1e-12)
    return np.argmax(doc_vectors @ centers.T, axis=1)


class Federated(LabEngine):
    """The lab engine with its keyword side split into per-index BM25s; everything else unchanged."""

    def federate(self, doc_shard: np.ndarray, base: LabEngine) -> None:
        self.__dict__.update({k: v for k, v in base.__dict__.items() if k not in ("bm25",)})
        ends = np.append(self.starts[1:], len(self.texts))
        chunk_shard = np.repeat(doc_shard, ends - self.starts)
        toks = [self.tokenize(t) for t in self._lex_texts(base)]
        self.shards = []
        for s in range(int(doc_shard.max()) + 1):
            rows = np.flatnonzero(chunk_shard == s)
            if len(rows):
                lex = self.cfg["lexical"]
                self.shards.append((rows, Bm25([toks[i] for i in rows], lex["k1"], lex["b"])))
        self.doc_shard = doc_shard

    @staticmethod
    def _lex_texts(base: LabEngine) -> list[str]:
        return base.lex_texts

    shared = False  # True: the router sums each searched index's counts so every index scores with the same statistics

    def _lexical(self, text: str) -> np.ndarray:
        q = self.tokenize(text)
        out = np.zeros(len(self.texts), dtype=np.float32)
        if not self.shared:
            for rows, bm in self.shards:
                out[rows] = bm.scores(q)
            return out
        # Per query: each index returns its document count, total length and, per query word, how many documents hold it.
        n = sum(bm.n for _, bm in self.shards)
        avgdl = sum(float(bm.dl.sum()) for _, bm in self.shards) / max(n, 1)
        df = {t: sum(len(bm.post[t][0]) for _, bm in self.shards if t in bm.post) for t in set(q)}
        for rows, bm in self.shards:
            norm = bm.k1 * (1 - bm.b + bm.b * bm.dl / avgdl)
            s = np.zeros(bm.n, dtype=np.float32)
            for t in set(q):
                p = bm.post.get(t)
                if p is None:
                    continue
                d, tf = p
                idf = np.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s[d] += idf * (tf * (bm.k1 + 1)) / (tf + norm[d])
            out[rows] = s
        return out

    def route(self, text: str, k: int, allowed: set[int]) -> list[str]:
        """Permission step: only the allowed indexes are searched; nothing from another index can be returned."""
        where = {d: int(s) for d, s in zip(self.doc_ids, self.doc_shard)}
        ranked = self.search_ids(text, len(self.doc_ids))
        return [d for d in ranked if where[d] in allowed][:k]

    def search_ids(self, text: str, k: int) -> list[str]:
        return self.search("q", text, k)


def evaluate(engine: LabEngine, qids: list[str], queries: dict, k: int = 100) -> dict:
    return {q: engine.search(q, queries[q], k) for q in qids}


def timing(single: LabEngine, fed: Federated, texts: list[str]) -> dict:
    """p95 of one index's lexical+dense work, against the slowest federated index's work plus the merge."""
    one, split = [], []
    for t in texts:
        q = single.tokenize(t)
        qv = single._qcache[t]
        s = time.perf_counter()
        lex = doc_scores(single.bm25.scores(q), single.starts)
        den = doc_scores(single.emb @ qv, single.starts)
        fuse(lex, den, single.cfg["fusion"], 100)
        one.append(time.perf_counter() - s)
        worst = 0.0
        for rows, bm in fed.shards:
            s = time.perf_counter()
            bm.scores(q)
            fed.emb[rows] @ qv
            worst = max(worst, time.perf_counter() - s)
        s = time.perf_counter()
        fuse(lex, den, fed.cfg["fusion"], 100)  # the router's merge over pooled candidates
        split.append(worst + time.perf_counter() - s)
    p = lambda xs: float(np.percentile(np.array(xs) * 1000, 95))
    return {"single_p95_ms": round(p(one), 2), "federated_p95_ms": round(p(split), 2), "ratio": round(p(split) / p(one), 3)}


def paired(a: dict, b: dict, qrels: dict, resamples: int = 10000) -> dict:
    qids = sorted(a)
    delta = [metrics.ndcg_at_k(b[q], qrels[q], 10) - metrics.ndcg_at_k(a[q], qrels[q], 10) for q in qids]
    rng = random.Random(20261114)
    dist = sorted(sum(rng.choices(delta, k=len(delta))) / len(delta) for _ in range(resamples))
    return {"delta": round(sum(delta) / len(delta), 5), "ci95": [round(dist[int(.025 * resamples)], 5), round(dist[int(.975 * resamples)], 5)]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="mix-fr-en")
    ap.add_argument("--sizes", default="4,16,48")
    ap.add_argument("--timing-queries", type=int, default=500)
    ap.add_argument("--shared-stats", action="store_true", help="the first fix: indexes score with statistics summed by the router")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    corpus, queries, qrels = fetch.load(args.dataset, "test")
    qids = sorted(q for q in queries if q in qrels and any(v > 0 for v in qrels[q].values()))
    single = LabEngine("federation-single", shipped_cfg(args.dataset))
    info = single.prepare(args.dataset, corpus)
    # keep the keyword texts the base engine indexed, so every split tokenizes exactly the same chunks
    ccfg, boost = single.cfg["chunker"], single.cfg["lexical"]["title_boost"]
    from lab import chunk
    single.lex_texts = [(f"{corpus[d][0]} " * (boost - 1) + part) if (boost > 1 and j == 0 and corpus[d][0]) else part
                        for d in single.doc_ids for j, part in enumerate(chunk(corpus[d][0], corpus[d][1], ccfg))]
    assert len(single.lex_texts) == len(single.texts)
    single.warm_queries([queries[q] for q in qids])
    base_rank = evaluate(single, qids, queries)
    base_ndcg = float(np.mean([metrics.ndcg_at_k(base_rank[q], qrels[q], 10) for q in qids]))
    doc_vectors = single.emb[single.starts] / np.maximum(np.linalg.norm(single.emb[single.starts], axis=1, keepdims=True), 1e-12)
    report = {"dataset": args.dataset, "queries": len(qids), "documents": info["documents"], "chunks": info["chunks"],
              "single_ndcg10": round(base_ndcg, 4), "runs": []}
    print(json.dumps({k: report[k] for k in ("dataset", "queries", "documents", "chunks", "single_ndcg10")}), flush=True)
    timing_texts = [queries[q] for q in qids[: args.timing_queries]]
    for split in ("random", "topic"):
        for n in [int(x) for x in args.sizes.split(",")]:
            shard = random_split(single.doc_ids, n) if split == "random" else topic_split(doc_vectors, n)
            fed = Federated("federation", single.cfg)
            fed.federate(shard, single)
            fed.shared = args.shared_stats
            rank = evaluate(fed, qids, queries)
            sizes = np.bincount(shard, minlength=n)
            row = {"split": split, "indexes": n, "docs_per_index_min_max": [int(sizes.min()), int(sizes.max())],
                   "ndcg10": round(float(np.mean([metrics.ndcg_at_k(rank[q], qrels[q], 10) for q in qids])), 4),
                   "vs_single": paired(base_rank, rank, qrels), "speed": timing(single, fed, timing_texts)}
            report["runs"].append(row)
            print(json.dumps(row), flush=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
