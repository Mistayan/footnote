"""Owned query routing experiment contracts; stdlib unittest."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import query_representation_experiment as experiment


class QueryRepresentationTests(unittest.TestCase):
    def test_bilingual_route_preserves_technical_bytes(self):
        route = experiment.lexical_representation
        self.assertEqual(route('Pourquoi SQLite WAL exige-t-il ce réseau ?'), 'SQLite WAL')
        self.assertEqual(route('Why does SQLite WAL require this network?'), 'SQLite WAL')
        self.assertEqual(route('Comment utiliser `must_not`, sqlite3.connect et Python 3.12 ?'), 'must_not sqlite3.connect 3.12')
        self.assertEqual(route('Which ordinary words apply?'), 'Which ordinary words apply?')


    def test_label_invariance_and_provenance(self):
        import hashlib
        text = 'SQLite WAL requires all processes on the same host.'
        doc = dict(id='a', text=text, start=0, end=len(text), source='s',
                   sha256=hashlib.sha256(text.encode()).hexdigest())
        docs = {'a': doc}
        states = {'a': 'NOT_ASSESSED'}
        first = experiment.replay_request('SQLite WAL network', ['a'], ['a'], docs, states)
        poisoned = {'a': dict(doc, relevant=False, answer='never', category='negative')}
        self.assertEqual(first, experiment.replay_request('SQLite WAL network', ['a'], ['a'], poisoned, states))
        self.assertEqual(first['evidence'][0], doc)
        with self.assertRaises(ValueError):
            experiment.replay_request('SQLite WAL', ['a'], [], {'a': dict(doc, text='changed')}, states)
        rejected = experiment.replay_request('SQLite WAL', ['a'], [], docs, {'a': 'REJECT_VERSION'})
        self.assertEqual(rejected['top5'], [])


    def test_executed_paired_replay_and_actual_smoke(self):
        import uuid
        run = experiment.REPO / 'artifacts/query-representation' / ('paired-' + uuid.uuid4().hex)
        report = experiment.run_experiment(run)
        self.assertEqual(report['replay_rows'], 128)
        self.assertEqual(report['baseline_historical_matches'], 32)
        self.assertEqual(report['smoke_requests'], 4)
        self.assertTrue(report['cleanup']['process_exited'])
        self.assertTrue(report['cleanup']['port_closed'])
        self.assertTrue(experiment.verify_run(run))
        print('VERIFIED_RUN=' + str(run))


if __name__ == '__main__':
    unittest.main()
