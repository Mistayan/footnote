"""Check a dot-to-L2 vector transformation against frozen Syntec inputs."""
import hashlib
import json
import argparse
from pathlib import Path
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench"
EXE = BENCH / "work/storage/omnigraph-0.15.0/unpacked/omnigraph.exe"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def cli(*args):
    result = subprocess.run(["rtk", "proxy", str(EXE), *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Omnigraph command failed {args}: {result.stderr}\n{result.stdout}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=("nfcorpus", "scifact", "alloprof", "mix-fr-en"))
    parser.add_argument("--batched", action="store_true")
    args = parser.parse_args()
    inputs = BENCH / "work/matched-inputs" / args.dataset
    out = BENCH / "work/storage/omnigraph-0.15.0" / (args.dataset + ("-transformed-batched-check" if args.batched else "-transformed-main-check"))
    meta = json.loads((inputs / "meta.json").read_text(encoding="utf-8"))
    for name, expected in meta["files_sha256"].items():
        if digest(inputs / name) != expected:
            raise RuntimeError(f"Input hash mismatch: {name}")
    rows = json.loads((inputs / "documents.json").read_text(encoding="utf-8"))
    vectors = np.load(inputs / "vectors.npy", allow_pickle=False)
    queries = np.load(inputs / "queries.npy", allow_pickle=False)[:100]
    ids = np.asarray([row["chunk_id"] for row in rows], dtype=np.int64)
    if len(set(ids)) != len(rows) or vectors.shape != (len(rows), meta["dimension"]):
        raise RuntimeError("Unexpected input dimensions or IDs")
    out.mkdir(exist_ok=False)
    graph = out / "graph.omni"
    schema = out / "schema.pg"
    query = out / "query.gq"
    data = out / "data.jsonl"
    dim = int(vectors.shape[1]) + 1
    schema.write_text(f"node Chunk {{ chunk: I64\n embedding: Vector({dim})\n}}\n", encoding="utf-8")
    query.write_text(f"query nearest_chunks($q: Vector({dim})) {{\n match {{ $d: Chunk }}\n"
                     " return { $d.chunk, nearest($d.embedding, $q) as distance }\n"
                     " order { nearest($d.embedding, $q) }\n limit 10\n}\n", encoding="utf-8")
    norm2 = np.sum(vectors.astype(np.float64) ** 2, axis=1)
    radius2 = float(norm2.max() + 1.0)
    transformed = np.column_stack((vectors, np.sqrt(radius2 - norm2))).astype(np.float32)
    with data.open("w", encoding="utf-8") as f:
        for chunk_id, vector in zip(ids, transformed):
            f.write(json.dumps({"type": "Chunk", "id": str(chunk_id),
                                "data": {"chunk": int(chunk_id), "embedding": vector.tolist()}}) + "\n")
    cli("lint", "--schema", schema, "--query", query)
    cli("init", "--schema", schema, graph)
    # Only an isolated, newly-created, disposable benchmark graph. The separate
    # branch attempt failed on this Windows build and its evidence is preserved.
    if args.batched:
        with data.open("r", encoding="utf-8") as source:
            batch = []
            batch_index = 0
            for line in source:
                batch.append(line)
                if len(batch) == 4096:
                    path = out / f"batch-{batch_index:03}.jsonl"
                    path.write_text("".join(batch), encoding="utf-8")
                    cli("load", "--target", graph, "--data", path, "--mode", "append", "--json")
                    batch.clear()
                    batch_index += 1
            if batch:
                path = out / f"batch-{batch_index:03}.jsonl"
                path.write_text("".join(batch), encoding="utf-8")
                cli("load", "--target", graph, "--data", path, "--mode", "append", "--json")
    else:
        cli("load", "--target", graph, "--data", data, "--mode", "append", "--json")
    mismatches, outputs = [], []
    for index, vector in enumerate(queries):
        params = out / f"params-{index:03}.json"
        params.write_text(json.dumps({"q": [*vector.tolist(), 0.0]}), encoding="utf-8")
        raw = json.loads(cli("query", "--target", graph, "--query", query,
                             "--params-file", params, "--json"))
        if raw.get("ranking", {}).get("exhaustive") is not True:
            raise RuntimeError("Omnigraph did not report exhaustive ranking")
        actual = [r["d.chunk"] for r in raw["rows"]]
        scores = vectors @ vector
        expected = ids[np.lexsort((ids, -scores))[:10]].tolist()
        outputs.append({"expected": expected, "actual": actual, "rows": raw["rows"]})
        if expected != actual:
            mismatches.append(index)
    overlaps = [len(set(x["expected"]) & set(x["actual"])) / 10 for x in outputs]
    result = {"dataset": args.dataset, "queries": len(queries), "chunks": len(rows), "radius_squared": radius2,
              "vector_dimension_before": int(vectors.shape[1]), "vector_dimension_after": dim,
              "ordered_top10_mismatch_queries": mismatches, "top10_mean_overlap": float(np.mean(overlaps)),
              "top10_min_overlap": min(overlaps), "input_meta_sha256": digest(inputs / "meta.json"),
              "runner_sha256": digest(Path(__file__)), "exe_sha256": digest(EXE),
              "scope": "transformed dot-to-L2 exact dense check; 100 queries; no timing claim"}
    (out / "rankings.json").write_text(json.dumps(outputs), encoding="utf-8")
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
