import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from memory_written_fixture import source_rows
from memory_written_questions import questions
from memory_written_run import accepted, fit_cutoff, frozen_data, paired_interval, path_of


class WrittenMemoryTest(unittest.TestCase):
    def test_corpus_scale_and_translation_pairs(self):
        rows = source_rows()
        self.assertEqual(len(rows), 600)
        self.assertEqual(sum(r['language'] == 'fr' for r in rows), 300)
        self.assertEqual(sum(r['language'] == 'en' for r in rows), 300)
        self.assertEqual(len({r['family'] for r in rows}), 300)
        for family in {r['family'] for r in rows}:
            pair = [r for r in rows if r['family'] == family]
            self.assertEqual({r['language'] for r in pair}, {'en', 'fr'})
            self.assertEqual(len({r['split'] for r in pair}), 1)
        self.assertTrue(all(len(r[v]) <= 2000 for r in rows for v in ('original', 'qualified', 'full')))
        self.assertEqual(len({(r['kind'], r['original']) for r in rows}), 600)

    def test_unknown_platform_not_invented_for_cache_fix(self):
        for row in source_rows():
            if row['topic'] == 'f4':
                self.assertNotIn(row['platform'], row['qualified'])
            if row['topic'] == 'f1':
                self.assertIn(row['platform'], row['qualified'])
                self.assertNotIn('only', row['qualified'])

    def test_questions_stay_in_project_split(self):
        rows = source_rows()
        qq = questions(rows)
        self.assertEqual(len(qq), 1200)
        self.assertEqual(sum(bool(q['gold']) for q in qq), 600)
        self.assertEqual(len([q for q in qq if q['split'] == 'heldout']), 800)
        self.assertEqual(len({q['project_group'] for q in qq if q['split'] == 'heldout'}), 20)
        for q in qq:
            self.assertLessEqual(len(q['query'].encode()), 512)
            if q['gold']:
                self.assertEqual(q['gold'], [q['family']])
            else:
                self.assertIn('absence', q)

    @unittest.skipUnless(path_of('.sources.freeze.json').exists(), 'requires locally frozen pilot data')
    def test_actual_files_match_source_before_question_freeze(self):
        sources, qq = frozen_data()
        self.assertEqual(sources, source_rows())
        self.assertEqual(qq, questions(sources))

    def test_cutoff_handles_tied_negatives(self):
        rows = [dict(hits=[dict(score=2.)]) for _ in range(10)]
        cutoff = fit_cutoff(rows)
        self.assertGreater(cutoff, 2.)
        self.assertFalse(any(accepted(r, cutoff) for r in rows))

    def test_bootstrap_uses_project_groups(self):
        qs = {str(i): dict(split='heldout', gold=['fact'], project_group=str(i // 2)) for i in range(4)}
        a = {key: dict(hits=[]) for key in qs}
        b = {key: dict(hits=[dict(family='fact', score=3)]) for key in qs}
        self.assertEqual(paired_interval(a, b, qs), [1., 1.])

    def test_preparation_preserves_existing_frozen_sources(self):
        from prepare_memory_written import prepare
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / 'fixture'
            evidence = Path(str(prefix) + '.sources.json')
            evidence.write_text('preserved', encoding='utf-8')
            with patch('prepare_memory_written.PREFIX', prefix):
                with self.assertRaises(FileExistsError):
                    prepare()
            self.assertEqual(evidence.read_text(encoding='utf-8'), 'preserved')


if __name__ == '__main__':
    unittest.main()
