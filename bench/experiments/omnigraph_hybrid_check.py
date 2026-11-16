"""Hybrid diagnostic using transformed Omnigraph L2 candidates and shared CC."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
sys.path[:0] = [str(BENCH), str(BENCH / "competitors"), str(BENCH / "experiments")]
import fetch  # noqa: E402
import metrics  # noqa: E402
from matched_engine import MatchedEngine, combine, INPUTS, POOL  # noqa: E402
from omnigraph_exact_check import cli, EXE  # noqa: E402


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=("syntec", "nfcorpus", "scifact", "alloprof", "mix-fr-en"))
    args = parser.parse_args()
    storage = BENCH / "work/storage/omnigraph-0.15.0"
    suffix = "-transformed-batched-check" if args.dataset == "mix-fr-en" else "-transformed-main-check"
    source = storage / (args.dataset + suffix)
    output = storage / (args.dataset + "-hybrid-check")
    output.mkdir(exist_ok=False)
    source_result = json.loads((source / "result.json").read_text(encoding="utf-8"))
    folder = INPUTS / args.dataset
    if source_result["input_meta_sha256"] != digest(folder / "meta.json") or source_result["exe_sha256"] != digest(EXE):
        raise RuntimeError("Input or Omnigraph binary differs from transformed graph")
    radius2 = source_result["radius_squared"]
    dim = source_result["vector_dimension_after"]
    query_file = output / "query.gq"
    query_file.write_text(f"query nearest_chunks($q: Vector({dim})) {{\n match {{ $d: Chunk }}\n"
                          " return { $d.chunk, nearest($d.embedding, $q) as distance }\n"
                          f" order {{ nearest($d.embedding, $q) }}\n limit {POOL}\n}}\n", encoding="utf-8")
    cli("lint", "--schema", source / "schema.pg", "--query", query_file)
    engine = MatchedEngine()
    try:
        corpus, queries, qrels = fetch.load(args.dataset, "test")
        engine.prepare(args.dataset, corpus)
        query_ids = list(engine.queries)[:100]
        reference = {qid: engine.search(qid, queries[qid], 20) for qid in query_ids}
        runs = []
        for _ in range(2):
            ranked = {}
            for index, qid in enumerate(query_ids):
                text, qvec = engine.queries[qid]
                expected_params = np.asarray(json.loads((source / f"params-{index:03}.json").read_text())["q"][:-1], dtype=np.float32)
                if not np.array_equal(expected_params, qvec):
                    raise RuntimeError(f"Frozen query vector differs: {qid}")
                query = " ".join(dict.fromkeys(re.findall(r"[^\W_]+", text.lower())))
                hits = engine.searcher.search(engine.index.parse_query(query, ["text"]), POOL).hits if query else []
                lexical = [(engine.searcher.doc(addr)["chunk_id"][0], score) for score, addr in hits]
                raw = json.loads(cli("query", "--target", source / "graph.omni", "--query", query_file,
                                     "--params-file", source / f"params-{index:03}.json", "--json"))
                if raw.get("ranking", {}).get("exhaustive") is not True:
                    raise RuntimeError("Non-exhaustive Omnigraph query")
                query_norm2 = float(np.sum(qvec.astype(np.float64) ** 2))
                dense = [(int(row["d.chunk"]), (radius2 + query_norm2 - float(row["distance"])) / 2) for row in raw["rows"]]
                ordered = combine(lexical, dense, 2 * POOL)
                docs = engine._fetch(ordered)
                seen, ranking = set(), []
                for chunk_id in ordered:
                    doc = docs.get(chunk_id)
                    if doc is not None and doc not in seen:
                        seen.add(doc)
                        ranking.append(doc)
                        if len(ranking) == 20:
                            break
                ranked[qid] = ranking
            runs.append(ranked)
        judged = {qid: qrels[qid] for qid in query_ids}
        result = {"dataset": args.dataset, "queries": len(query_ids), "chunks": len(engine.ids),
                  "input_meta_sha256": digest(folder / "meta.json"), "runner_sha256": digest(Path(__file__)),
                  "reference_metrics": metrics.evaluate(reference, judged), "omnigraph_metrics": metrics.evaluate(runs[0], judged),
                  "rankings_differ_from_reference": sum(reference[q] != runs[0][q] for q in query_ids),
                  "repeat_rankings_differ": sum(runs[0][q] != runs[1][q] for q in query_ids),
                  "scope": "100 queries; transformed L2 candidates, shared SQLite IDs, Tantivy and CC; no timing claim"}
        (output / "rankings.json").write_text(json.dumps({"reference": reference, "omnigraph": runs}, ensure_ascii=False), encoding="utf-8")
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
