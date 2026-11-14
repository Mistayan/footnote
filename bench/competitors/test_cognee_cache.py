"""Cache key for built Cognee indexes: shared by dense and lexical, changed by anything that changes the index."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cognee_engine as ce  # noqa: E402

PINS = {"cognee": "1.6.8", "fastembed": "0.7", "lancedb": "0.25"}
CORPUS = {"b": ("", "two"), "a": ("T", "one")}


class IndexKey(unittest.TestCase):
    def key(self, **kw):
        args = {"versions": PINS, "embedder": ce.CogneeEngine.embedder, "chunk_tokens": 512, "corpus": CORPUS} | kw
        return ce.index_key(**args)

    def test_dense_and_lexical_share_one_index(self):
        self.assertEqual(ce.CogneeEngine.embedder, ce.CogneeLexical.embedder)
        self.assertEqual(self.key(), self.key(corpus=dict(reversed(CORPUS.items()))))  # insertion order is irrelevant

    def test_anything_that_changes_the_index_changes_the_key(self):
        base = self.key()
        for change in ({"embedder": ce.CogneeMultilingual.embedder}, {"chunk_tokens": 256},
                       {"versions": PINS | {"cognee": "1.6.9"}}, {"corpus": CORPUS | {"a": ("T", "one!")}}):
            self.assertNotEqual(base, self.key(**change), change)


if __name__ == "__main__":
    unittest.main()
