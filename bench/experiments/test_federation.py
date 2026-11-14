"""Federation router: permission isolation and per-index keyword statistics, on a tiny keyword-only corpus (no models).

    bench/.labenv/Scripts/python.exe -I bench/experiments/test_federation.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent / "lab"), str(HERE)]
import federation as f  # noqa: E402
from lab import LabEngine  # noqa: E402

CFG = {"dense": {"on": False}, "fusion": {"kind": "lexical"}, "chunker": {"kind": "whole"}}
CORPUS = {
    "hr-1": ("Salaries", "salary review process for HR staff"),
    "hr-2": ("Leave", "parental leave and salary during leave"),
    "eng-1": ("Deploys", "deploy checklist and salary of nobody"),
    "eng-2": ("Incidents", "incident review and postmortem"),
}


def engines():
    base = LabEngine("t", CFG)
    base.prepare("t", CORPUS)
    base.lex_texts = list(base.texts)
    fed = f.Federated("t", CFG)
    shard = np.array([0 if d.startswith("hr") else 1 for d in base.doc_ids])
    fed.federate(shard, base)
    return base, fed


class Router(unittest.TestCase):
    def test_never_returns_a_document_outside_the_allowed_indexes(self):
        _, fed = engines()
        for allowed, prefix in (({0}, "hr"), ({1}, "eng")):
            hits = fed.route("salary review", 10, allowed)
            self.assertTrue(hits, allowed)
            self.assertTrue(all(h.startswith(prefix) for h in hits), hits)
        self.assertEqual(fed.route("salary", 10, set()), [])

    def test_each_index_keeps_its_own_keyword_statistics(self):
        base, fed = engines()
        q = base.tokenize("salary")
        whole = base.bm25.scores(q)
        split = fed._lexical("salary")
        # "salary" is in 2 of 2 HR documents but 1 of 2 engineering ones: per-index rarity differs from the whole corpus
        self.assertFalse(np.allclose(whole, split))
        self.assertTrue((split > 0).sum() == (whole > 0).sum())

    def test_splits_cover_every_document(self):
        ids = [f"d{i}" for i in range(200)]
        s = f.random_split(ids, 16)
        self.assertEqual(len(s), 200)
        self.assertTrue(0 <= s.min() and s.max() < 16)
        vecs = np.random.default_rng(1).normal(size=(200, 8))
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        t = f.topic_split(vecs, 4)
        self.assertEqual(set(np.unique(t)) <= set(range(4)), True)


if __name__ == "__main__":
    unittest.main()
