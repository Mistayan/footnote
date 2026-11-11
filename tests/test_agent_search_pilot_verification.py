"""Post-run mechanical verification only; no semantic scoring or new inference."""
import unittest
from pathlib import Path


class VerificationTests(unittest.TestCase):
    def test_actual_run_reconciles_wire_usage_tools_and_evidence(self):
        from tools.agent_search_pilot.verify import verify
        run=Path('artifacts/agent-search-pilot/diagnostic-de868c3bac8c4d47986bc8a861189699')
        result=verify(run)
        self.assertEqual(result['task_executions'], 16)
        self.assertEqual(result['wire_requests'], 32)
        self.assertEqual(result['terminal_completions'], 32)
        self.assertEqual(result['actual_searches'], 16)
        self.assertEqual(result['actual_gets'], 0)
        self.assertEqual(result['source_presentations_checked'], 80)
        self.assertTrue(result['frozen_artifact_hashes_valid'])
        self.assertTrue(result['source_scope_valid'])
        self.assertEqual(result['source_scope_checks'], 80)
        self.assertIsNone(result['cost_usd'])
        self.assertEqual(result['semantic_success'], 'PENDING independent reviewer')


if __name__=='__main__':
    unittest.main()
