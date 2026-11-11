"""Focused vertical TDD for same-pool reranking; integration opt-in."""
import importlib
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

class PivotRerankTests(unittest.TestCase):
    def test_builder_freezes_original_pool_without_labels(self):
        p = importlib.import_module('pivot_rerank_experiment')
        row = dict(query='ne pas', language='fr', candidates=['b', 'a'], pool20=['b','a','rejected'], relevant=['a'], incompatible=['b'])
        docs = {'a':dict(id='a',text='A'), 'b':dict(id='b',text='B')}
        built = p.build_inputs(row['query'], row['language'], row['candidates'], docs)
        self.assertEqual(built, dict(query='ne pas',language='fr',documents=[docs['b'],docs['a']]))
        self.assertNotIn('relevant', repr(built))
        self.assertRaises(ValueError,p.build_inputs,'q','fr',['a','a'],docs)
        self.assertRaises(ValueError,p.build_inputs,'q','fr',['a']*21,docs)

    def test_fixed_half_logit_combination_and_identity_control(self):
        p = importlib.import_module('pivot_rerank_experiment')
        original = {'b': 3.0, 'a': 1.0}
        pivot = {'b': -1.0, 'a': 1.0}
        variants = p.combine_scores(original,pivot,'fr')
        self.assertEqual(variants['combined'], {'b':1.0,'a':1.0})
        self.assertEqual(p.order_scores(variants['combined']), ['a','b'])
        self.assertEqual(p.combine_scores(original,pivot,'en')['pivot'], original)
        self.assertRaises(ValueError,p.combine_scores,original,{'a':1.0},'fr')
        self.assertRaises(ValueError,p.combine_scores,original,{'a':1.0,'b':float('nan')},'fr')

    def test_actual_frozen_pool_experiment(self):
        target = os.environ.get('PIVOT_RERANK_RUN')
        if not target:
            self.skipTest('opt-in actual CPU translator and incumbent reranker')
        p = importlib.import_module('pivot_rerank_experiment')
        report = p.experiment(Path(target))
        self.assertEqual(report['questions'],60)
        self.assertEqual(report['result_rows'],180)
        self.assertEqual(report['baseline_mismatches'],[])
        self.assertEqual(report['english_mismatches'],[])
        self.assertTrue(report['cleanup']['translator_exited'])
        self.assertTrue(p.verify_run(Path(target)))
        self.assertRaises(FileExistsError,p.experiment,Path(target))

if __name__ == '__main__': unittest.main()
