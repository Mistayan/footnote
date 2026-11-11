import unittest

class Audit(unittest.TestCase):
    def test_frozen_real_run_independently_replays_metrics_and_provenance(self):
        from tools.accuracy_validation_v2.audit import audit
        report=audit()
        self.assertEqual(report['rows'],104)
        self.assertEqual(report['answerable'],40)
        self.assertTrue(report['all_hashes_and_offsets_verified'])
        self.assertTrue(report['cleanup_verified'])

    def test_global_duplicate_quotes_are_not_hidden_by_source_scope(self):
        from tools.accuracy_validation_v2.audit import audit
        report=audit()
        self.assertFalse(report['global_quote_label_complete'])
        self.assertEqual(len(report['global_quote_label_omissions']),4)

if __name__=='__main__':unittest.main()
