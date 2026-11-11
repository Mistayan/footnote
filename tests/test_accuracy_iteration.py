"""Owned accuracy iteration tests; never load sealed fresh evaluation."""
import unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class RankerTest(unittest.TestCase):
    def test_resident_multilingual_pair_and_length_receipt(self):
        from tools.accuracy_iteration.ranker import ResidentRanker
        model=ROOT/'artifacts/accuracy-iteration/ai-20261020-gte/gte-int8'
        r=ResidentRanker(model,512)
        docs=[{'id':'paris','text':'Paris est la capitale de la France.'},{'id':'cat','text':'A cat sleeps in a basket.'}]
        out=r.evaluate('What is the capital of France?',docs)
        self.assertEqual(out['ranked'][0],'paris')
        self.assertEqual(set(out['scores']),{'paris','cat'})
        self.assertEqual(out['session_loads'],1)
        self.assertEqual(r.evaluate('capitale de France',docs)['session_loads'],1)
        self.assertTrue(all(n>0 for n in out['pair_tokens'].values()))
        self.assertGreater(out['wall_ms'],0)

class FloatControlTest(unittest.TestCase):
    def test_frozen_pool_float_control(self):
        import os
        if not os.environ.get('ACCURACY_FLOAT_RUN'): self.skipTest('explicit FP32 integration opt-in')
        from tools.accuracy_iteration.float_control import experiment
        report=experiment(Path(os.environ['ACCURACY_FLOAT_RUN']))
        self.assertEqual(report['rows'],32)
        self.assertTrue(report['same_candidates'])

class JinaControlTest(unittest.TestCase):
    def test_jina_frozen_pool_controls(self):
        import os
        if not os.environ.get('ACCURACY_JINA_RUN'): self.skipTest('explicit Jina integration opt-in')
        from tools.accuracy_iteration.jina_control import experiment
        report=experiment(Path(os.environ['ACCURACY_JINA_RUN']))
        self.assertEqual(report['rows'],64)
        self.assertTrue(report['same_candidates'])

class ExportTest(unittest.TestCase):
    def test_callable_uses_only_query_candidates_and_explicit_threshold(self):
        import tempfile,json
        from tools.accuracy_iteration.evaluator import create_evaluator
        config={'variant':'baseline','models':[{'path':str(ROOT/'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model'),'cap':512}],'threshold':1000000,'top_k':5}
        evaluate=create_evaluator(config)
        out=evaluate('What is the capital of France?',[{'id':'paris','text':'Paris is the capital of France.'}])
        self.assertEqual(out['top5'],[])
        self.assertEqual(out['ranked'],['paris'])
        self.assertEqual(out['score_kind'],'uncalibrated raw logit')
        self.assertFalse(out['accepted'])

    def test_frozen_frontmatter_transform_changes_pairs_not_evidence(self):
        from tools.accuracy_iteration.evaluator import create_evaluator
        from tokenizers import Tokenizer
        model=ROOT/'artifacts/accuracy-iteration/ai-20261020-gte/jina-int8'
        cfg={'variant':'jina_no_frontmatter','models':[{'path':str(model),'cap':512}],'threshold':None,'preprocess':'strip_frontmatter'}
        docs=[{'id':'a','text':'---\ntitle: Generic metadata\n---\n\nActual proof.'}]
        out=create_evaluator(cfg)('Question?',docs)
        counter=Tokenizer.from_file(str(model/'tokenizer.json')); counter.no_padding(); counter.no_truncation()
        self.assertEqual(out['pair_tokens'][0]['a'],len(counter.encode('Question?','\nActual proof.').ids))
        self.assertTrue(docs[0]['text'].startswith('---'))

class AuditTest(unittest.TestCase):
    def test_independent_live_audit(self):
        from tools.accuracy_iteration.audit import audit
        report=audit(ROOT/'artifacts/accuracy-iteration/ai-20261020-gte/int8-live-v1')
        self.assertEqual(report['rows'],96)
        self.assertEqual(report['queries'],32)
        self.assertTrue(report['source_offsets_verified'])
    def test_independent_export_abstention_audit(self):
        from tools.accuracy_iteration.audit import audit
        report=audit(ROOT/'artifacts/accuracy-iteration/ai-20261020-gte/export-replay-v1')
        self.assertEqual(report['rows'],64)
        self.assertEqual(report['queries'],32)

class PivotControlTest(unittest.TestCase):
    def test_new_ranker_pivot_frozen_pool_controls(self):
        import os
        if not os.environ.get('ACCURACY_PIVOT_RUN'): self.skipTest('explicit translated-ranker integration opt-in')
        from tools.accuracy_iteration.pivot_control import experiment
        report=experiment(Path(os.environ['ACCURACY_PIVOT_RUN']))
        self.assertEqual(report['rows'],128)
        self.assertTrue(report['cleanup']['translator_exited'])

class PreparationTest(unittest.TestCase):
    def test_frontmatter_only_at_start_is_removed_without_body_change(self):
        from tools.accuracy_iteration.preparation import strip_frontmatter
        self.assertEqual(strip_frontmatter('---\ntitle: Generic\n---\n\n# Actual\nProof'), '\n# Actual\nProof')
        self.assertEqual(strip_frontmatter('# Actual\n---\nProof'), '# Actual\n---\nProof')
        self.assertEqual(strip_frontmatter('---\ntitle: incomplete'), '---\ntitle: incomplete')
    def test_actual_preparation_control(self):
        import os
        if not os.environ.get('ACCURACY_PREPARATION_RUN'): self.skipTest('explicit preparation integration opt-in')
        from tools.accuracy_iteration.preparation import experiment
        report=experiment(Path(os.environ['ACCURACY_PREPARATION_RUN']))
        self.assertEqual(report['rows'],64)
        self.assertGreater(report['changed_pairs'],0)

class FusionControlTest(unittest.TestCase):
    def test_bounded_final_rank_fusion_replay(self):
        import os
        if not os.environ.get('ACCURACY_FUSION_RUN'): self.skipTest('explicit fixed final-fusion replay opt-in')
        from tools.accuracy_iteration.fusion_control import experiment
        report=experiment(Path(os.environ['ACCURACY_FUSION_RUN']))
        self.assertEqual(report['rows'],256)
        self.assertEqual(report['actual_model_inference_calls'],0)

class ExportReplayTest(unittest.TestCase):
    def test_full_exported_callable_execution(self):
        import os
        if not os.environ.get('ACCURACY_EXPORT_RUN'): self.skipTest('explicit full exported evaluator replay opt-in')
        from tools.accuracy_iteration.export_replay import experiment
        report=experiment(Path(os.environ['ACCURACY_EXPORT_RUN']))
        self.assertEqual(report['rows'],32)
        self.assertGreater(report['actual_pairs'],500)
        self.assertTrue(report['config_unchanged'])

class ReviewTest(unittest.TestCase):
    def test_review_contains_full_evidence_and_unknown(self):
        from tools.accuracy_iteration.review import render_review
        rows=[dict(id='a',query='Question?',variant='x',relevant=['yes'],incompatible=['bad'],top5=['other'],ranked=['other','yes'],logits={'other':2,'yes':1},metrics={'p1':0},pair_tokens={'yes':20},rerank_ms=1,evidence=[{'id':'other','text':'Original full passage','url':'https://example.com','start':0,'end':21,'sha256':'hash'}])]
        text=render_review(rows)
        self.assertIn('Original full passage',text)
        self.assertIn('UNKNOWN',text)
        self.assertIn('Question?',text)
        self.assertIn('yes',text)

class ExperimentTest(unittest.TestCase):
    def test_fixed_pool_live_server_and_replay(self):
        import os
        if not os.environ.get('ACCURACY_ITERATION_RUN'): self.skipTest('explicit real integration opt-in')
        from tools.accuracy_iteration.experiment import experiment,verify
        run=Path(os.environ['ACCURACY_ITERATION_RUN'])
        out=experiment(run)
        self.assertEqual(out['rows'],96)
        self.assertTrue(out['cleanup']['port_closed'])
        self.assertTrue(verify(run))

if __name__=='__main__': unittest.main()
