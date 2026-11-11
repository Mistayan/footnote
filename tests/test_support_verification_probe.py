import unittest
from tools.support_verification_probe import core

class SpanTest(unittest.TestCase):
    def test_span_uses_context_only_and_joint_valid_end(self):
        self.assertTrue(hasattr(core, 'decode_span'), 'missing constrained span decoder')
        got=core.decode_span('ab cd', [99,2,3,0], [99,1,4,0], [None,1,1,None], [(0,0),(0,2),(3,5),(0,0)], 0, 2)
        self.assertEqual((got['text'],got['start'],got['end']),('cd',3,5))
        self.assertEqual(got['null_minus_span'],191)

class MetricsTest(unittest.TestCase):
    def test_abstentions_are_misses_in_all_answerable_denominator(self):
        self.assertTrue(hasattr(core,'counts'),'missing all-answerable metrics')
        rows=[dict(answerable=True,correct=True,accepted=True),dict(answerable=True,correct=True,accepted=False),dict(answerable=False,correct=False,accepted=True)]
        self.assertEqual(core.counts(rows),dict(correct_accepted=1,answerable=2,answerable_accepted=1,answerable_rejected=1,noanswer=1,noanswer_false_accept=1,accepted=2,p1_all_answerable=0.5,coverage=0.5,selected_label_precision=0.5))

class RealQATest(unittest.TestCase):
    def test_real_onnx_answer_is_source_anchored(self):
        self.assertTrue(hasattr(core,'QA'),'missing resident QA adapter')
        from pathlib import Path
        qa=core.QA(Path('tools/support_verification_probe/model'))
        text='My name is Wolfgang and I live in Berlin.'
        result=qa.answer('Where do I live?',text)
        self.assertEqual(text[result['start']:result['end']],result['text'])
        self.assertIn('Berlin',result['text'])
        self.assertTrue(isinstance(result['null_minus_span'],float))

class PipelineTest(unittest.TestCase):
    def test_frozen_development_probe_executes_real_pairs(self):
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec('tools.support_verification_probe.runner'),'missing bounded experiment runner')
        from tools.support_verification_probe.runner import run
        result=run()
        self.assertEqual(result['queries'],21)
        self.assertEqual(result['qa_pairs'],420)
        self.assertEqual(result['mmarco_pairs'],420)
        self.assertTrue(result['historical_unchanged'])
        self.assertEqual(result['qa_sessions'],1)

if __name__=='__main__': unittest.main()
