"""One-process SDK transport using Hermes provider resolution, no AIAgent defaults.
No credentials are opened directly, printed, or persisted. Stdout is JSONL only.
"""
import json
import os
import sys
import time
from pathlib import Path

HERMES = Path('C:/Users/johan/AppData/Local/hermes/hermes-agent')
sys.path.insert(0, str(HERMES))
os.environ['HERMES_DISABLE_LAZY_INSTALLS'] = '1'
import openai
import httpx
from agent.sdk_transform_bypass import bypass_sdk_request_transform


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


def wire_receipt(request):
    body = json.loads(request.content)
    if body['model'] != 'gpt-6.1-sol' or body['max_output_tokens'] != 4096:
        raise ValueError('effective wire model/cap mismatch')
    if [t['name'] for t in body['tools']] != ['search', 'get']:
        raise ValueError('effective wire tool boundary mismatch')
    return dict(kind='wire_request', url=str(request.url), body=body)


def dispatch(client, request, record):
    if request.get('model') != 'gpt-6.1-sol' or request.get('max_output_tokens') != 4096:
        raise ValueError('model/token cap mismatch')
    if [t['name'] for t in request['tools']] != ['search', 'get']:
        raise ValueError('tool schema mismatch')
    start = time.perf_counter()
    with client.responses.create(**bypass_sdk_request_transform(request)) as stream:
        for event in stream:
            item = event.model_dump(mode='json')
            record(dict(kind='sse', event=item))
            if item['type'] == 'response.completed':
                response = item['response']
                if response.get('status') != 'completed':
                    raise RuntimeError('terminal response not completed')
                record(dict(kind='terminal', elapsed_seconds=time.perf_counter()-start,
                            response_id=response.get('id'), model=response.get('model'), usage=response.get('usage')))
                return response
            if item['type'] in ('error','response.failed','response.incomplete'):
                raise RuntimeError('inference terminal failure: '+json.dumps(item))
    raise RuntimeError('stream ended without response.completed')


def offline_test():
    # Synthetic SSE is exclusively an offline harness test, NEVER pilot evidence.
    wire = []
    receipts = []
    response = dict(id='resp_offline', object='response', created_at=0, model='gpt-6.1-sol', status='completed',
                    output=[], usage=None)
    def handler(request):
        body = json.loads(request.content)
        wire.append(body)
        payload = 'event: response.completed\ndata: '+json.dumps(dict(type='response.completed',response=response))+'\n\n'
        # Any drain beyond terminal completion would see an explicit failure frame.
        payload += 'event: error\ndata: '+json.dumps(dict(type='error',message='must not drain'))+'\n\n'
        return httpx.Response(200, headers={'content-type':'text/event-stream'}, content=payload)
    client = openai.OpenAI(api_key='offline-dummy',base_url='https://offline.invalid',max_retries=0,
                          http_client=httpx.Client(transport=httpx.MockTransport(handler), event_hooks={'request':[lambda r: receipts.append(wire_receipt(r))]}))
    request = dict(model='gpt-6.1-sol',input=[dict(role='user',content='offline')],tools=[dict(type='function',name=n,parameters={}) for n in ['search','get']],max_output_tokens=4096,stream=True)
    events = []
    result = dispatch(client, request, events.append)
    assert result['id'] == 'resp_offline' and len([e for e in events if e['kind']=='sse']) == 1
    client.close()
    failures = []
    def reject(request):
        failures.append(1)
        return httpx.Response(429,json={'error':{'message':'offline quota failure','type':'rate_limit_error'}})
    client = openai.OpenAI(api_key='offline-dummy',base_url='https://offline.invalid',max_retries=0,
                          http_client=httpx.Client(transport=httpx.MockTransport(reject)))
    try:
        dispatch(client,request,events.append)
        raise AssertionError('expected offline quota refusal')
    except openai.RateLimitError:
        pass
    finally:
        client.close()
    emit(dict(terminal_completion_stops_stream=True,sdk_max_retries=0,wire_tool_names=[t['name'] for t in wire[0]['tools']],max_output_tokens=wire[0]['max_output_tokens'],error_dispatches=len(failures), wire_url=receipts[0]['url'], wire_model=receipts[0]['body']['model']))


def main():
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from agent.codex_headers import codex_cloudflare_headers
    runtime = resolve_runtime_provider(requested='openai-codex',target_model='gpt-6.1-sol')
    safe_route = {k:runtime.get(k) for k in ['provider','base_url','api_mode','source']}
    if safe_route['base_url'] != 'https://chatgpt.com/backend-api/codex' or safe_route['api_mode'] != 'codex_responses':
        raise RuntimeError('parent route mismatch; no fallback authorized')
    key = runtime['api_key']
    client = openai.OpenAI(api_key=key,base_url=runtime['base_url'],max_retries=0,timeout=180,
                          default_headers=codex_cloudflare_headers(key,base_url=runtime['base_url']),
                          http_client=httpx.Client(timeout=180, event_hooks={'request':[lambda r: emit(wire_receipt(r))]}))
    emit(dict(kind='ready',route=safe_route,model='gpt-6.1-sol',sdk_max_retries=client.max_retries,sdk_version=openai.__version__))
    try:
        for line in sys.stdin:
            request = json.loads(line)
            try:
                result = dispatch(client,request,emit)
                emit(dict(kind='result',response=result))
            except Exception as error:
                # Provider body contains public task input only; never serialize headers or credentials.
                emit(dict(kind='failure',error_type=type(error).__name__,status_code=getattr(error,'status_code',None),
                          body=getattr(error,'body',None),message=str(error)[:2000],usage=None))
                return 2
    finally:
        client.close()
    return 0


if __name__ == '__main__':
    if '--offline-test' in sys.argv:
        offline_test()
    else:
        try:
            sys.exit(main())
        except Exception as error:
            emit(dict(kind='startup_failure',error_type=type(error).__name__,message=str(error)[:1500],usage=None))
            sys.exit(2)
