import unittest

from memory_cutoff_analysis import analyse


class CutoffAnalysisTest(unittest.TestCase):
    def test_ties_and_heldout_do_not_change_cutoff(self):
        rows = [{'split': 'dev', 'label': 'negative', 'hybrid': [{'score': 1, 'relevant': False}]} for _ in range(5)]
        rows += [{'split': 'heldout', 'label': 'positive', 'keyword_hit': False,
                  'hybrid': [{'score': 2, 'relevant': True}]} for _ in range(10)]
        rows += [{'split': 'heldout', 'label': 'negative', 'hybrid': []}]
        result = analyse(rows, samples=100)
        self.assertGreater(result['cutoff'], 1)
        self.assertTrue(result['pass'])
        rows[-1]['hybrid'] = [{'score': 10, 'relevant': False}]
        result2 = analyse(rows, samples=100)
        self.assertEqual(result['cutoff'], result2['cutoff'])
        self.assertFalse(result2['pass'])

    def test_missing_scores_rejected(self):
        with self.assertRaises((ValueError, KeyError)):
            analyse([{'split': 'dev', 'label': 'negative', 'hybrid': [{'score': float('nan')}]}])


if __name__ == '__main__':
    unittest.main()
