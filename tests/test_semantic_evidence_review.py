import unittest
from tools.semantic_evidence_review import audit

class SemanticReviewTests(unittest.TestCase):
    def test_exact_quote_closure_includes_other_editions_without_equating_applicability(self):
        sources = {'en': 'old same proof end', 'fr': 'new same proof end'}
        windows = [{'id': 'a', 'source': 'en', 'start': 0, 'end': 18}, {'id': 'b', 'source': 'fr', 'start': 0, 'end': 18}]
        found = audit.quote_closure('same proof', sources, windows)
        self.assertEqual([x['window_id'] for x in found], ['a', 'b'])
        self.assertTrue(all(x['compatibility'] == 'UNREVIEWED' for x in found))
        self.assertEqual(found[0]['source_start'], 4)
        self.assertEqual(audit.quote_closure('SAME proof', sources, windows), [])

    def test_exact_spans_reject_approximation(self):
        self.assertEqual(audit.exact_span('before proof after', 100, 'proof'), {'quote': 'proof', 'passage_start': 7, 'passage_end': 12, 'source_start': 107, 'source_end': 112})
        with self.assertRaises(ValueError):
            audit.exact_span('before proof after', 100, 'PROOF')

    def test_packet_deduplicates_query_text_and_hides_labels(self):
        e = {'id': 'goldid', 'text': 'proof', 'source': 'en', 'url': 'https://example.org/3.13', 'start': 0, 'end': 5, 'sha256': 'hash', 'raw_sha256': 'raw'}
        rows = [{'id': 'q', 'query': 'Why 3.13?', 'variant': v, 'relevant': ['goldid'], 'scores': {'goldid': 8}, 'accepted': True, 'evidence': [e]} for v in ['selected', 'baseline']]
        packet, mapping = audit.blind_pairs(rows, seed=3)
        self.assertEqual(len(packet), 1)
        self.assertEqual(len(mapping), 2)
        self.assertEqual(set(packet[0]), {'review_id', 'query', 'passage'})
        self.assertNotIn('id', packet[0]['passage'])
        self.assertNotIn('judgment', packet[0]['passage'])
        self.assertNotIn('variant', str(packet))

    def test_scoring_abstention_and_uncertainty_denominators(self):
        rows = [
            {'answerable': True, 'accepted': True, 'verdict': 'pass'},
            {'answerable': True, 'accepted': False, 'verdict': 'pass'},
            {'answerable': True, 'accepted': True, 'verdict': 'uncertain'},
            {'answerable': True, 'accepted': True, 'verdict': 'fail'},
            {'answerable': False, 'accepted': True, 'verdict': 'fail'},
            {'answerable': False, 'accepted': False, 'verdict': 'fail'}]
        s = audit.score(rows)
        self.assertEqual(s['raw_p1'], {'lower_n': 2, 'upper_n': 3, 'denominator': 4})
        self.assertEqual(s['accepted_p1_all_answerable'], {'lower_n': 1, 'upper_n': 2, 'denominator': 4})
        self.assertEqual(s['conditional_precision_all_accepted'], {'lower_n': 1, 'upper_n': 2, 'denominator': 4})
        self.assertEqual(s['answerable_coverage'], {'numerator': 3, 'denominator': 4})
        self.assertEqual(s['noanswer_false_accept'], {'numerator': 1, 'denominator': 2})

    def test_saved_run_ledger_covers_104_rows_and_verbatim_proofs(self):
        from pathlib import Path
        output = audit.ROOT / (audit.ROOT / 'tools/semantic_evidence_review/ACTIVE-RUN.txt').read_text()
        ledger, metrics = audit.assemble(output)
        self.assertEqual(len(ledger), 104)
        self.assertEqual(len({r['review_id'] for r in ledger}), 62)
        for pipeline in metrics.values():
            self.assertEqual(pipeline['raw_p1']['denominator'], 40)
            self.assertEqual(pipeline['noanswer_false_accept']['denominator'], 12)
        for row in ledger:
            p, e = row['passage'], row['evidence_span']
            self.assertEqual(p['text'][e['passage_start']:e['passage_end']], e['quote'])
            source = (audit.SNAP / 'sources' / (p['source'] + '.txt')).read_text(encoding='utf8')
            self.assertEqual(source[e['source_start']:e['source_end']], e['quote'])

if __name__ == '__main__':
    unittest.main()
