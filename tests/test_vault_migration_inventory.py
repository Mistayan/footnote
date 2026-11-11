"""Synthetic-only, local inventory contract tests."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools/vault_migration_inventory.py'
SCRATCH = Path('C:/Users/johan/AppData/Local/hermes/cache/scratch') if os.name == 'nt' else Path(os.environ.get('TMPDIR', '/tmp'))


def sandbox():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=SCRATCH)


def load_module():
    assert MODULE.exists(), 'inventory implementation missing'
    spec = importlib.util.spec_from_file_location('inventory', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InventoryTests(unittest.TestCase):
    def test_snapshot_hashes_duplicates_and_read_only(self):
        m = load_module()
        with sandbox() as t:
            root = Path(t) / 'source'
            root.mkdir()
            (root / 'a.md').write_text('Synthetic knowledge', encoding='utf-8')
            (root / 'b.txt').write_bytes((root / 'a.md').read_bytes())
            (root / 'scan.pdf').write_bytes(b'%PDF synthetic')
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            out = Path(t) / 'output'
            result = m.inventory(root, out)
            rows = [json.loads(s) for s in (out / 'manifest.jsonl').read_text().splitlines()]
            self.assertEqual(result['status_counts'], {'eligible': 2, 'unsupported': 1})
            self.assertEqual(result['duplicate_groups'], 1)
            self.assertTrue(result['verification']['eligible_hashes_unchanged'])
            self.assertEqual(len([r for r in rows if r.get('sha256')]), 2)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})

    def test_boundaries_secrets_and_formats(self):
        m = load_module()
        with sandbox() as t:
            root = Path(t) / 'source'
            root.mkdir()
            for name, data in {'budget.md': b'Balance 1234.50 EUR',
                               '.env': b'not read', 'passwords.txt': b'not read',
                               'ordinary.md': b'password = synthetic-value',
                               'bad.txt': b'\xff\xfe', 'big.md': b'x' * 300}.items():
                (root / name).write_bytes(data)
            for folder in ['node_modules', '.obsidian', 'project']:
                (root / folder).mkdir()
                (root / folder / 'hidden.md').write_text('not traversed')
            (root / 'project' / '.git').mkdir()
            os.link(root / 'budget.md', root / 'hard.md')
            (root / 'finance.md').write_text('Balance 1234.50 EUR')
            out = Path(t) / 'out'
            m.inventory(root, out, max_bytes=200)
            rows = {r['path']: r for r in map(json.loads, (out / 'manifest.jsonl').read_text().splitlines())}
            for name in ['budget.md', 'hard.md']:
                self.assertEqual(rows[name]['status'], 'skip_hardlink')
            self.assertEqual(rows['finance.md']['status'], 'eligible')
            self.assertEqual(rows['.env']['status'], 'skip_sensitive_name')
            self.assertEqual(rows['passwords.txt']['status'], 'skip_sensitive_name')
            self.assertEqual(rows['ordinary.md']['status'], 'quarantine_secret')
            self.assertEqual(rows['bad.txt']['status'], 'encoding_error')
            self.assertEqual(rows['big.md']['status'], 'oversize')
            self.assertEqual(rows['project']['status'], 'skip_project_repository')
            self.assertNotIn('project/hidden.md', rows)
            self.assertNotIn('synthetic-value', (out / 'manifest.jsonl').read_text())
            with self.assertRaises(ValueError):
                m.inventory(root, root / 'forbidden')

    def test_empty_directories_are_explicit_snapshot_entries(self):
        m = load_module()
        with sandbox() as t:
            root = Path(t) / 'source'
            (root / 'empty').mkdir(parents=True)
            out = Path(t) / 'out'
            result = m.inventory(root, out)
            self.assertEqual(result['status_counts'], {'traversed_directory': 1})
            self.assertEqual(result['observed_file_entries'], 0)

    def test_sensitive_key_card_names(self):
        m = load_module()
        with sandbox() as t:
            root = Path(t) / 'source'
            root.mkdir()
            for name in ['keys.txt', 'card.txt', 'key.md']:
                (root / name).write_bytes(b'never inspect')
            out = Path(t) / 'out'
            result = m.inventory(root, out)
            self.assertEqual(result['status_counts'], {'skip_sensitive_name': 3})

    def test_reparse_predicate_and_link_boundary(self):
        from types import SimpleNamespace
        import stat
        m = load_module()
        self.assertTrue(m.is_link(SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)))
        with sandbox() as t:
            root, outside = Path(t) / 'source', Path(t) / 'outside'
            root.mkdir()
            outside.mkdir()
            (outside / 'unreachable.md').write_text('Synthetic external')
            try:
                os.symlink(outside, root / 'linked', target_is_directory=True)
            except OSError:
                if os.name != 'nt':
                    raise
                import subprocess
                receipt = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(root / 'linked'), str(outside)], capture_output=True)
                self.assertEqual(receipt.returncode, 0)
            out = Path(t) / 'out'
            result = m.inventory(root, out)
            self.assertEqual(result['observed_file_entries'], 0)
            rows = [json.loads(s) for s in (out / 'manifest.jsonl').read_text().splitlines()]
            self.assertEqual([(r['path'], r['status']) for r in rows], [('linked', 'skip_reparse')])

    def test_concurrent_change_blocks_import(self):
        from unittest.mock import patch
        m = load_module()
        with sandbox() as t:
            root = Path(t) / 'source'
            root.mkdir()
            note = root / 'a.md'
            note.write_text('before synthetic')
            original = m.scan
            calls = []
            def scanning(p):
                calls.append(1)
                if len(calls) == 2:
                    note.write_text('changed synthetic bytes')
                return original(p)
            with patch.object(m, 'scan', scanning):
                result = m.inventory(root, Path(t) / 'out')
            self.assertFalse(result['import_ready'])
            self.assertFalse(result['verification']['metadata_unchanged'])
            self.assertFalse(result['verification']['eligible_hashes_unchanged'])

    def test_frontmatter_roles_and_local_link_map(self):
        m = load_module()
        with sandbox() as t:
            root = Path(t) / 'source'
            root.mkdir()
            (root / 'a.md').write_bytes(b'---\r\ntype: reference\r\nsource: https://example.invalid\r\n---\r\n[[b]] [[missing]] [ref](b.md)')
            (root / 'b.md').write_text('---\ntype: author-note\n---\nSynthetic body')
            out = Path(t) / 'out'
            m.inventory(root, out)
            rows = {r['path']: r for r in map(json.loads, (out / 'manifest.jsonl').read_text().splitlines())}
            self.assertEqual(rows['a.md']['metadata']['role_hint'], 'original_reference')
            self.assertEqual(rows['b.md']['metadata']['role_hint'], 'author_note')
            self.assertEqual(rows['a.md']['metadata']['frontmatter_keys'], ['source', 'type'])
            links = [json.loads(s) for s in (out / 'links.jsonl').read_text().splitlines()]
            self.assertEqual(sum(r['status'] == 'resolved' for r in links), 2)
            self.assertEqual(sum(r['status'] == 'unresolved' for r in links), 1)
            self.assertNotIn('Synthetic body', (out / 'manifest.jsonl').read_text())


if __name__ == '__main__':
    unittest.main()
