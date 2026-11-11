"""Standalone BM25 diagnostic contracts; no network or model needed for unit tests."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))


class BM25Tests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('bm25_retrieval_benchmark'),
                             'new standalone BM25 module must exist')
        import bm25_retrieval_benchmark
        return bm25_retrieval_benchmark

    def test_standard_okapi_formula_and_identifier_tokenization(self):
        m = self.module()
        self.assertEqual(m.tokens('TaskGroup task_group Python3.11 A.B CAFÉ'),
                         ['taskgroup', 'task_group', 'python3.11', 'a.b', 'café'])
        index = m.OkapiBM25([{'id': 'a', 'text': 'task_group task_group'},
                             {'id': 'b', 'text': 'taskgroup'}], k1=1.2, b=0.75)
        scores = dict(index.search('task_group', limit=20))
        expected = math.log(1 + (2 - 1 + .5) / (1 + .5)) * (2 * 2.2) / (2 + 1.2 * (.25 + .75 * 2 / 1.5))
        self.assertAlmostEqual(scores['a'], expected, places=12)
        self.assertNotIn('b', scores)
        self.assertEqual(index.search('absent'), [])
        self.assertEqual(index.search(''), [])
        self.assertEqual(index.search('task_group task_group'), index.search('task_group'))
        tied = m.OkapiBM25([{'id': 'b', 'text': 'x'}, {'id': 'a', 'text': 'x'}])
        self.assertEqual([n for n, _ in tied.search('x')], ['a', 'b'])
        self.assertEqual(m.OkapiBM25([]).search('x'), [])
        with self.assertRaises(ValueError):
            m.OkapiBM25([], b=2)

    def test_uniform_source_representation_and_version_gate(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'representation'), 'source-only representation missing')
        doc = {'id': 'x', 'source': 's', 'text': 'Exact TaskGroup body'}
        sources = {'s': {'url': 'https://raw.githubusercontent.com/python/cpython/v3.12.3/Doc/library/asyncio-task.rst'}}
        texts = {'s': 'Async Tasks\n===========\nOriginal source'}
        enriched = m.representation([doc], sources, texts)
        self.assertEqual(enriched[0]['text'], 'Async Tasks\nExact TaskGroup body')
        sources['s']['relevant'] = ['secret label']
        self.assertEqual(enriched, m.representation([doc], sources, texts))
        states = m.version_states('Python 3.11 request', {'x': doc}, sources)
        self.assertEqual(states['x'], 'REJECT_VERSION')
        self.assertEqual(m.gated_pool(['x'], states), (['x'], [], []))
        sources['s']['url'] = 'https://example.org/unknown'
        self.assertEqual(m.version_states('Python 3.12 request', {'x': doc}, sources)['x'], 'REJECT_UNKNOWN')
        self.assertEqual(m.gated_pool(['x'], {'x': 'NOT_ASSESSED'}), (['x'], ['x'], ['x']))

    def test_paired_runner_and_real_integration_when_requested(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'experiment'), 'frozen paired runner missing')
        with self.assertRaises(ValueError):
            m.experiment(TOOLS / 'forbidden-artifact')
        import os
        if os.environ.get('RUN_BM25_INTEGRATION') == '1':
            import json
            import uuid
            run = TOOLS.parent / 'artifacts/bm25-retrieval' / uuid.uuid4().hex
            report = m.experiment(run)
            self.assertEqual(report['rows'], 448)
            self.assertEqual(report['verification']['gate_violations'], 0)
            self.assertTrue(report['verification']['ranks_stable_across_blocks'])
            self.assertEqual(report['verification']['verified_rows'], 448)
            self.assertTrue(report['cleanup']['process_exited'])
            self.assertTrue(report['cleanup']['port_closed'])
            self.assertEqual(json.loads((run / 'report.json').read_bytes()), report)
            print('BM25_VERIFIED_RUN=' + str(run), flush=True)

    def test_compact_delivery_preserves_full_evidence_and_source_identity(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'compact_delivery'), 'lossless delivery representation missing')
        citation = {'parent_id': 'p', 'passage_id': 'p', 'source': 's', 'url': 'https://example.org/s',
                    'source_raw_sha256': 'rawhash', 'start': 2, 'end': 8, 'text': 'proof!',
                    'snippet': 'proof', 'status': 'UNKNOWN/unjudged', 'sha256': 'passagehash',
                    'metadata': {'version': 'UNKNOWN'}}
        packed = m.compact_delivery({'query': 'question', 'snippets_sources': [citation]})
        self.assertEqual(packed['query'], 'question')
        self.assertEqual(packed['evidence'][0]['text'], 'proof!')
        self.assertEqual(packed['evidence'][0]['parent_id'], 'p')
        for key in ('url', 'source_raw_sha256', 'start', 'end', 'source', 'sha256', 'metadata'):
            self.assertEqual(packed['evidence'][0][key], citation[key])
        self.assertNotIn('snippet', packed['evidence'][0])
        self.assertNotIn('passage_id', packed['evidence'][0])
        other = dict(citation, passage_id='child')
        self.assertEqual(m.compact_delivery({'query': 'q', 'snippets_sources': [other]})['evidence'][0]['passage_id'], 'child')


if __name__ == '__main__':
    unittest.main()
