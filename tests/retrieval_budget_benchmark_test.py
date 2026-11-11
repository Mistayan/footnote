"""Budget/gating contract; real server integration opt-in, no downloads."""
import importlib
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


class BudgetContract(unittest.TestCase):
    def test_gate_uses_only_pinned_source_labels_rejects_unknown_and_rechecks_presentation(self):
        self.assertIsNotNone(importlib.util.find_spec('retrieval_budget_benchmark'),
                             'budget harness must exist')
        b = importlib.import_module('retrieval_budget_benchmark')
        sources = {'old': {'url': 'https://raw.githubusercontent.com/python/cpython/v3.11.9/Doc/library/sqlite3.rst'},
                   'new': {'url': 'https://raw.githubusercontent.com/python/cpython/v3.12.3/Doc/library/sqlite3.rst'},
                   'unknown': {'url': 'https://example.org/Python-3.11'}}
        docs = {k: {'source': k, 'text': 'Python 3.11 answers perfectly'} for k in sources}
        query = {'query': 'Python 3.11 sqlite3', 'relevant': ['new']}
        states = b.eligibility(query['query'], docs, sources)
        self.assertEqual(states, {'old': 'MATCH_EXPLICIT_FAMILY', 'new': 'REJECT_VERSION',
                                  'unknown': 'REJECT_UNKNOWN'})
        self.assertEqual(b.select_candidates(['new', 'unknown', 'old'], states, True, 5), ['old'])
        self.assertEqual(b.present(['new', 'old', 'unknown'], states, True), ['old'])
        self.assertEqual(b.present(['new', 'old', 'unknown'], states, False), ['new', 'old', 'unknown'])
        self.assertEqual(b.eligibility('sqlite3 backup', docs, sources),
                         dict.fromkeys(docs, 'NOT_ASSESSED'))
        self.assertEqual(b.select_candidates(['new', 'unknown', 'old'], states, False, 2), ['new', 'unknown'])

    def test_missed_eligible_proofs_partition_pool_budget_and_presentation_losses(self):
        b = importlib.import_module('retrieval_budget_benchmark')
        self.assertTrue(hasattr(b, 'proof_audit'), 'explicit proof audit missing')
        states = {'a': 'MATCH_EXPLICIT_FAMILY', 'b': 'MATCH_EXPLICIT_FAMILY',
                  'c': 'MATCH_EXPLICIT_FAMILY', 'd': 'REJECT_VERSION',
                  'u': 'REJECT_UNKNOWN'}
        audit = b.proof_audit(['a', 'b', 'c', 'd', 'u'], states,
                              ['a', 'b', 'd'], ['a'], [])
        self.assertEqual(audit['eligible_selected_proofs'], ['a', 'b', 'c'])
        self.assertEqual(audit['missing_from_pool'], ['c'])
        self.assertEqual(audit['lost_to_budget_or_gate'], ['b'])
        self.assertEqual(audit['lost_at_presentation'], ['a'])
        self.assertEqual(audit['missed_eligible_proof_count'], 3)
        self.assertEqual(audit['selected_ineligible_proofs'], ['d', 'u'])

    def test_real_resident_budget_experiment_contract(self):
        b = importlib.import_module('retrieval_budget_benchmark')
        self.assertTrue(hasattr(b, 'experiment'), 'real server budget experiment missing')
        target = os.environ.get('BUDGET_REAL_RUN')
        if not target:
            self.skipTest('BUDGET_REAL_RUN required for real model/server integration')
        report = b.experiment(Path(target))
        self.assertEqual(report['rows'], 32 * 8 * 4)
        self.assertEqual(report['baseline_top5_parity'], 32)
        self.assertTrue(report['inputs_stable'])
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertEqual(report['verification']['verified_rows'], report['rows'])
        self.assertEqual(report['verification']['gate_violations'], 0)
        self.assertEqual(report['verification']['same_pool_pairs'], 32 * 4)
        self.assertTrue(report['verification']['ranks_stable_across_blocks'])


if __name__ == '__main__':
    unittest.main()
