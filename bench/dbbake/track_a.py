"""Track A, lexical quality across storage engines: same documents, same queries, same metrics, OR semantics, BM25 ranking.

    bench/.dbenv/Scripts/python.exe -I bench/dbbake/track_a.py scifact --split heldout

Each engine runs with the tokenizer settings written next to it. A failing engine is recorded as a failure (a result), not skipped.
Results are appended to bench/dbbake/results.jsonl. Latency is wall time of one query on this machine, single caller, after a warm-up.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import metrics  # noqa: E402

WORD = re.compile(r"\w+", re.UNICODE)


def words(q: str) -> list[str]:
    return list(dict.fromkeys(w.lower() for w in WORD.findall(q)))[:64]


def doc_text(doc) -> str:
    title, text = doc
    return f"{title}\n{text}" if title else text


class Fts5:
    def __init__(self, tok: str):
        self.tok, self.dir = tok, Path(tempfile.mkdtemp(prefix="dbbake-"))

    def build(self, corpus: dict) -> None:
        self.db = sqlite3.connect(self.dir / "i.db")
        self.db.execute(f"CREATE VIRTUAL TABLE t USING fts5(id UNINDEXED, body, tokenize='{self.tok}')")
        self.db.executemany("INSERT INTO t(id, body) VALUES (?, ?)", ((i, doc_text(d)) for i, d in corpus.items()))
        self.db.commit()

    def search(self, q: str, k: int) -> list[str]:
        w = words(q)
        if not w:
            return []
        match = " OR ".join('"' + x + '"' for x in w)
        return [r[0] for r in self.db.execute("SELECT id FROM t WHERE t MATCH ? ORDER BY bm25(t) LIMIT ?", (match, k))]

    def size(self) -> int:
        self.db.close()
        return sum(f.stat().st_size for f in self.dir.iterdir())


class Tantivy:
    def __init__(self, tokenizer: str):
        self.tokenizer, self.dir = tokenizer, Path(tempfile.mkdtemp(prefix="dbbake-"))

    def build(self, corpus: dict) -> None:
        import tantivy
        sb = tantivy.SchemaBuilder()
        sb.add_text_field("id", stored=True, tokenizer_name="raw")
        sb.add_text_field("body", stored=False, tokenizer_name=self.tokenizer)
        self.index = tantivy.Index(sb.build(), path=str(self.dir))
        w = self.index.writer(heap_size=200_000_000, num_threads=1)
        for i, d in corpus.items():
            w.add_document(tantivy.Document(id=i, body=doc_text(d)))
        w.commit()
        self.index.reload()
        self.searcher = self.index.searcher()

    def search(self, q: str, k: int) -> list[str]:
        w = words(q)
        if not w:
            return []
        query = self.index.parse_query(" ".join(w), ["body"])  # default conjunction is OR
        hits = self.searcher.search(query, k).hits
        return [self.searcher.doc(a)["id"][0] for _, a in hits]

    def size(self) -> int:
        return sum(f.stat().st_size for f in self.dir.rglob("*") if f.is_file())


class DuckFts:
    def __init__(self, stemmer: str):
        self.stemmer, self.dir = stemmer, Path(tempfile.mkdtemp(prefix="dbbake-"))

    def build(self, corpus: dict) -> None:
        import duckdb
        self.db = duckdb.connect(str(self.dir / "i.duckdb"))
        self.db.execute("CREATE TABLE docs(id VARCHAR, body VARCHAR)")
        self.db.executemany("INSERT INTO docs VALUES (?, ?)", [(i, doc_text(d)) for i, d in corpus.items()])
        self.db.execute("INSTALL fts; LOAD fts;")
        self.db.execute(f"PRAGMA create_fts_index('docs', 'id', 'body', stemmer='{self.stemmer}', stopwords='none', strip_accents=1, lower=1, overwrite=1)")

    def search(self, q: str, k: int) -> list[str]:
        w = words(q)
        if not w:
            return []
        rows = self.db.execute("SELECT id FROM (SELECT id, fts_main_docs.match_bm25(id, ?, conjunctive := 0) AS s FROM docs) WHERE s IS NOT NULL "
                               "ORDER BY s DESC LIMIT ?", [" ".join(w), k]).fetchall()
        return [r[0] for r in rows]

    def size(self) -> int:
        self.db.close()
        return sum(f.stat().st_size for f in self.dir.iterdir())


class LanceFts:
    def __init__(self, stem: bool, language: str):
        self.stem, self.language, self.dir = stem, language, Path(tempfile.mkdtemp(prefix="dbbake-"))

    def build(self, corpus: dict) -> None:
        import lancedb
        import pyarrow as pa
        self.db = lancedb.connect(str(self.dir))
        items = list(corpus.items())
        tbl = pa.table({"id": [key for key, _ in items], "body": [doc_text(doc) for _, doc in items]})
        self.t = self.db.create_table("t", tbl)
        from lancedb.index import FTS
        self.t.create_index("body", config=FTS(base_tokenizer="simple", language=self.language, stem=self.stem,
                                             remove_stop_words=False, ascii_folding=True))

    def search(self, q: str, k: int) -> list[str]:
        w = words(q)
        if not w:
            return []
        return [r["id"] for r in self.t.search(" ".join(w), query_type="fts").select(["id", "_score"]).limit(k).to_list()]

    def size(self) -> int:
        return sum(f.stat().st_size for f in self.dir.rglob("*") if f.is_file())


ENGINES = {
    "sqlite-fts5 unicode61": lambda: Fts5("unicode61 remove_diacritics 2"),
    "sqlite-fts5 porter": lambda: Fts5("porter unicode61 remove_diacritics 2"),
    "tantivy default": lambda: Tantivy("default"),
    "tantivy en_stem": lambda: Tantivy("en_stem"),
    "tantivy fr_stem": lambda: Tantivy("fr_stem"),
    "duckdb-fts porter": lambda: DuckFts("porter"),
    "duckdb-fts french": lambda: DuckFts("french"),
    "duckdb-fts none": lambda: DuckFts("none"),
    "lancedb-fts nostem": lambda: LanceFts(False, "English"),
    "lancedb-fts english": lambda: LanceFts(True, "English"),
    "lancedb-fts french": lambda: LanceFts(True, "French"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--split", default="heldout")
    ap.add_argument("--only", help="substring filter on engine names")
    args = ap.parse_args()
    corpus, queries, qrels = fetch.load(args.dataset, args.split)
    for name, make in ENGINES.items():
        if args.only and args.only not in name:
            continue
        row = {"track": "A", "dataset": args.dataset, "split": args.split, "engine": name, "documents": len(corpus), "queries": len(queries)}
        eng = make()
        try:
            t0 = time.perf_counter()
            eng.build(corpus)
            row["build_s"] = round(time.perf_counter() - t0, 2)
            qs = list(queries.items())
            for _, q in qs[:10]:
                eng.search(q, 10)
            rankings, times = {}, []
            for qid, q in qs:
                a = time.perf_counter()
                rankings[qid] = metrics.dedupe(eng.search(q, 10))
                times.append((time.perf_counter() - a) * 1000)
            s = metrics.evaluate(rankings, qrels)
            row.update({"ndcg@10": round(s["ndcg@10"], 4), "recall@10": round(s["recall@10"], 4), "empty": s["queries_empty"],
                        "p50_ms": round(statistics.median(times), 2), "p95_ms": round(sorted(times)[int(.95 * (len(times) - 1))], 2),
                        "disk_mb": round(eng.size() / 1e6, 1)})
        except Exception as e:  # a failure is a result
            row["error"] = f"{type(e).__name__}: {e}"[:300]
        finally:
            shutil.rmtree(eng.dir, ignore_errors=True)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        with (HERE / "results.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
