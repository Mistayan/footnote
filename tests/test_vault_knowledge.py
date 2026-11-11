"""Owned manifest importer tests; no access to the personal vault."""
import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path

class ManifestSafety(unittest.TestCase):
    def test_recursive_paths_and_denied_paths(self):
        core = importlib.import_module('tools.vault_knowledge.core')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(core.source_path(root, 'nested/note.md'), root/'nested/note.md')
            for name in ('../x.md', '/x.md', 'C:/x.md', 'a\\x.md', '.git/config', '.env', 'nested/credentials.json', 'a/../b.md', 'a:stream.md'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    core.source_path(root, name)

class SourceRevalidation(unittest.TestCase):
    def test_import_read_rejects_hardlinks_repositories_and_secret_content(self):
        import os
        from tools.vault_knowledge.core import Vault
        from tools.vault_migration_inventory import SECRET
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            vault = Vault.__new__(Vault)
            vault.root = root
            vault.max_file_bytes = 1024*1024
            (root/'.git').mkdir()
            (root/'root-note.md').write_text('authorized vault root')
            self.assertEqual(vault.read('root-note.md'), b'authorized vault root')
            (root/'a.md').write_text('safe content')
            os.link(root/'a.md', root/'hard.md')
            with self.assertRaisesRegex(ValueError, 'hardlink'):
                vault.read('a.md')
            project = root/'project';project.mkdir();(project/'.git').mkdir()
            (project/'note.md').write_text('safe content')
            with self.assertRaisesRegex(ValueError, 'repository'):
                vault.read('project/note.md')
            (root/'ordinary.md').write_text('password = synthetic-test-value')
            with self.assertRaisesRegex(ValueError, 'secret'):
                vault.read('ordinary.md')

if __name__ == '__main__': unittest.main()
