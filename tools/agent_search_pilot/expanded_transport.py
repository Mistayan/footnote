"""Reuse existing exact provider resolution/SSE handling; enforce versioned wire schema."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.agent_search_pilot import transport as pilot
from tools.agent_search_pilot.expanded_core import FINAL_SCHEMA, MODEL, TOOLS

base_wire_receipt = pilot.wire_receipt


def wire_receipt(request):
    receipt = base_wire_receipt(request)
    fmt = receipt['body'].get('text', {}).get('format', {})
    if fmt != dict(type='json_schema',name='agent_final_v1',strict=True,schema=FINAL_SCHEMA):
        raise ValueError('effective wire final schema mismatch')
    return receipt


def offline_test():
    receipts = []
    response = dict(id='resp_offline',object='response',created_at=0,model=MODEL,status='completed',output=[],usage=None)
    def handler(request):
        payload='event: response.completed\ndata: '+json.dumps(dict(type='response.completed',response=response))+'\n\n'
        payload+='event: error\ndata: '+json.dumps(dict(type='error',message='must not drain'))+'\n\n'
        return pilot.httpx.Response(200,headers={'content-type':'text/event-stream'},content=payload)
    client=pilot.openai.OpenAI(api_key='offline-dummy',base_url='https://offline.invalid',max_retries=0,
        http_client=pilot.httpx.Client(transport=pilot.httpx.MockTransport(handler),event_hooks={'request':[lambda r:receipts.append(wire_receipt(r))]}))
    request=dict(model=MODEL,input=[dict(role='user',content='offline control')],tools=TOOLS,max_output_tokens=4096,stream=True,
        text=dict(format=dict(type='json_schema',name='agent_final_v1',strict=True,schema=FINAL_SCHEMA)))
    events=[]
    try:
        result=pilot.dispatch(client,request,events.append)
        assert result['id']=='resp_offline'
        assert len([e for e in events if e['kind']=='sse'])==1
        # Verify a deliberately missing schema cannot pass the actual hook.
        bad=pilot.httpx.Request('POST','https://offline.invalid/responses',json={k:v for k,v in request.items() if k!='text'})
        try:wire_receipt(bad)
        except ValueError:pass
        else:raise AssertionError('missing wire schema accepted')
        pilot.emit(dict(wire_schema_validated=True,terminal_completion_stops_stream=True,sdk_max_retries=client.max_retries))
    finally:client.close()


if __name__=='__main__':
    if '--offline-test' in sys.argv:
        offline_test()
    else:
        pilot.wire_receipt=wire_receipt
        try:sys.exit(pilot.main())
        except Exception as error:
            pilot.emit(dict(kind='startup_failure',error_type=type(error).__name__,message=str(error)[:1500],usage=None))
            sys.exit(2)
