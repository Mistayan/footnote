"""The version rule's arithmetic (docs/VERSIONING.md): `python scripts/test_next_version.py`."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("next_version", Path(__file__).with_name("next-version.py"))
nv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nv)


class Rule(unittest.TestCase):
    def test_commit_kinds(self):
        self.assertEqual(nv.kind("feat(launcher): glass rework", ""), "feature")
        self.assertEqual(nv.kind("fix(hook): windows paths", ""), "patch")
        self.assertEqual(nv.kind("docs: versioning", ""), "patch")
        self.assertEqual(nv.kind("feat(mcp)!: rename footnote_recall", ""), "breaking")
        self.assertEqual(nv.kind("refactor(store): new schema", "Body.\n\nBREAKING CHANGE: memory.db needs a migration"), "breaking")
        self.assertEqual(nv.kind("Merge pull request #1", ""), "patch")

    def test_bumps_before_one(self):
        self.assertEqual(nv.bump("v0.1.0-alpha.3", ["feature", "patch"]), "0.2.0")
        self.assertEqual(nv.bump("v0.2.0", ["patch"]), "0.2.1")
        self.assertEqual(nv.bump("v0.2.1", ["breaking"]), "0.3.0")
        self.assertIsNone(nv.bump("v0.2.1", []))

    def test_bumps_from_one(self):
        self.assertEqual(nv.bump("v1.4.2", ["breaking", "feature"]), "2.0.0")
        self.assertEqual(nv.bump("v1.4.2", ["feature"]), "1.5.0")
        self.assertEqual(nv.bump("v1.4.2", ["patch", "patch"]), "1.4.3")

    def test_manifests_agree(self):
        found = nv.manifests()
        self.assertTrue(found, "no manifest read")
        self.assertEqual(set(found.values()), {found["Cargo.toml"]}, found)


if __name__ == "__main__":
    unittest.main()
