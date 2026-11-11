"""Read-only verification of the completed diagnostic evidence bundle."""
import json,unittest,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'artifacts/evidence-completion/diagnostic-4d656d0e6d954964aadbf9deb9478a2b'
def load(name):return json.loads((RUN/name).read_text(encoding='utf8'))

class LiveEvidenceTests(unittest.TestCase):
    def test_exact_manifest_readback(self):
        for name,h in load('artifact-sha256.json').items():
            self.assertEqual(hashlib.sha256((RUN/name).read_bytes()).hexdigest(),h,name)

    def test_all_factors_and_frozen_scores(self):
        rows=load('results-DO-NOT-SEND.json')
        self.assertEqual(len(rows),208)
        self.assertEqual(len({r['id'] for r in rows}),52)
        for q in {r['id'] for r in rows}:
            group=[r for r in rows if r['id']==q]
            for gated in (0,1):
                a=next(r for r in group if r['variant']==f'completion0_constraint{gated}')
                b=next(r for r in group if r['variant']==f'completion1_constraint{gated}')
                self.assertEqual(a['ranked'],b['ranked']);self.assertEqual(a['scores'],b['scores']);self.assertEqual(a['accepted'],b['accepted'])
            for r in group:
                if r['variant'].endswith('constraint1') and r['request']:
                    self.assertTrue(all(e['provenance']['language']==r['request']['source_language'] for e in r['evidence']))

    def test_blind_packet_has_no_mapping_labels_or_pipeline(self):
        packet=load('blind-packet.json');self.assertEqual(len(packet),102)
        forbidden={'id','variant','accepted','scores','relevant','expected_spans','original','version','rank','pipeline'}
        self.assertTrue(all(not (forbidden & set(row)) for row in packet))
        self.assertEqual(len(load('mapping-DO-NOT-SEND.json')),208)

if __name__=='__main__':unittest.main()
