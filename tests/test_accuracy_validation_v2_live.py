"""Opt-in real replay/diagnostic; writes unique receipts, never alters selected inputs."""
import os
import unittest

class LiveReplay(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('RUN_ACCURACY_V2_LIVE')=='1','opt-in actual resident workload')
    def test_replay21_then_frozen_diagnostic_and_dev_refusal(self):
        from tools.accuracy_validation_v2.replay import run
        report=run()
        self.assertEqual(report['exact_parity_requests'],21)
        self.assertEqual(report['diagnostic']['answerable'],48)
        self.assertTrue(report['cleanup']['server']['port_closed'])

    @unittest.skipUnless(os.environ.get('RUN_ACCURACY_V2_ADAPTER')=='1','opt-in real adapter parity')
    def test_adapter_reuses_exact_identity_search_on_development(self):
        from tools.accuracy_validation_v2.session import verify_adapter
        self.assertTrue(verify_adapter())

    @unittest.skipUnless(os.environ.get('RUN_ACCURACY_V2_FRESH')=='1','opt-in sealed fresh validation')
    def test_fresh_actual_frozen_run(self):
        from tools.accuracy_validation_v2.validate import run
        report=run()
        self.assertEqual(report['selected']['answerable'],40)
        self.assertEqual(report['selected']['noanswer'],12)
        self.assertTrue(report['cleanup']['server']['port_closed'])
        self.assertTrue(report['verified'])

if __name__=='__main__':unittest.main()
