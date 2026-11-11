import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class IdentityCallableTests(unittest.TestCase):
    def test_live_identity_callable(self):
        if '--live' not in sys.argv:self.skipTest('explicit actual Qdrant callable')
        from tools.acquisition_repair.identity_evaluator import verify_identity
        self.assertEqual(verify_identity()['exact_parity_requests'],21)
if __name__=='__main__':unittest.main()
