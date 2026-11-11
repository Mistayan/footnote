"""Focused TDD tests; no runtime or shared-environment mutation."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import pivot_language_experiment as p

class PivotTests(unittest.TestCase):
 def test_immutable_roundtrip_and_corruption_rejected(self):
  text='Ne pas traduire `must_not` ni sqlite3.connect en Python 3.12; WAL != NULL et foo_bar.'
  masked,spans=p.protect(text)
  self.assertGreaterEqual(len(spans),7)
  for token,original in spans:
   self.assertNotIn(original,masked)
  self.assertEqual(p.restore(masked,spans),text)
  self.assertRaises(ValueError,p.restore,masked.replace(spans[0][0],''),spans)
  self.assertRaises(ValueError,p.restore,masked+spans[0][0],spans)
  self.assertRaises(ValueError,p.restore,masked+' BKSPAN999999Z',spans)

 def test_translation_only_natural_spans_and_failclosed(self):
  seen=[]
  def translate(s): seen.append(s); return s.replace('jamais','never')
  result=p.pivot_query('jamais `must_not` 3.12', 'fr', translate)
  self.assertEqual(result['pivot'],'never `must_not` 3.12')
  self.assertFalse(any('must_not' in s or '3.12' in s for s in seen))
  self.assertEqual(p.pivot_query('jamais `x`','en',translate)['pivot'],'jamais `x`')
  bad=p.pivot_query('jamais `x`','fr',lambda s:'BKSPAN999999Z')
  self.assertEqual(bad['pivot'],'jamais `x`')
  self.assertFalse(bad['ok'])

 def test_fixed_acquisition_and_determinism(self):
  dense=['d'+str(i) for i in range(60)]
  original=['o'+str(i) for i in range(20)]
  pivot=['p'+str(i) for i in range(20)]
  for variant in ('baseline','pivot','fusion'):
   order,scores,admitted=p.rank_candidates(dense,original,pivot,variant)
   self.assertEqual(len(admitted),20)
   self.assertLessEqual(len(order[:20]),20)
   self.assertEqual((order,scores,admitted),p.rank_candidates(dense,original,pivot,variant))
  _,_,admitted=p.rank_candidates(dense,original,pivot,'fusion')
  self.assertEqual(set(admitted),set(original[:10]+pivot[:10]))
  self.assertRaises(ValueError,p.rank_candidates,dense,original,pivot,'unknown')

 def test_real_isolated_experiment(self):
  import os
  target=os.environ.get('PIVOT_LANGUAGE_RUN')
  if not target:self.skipTest('explicit opt-in full real translation/Qdrant run')
  report=p.experiment(Path(target))
  self.assertEqual(report['requests'],180)
  self.assertTrue(p.verify_run(Path(target)))
  self.assertTrue(report['cleanup']['process_exited'])
  self.assertTrue(report['cleanup']['port_closed'])

if __name__=='__main__': unittest.main()
