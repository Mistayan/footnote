import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class EvidenceViewTest(unittest.TestCase):
    def test_views_are_exact_source_spans_and_label_blind(self):
        spec = importlib.util.spec_from_file_location('views', ROOT/'tools/evidence_view_experiment.py')
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        source = 'Document title\n==============\n\nFirst paragraph without target.\n\n.. function:: target(x)\n\nThe target returns a useful value.\n\nOther material.'
        start = source.index('First paragraph')
        parent = dict(id='x', source='s', start=start, end=len(source), text=source[start:])
        a = m.build_views('target value', parent, source, 'crop320')
        b = m.build_views('target value', parent | {'relevant': ['poison'], 'expected_spans': ['poison']}, source, 'crop320')
        self.assertEqual(a, b)
        for view in a:
            self.assertEqual(view['text'], '\n\n'.join(source[s['start']:s['end']] for s in view['spans']))
        self.assertIn('target', a[0]['text'])
        with self.assertRaises(ValueError):
            m.build_views('q', parent | {'text': 'generated'}, source, 'crop320')

    def test_max_aggregation_and_noanswer_denominators(self):
        spec = importlib.util.spec_from_file_location('views', ROOT/'tools/evidence_view_experiment.py')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        ranking, scores = m.aggregate({'a::0': -2., 'a::1': 3., 'b::0': 1.}, {'a::0':'a','a::1':'a','b::0':'b'})
        self.assertEqual(ranking, ['a','b'])
        self.assertEqual(scores, {'a':3.,'b':1.})
        stats = m.measure([{'relevant':['a'], 'ranking':['a'], 'scores':{'a':3.}}, {'relevant':['b'], 'ranking':['a','b'], 'scores':{'a':2.}}, {'relevant':[], 'ranking':['a'], 'scores':{'a':1.}}], 2.5)
        self.assertEqual(stats, dict(answerable=2, correct=1, accepted_answerable=1, accepted_correct=1, rejected_answerable=1, noanswer=1, false_accepts=0))

    @unittest.skipUnless(__import__('os').environ.get('EVIDENCE_VIEW_LIVE') == '1', 'explicit isolated live execution')
    def test_finite_live_development_run(self):
        import sys
        sys.path.insert(0,str(ROOT/'tools')); sys.path.insert(0,str(ROOT))
        import evidence_view_experiment as m
        report=m.run_experiment()
        self.assertEqual(report['requests'],126)
        self.assertEqual(report['baseline_parity'],21)
        self.assertTrue(report['cleanup']['server']['process_exited'])
        self.assertTrue(report['cleanup']['server']['port_closed'])

if __name__ == '__main__': unittest.main()
