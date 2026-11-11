import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class ConfirmationTest(unittest.TestCase):
    def test_uniform_blocks_keep_original_offsets(self):
        from tools.final_multilingual_confirmation.corpus import blocks
        text='abc def.\n'*600
        rows=blocks('s',text)
        self.assertEqual(rows[0]['start'],0)
        self.assertEqual(rows[1]['start'],900)
        self.assertTrue(all(r['text']==text[r['start']:r['end']] for r in rows))
        self.assertEqual(rows[-1]['end'],len(text))

    def test_extract_keeps_only_document_body(self):
        from tools.final_multilingual_confirmation.corpus import extract
        raw=b'<html><nav>noise</nav><div role="main"><h1>Title</h1><p>A &lt; B.</p><pre>&gt;&gt;&gt; 2\n2</pre></div><footer>noise</footer></html>'
        text=extract(raw)
        self.assertNotIn('noise',text)
        self.assertIn('A < B.',text)
        self.assertIn('>>> 2\n2',text)

    def test_candidate_reuses_selected_functions(self):
        from tools.final_multilingual_confirmation.runner import Candidate,CONFIG
        from tools.evidence_completion.experiment import Session
        from tools.acquisition_repair.identity_evaluator import IdentitySearchSession
        self.assertIs(Candidate.constrained,Session.constrained)
        self.assertIs(Candidate.search,IdentitySearchSession.search)
        self.assertEqual(CONFIG['cutoff'],2.5)
        self.assertEqual(CONFIG['completion_max_chars'],2500)
        self.assertEqual(CONFIG['pool'],20)

if __name__=='__main__':unittest.main()
