import os,unittest

class DevRanking(unittest.TestCase):
    def test_uniform_views_preserve_parent_identity_and_exact_substrings(self):
        from tools.accuracy_validation_v2.dev_intervention import views
        d=dict(id='p',text='abcdefghi',source='s',start=10,end=19)
        result=views([d],4,3)
        self.assertEqual([r['text'] for r in result],['abcd','defg','ghi'])
        self.assertEqual({r['parent_id'] for r in result},{'p'})
        self.assertEqual([r['start'] for r in result],[10,13,16])

    @unittest.skipUnless(os.environ.get('RUN_ACCURACY_V2_DEV')=='1','opt-in real dev-only ranker intervention')
    def test_real_dev_only_intervention(self):
        from tools.accuracy_validation_v2.dev_intervention import run
        report=run()
        self.assertEqual(report['requests'],21)
        self.assertTrue(report['fresh_test_not_loaded'])

if __name__=='__main__':unittest.main()
