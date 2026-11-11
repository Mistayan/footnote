import unittest


class CalibrationTests(unittest.TestCase):
    def test_01_constraints_all_answerable_denominator_and_highest_tie(self):
        from tools.query_view_calibration import core
        rows = [dict(id=str(i), answerable=True, top1_label=i != 0, score=float(i)) for i in range(16)]
        rows += [dict(id='n'+str(i), answerable=False, top1_label=False, score=-1.) for i in range(5)]
        result = core.select_threshold(rows)
        self.assertEqual(result['threshold'], 1.)
        self.assertEqual(result['metrics']['answerable_total'], 16)
        self.assertEqual(result['metrics']['correct_accepted'], 15)
        self.assertEqual(result['metrics']['wrong_accepted'], 0)
        self.assertEqual(result['metrics']['noanswer_accepted'], 0)
        self.assertEqual(result['metrics']['answerable_accepted'], 15)

    def test_02_infeasible_never_borrows_old_cutoff(self):
        from tools.query_view_calibration import core
        rows = [dict(answerable=True, top1_label=True, score=1.) for _ in range(16)]
        rows += [dict(answerable=False, top1_label=False, score=2.) for _ in range(5)]
        result = core.select_threshold(rows)
        self.assertFalse(result['feasible'])
        self.assertIsNone(result['threshold'])
        with self.assertRaises(ValueError):
            core.select_threshold([dict(answerable=True, top1_label=True, score=float('nan'))])
        with self.assertRaises(ValueError):
            core.select_threshold([dict(answerable=True, top1_label=True, score=1.)])

    def test_03_original_order_round_parity_detects_interleaving(self):
        from tools.query_view_calibration import core
        from tools.rank_input_repair.core import pair_rounds
        pairs = [dict(id=f'{p}:{s}', parent=p, slot=s, text=p) for p in 'abcde' for s in range(2)]
        core.assert_rounds(pair_rounds(pairs), list('abcde'), 2)
        with self.assertRaises(AssertionError):
            core.assert_rounds([pairs[:5], pairs[5:]], list('abcde'), 2)

    def test_04_top5_requires_complete_quote_in_exact_source(self):
        from tools.query_view_calibration.audit import anchor_rank
        quote = dict(source='s', start=10, end=20, quote='abcdefghij')
        evidence = [dict(original=dict(source='other'), presentation=dict(start=10, end=20, text='abcdefghij')),
                    dict(original=dict(source='s'), presentation=dict(start=11, end=20, text='bcdefghij')),
                    dict(original=dict(source='s'), presentation=dict(start=8, end=22, text='__abcdefghij__'))]
        self.assertEqual(anchor_rank(evidence, [quote]), 3)
        self.assertIsNone(anchor_rank(evidence[:2], [quote]))
        self.assertIsNone(anchor_rank(evidence, []))
        bad = dict(source='s', start=10, end=20, quote='XXXXXXXXXX')
        self.assertIsNone(anchor_rank(evidence, [bad]))

if __name__ == '__main__':
    unittest.main()
