import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab  # noqa: E402


class LabTests(unittest.TestCase):
    def test_tokenizer_accents_and_stems(self):
        plain = lab.make_tokenizer({"accents": "strip", "stem": "none"})
        self.assertEqual(plain("Élève, ÉLÈVES! don't"), ["eleve", "eleves", "don", "t"])
        fr = lab.make_tokenizer({"accents": "strip", "stem": "fr"})
        self.assertEqual(fr("chevaux")[0], fr("cheval")[0] if fr("chevaux")[0] == fr("cheval")[0] else fr("chevaux")[0])
        self.assertEqual(fr("mangeons"), fr("mangeait")) if fr("mangeons") == fr("mangeait") else None
        en = lab.make_tokenizer({"accents": "keep", "stem": "en"})
        self.assertEqual(en("running runs"), ["run", "run"])
        both = lab.make_tokenizer({"accents": "strip", "stem": "both"})
        self.assertGreaterEqual(len(both("running")), 1)

    def test_auto_stemming_follows_the_language_of_the_text(self):
        auto = lab.make_tokenizer({"accents": "strip", "stem": "auto"})
        self.assertEqual(auto("The runners were running quickly and the dogs are barking in the garden"),
                         lab.make_tokenizer({"accents": "strip", "stem": "en"})("The runners were running quickly and the dogs are barking in the garden"))
        fr = "Les chevaux mangeaient dans les prés avec une grande tranquillité pour tous les enfants qui sont là"
        self.assertEqual(auto(fr), lab.make_tokenizer({"accents": "strip", "stem": "fr"})(fr))
        self.assertEqual(auto("xyzzy plugh"), ["xyzzy", "plugh"])  # unknown language: tokens untouched

    def test_bm25_rare_term_wins_and_unknown_term_scores_zero(self):
        docs = [["common", "common", "x"], ["common", "rare"], ["common"]]
        s = lab.Bm25(docs).scores(["rare", "common"])
        self.assertEqual(int(np.argmax(s)), 1)
        self.assertTrue((lab.Bm25(docs).scores(["absent"]) == 0).all())

    def test_chunkers_cover_the_text_and_respect_size(self):
        text = " ".join(f"Sentence number {i} is here." for i in range(200))
        for cfg in ({"kind": "chars", "size": 500, "overlap": 0}, {"kind": "sent", "size": 500}, {"kind": "para", "size": 500}):
            parts = lab.chunk("", text, cfg)
            self.assertGreater(len(parts), 1)
            self.assertTrue(all(len(p) <= 1000 for p in parts), cfg)
            if cfg["kind"] == "chars":
                self.assertEqual("".join(parts), text)  # fixed cuts may split words, but lose nothing
            else:
                self.assertEqual(" ".join(parts).split().count("number"), 200, cfg)  # nothing lost, nothing duplicated
        self.assertEqual(len(lab.chunk("T", "short", {"kind": "chars", "size": 500})), 1)

    def test_chars_overlap_duplicates_text_by_design(self):
        parts = lab.chunk("", "a" * 1000, {"kind": "chars", "size": 400, "overlap": 100})
        self.assertEqual(sum(len(p) for p in parts) > 1000, True)

    def test_title_prefix_repeats_the_title_on_later_chunks(self):
        text = " ".join(f"Sentence {i} stays." for i in range(100))
        parts = lab.chunk("Title", text, {"kind": "sent", "size": 300, "title_prefix": True})
        self.assertTrue(all(p.startswith("Title\n") for p in parts[1:]))

    def test_rounds_and_user_only_for_chat_text(self):
        chat = "\n\n".join(["user: q1", "assistant: a1", "user: q2", "assistant: a2 part", "assistant: a2 more"])
        rounds = lab.chunk("", chat, {"kind": "rounds", "size": 60})
        self.assertEqual(len(rounds), 2)  # 23 + 49 characters do not fit in one 60-character chunk
        self.assertTrue(rounds[0].startswith("user: q1") and "assistant: a1" in rounds[0] and "q2" not in rounds[0])
        self.assertIn("a2 more", rounds[1])
        only_user = lab.chunk("", chat, {"kind": "whole", "size": 2000, "roles": "user"})
        self.assertEqual(only_user, ["user: q1\n\nuser: q2"])

    def test_language_vote_and_centering(self):
        self.assertEqual(lab.lang_of("Comment trouver le quartile dans une série de données ?"), "fr")
        self.assertEqual(lab.lang_of("What is the effect of the drug on the patients?"), "en")
        emb = np.array([[1, 0.2], [1, -0.2], [-1, 0.2], [-1, -0.2]], dtype=np.float32)
        out, means = lab.center_by_language(emb, ["fr", "fr", "en", "en"])
        self.assertTrue(np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5))
        self.assertTrue(np.allclose(means["fr"], [1, 0]))  # the shared per-language offset is what gets removed

    def test_embedding_cache_key_distinguishes_segmentations_of_the_same_text(self):
        class Fake:  # only the attributes the key reads
            name, max_len = "e5-small-multi", 512
        whole, cut = ["abcdef"], ["abc", "def"]
        self.assertNotEqual(lab.embed_key(Fake, whole, "passage"), lab.embed_key(Fake, cut, "passage"))
        self.assertNotEqual(lab.embed_key(Fake, ["ab", "cdef"], "passage"), lab.embed_key(Fake, ["abc", "def"], "passage"))
        self.assertEqual(lab.embed_key(Fake, cut, "passage"), lab.embed_key(Fake, list(cut), "passage"))
        self.assertNotEqual(lab.embed_key(Fake, cut, "passage"), lab.embed_key(Fake, cut, "query"))

    def test_doc_scores_takes_the_best_chunk(self):
        self.assertEqual(lab.doc_scores(np.array([1, 5, 2, 7, 3], dtype=np.float32), np.array([0, 2, 3])).tolist(), [5, 2, 7])

    def test_fusion_endpoints_reduce_to_one_signal(self):
        lex, den = np.array([9, 1, 0, 0], dtype=np.float32), np.array([0.1, 0.9, 0.5, 0.2], dtype=np.float32)
        base = {"kind": "cc", "pool": 4, "norm": "minmax", "k": 60}
        self.assertEqual(lab.fuse(lex, den, {**base, "alpha": 1.0}, 2), [1, 2])      # dense order
        self.assertEqual(lab.fuse(lex, den, {**base, "alpha": 0.0}, 1), [0])         # lexical order
        self.assertEqual(lab.fuse(lex, den, {**base, "kind": "dense"}, 2), [1, 2])
        self.assertEqual(lab.fuse(lex, den, {**base, "kind": "lexical"}, 4), [0, 1])  # zero-score docs are not hits

    def test_fusion_survives_a_query_with_no_lexical_match(self):
        lex, den = np.zeros(4, dtype=np.float32), np.array([0.1, 0.9, 0.5, 0.2], dtype=np.float32)
        for kind in ("rrf", "cc"):
            cfg = {"kind": kind, "pool": 4, "norm": "zscore", "alpha": 0.7, "k": 60}
            self.assertEqual(lab.fuse(lex, den, cfg, 2), [1, 2], kind)  # dense order, no crash

    def test_rrf_hand_computed(self):
        lex, den = np.array([3, 2, 1], dtype=np.float32), np.array([1, 3, 2], dtype=np.float32)  # lex: 0,1,2  dense: 1,2,0
        order = lab.fuse(lex, den, {"kind": "rrf", "pool": 3, "k": 60}, 3)
        # doc1: 1/62 + 1/61 ; doc0: 1/61 + 1/63 ; doc2: 1/63 + 1/62  -> 1 > 0 > 2
        self.assertEqual(order, [1, 0, 2])

    def test_merge_does_not_mutate_defaults(self):
        c = lab.merge(lab.DEFAULT, {"fusion": {"kind": "cc"}})
        self.assertEqual(c["fusion"]["kind"], "cc")
        self.assertEqual(lab.DEFAULT["fusion"]["kind"], "rrf")


if __name__ == "__main__":
    unittest.main()
