"""Acceptance bridge contract; integration receipts are produced by the live campaign."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))

class BridgeTest(unittest.TestCase):
    def test_bridge_exists_and_preserves_direct_callable(self):
        from tools import fresh_challenger_bridge as bridge
        docs=[{'id':'original-a','text':'---\nx: y\n---\nOriginal proof'}]
        observed=[]
        def selected(question,candidates):
            observed.append((question,candidates))
            return {'ranked':['original-a'],'scores':{'original-a':1.0},'top5':['original-a'],'accepted':True}
        result=bridge.invoke(selected,'Question?',docs)
        self.assertEqual(observed,[('Question?',docs)])
        self.assertEqual(result['top5'],['original-a'])
        self.assertTrue(docs[0]['text'].startswith('---'))

    def test_invalid_budget_identity_and_output_fail_closed(self):
        from tools import fresh_challenger_bridge as bridge
        def empty(q,ds):return {'ranked':[],'scores':{},'top5':[],'accepted':False}
        with self.assertRaises(ValueError):bridge.invoke(empty,'q',[{'id':str(i),'text':'x'} for i in range(21)])
        with self.assertRaises(ValueError):bridge.invoke(empty,'q',[{'id':'x','text':'a'},{'id':'x','text':'b'}])
        with self.assertRaises(ValueError):bridge.invoke(empty,'q',[{'id':'x','text':'a'}])

    def test_declaration_is_complete_and_checks_exact_selected_hash(self):
        from tools import fresh_challenger_bridge as bridge
        declaration=bridge.declaration()
        self.assertEqual(declaration['files'][bridge.SELECTED.relative_to(ROOT).as_posix()],bridge.SELECTED_SHA)
        self.assertEqual(declaration['config']['selected']['threshold'],0)
        self.assertEqual(declaration['config']['acquisition']['pool'],20)
        self.assertEqual(declaration['config']['acquisition']['applicability_gate'],'NONE, identical to fresh baseline')
        for name in ('tools/accuracy_iteration/evaluator.py','tools/accuracy_iteration/ranker.py','tools/accuracy_iteration/preparation.py','tools/fresh_challenger_bridge.py','tools/fresh_retrieval_evaluation.py'):
            self.assertIn(name,declaration['files'])
        self.assertTrue(any(n.endswith('jina-int8/model.onnx') for n in declaration['files']))
        self.assertTrue(any(n.endswith('reranker-model/tokenizer.json') for n in declaration['files']))

    def test_live_runner_and_auditor_are_available(self):
        from tools import fresh_challenger_bridge as bridge
        self.assertTrue(callable(bridge.evaluate))
        self.assertTrue(callable(bridge.audit))
        self.assertTrue(callable(bridge.freeze_and_release))

    def test_live_receipt_when_requested(self):
        import os
        path=os.environ.get('BK_BRIDGE_RUN')
        if not path:self.skipTest('set BK_BRIDGE_RUN to independently audit actual live receipt')
        from tools import fresh_challenger_bridge as bridge
        result=bridge.audit(Path(path))
        self.assertTrue(result['pass'])

if __name__=='__main__':unittest.main()
