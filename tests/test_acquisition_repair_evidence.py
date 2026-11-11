import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class EvidenceTests(unittest.TestCase):
    def test_saved_run_replays_every_pool_and_preserves_frozen_labels(self):
        from tools.acquisition_repair.audit import audit
        report=audit(ROOT/'artifacts/acquisition-repair/ar-40915afaca8b4fcdb699e70d7ad1b5bf')
        self.assertTrue(report['verified'])
        self.assertEqual(report['acquisition_rows'],966)
        self.assertEqual(report['rerank_rows'],148)
        self.assertEqual(report['validated_source_records'],3125)

if __name__=='__main__':unittest.main()
