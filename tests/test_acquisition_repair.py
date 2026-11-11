import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

class AcquisitionRepairTests(unittest.TestCase):
    def test_source_wide_slices_cover_every_character_fit_and_map_exactly(self):
        from tools.acquisition_repair.core import source_slices
        from tokenizers import Tokenizer, models, pre_tokenizers
        tok = Tokenizer(models.WordLevel({'[UNK]': 0}, unk_token='[UNK]'))
        tok.pre_tokenizer = pre_tokenizers.Whitespace()
        text = ' '.join('word'+str(i) for i in range(60))
        parents = [dict(id='p0', source='s', start=0, end=len(text), text=text)]
        children = source_slices({'s': text}, parents, tok, 12, overlap=4)
        self.assertGreater(len(children), 1)
        covered = set()
        for child in children:
            self.assertEqual(child['text'], text[child['start']:child['end']])
            self.assertLessEqual(len(tok.encode(child['text']).ids), 12)
            self.assertEqual(child['parent_ids'], ['p0'])
            covered.update(range(child['start'], child['end']))
        self.assertEqual(covered, set(range(len(text))))
        self.assertLess(children[1]['start'], children[0]['end'])

    def test_parent_dedup_union_budget_and_unknown_ids_fail_closed(self):
        from tools.acquisition_repair.core import acquire
        points = [dict(id=2, score=.9), dict(id=1, score=.9), dict(id=3, score=.8)]
        records = [dict(id='a', parent_ids=['p2', 'p1']), dict(id='b', parent_ids=['p2']), dict(id='c', parent_ids=['p3'])]
        result = acquire(points, records, ['p4', 'p2'], 3, 100)
        self.assertEqual(result['dense'], ['p1', 'p2', 'p3'])
        self.assertEqual(result['pool'], ['p2', 'p1', 'p4'])
        self.assertEqual(set(result['union']), {'p1', 'p2', 'p3', 'p4'})
        self.assertEqual(len(result['pool']), len(set(result['pool'])))
        with self.assertRaises(ValueError):
            acquire([dict(id=99, score=1)], records, [], 20, 100)

    def test_full_resident_experiment(self):
        # Explicit opt-in because this exercises real CPU models/Qdrant.
        if '--live' not in sys.argv:
            self.skipTest('run with --live for bounded actual experiment')
        from tools.acquisition_repair.experiment import experiment
        result = experiment()
        self.assertTrue(result['verified'])
        self.assertEqual(result['counts']['development_queries'], 21)
        self.assertEqual(result['counts']['diagnostic_queries'], 63)
        self.assertFalse(result['fresh_acceptance'])

if __name__ == '__main__':
    unittest.main()
