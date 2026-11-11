import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import accuracy_stepping_stone as a

class AccuracyTests(unittest.TestCase):
    def test_metrics_keep_fixed_cutoffs_and_coverage(self):
        m=a.metrics(['x','p'],{'relevant':['p'],'incompatible':['x']},['p'])
        self.assertEqual(m['p1'],0)
        self.assertAlmostEqual(m['p3'],1/3)
        self.assertEqual(m['p5'],.2)
        self.assertEqual(m['mrr'],.5)
        self.assertEqual(m['recall5'],1)
        self.assertEqual(m['candidate_recall'],1)
        self.assertEqual(m['incompatible_top1'],1)
        self.assertEqual(m['accepted'],1)
        self.assertEqual(a.metrics([],{'relevant':[],'incompatible':[]},[])['noanswer_false_accept'],0)

    def test_pool_is_bounded_label_free_and_deterministic(self):
        dense1=[f'a{i}' for i in range(60)]; dense2=[f'b{i}' for i in range(60)]
        lexical=[f'c{i}' for i in range(20)]; exact=['operator']
        p=a.union_pool(dense1,dense2,lexical,exact)
        self.assertEqual(len(p),20)
        self.assertEqual(len(set(p)),20)
        self.assertIn('operator',p)
        self.assertTrue(set(dense1[:6]+dense2[:6]+lexical[:6])<=set(p))
        self.assertEqual(a.union_pool([],[],[],[]),[])

    def test_selection_rejects_holdout_and_empty_development(self):
        rows=[dict(split='development',variant='baseline',metrics={'p1':0,'mrr':.5}),dict(split='development',variant='bge',metrics={'p1':1,'mrr':1})]
        self.assertEqual(a.choose_development(rows),'bge')
        with self.assertRaises(ValueError): a.choose_development(rows+[dict(rows[0],split='holdout')])
        with self.assertRaises(ValueError): a.choose_development([])

    def test_real_run_and_replay(self):
        import os,json
        if not os.environ.get('ACCURACY_STEPPING_RUN'): self.skipTest('opt-in real local server/model experiment')
        run=Path(os.environ['ACCURACY_STEPPING_RUN'])
        report=a.experiment(run)
        self.assertEqual(report['rows'],96)
        self.assertTrue(a.verify_run(run))
        rows=json.loads((run/'raw-results.json').read_bytes())
        self.assertEqual(len(rows),96)
        for r in rows:
            self.assertLessEqual(len(r['candidates']),20)
            self.assertTrue(set(r['top5'])<=set(r['candidates']))
        self.assertTrue(json.loads((run/'cleanup.json').read_bytes())['port_closed'])

    def test_heading_context_is_uniform_label_free_non_displacing(self):
        from tokenizers import Tokenizer
        tokenizer=Tokenizer.from_file(str(a.RESEARCH/'bge-model/tokenizer.json'))
        source='# Manual\n\n## Dry run\n\nPreview only without deletion.\n'
        doc={'id':'x','source':'s','start':source.index('Preview'),'text':'Preview only without deletion.'}
        enriched=a.heading_context('How to preview?',doc,{'s':source},tokenizer)
        self.assertTrue(enriched.startswith(doc['text']))
        self.assertIn('Dry run',enriched)
        self.assertEqual(enriched,a.heading_context('How to preview?',dict(doc,relevant=False,incompatible=True),{'s':source},tokenizer))
        self.assertEqual(a.heading_context('How?',doc,{'s':source},tokenizer,cap=4),doc['text'])
        tokenizer.no_truncation(); tokenizer.no_padding()
        self.assertLessEqual(len(tokenizer.encode('How to preview?',enriched).ids),512)

    def test_real_context_followup(self):
        import os,json
        if not os.environ.get('ACCURACY_FOLLOWUP_RUN'): self.skipTest('opt-in diagnostic source-context followup')
        run=Path(os.environ['ACCURACY_FOLLOWUP_RUN'])
        report=a.experiment(run,diagnostic=True,context=True,fresh_only=True)
        self.assertEqual(report['rows'],32)
        self.assertTrue(a.verify_run(run))
        rows=json.loads((run/'raw-results.json').read_bytes())
        self.assertTrue(any(r.get('reranker_context_changed',0)>0 for r in rows))

if __name__=='__main__': unittest.main()
