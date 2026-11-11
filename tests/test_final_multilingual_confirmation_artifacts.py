"""Post-run evidence acceptance checks; no tuning or semantic relevance scoring."""
import unittest,json,hashlib,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
RUN=ROOT/'artifacts/final-multilingual-confirmation/fresh-c6cfd7b5ae4149e7b9f76484e52bf863'
def load(name):return json.loads((RUN/name).read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
class ArtifactVerification(unittest.TestCase):
    def test_frozen_gold_and_four_directions(self):
        gold=load('gold-DO-NOT-SEND.json');answerable=[q for q in gold if q['answerable']]
        self.assertEqual(len(gold),52);self.assertEqual(len(answerable),40)
        # Equal short answers (e.g. ValueError) are different facts when APIs/conditions differ.
        self.assertEqual(len({(q['acceptable_quotes'][0]['source'],q['acceptable_quotes'][0]['start'],q['acceptable_quotes'][0]['end']) for q in answerable}),40)
        for a in ['en','fr']:
            for b in ['en','fr']:self.assertEqual(sum(q['language']==a and q['evidence_language']==b for q in answerable),10)
        for q in answerable:
            for span in q['acceptable_quotes']:
                source=(RUN/'sources'/(span['source']+'.txt')).read_text(encoding='utf8')
                self.assertEqual(source[span['start']:span['end']],span['quote'])
                self.assertIn(span['source'],q['applicability']['eligible_sources'])
    def test_freeze_manifest_and_code_copies(self):
        freeze=load('freeze.json')
        for n,h in freeze['files'].items():self.assertEqual(sha(RUN/n),h,n)
        for n,h in freeze['code'].items():
            self.assertEqual(sha(ROOT/n),h,n);self.assertEqual(sha(RUN/'code-freeze'/n),h,n)
        for n,h in freeze['models'].items():self.assertEqual(sha(ROOT/n),h,n)
        for n,h in load('artifact-sha256.json').items():self.assertEqual(sha(RUN/n),h,n)
    def test_actual_requests_blindness_and_excerpt_hashes(self):
        rows=[json.loads(line) for line in (RUN/'actual-records-DO-NOT-SEND.jsonl').read_text(encoding='utf8').splitlines()]
        packet=load('blind-packet.json');mapping=load('mapping-DO-NOT-SEND.json')
        self.assertEqual(len(rows),52);self.assertEqual(len({r['id'] for r in rows}),52)
        self.assertEqual(len(packet),52);self.assertEqual(len(mapping),52)
        self.assertEqual({r['review_id'] for r in packet},{m['review_id'] for m in mapping})
        self.assertEqual({m['id'] for m in mapping},{r['id'] for r in rows})
        for row in packet:
            self.assertTrue({'id','accepted','answerable','scores','expected_ids','variant','answer_statement'}.isdisjoint(row))
        snippets=0
        for row in rows:
            for e in row['evidence']:
                d=e['original'];v=e['presentation'];p=e['provenance'];source=(RUN/'sources'/(d['source']+'.txt')).read_text(encoding='utf8')
                self.assertEqual(source[v['start']:v['end']],v['text'])
                self.assertEqual(hashlib.sha256(v['text'].encode()).hexdigest(),v['sha256'])
                self.assertEqual(sha(RUN/'sources'/(d['source']+'.raw')),p['sha256'])
                self.assertEqual(sha(RUN/'sources'/(d['source']+'.txt')),p['text_sha256'])
                self.assertLessEqual(len(v['text']),2500)
                if row['request_constraints']:self.assertEqual(p['language'],row['request_constraints']['source_language'])
                snippets+=1
        self.assertEqual(snippets,260)
    def test_actual_qdrant_and_cleanup(self):
        report=load('report.json');cleanup=report['cleanup']['server']
        self.assertEqual(report['index']['indexed_vectors_count'],500)
        self.assertEqual(report['index']['points_count'],500)
        self.assertTrue(cleanup['process_exited']);self.assertTrue(cleanup['port_closed'])
        with socket.socket() as s:
            s.settimeout(.3);self.assertNotEqual(s.connect_ex(('127.0.0.1',cleanup['port'])),0)
        import psutil
        self.assertFalse(psutil.pid_exists(cleanup['pid']))
if __name__=='__main__':unittest.main()
