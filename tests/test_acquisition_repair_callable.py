import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class CallableTests(unittest.TestCase):
    def test_preservation_rejects_changed_flags_assignments_versions_and_negation(self):
        from tools.acquisition_repair.evaluator import preserve_query
        for query,pivot in [('Avec --decorate=full en Python 3.13','With --decorate=short in Python 3.13'),('Avec strict=True','With strict=False'),('Ne pas supprimer itertools.batched','Delete itertools.batched'),('Avec Python 3.13','With Python 3.12')]:
            self.assertFalse(preserve_query(query,pivot))
        self.assertTrue(preserve_query('Ne pas supprimer --full-diff en Python 3.13','Do not delete --full-diff in Python 3.13'))

    def test_live_callable_development_parity(self):
        if '--live' not in sys.argv:
            self.skipTest('explicit real-model/actual backend test')
        from tools.acquisition_repair.evaluator import verify_callable
        report=verify_callable()
        self.assertTrue(report['verified'])
        self.assertEqual(report['requests'],21)
        self.assertEqual(report['exact_scores_ranks_pools'],21)

if __name__=='__main__':unittest.main()
