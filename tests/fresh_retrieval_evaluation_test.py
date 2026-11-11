"""Focused new evaluator contract tests; public inputs only."""
import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fresh_retrieval_evaluation as f

class Contracts(unittest.TestCase):
    def test_all_answerable_denominator_and_noanswer_gate(self):
        rows=[{'relevant':['a'],'top5':['a']},{'relevant':['b'],'top5':[]},{'relevant':[],'top5':['x']}]
        s=f.summarize(rows)
        self.assertEqual(s['p1'],.5)
        self.assertEqual(s['answerable_coverage'],.5)
        self.assertEqual(s['noanswer_falseaccept'],1)
        self.assertFalse(s['proposed_gate_pass'])
        self.assertLess(s['p1_wilson95'][0],.5)
        self.assertGreater(s['p1_wilson95'][1],.5)

    def test_uniform_windows_and_all_expected_quote_hits(self):
        text='0123456789'*100
        docs=f.windows('s',text,width=140,stride=90)
        self.assertTrue(all(text[d['start']:d['end']]==d['text'] for d in docs))
        q=f.annotate('q','What?',{'s':'23456789'},docs,{'s':text},'development','en','en')
        self.assertEqual(q['relevant'],[d['id'] for d in docs if '23456789' in d['text']])
        with self.assertRaises(ValueError):f.annotate('x','?',{'s':'absent'},docs,{'s':text},'test','fr','en')

    def test_sealed_test_rejects_unfrozen_candidate(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            f.save(p/'freeze.json',{'files':{}})
            with self.assertRaises(ValueError):f.authorize_split(p,'test')
            self.assertIsNone(f.authorize_split(p,'development'))

    def test_real_development_baselines_opt_in(self):
        import os
        if not os.environ.get('FRESH_EVALUATION_SNAPSHOT'):self.skipTest('real server execution opt-in')
        report=f.evaluate(Path(os.environ['FRESH_EVALUATION_SNAPSHOT']),'development')
        self.assertEqual(report['rows'],105)
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertTrue(f.verify_run(Path(report['run'])))

if __name__=='__main__': unittest.main()
