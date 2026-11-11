"""Finite, opt-in public retrieval experiment acceptance tests."""
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import relevance_candidate_experiment as exp


class CandidateExperimentTest(unittest.TestCase):
    def test_exact_branch_preserves_negative_operator_identity(self):
        docs = [{'id': 'no', 'text': 'must_not != error.code'},
                {'id': 'yes', 'text': 'must not = error code'},
                {'id': 'other', 'text': 'should != other.code'}]
        db = exp.exact_index(docs)
        try:
            self.assertEqual(exp.exact_search(db, 'must_not'), ['no'])
            self.assertEqual(exp.exact_search(db, 'error.code'), ['no'])
            self.assertEqual(exp.exact_search(db, '!='), ['no', 'other'])
            self.assertEqual(exp.exact_search(db, 'What excludes a point?'), [])
            pool = exp.quota_pool(['d' + str(i) for i in range(30)], ['yes'], ['no'])
            self.assertIn('no', pool)
            self.assertIn('d9', pool)
            self.assertEqual(len(pool), 20)
        finally:
            db.close()


    def test_source_structure_preserves_all_evidence_without_judgments(self):
        source = '# Operators\n\n## Exclusions\n' + 'alpha beta gamma ' * 12 + '\nLast proof != STOP\n'
        doc = {'id': 'p', 'source': 's', 'start': 0, 'end': len(source), 'text': source}
        class Budget:
            manifest = {'max_length': 55}
            def token_count(self, text, kind):
                return len(text)
        chunks = exp.structural_chunks([doc], {'s': source}, Budget())
        self.assertEqual(''.join(c['text'] for c in chunks), source)
        self.assertTrue(all(len(c['encoded_text']) < 55 for c in chunks))
        for c in chunks:
            self.assertTrue(c['encoded_text'].startswith(c['text']))
            self.assertEqual(source[c['start']:c['end']], c['text'])
            for heading in c['headings']:
                self.assertEqual(source[heading['start']:heading['end']], heading['text'])
        poisoned = dict(doc, relevant=['secret'], incompatible=['other'], label='leak')
        self.assertEqual(chunks, exp.structural_chunks([poisoned], {'s': source}, Budget()))
        self.assertTrue(any('Exclusions' in h['text'] for c in chunks for h in c['headings']))


    def test_development_only_abstention_does_not_claim_unknown_is_wrong(self):
        rows = [{'split': 'development', 'relevant': ['p'], 'signal': 2},
                {'split': 'development', 'relevant': [], 'signal': 1}]
        self.assertEqual(exp.fit_abstention(rows), 2)
        with self.assertRaises(ValueError):
            exp.fit_abstention([dict(rows[0], split='holdout'), rows[1]])
        with self.assertRaises(ValueError):
            exp.fit_abstention(rows[:1])


    def test_real_frozen_server_matrix(self):
        run = os.environ.get('RELEVANCE_CANDIDATE_RUN')
        if not run:
            self.skipTest('set RELEVANCE_CANDIDATE_RUN to a NEW owned path')
        import json
        import hashlib
        report = exp.experiment(Path(run))
        self.assertEqual(report['rows'], 640)
        self.assertEqual(report['baseline_pool_parity'], 32)
        self.assertTrue(report['inputs_stable'])
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        rows = json.loads((Path(run) / 'raw-results.json').read_bytes())
        self.assertEqual(len(rows), report['rows'])
        import technical_quality as tq
        stable = {}
        for row in rows:
            self.assertEqual(row['metrics'], tq.score(row['top5'], row))
            self.assertTrue(set(row['top5']) <= set(row['candidates']))
            self.assertTrue(all(not row['eligibility'][n].startswith('REJECT') for n in row['top5'] + row['candidates']))
            key = (row['id'], row['variant'])
            if key in stable:
                self.assertEqual(stable[key], row['top5'])
            stable[key] = row['top5']
            for snippet in row['snippets_sources']:
                self.assertEqual(hashlib.sha256(snippet['text'].encode()).hexdigest(), snippet['sha256'])
        for name, expected in json.loads((Path(run) / 'evidence-sha256.json').read_bytes()).items():
            self.assertEqual(hashlib.sha256((Path(run) / name).read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
