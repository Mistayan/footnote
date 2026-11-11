import os,unittest

class Recovery(unittest.TestCase):
    def test_infrastructure_patch_has_only_predeclared_storage_receipt_changes(self):
        from tools.accuracy_validation_v2.recover import patched_source
        source,edits=patched_source()
        self.assertEqual(len(edits),3)
        self.assertIn("ROOT/'artifacts/accuracy-validation-v2'/('run-'+uuid.uuid4().hex)",source)
        self.assertNotIn("run=SNAPSHOT/'runs'/uuid.uuid4().hex",source)

    @unittest.skipUnless(os.environ.get('RUN_ACCURACY_V2_RECOVERY')=='1','opt-in actual frozen-method infrastructure retry')
    def test_actual_short_path_recovery(self):
        from tools.accuracy_validation_v2.recover import recover
        report=recover()
        self.assertEqual(report['rows'],104)
        self.assertTrue(report['verified'])
        self.assertTrue(report['cleanup']['server']['port_closed'])

if __name__=='__main__':unittest.main()
