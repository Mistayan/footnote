"""Convert an MTEB-style parquet retrieval dataset (corpus/queries/qrels) to BEIR-style JSONL/TSV. Run through `uv run --with pyarrow`."""
import csv
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

src, out = Path(sys.argv[1]), Path(sys.argv[2])
def rows(sub: str):
    return pq.read_table(next((src / sub).glob("*.parquet"))).to_pylist()

with (out / "corpus.jsonl").open("w", encoding="utf-8", newline="\n") as f:
    for r in rows("corpus"):
        f.write(json.dumps({"_id": r["_id"], "title": r.get("title") or "", "text": r.get("text") or ""}, ensure_ascii=False) + "\n")
with (out / "queries.jsonl").open("w", encoding="utf-8", newline="\n") as f:
    for r in rows("queries"):
        f.write(json.dumps({"_id": r["_id"], "text": r["text"]}, ensure_ascii=False) + "\n")
with (out / "qrels.tsv").open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n")
    for r in rows("qrels"):
        w.writerow([r["query-id"], r["corpus-id"], int(r["score"])])
print("converted", {sub: len(rows(sub)) for sub in ("corpus", "queries", "qrels")})
