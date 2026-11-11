"""Contract tests for fresh, label-blind validation; no live resources."""
import importlib
import unittest

class ValidationContract(unittest.TestCase):
    def test_exact_quote_labels_include_every_original_window(self):
        m=importlib.import_module('tools.accuracy_validation_v2.protocol')
        docs=[dict(id='a',source='s',text='the proof'),dict(id='b',source='s',text='proof end'),dict(id='c',source='s',text='proo')]
        self.assertEqual(m.expected_windows(docs,'s','proof'),['a','b'])
        with self.assertRaises(ValueError):m.expected_windows(docs,'s','absent')

    def test_refusal_does_not_inflate_all_answerable_denominator(self):
        m=importlib.import_module('tools.accuracy_validation_v2.protocol')
        rows=[dict(relevant=['x'],ranked=['x'],scores={'x':4}),dict(relevant=['y'],ranked=['y'],scores={'y':-2}),dict(relevant=[],ranked=['z'],scores={'z':-3})]
        s=m.summarize(rows,0)
        self.assertEqual(s['p1_all_answerable'],.5)
        self.assertEqual(s['accepted_precision'],1)
        self.assertEqual(s['answerable_coverage'],.5)
        self.assertEqual(s['noanswer_falseaccepts'],0)
        fit=m.fit_refusal(rows,[-10,0,10])
        self.assertEqual(fit['cutoff'],0)

    def test_seal_rejects_any_changed_bound_input(self):
        import tempfile
        from pathlib import Path
        m=importlib.import_module('tools.accuracy_validation_v2.protocol')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'input.json').write_text('{}')
            m.seal(root,['input.json'])
            self.assertTrue(m.verify_seal(root))
            (root/'input.json').write_text('[]')
            with self.assertRaises(ValueError):m.verify_seal(root)

if __name__=='__main__':unittest.main()
