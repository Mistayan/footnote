"""Personal knowledge refinement: vertical RED/GREEN acceptance."""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


def subject(case, name):
    try:
        module = importlib.import_module('retrieval_refinement')
    except ModuleNotFoundError:
        case.fail('missing refinement behavior: ' + name)
    case.assertTrue(hasattr(module, name), 'missing refinement behavior: ' + name)
    return getattr(module, name)


class RefinementTests(unittest.TestCase):
    def test_source_gate_before_selection_rejects_known_wrong_and_missing(self):
        select = subject(self, 'select_candidates')
        docs = {n: {'id': n, 'source': n, 'text': n} for n in ('wrong', 'missing', 'right')}
        metadata = {'wrong': {'version': '3.11.9', 'product': 'Python'},
                    'missing': {}, 'right': {'version': '3.12.3', 'product': 'Python'}}
        result = select('Python 3.12 sqlite3', ['wrong', 'missing', 'right'],
                        ['wrong', 'right'], docs, metadata, 1, True)
        self.assertEqual(result['pool'], ['right'])
        self.assertEqual(result['top5'], ['right'])
        self.assertEqual(result['eligibility']['wrong'], 'REJECT_VERSION')
        self.assertEqual(result['eligibility']['missing'], 'REJECT_UNKNOWN')

    def test_same_pool_reranking_budget_and_final_gate_prevents_311_leak(self):
        select = subject(self, 'select_candidates')
        docs = {n: {'id': n, 'source': n, 'text': n} for n in ('wrong', 'a', 'b', 'c')}
        metadata = {n: {'version': '3.12.3', 'product': 'Python'} for n in docs}
        metadata['wrong']['version'] = '3.11.9'
        class AdversarialRanker:
            def rank(self, query, documents):
                self.seen = [d['id'] for d in documents]
                return ['wrong'] + list(reversed(self.seen)), {n: float(i) for i, n in enumerate(self.seen)}
        ranker = AdversarialRanker()
        ranker.seen = None
        control = select('Python 3.12 API', list(docs), [], docs, metadata, 2, True)
        result = select('Python 3.12 API', list(docs), [], docs, metadata, 2, True, ranker)
        self.assertEqual(ranker.seen, control['pool'])
        self.assertEqual(len(ranker.seen), 2)
        self.assertEqual(result['top5'], list(reversed(control['pool'])))
        self.assertNotIn('wrong', result['top5'])
        ungated = select('Python 3.12 API', list(docs), [], docs, metadata, 2, False)
        self.assertIn('wrong', ungated['pool'])
        self.assertEqual(select('no version', list(docs), [], docs, {}, 2, True)['eligibility']['wrong'], 'NOT_ASSESSED')

    def test_frozen_experiment_is_available(self):
        self.assertTrue(callable(subject(self, 'experiment')))

    @unittest.skipUnless(os.environ.get('REFINEMENT_REAL_RUN'), 'opt-in existing models and isolated server')
    def test_actual_frozen_server_run(self):
        run = Path(os.environ['REFINEMENT_REAL_RUN'])
        report = subject(self, 'experiment')(run)
        self.assertEqual(report['rows'], 32 * 12 * 3)
        self.assertTrue(report['inputs_stable'])
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertEqual(report['pair_pool_checks'], 32 * 6 * 3)
        self.assertEqual(report['gated_known_wrong'], 0)
        self.assertEqual(report['gated_unknown_version'], 0)
        self.assertEqual(report['repeat_top5_stable'], 32 * 12)
        self.assertTrue(report['manifest_verified'])
        freeze = json.loads((run / 'freeze.json').read_bytes())
        self.assertLessEqual(freeze['utc'], report['first_inference_utc'])


if __name__ == '__main__':
    unittest.main()
