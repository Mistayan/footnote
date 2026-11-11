"""Strict TDD regression and opt-in real-server acceptance for ablations."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


class AblationTests(unittest.TestCase):
    def test_context_uses_only_pinned_explicit_version(self):
        self.assertIsNotNone(importlib.util.find_spec('retrieval_ablation'), 'missing standalone context implementation')
        import retrieval_ablation as a
        source = {'title': 'Transaction control', 'url': 'https://raw.githubusercontent.com/python/cpython/v3.11.9/Doc/library/sqlite3.rst'}
        metadata = a.source_metadata(source)
        self.assertEqual(metadata['version'], '3.11.9')
        doc = {'anchor': 'Transaction control', 'source': 'py311', 'text': 'original evidence'}
        text = a.context_text(doc, source)
        self.assertIn('Title: Transaction control', text)
        self.assertIn('Version: 3.11.9', text)
        self.assertTrue(text.endswith('\n\noriginal evidence'))
        self.assertEqual(a.source_metadata({'url': 'https://www.sqlite.org/wal.html'})['version'], 'UNKNOWN')
        q = a.source_metadata({'url': 'https://raw.githubusercontent.com/qdrant/landing_page/' + 'a' * 40 + '/search.md'})
        self.assertEqual(q['version'], 'UNKNOWN')
        self.assertEqual(q['revision'], 'a' * 40)
        self.assertEqual(a.source_metadata({'url': 'https://raw.githubusercontent.com/python/cpython/main/Doc/x'})['version'], 'UNKNOWN')

    def test_or_bm25_retains_technical_identifiers_and_matches_any_term(self):
        import retrieval_ablation as a
        self.assertTrue(hasattr(a, 'lexical_or'), 'missing OR BM25 branch')
        import technical_quality as tq
        docs = [{'id': 'a', 'text': 'SQLITE_BUSY_SNAPSHOT recovery'},
                {'id': 'b', 'text': 'isolation_level None'}, {'id': 'c', 'text': 'unrelated'}]
        db = tq.lexical_index(docs)
        try:
            self.assertEqual(a.technical_tokens('SQLITE_BUSY_SNAPSHOT isolation_level check_same_thread 3.11'),
                             ['SQLITE_BUSY_SNAPSHOT', 'isolation_level', 'check_same_thread', '3.11'])
            self.assertEqual(set(a.lexical_or(db, 'SQLITE_BUSY_SNAPSHOT isolation_level missing')), {'a', 'b'})
            self.assertEqual(tq.lexical_search(db, 'SQLITE_BUSY_SNAPSHOT isolation_level missing'), [])
            self.assertEqual(a.lexical_or(db, ''), [])
        finally:
            db.close()

    def test_strict_version_filter_rejects_unknown_without_inferred_compatibility(self):
        import retrieval_ablation as a
        self.assertTrue(hasattr(a, 'admissibility'), 'missing explicit applicability policy')
        known = a.source_metadata({'url': 'https://raw.githubusercontent.com/python/cpython/v3.11.9/Doc/library/sqlite3.rst'})
        unknown = a.source_metadata({'url': 'https://www.sqlite.org/wal.html'})
        self.assertEqual(a.admissibility('Python 3.11 transactions', known), 'MATCH_EXPLICIT_FAMILY')
        self.assertEqual(a.admissibility('Python 3.12 transactions', known), 'REJECT_VERSION')
        self.assertEqual(a.admissibility('Python 3.11 transactions', unknown), 'REJECT_UNKNOWN')
        self.assertEqual(a.admissibility('SQLite WAL', unknown), 'NOT_ASSESSED')

    @unittest.skipUnless(__import__('os').environ.get('ABLATION_RERANKER'), 'opt-in model inference')
    def test_resident_crossencoder_scores_fixed_pool_without_changing_evidence(self):
        import os
        import retrieval_ablation as a
        self.assertTrue(hasattr(a, 'CrossEncoder'), 'missing isolated resident reranker')
        model = a.CrossEncoder(Path(os.environ['ABLATION_RERANKER']))
        docs = [{'id': 'a', 'text': 'SQLite supports online database backup.'},
                {'id': 'b', 'text': 'The sky is blue.'}]
        before = [dict(d) for d in docs]
        ids, scores = model.rank('How do I back up SQLite?', docs)
        self.assertEqual(set(ids), {'a', 'b'})
        self.assertEqual(len(scores), 2)
        self.assertTrue(all(__import__('math').isfinite(s) for s in scores.values()))
        self.assertEqual(model.rank('How do I back up SQLite?', docs)[0], ids)
        self.assertEqual(docs, before)

    @unittest.skipUnless(__import__('os').environ.get('ABLATION_REAL_RUN'), 'opt-in actual Qdrant server')
    def test_frozen_experiment_runs_real_server_and_preserves_baseline(self):
        import os
        import retrieval_ablation as a
        self.assertTrue(hasattr(a, 'experiment'), 'missing runnable ablation integration')
        report = a.experiment(Path(os.environ['ABLATION_REAL_RUN']),
                              Path(os.environ['ABLATION_RERANKER']) if os.environ.get('ABLATION_RERANKER') else None)
        self.assertEqual(report['baseline_top5_parity'], 32)
        self.assertEqual(report['server_identity']['version'], '1.19.2')
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['inputs_stable'])
        self.assertEqual(report['query_count'], 32)
        self.assertEqual(report['rows'], 32 * 2 * len(report['variants']))
        self.assertTrue(report['manifest_verified'])
        self.assertEqual(len(report['summaries']), 2 * 2 * len(report['variants']))

    def test_context_without_curated_anchor_keeps_title_unknown(self):
        import retrieval_ablation as a
        doc = {'id': 'unlabeled', 'source': 'wal', 'text': 'public excerpt'}
        self.assertIn('Title: UNKNOWN', a.context_text(doc, {'url': 'https://www.sqlite.org/wal.html'}))

    def test_context_title_is_source_derived_not_selected_evidence_anchor(self):
        import retrieval_ablation as a
        self.assertTrue(hasattr(a, 'source_title'), 'missing unbiased source title extraction')
        self.assertEqual(a.source_title('---\ntitle: Filtering\n---\n'), 'Filtering')
        self.assertEqual(a.source_title('.. currentmodule:: asyncio\n\n=====\nCoroutines and Tasks\n=====\n'), 'Coroutines and Tasks')
        self.assertEqual(a.source_title('Write-Ahead Logging Small. Fast. Reliable. Home'), 'Write-Ahead Logging')
        self.assertEqual(a.source_title('unstructured text without a known heading'), 'UNKNOWN')
        doc = {'anchor': 'selected evidence only', 'text': 'body'}
        text = a.context_text(doc, {'url': 'https://www.sqlite.org/wal.html', 'title': 'Write-Ahead Logging'})
        self.assertIn('Title: Write-Ahead Logging', text)
        self.assertNotIn('selected evidence only', text)


if __name__ == '__main__':
    unittest.main()
