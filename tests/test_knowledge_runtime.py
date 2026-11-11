"""Small orchestration contract; real backend acceptance lives in companion test."""
import unittest


class ControlledSync(unittest.TestCase):
    def test_sync_observes_only_configured_files_before_reconciliation(self):
        try:
            from tools.knowledge_runtime import KnowledgeRuntime
        except ImportError:
            self.fail('packaged controlled-sync runtime is not implemented')
        class Authority:
            allowed = ['one.md', 'two.txt']
            write = True
            def __init__(self):
                self.events = []
            def read_source(self, name):
                self.events.append(('read', name))
                return b'original' if name == 'one.md' else None
            def handle(self, request):
                self.events.append(request)
                return {'changed': 1, 'pending': 2} if request['op'] == 'ingest' else {'pending': 0}
        authority = Authority()
        runtime = KnowledgeRuntime(authority)
        result = runtime.handle({'op': 'sync'})
        self.assertEqual(result, {'changed': 1, 'pending': 0})
        self.assertEqual(authority.events[:2], [('read', 'one.md'), ('read', 'two.txt')])
        self.assertEqual(authority.events[2], {'op': 'ingest', 'expected': {
            'one.md': '0682c5f2076f099c34cfdd15a9e063849ed437a49677e6fcc5b4198c76575be5',
            'two.txt': None}})
        self.assertEqual(authority.events[3], {'op': 'sync'})

    def test_sync_rejects_bad_request_identity_before_source_reads(self):
        from tools.knowledge_runtime import KnowledgeRuntime
        class MustNotRead:
            write = True
            @property
            def allowed(self):
                raise AssertionError('invalid request touched sources')
        runtime = KnowledgeRuntime(MustNotRead())
        for request_id in (42, 'x' * 65):
            with self.subTest(request_id=request_id), self.assertRaisesRegex(ValueError, 'request_id'):
                runtime.handle({'op': 'sync', 'request_id': request_id})


if __name__ == '__main__':
    unittest.main()
