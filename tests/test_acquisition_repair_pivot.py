import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class PivotControlTests(unittest.TestCase):
    def test_live_identity_pivot_control(self):
        if '--live' not in sys.argv:self.skipTest('explicit CPU rerank control')
        from tools.acquisition_repair.pivot_control import run_control
        r=run_control()
        self.assertEqual(r['requests'],21)
        self.assertTrue(r['verified'])

if __name__=='__main__':unittest.main()
