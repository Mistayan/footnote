"""Read-only verifier controls. Never dispatches a model."""
import importlib
import json
import unittest
from tools.agent_search_pilot.expanded_core import MODEL, TOOLS, SYSTEM, FINAL_SCHEMA


class VerificationTests(unittest.TestCase):
    def test_effective_wire_schema_route_and_visibility(self):
        try:m=importlib.import_module('tools.agent_search_pilot.expanded_verify')
        except ModuleNotFoundError:self.fail('Read-only wire verifier is not implemented')
        body=dict(model=MODEL,tools=TOOLS,instructions=SYSTEM,max_output_tokens=4096,
                  input=[dict(role='user',content='question')],
                  text=dict(format=dict(type='json_schema',name='agent_final_v1',strict=True,schema=FINAL_SCHEMA)))
        event=dict(url='https://chatgpt.com/backend-api/codex/responses',body=body)
        self.assertTrue(m.verify_wire(event))
        for delta in [dict(model='other'),dict(max_output_tokens=9999),dict(tools=[]),dict(text={}),dict(instructions='different')]:
            with self.subTest(delta=delta):self.assertRaises(AssertionError,m.verify_wire,event|dict(body=body|delta))
        self.assertRaises(AssertionError,m.verify_wire,event|dict(url='https://other.invalid/responses'))


if __name__=='__main__':unittest.main()
