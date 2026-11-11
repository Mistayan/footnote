"""Additive candidate-recall experiment acceptance tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


class CandidateRecallTest(unittest.TestCase):
    def test_exact_index_preserves_identifier_operator_negation_and_offsets(self):
        import candidate_recall_benchmark as c
        text = '<b>`must_not`</b> != must not; SQLITE_BUSY_SNAPSHOT >= 3.12'
        spans = c.literal_spans(text)
        self.assertEqual([text[s['start']:s['end']] for s in spans], [s['raw'] for s in spans])
        self.assertIn('must_not', [s['token'] for s in spans])
        self.assertIn('!=', [s['token'] for s in spans])
        self.assertIn('>=', [s['token'] for s in spans])
        self.assertIn('not', [s['token'] for s in spans])
        corpus = [{'id': 'good', 'text': text}, {'id': 'bad', 'text': 'must not must should not'}]
        db = c.exact_index(corpus)
        try:
            self.assertEqual(c.lexical(db, 'MUST_NOT', 20, True), ['good'])
            self.assertEqual(c.lexical(db, '!=', 20, True), ['good'])
            self.assertEqual(c.lexical(db, '', 20, True), [])
        finally:
            db.close()

    def test_candidate_recall_separate_from_final_and_unknown_not_filtered(self):
        import candidate_recall_benchmark as c
        q = {'relevant': ['proof', 'other'], 'incompatible': ['wrong']}
        result = c.diagnose(q, ['unknown', 'wrong', 'a', 'b', 'c', 'proof'])
        self.assertEqual(result['candidate_recall'], .5)
        self.assertEqual(result['recall5'], 0)
        self.assertEqual(result['top1'], 0)
        self.assertEqual(result['mrr5'], 0)
        self.assertEqual(result['unknown'], ['unknown', 'a', 'b', 'c'])
        self.assertEqual(result['incompatible'], ['wrong'])
        self.assertEqual(result['missing_pool'], ['other'])
        result = c.diagnose({'relevant': [], 'incompatible': []}, ['unknown'])
        self.assertIsNone(result['candidate_recall'])
        self.assertIsNone(result['mrr5'])
        self.assertTrue(result['noanswer_false_acceptance'])

    def test_fusion_respects_frozen_acquisition_depth_not_incumbent_hidden_caps(self):
        import candidate_recall_benchmark as c
        dense = ['d' + str(i) for i in range(100)]
        lex = ['l' + str(i) for i in range(100)]
        result = c.fuse_candidates(dense, lex)
        self.assertEqual(len(result), 200)
        self.assertIn('d99', result)
        self.assertIn('l99', result)
        self.assertEqual(result[:4], ['d0', 'l0', 'd1', 'l1'])
        self.assertEqual(c.fuse_candidates(['same', 'a'], ['same', 'b'])[0], 'same')

    def test_token_cap_not_trailing_whitespace_defines_truncation(self):
        import candidate_recall_benchmark as c
        summary = c.truncation_summary([
            {'tokens': 130, 'omitted_text': 'proof'},
            {'tokens': 20, 'omitted_text': '\n\n'},
            {'tokens': 128, 'omitted_text': ''}], 128)
        self.assertEqual(summary, {'over_token_cap': 1, 'at_or_above_cap': 2,
                                   'omitted_nonwhitespace': 1, 'unencoded_tail': 2})

    def test_angle_brackets_in_code_are_not_mistaken_for_html(self):
        import candidate_recall_benchmark as c
        text = 'a<b>c; vector<T>; <b>must_not</b>'
        tokens = [s['raw'] for s in c.literal_spans(text)]
        self.assertEqual(tokens, ['a', '<', 'b', '>', 'c', 'vector', '<', 'T', '>', '<', 'b', '>', 'must_not', '<', '/', 'b', '>'])

    def test_real_owned_qdrant_frozen_matrix(self):
        import os
        import json
        import hashlib
        import candidate_recall_benchmark as c
        run = os.environ.get('CANDIDATE_REAL_RUN')
        if not run:
            self.skipTest('set CANDIDATE_REAL_RUN to NEW owned path')
        report = c.experiment(Path(run))
        self.assertEqual(report['rows'], 32 * 6 * 3)
        self.assertEqual(report['baseline_parity'], 32)
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertTrue(report['inputs_stable'])
        rows = json.loads((Path(run) / 'raw-results.json').read_bytes())
        self.assertEqual(len(rows), report['rows'])
        for row in rows:
            self.assertEqual(row['top5'], row['pool'][:5])
            self.assertEqual(row['diagnostic'], c.diagnose(row, row['pool']))
            self.assertLessEqual(len(row['pool']), row['budget'])
            self.assertEqual(len(row['pool']), len(set(row['pool'])))
            for snippet in row['snippets_sources']:
                self.assertEqual(hashlib.sha256(snippet['text'].encode()).hexdigest(), snippet['sha256'])
        for name, expected in json.loads((Path(run) / 'evidence-sha256.json').read_bytes()).items():
            self.assertEqual(hashlib.sha256((Path(run) / name).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
