"""Matched SQLite/Tantivy and LanceDB controls. See experiments/LANCEDB-MATCHED.md.

Run through bench/run.py as ext:matched-*. Query vectors are precomputed and
excluded from latency for every control. Stores retain the same text and vectors.
"""
from __future__ import annotations

import importlib.metadata as md
import json
from pathlib import Path
import re
import sqlite3
import statistics
import tempfile
import time

import numpy as np

from engines import clip, dir_bytes, sha256_file, WORK
import fetch

INPUTS = WORK / "matched-inputs"
POOL = 100


def combine(lexical: list[tuple[int, float]], dense: list[tuple[int, float]], k: int) -> list[int]:
    """Same per-pool standardization and missing-score floor as lab CC."""
    if not lexical:
        return [key for key, _ in dense[:k]]

    def zscores(items):
        values = [value for _, value in items]
        mean, sd = statistics.mean(values), statistics.pstdev(values) or 1.0
        return {key: (value - mean) / sd for key, value in items}

    lexical, dense = zscores(lexical), zscores(dense)
    floor_l, floor_d = min(lexical.values()) - 1e-9, min(dense.values()) - 1e-9
    score = {key: .55 * dense.get(key, floor_d) + .45 * lexical.get(key, floor_l) for key in lexical.keys() | dense.keys()}
    return sorted(score, key=lambda key: (-score[key], key))[:k]


class MatchedEngine:
    store = "sqlite"
    lexical = "tantivy"
    fusion = "cc"
    id = "matched-sqlite-tantivy"
    latency_scope = "resident in-process matched retrieval, precomputed query vector; excludes encoding; includes document-ID fetch"

    def __init__(self):
        self.db = self.table = None
        self.config = {"store": self.store, "lexical": self.lexical, "fusion": self.fusion,
                       "model": "bekko-a8m only, identical precomputed query and passage vectors",
                       "chunking": "identical exported product chunks, 2000 characters",
                       "vectors": "source int8 decoded to float32, dot product, exact; no ANN",
                       "tokenizer": "simple, lowercase, English stem, accent fold, no stopwords, max token 40",
                       "pool": POOL, "alpha": .55, "rrf_k": 60, "query_clip_bytes": 500,
                       "caveat": "component experiment, not the production two-model pipeline; encoding excluded"}

    def versions(self):
        return {"numpy": md.version("numpy"), "lancedb": md.version("lancedb"), "tantivy": md.version("tantivy"),
                "pyarrow": md.version("pyarrow"), "sqlite": sqlite3.sqlite_version,
                "adapter_sha256": sha256_file(Path(__file__)), "input": self.meta}

    def prepare(self, dataset: str, corpus: dict) -> dict:
        folder = INPUTS / dataset
        self.meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if self.meta["dataset"] != dataset or self.meta["split"] != "test" or self.meta["dataset_pin"] != fetch.dataset_pin(dataset):
            raise ValueError("matched input dataset pin differs")
        for name in ("documents.json", "queries.json", "vectors.npy", "queries.npy"):
            if sha256_file(folder / name) != self.meta["files_sha256"][name]:
                raise ValueError(f"matched input hash mismatch: {name}")
        rows = json.loads((folder / "documents.json").read_text(encoding="utf-8"))
        items = json.loads((folder / "queries.json").read_text(encoding="utf-8"))
        vectors = np.load(folder / "vectors.npy", allow_pickle=False)
        qvectors = np.load(folder / "queries.npy", allow_pickle=False)
        self.ids = np.array([row["chunk_id"] for row in rows], dtype=np.int64)
        if (len(set(self.ids)) != len(rows) or {row["doc_id"] for row in rows} != set(corpus)
                or vectors.shape != (len(rows), self.meta["dimension"])
                or qvectors.shape != (len(items), self.meta["dimension"])
                or len({qid for qid, _ in items}) != len(items)
                or not np.isfinite(vectors).all() or not np.isfinite(qvectors).all()):
            raise ValueError("matched input shape, coverage or vector mismatch")
        self.queries = {qid: (text, qvectors[i]) for i, (qid, text) in enumerate(items)}
        WORK.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix=f"{dataset}-{self.id}-", dir=WORK))
        started = time.perf_counter()
        if self.store == "sqlite":
            self.db = sqlite3.connect(self.root / "chunks.db")
            self.db.execute("CREATE TABLE chunks(chunk_id INTEGER PRIMARY KEY,doc_id TEXT NOT NULL,text TEXT NOT NULL,vector BLOB NOT NULL)")
            self.db.executemany("INSERT INTO chunks VALUES(?,?,?,?)",
                                [(row["chunk_id"], row["doc_id"], row["text"], vectors[i].astype("<f4").tobytes()) for i, row in enumerate(rows)])
            self.db.commit()
            self.vectors = np.stack([np.frombuffer(row[0], dtype="<f4") for row in self.db.execute("SELECT vector FROM chunks ORDER BY chunk_id")])
        else:
            import lancedb
            import pyarrow as pa
            self.db = lancedb.connect(str(self.root / "lance"))
            vector_column = pa.FixedSizeListArray.from_arrays(pa.array(vectors.reshape(-1), type=pa.float32()), vectors.shape[1])
            self.table = self.db.create_table("chunks", pa.table({"chunk_id": self.ids, "doc_id": [r["doc_id"] for r in rows],
                                                                 "text": [r["text"] for r in rows], "vector": vector_column}))
            if self.lexical == "native":
                from lancedb.index import FTS
                self.table.create_index("text", config=FTS(base_tokenizer="simple", language="English",
                                        stem=True, remove_stop_words=False, ascii_folding=True, max_token_length=40))
            else:
                stored = sorted(self.table.to_arrow().to_pylist(), key=lambda row: row["chunk_id"])
                self.vectors = np.array([row["vector"] for row in stored], dtype=np.float32)
        if self.lexical == "tantivy":
            import tantivy
            schema = tantivy.SchemaBuilder()
            schema.add_integer_field("chunk_id", stored=True)
            schema.add_text_field("text", stored=False, tokenizer_name="matched", index_option="freq")
            index_folder = self.root / "tantivy"
            index_folder.mkdir()
            self.index = tantivy.Index(schema.build(), path=str(index_folder))
            analyzer = (tantivy.TextAnalyzerBuilder(tantivy.Tokenizer.simple()).filter(tantivy.Filter.remove_long(40))
                        .filter(tantivy.Filter.lowercase()).filter(tantivy.Filter.ascii_fold())
                        .filter(tantivy.Filter.stemmer("english")).build())
            self.index.register_tokenizer("matched", analyzer)
            writer = self.index.writer(heap_size=20_000_000, num_threads=1)
            for row in rows:
                writer.add_document(tantivy.Document(chunk_id=row["chunk_id"], text=row["text"]))
            writer.commit()
            writer.wait_merging_threads()
            self.index.reload()
            self.searcher = self.index.searcher()
        build_ms = (time.perf_counter() - started) * 1000
        store = dir_bytes(self.root)
        return {"documents": len(corpus), "chunks": len(rows), "build_ms": build_ms, "embed_ms": None,
                "input_export_ms": self.meta.get("export_ms"), "disk_bytes": store, "store_bytes": store,
                "sqlite_bytes": dir_bytes(self.root / "chunks.db"), "lancedb_bytes": dir_bytes(self.root / "lance"),
                "tantivy_bytes": dir_bytes(self.root / "tantivy"), "query_encoding_included": False}

    def _fetch(self, ids):
        if not ids:
            return {}
        if self.store == "sqlite":
            placeholders = ",".join("?" for _ in ids)
            return dict(self.db.execute(f"SELECT chunk_id,doc_id FROM chunks WHERE chunk_id IN ({placeholders})", ids))
        return {row["chunk_id"]: row["doc_id"] for row in self.table.search().where(
            "chunk_id IN (" + ",".join(str(int(key)) for key in ids) + ")").select(["chunk_id", "doc_id"]).limit(len(ids)).to_list()}

    def search(self, qid: str, text: str, k: int) -> list[str]:
        expected, query_vector = self.queries[qid]
        if clip(text) != expected:
            raise ValueError("query text differs from the frozen vector input")
        query = " ".join(dict.fromkeys(re.findall(r"[^\W_]+", expected.lower())))
        if self.lexical == "tantivy":
            hits = self.searcher.search(self.index.parse_query(query, ["text"]), POOL).hits if query else []
            lexical = [(self.searcher.doc(address)["chunk_id"][0], score) for score, address in hits]
            scores = self.vectors @ query_vector
            order = np.lexsort((self.ids, -scores))[:POOL]
            dense = [(int(self.ids[i]), float(scores[i])) for i in order]
            ranked = combine(lexical, dense, 2 * POOL)
        else:
            lexical_table = (self.table.search(query, query_type="fts", fts_columns="text").select(["chunk_id", "_score"])
                             .with_row_id(True).limit(POOL).to_arrow()) if query else None
            dense_table = (self.table.search(query_vector, vector_column_name="vector").metric("dot").bypass_vector_index()
                           .select(["chunk_id", "_distance"]).with_row_id(True).limit(POOL).to_arrow())
            if self.fusion == "rrf" and lexical_table is not None:
                from lancedb.rerankers import RRFReranker
                hits = RRFReranker(K=60).rerank_hybrid(query, dense_table, lexical_table).to_pylist()
                ranked = [hit["chunk_id"] for hit in hits]
            else:
                lexical = [(hit["chunk_id"], float(hit["_score"])) for hit in lexical_table.to_pylist()] if lexical_table is not None else []
                dense = [(hit["chunk_id"], 1 - float(hit["_distance"])) for hit in dense_table.to_pylist()]
                ranked = combine(lexical, dense, 2 * POOL)
        documents = self._fetch(ranked)
        out, seen = [], set()
        for key in ranked:
            document = documents.get(key)
            if document is not None and document not in seen:
                out.append(document)
                seen.add(document)
                if len(out) == k:
                    break
        return out

    def close(self):
        if self.store == "sqlite" and self.db is not None:
            self.db.close()
        self.db = self.table = None


class LanceRRF(MatchedEngine):
    id, store, lexical, fusion = "matched-lance-rrf", "lance", "native", "rrf"


class LanceCC(MatchedEngine):
    id, store, lexical = "matched-lance-cc", "lance", "native"


class LanceTantivy(MatchedEngine):
    id, store = "matched-lance-tantivy", "lance"


ENGINES = {engine.id: engine for engine in (MatchedEngine, LanceRRF, LanceCC, LanceTantivy)}
