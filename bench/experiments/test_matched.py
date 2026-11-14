"""Actual backend smoke checks and matched-input integrity boundaries."""
import hashlib
import contextlib
import io
import json
from pathlib import Path
import struct
import sqlite3
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(BENCH / "lab"))
sys.path.insert(0, str(BENCH / "competitors"))
sys.path.insert(0, str(BENCH / "dbbake"))
import matched_engine as engines
import matched_inputs
from matched_inputs import decode
from lab import fuse, merge, DEFAULT
from track_a import LanceFts
from track_a_scale import Lazy


class MatchedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "inputs/toy"
        self.folder.mkdir(parents=True)
        self.rows = [{"chunk_id": 1, "doc_id": "apple", "text": "fresh red apple"},
                     {"chunk_id": 2, "doc_id": "apple", "text": "apple tree"},
                     {"chunk_id": 3, "doc_id": "pear", "text": "fresh green pear"}]
        self.corpus = {"apple": ("", "fresh red apple\napple tree"), "pear": ("", "fresh green pear")}
        (self.folder / "documents.json").write_text(json.dumps(self.rows), encoding="utf-8")
        (self.folder / "queries.json").write_text(json.dumps([["a", "apple"], ["p", "pear"]]), encoding="utf-8")
        np.save(self.folder / "vectors.npy", np.array([[1, 0], [1, 0], [0, 1]], dtype=np.float32))
        np.save(self.folder / "queries.npy", np.array([[1, 0], [0, 1]], dtype=np.float32))
        self.meta = {"dataset": "toy", "split": "test", "dataset_pin": {"sha256": "toy"}, "dimension": 2,
                     "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.folder.iterdir()}}
        (self.folder / "meta.json").write_text(json.dumps(self.meta), encoding="utf-8")
        for target, value in (("INPUTS", self.root / "inputs"), ("WORK", self.root / "work")):
            patcher = patch.object(engines, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        pin = patch.object(engines.fetch, "dataset_pin", return_value=self.meta["dataset_pin"])
        pin.start()
        self.addCleanup(pin.stop)

    def test_real_backends_rank_and_roundtrip_identical_inputs(self):
        baseline = None
        for engine_class in engines.ENGINES.values():
            with self.subTest(engine=engine_class.id):
                engine = engine_class()
                info = engine.prepare("toy", self.corpus)
                self.assertGreater(info["store_bytes"], 0)
                self.assertEqual(engine._fetch([1, 2, 3]), {1: "apple", 2: "apple", 3: "pear"})
                self.assertEqual(engine.search("a", "apple", 2), ["apple", "pear"])
                self.assertEqual(engine.search("p", "pear", 2), ["pear", "apple"])
                self.assertEqual(engine.search("a", "apple", 2), ["apple", "pear"])
                with self.assertRaisesRegex(ValueError, "query text differs"):
                    engine.search("a", "pear", 2)
                if engine.lexical == "tantivy":
                    np.testing.assert_array_equal(engine.vectors, np.array([[1, 0], [1, 0], [0, 1]], dtype=np.float32))
                    ranking = engine.search("a", "apple", 2)
                    if baseline is not None:
                        self.assertEqual(ranking, baseline)
                    baseline = ranking
                else:
                    hits = engine.table.search([1., 0.], vector_column_name="vector").metric("dot").bypass_vector_index().limit(3).to_list()
                    self.assertAlmostEqual(hits[0]["_distance"], 0.)
                    self.assertAlmostEqual(hits[-1]["_distance"], 1.)
                engine.close()

    def test_tampered_artifact_fails_before_build(self):
        (self.folder / "queries.json").write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "input hash mismatch"):
            engines.MatchedEngine().prepare("toy", self.corpus)
        self.assertFalse((self.root / "work").exists())

    def test_lancedb_lexical_scale_accepts_the_shared_lazy_corpus(self):
        folder = self.root / "lazy-lance"
        folder.mkdir()
        with patch("track_a.tempfile.mkdtemp", return_value=str(folder)):
            engine = LanceFts(True, "English")
        corpus = Lazy([["apple", "tree", "fresh", "fruit"]], 5)
        engine.build(corpus)
        self.assertEqual(engine.t.count_rows(), 5)
        self.assertEqual(set(engine.search("apple", 10)), {f"d{i}" for i in range(5)})

    def test_native_fts_add_edit_delete_before_and_after_optimize(self):
        engine = engines.LanceCC()
        engine.prepare("toy", self.corpus)
        table = engine.table

        def matches(text):
            return [row["chunk_id"] for row in table.search(text, query_type="fts", fts_columns="text")
                    .select(["chunk_id", "_score"]).limit(10).to_list()]

        table.add([{"chunk_id": 4, "doc_id": "new", "text": "quinceunique", "vector": [0., 1.]}])
        self.assertEqual(matches("quinceunique"), [4])
        table.update(where="chunk_id=4", values={"text": "plumunique"})
        self.assertEqual(matches("quinceunique"), [])
        self.assertEqual(matches("plumunique"), [4])
        table.optimize()
        self.assertEqual(matches("plumunique"), [4])
        table.delete("chunk_id=4")
        self.assertEqual(matches("plumunique"), [])
        table.optimize()
        self.assertEqual(matches("plumunique"), [])
        engine.close()

    def test_cc_matches_existing_lab_rule(self):
        rng = np.random.default_rng(20261113)
        lexical, dense = rng.random(210), rng.random(210)
        lexical[:20] = 0
        lex_ids = np.argsort(-lexical, kind="stable")[:100]
        dense_ids = np.argsort(-dense, kind="stable")[:100]
        actual = engines.combine([(int(i), float(lexical[i])) for i in lex_ids], [(int(i), float(dense[i])) for i in dense_ids], 20)
        cfg = merge(DEFAULT, {"fusion": {"kind": "cc", "norm": "zscore", "alpha": .55}})["fusion"]
        self.assertEqual(actual, fuse(lexical, dense, cfg, 20))
        self.assertEqual(engines.combine([], [(2, -.2), (1, -.4)], 1), [2])

    def test_decode_preserves_source_values_and_rejects_corruption(self):
        blob = struct.pack("<f", 1 / 127) + bytes([127, 0])
        np.testing.assert_allclose(decode(blob, 2), [1, 0])
        for corrupt in (blob[:-1], struct.pack("<f", float("nan")) + bytes([127, 0]), struct.pack("<f", 0) + bytes([127, 0])):
            with self.assertRaises(ValueError):
                decode(corrupt, 2)

    def test_export_reads_source_without_changing_it_and_freezes_query_text(self):
        source = self.root / "work/syntec/ens/k.db"
        source.parent.mkdir(parents=True)
        lock = {"revision": "pinned", "files": {"model.onnx": "model-hash"}}
        manifest = {"repository": "hotchpotch/bekko-embedding-v1-a8m", "revision": "pinned",
                    "files": {"model.onnx": {"sha256": "model-hash"}}}
        with sqlite3.connect(source) as db:
            db.executescript("CREATE TABLE embedding_models(identity,manifest,dimension); CREATE TABLE sources(id,path,status); "
                             "CREATE TABLE chunks(id,source_id,heading,text); CREATE TABLE embeddings(id,kind,model,vector);")
            db.execute("INSERT INTO embedding_models VALUES(?,?,?)", ("model", json.dumps(manifest), 2))
            for key, name, blob in ((1, "apple", bytes([127, 0])), (2, "pear", bytes([0, 127]))):
                db.execute("INSERT INTO sources VALUES(?,?,?)", (key, str(self.root / f"{name}.txt"), "indexed"))
                db.execute("INSERT INTO chunks VALUES(?,?,?,?)", (key, key, "", name))
                db.execute("INSERT INTO embeddings VALUES(?,?,?,?)", (key, "chunk", "model", struct.pack("<f", 1 / 127) + blob))
        db.close()
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        (self.root / "lab").mkdir()
        (self.root / "lab/lab.py").write_text("fixture encoder", encoding="utf-8")
        encoder = SimpleNamespace(embed=lambda texts, kind: np.tile(np.array([[1., 0.]], dtype=np.float32), (len(texts), 1)))
        with patch.object(matched_inputs, "BENCH", self.root), patch.object(matched_inputs, "ROOT", self.root / "export"), \
             patch.object(matched_inputs.fetch, "load", return_value=(self.corpus, {"q": "é" * 400}, {})), \
             patch.object(matched_inputs.models, "lock_entry", return_value=lock), \
             patch.object(matched_inputs, "Encoder", return_value=encoder), \
             patch("sys.argv", ["matched_inputs", "syntec"]), contextlib.redirect_stdout(io.StringIO()):
            matched_inputs.main()
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                matched_inputs.main()
        exported = self.root / "export/syntec"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)
        self.assertEqual(json.loads((exported / "queries.json").read_text(encoding="utf-8")), [["q", "é" * 250]])
        np.testing.assert_allclose(np.load(exported / "vectors.npy"), [[1, 0], [0, 1]])
        metadata = json.loads((exported / "meta.json").read_text(encoding="utf-8"))
        for name, digest in metadata["files_sha256"].items():
            self.assertEqual(hashlib.sha256((exported / name).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
