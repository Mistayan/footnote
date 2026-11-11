"""Read-only accounting/scope/provenance audit, never a semantic judge or inference."""
import json
import socket
import statistics
import sys
from collections import Counter
from pathlib import Path
from tools.agent_search_pilot.core import validate_evidence
from tools.agent_search_pilot.verify import jsonl
from tools.agent_search_pilot.retrieval import SNAP, load, sha
from .expanded_core import MODEL, TOOLS, SYSTEM, FINAL_SCHEMA, validate_final
from .expanded_runner import ROOT, OLD_IDS, dump, summarize_usage


def verify_wire(event):
    body=event['body']
    assert event['url']=='https://chatgpt.com/backend-api/codex/responses'
    assert body['model']==MODEL and body['max_output_tokens']==4096
    assert body['tools']==TOOLS and body['instructions']==SYSTEM
    assert body.get('text',{}).get('format')==dict(type='json_schema',name='agent_final_v1',strict=True,schema=FINAL_SCHEMA)
    return True


def verify(run):
    run=Path(run).resolve()
    seal=load(run/'FREEZE.json')
    manifest=load(run/'artifact-sha256.json')
    for p,h in manifest.items():assert sha(run/p)==h,p
    for p,h in seal['protected'].items():assert sha(p)==h,p
    for p,h in seal['models'].items():assert sha(ROOT/p)==h,p
    events=jsonl(run/'sdk-events.jsonl')
    wire=[e for e in events if e['kind']=='wire_request']
    terminals=[e for e in events if e['kind']=='terminal']
    responses=[e['response'] for e in events if e['kind']=='result']
    dispatches=jsonl(run/'dispatches.jsonl')
    traces=jsonl(run/'traces.jsonl')
    rows=jsonl(run/'answers.jsonl')
    modeltraces=[t for t in traces if t['kind']=='model']
    tooltraces=[t for t in traces if t['kind']=='tool']
    retrieval=[t for t in traces if t['kind']=='retrieval']
    report=load(run/'report.json')
    assert len(wire)==len(terminals)==len(responses)==len(modeltraces)==len(dispatches)==report['model_dispatches']<=64
    assert len(rows)==len({r['task_id'] for r in rows})==20
    assert seal['utc'] <= dispatches[0]['utc']
    assert load(run/'route.json')['sdk_max_retries']==0
    assert not any(e['kind'] in ('failure','startup_failure') for e in events)
    tasks={t['id']:t for t in seal['tasks']}
    assert set(tasks)=={r['task_id'] for r in rows} and not set(tasks)&set(OLD_IDS)
    assert seal['system']==SYSTEM and seal['final_schema']==FINAL_SCHEMA
    for i,(w,response,t) in enumerate(zip(wire,responses,modeltraces)):
        verify_wire(w)
        assert w['body']==dispatches[i]['request']==t['request']
        assert response['model']==MODEL and response['status']=='completed'
        assert response['id']==terminals[i]['response_id'] and response['usage']==terminals[i]['usage']
        assert (response.get('usage') or {}).get('output_tokens',0)<=4096
        assert t['response']==response
    from tools.request_scope_repair.compiler import build_catalog,compile_scope,eligible
    sources=load(SNAP/'source-receipts.json')
    raw={s:(SNAP/'sources'/(s+'.raw')).read_text(encoding='utf8') for s in sources}
    texts={s:(SNAP/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources}
    catalog=build_catalog(sources,raw)
    presentations=0
    for row in rows:
        tid=row['task_id']
        assert row['query']==tasks[tid]['query']
        tt=[t for t in tooltraces if t['task_id']==tid]
        searches=[t for t in tt if t['call']['name']=='search' and 'error' not in t['result']]
        gets=[t for t in tt if t['call']['name']=='get' and 'error' not in t['result']]
        refused=[t for t in tt if 'error' in t['result']]
        assert len(searches)==row['searches']<=3
        assert len(gets)==row['gets']<=5 and len(refused)==row['refused_tool_calls']
        mt=[t for t in modeltraces if t['task_id']==tid]
        assert len(mt)==row['model_turns']<=4
        assert mt[0]['request']['tool_choice']=='auto'
        assert mt[0]['request']['input']==[dict(role='user',content=row['query'])]
        if len(mt)==4:assert mt[-1]['request']['tool_choice']=='none'
        rej=[t for t in traces if t['kind']=='validation_reject' and t['task_id']==tid]
        assert len(rej)==len(row['invalid_finals'])
        assert row['validation_retries']<=1
        assert row['validation_retries']==min(1,sum(t['turn']<4 for t in rej))
        hits=[h for t in searches for h in t['result']['candidates']]+[t['result']['evidence'] for t in gets]
        assert all(t['result']['trust']=='untrusted_source_data' and len(t['result']['candidates'])<=5 for t in searches)
        handles={h['handle'] for h in hits}
        assert validate_final(row['raw_final'],handles)==row['final']
        scope=compile_scope(row['query'],catalog)
        for hit in hits:
            validate_evidence(hit,texts)
            assert sha(SNAP/'sources'/(hit['source']+'.txt'))==hit['source_sha256']
            assert hit['scope']==scope['constraints']
            assert eligible([dict(source=hit['source'])],catalog,scope)
            assert hit['provenance']==sources[hit['source']]
            assert hit['provenance']['language']==scope['constraints']['source_language']
            assert scope['constraints']['documented_version']=='3.13'
            presentations+=1
        rr=[r for r in retrieval if r['task_id']==tid]
        assert len(rr)==len(searches)
        for r,t in zip(rr,searches):
            assert r['hits']==t['result']['candidates']
            assert r['ranking']['variant']=='query2'
            assert len(r['ranking']['pairs'])==2*len(r['acquisition']['pool'])
        # Evidence rows must be exactly actual tool returns, not archived/oracle passages.
        assert {h['handle'] for h in row['evidence']}==handles
    usage=summarize_usage(responses)
    assert usage==report['usage']
    assert report['searches']==sum(r['searches'] for r in rows)==len(retrieval)
    assert report['gets']==sum(r['gets'] for r in rows)
    assert report['validation_retries']==sum(r['validation_retries'] for r in rows)
    assert report['refused_tool_calls']==sum(r['refused_tool_calls'] for r in rows)
    packet=load(run/'blind-answer-packet.json')
    mapping=load(run/'mapping-DO-NOT-SEND.json')
    assert len(packet)==len(mapping)==20
    assert len({e['review_id'] for e in packet})==20
    for entry,identity in zip(packet,mapping):
        assert entry['review_id']==identity['review_id']
        row=next(r for r in rows if r['task_id']==identity['task_id'])
        assert entry['question']==row['query'] and entry['final_answer']==row['final'] and entry['raw_final']==row['raw_final']
        expected=[{k:v for k,v in h.items() if k not in ['scope','trust','boundary_complete']} for h in row['evidence']]
        assert entry['source_passages']==expected
        assert set(entry)=={'review_id','question','final_answer','raw_final','source_passages'}
    start=load(run/'resident-start.json')
    cleanup=load(run/'cleanup.json')
    assert cleanup['sdk']['process_exited']
    assert cleanup['resident']['server']['process_exited'] and cleanup['resident']['server']['port_closed']
    with socket.socket() as sock:
        sock.settimeout(2)
        port_closed=sock.connect_ex(('127.0.0.1',start['port']))!=0
    import psutil
    pid_absent=not psutil.pid_exists(start['pid'])
    assert port_closed and pid_absent
    return dict(task_executions=len(rows),wire_requests=len(wire),terminal_completions=len(terminals),
        searches=len(retrieval),gets=report['gets'],validation_retries=report['validation_retries'],refused_tool_calls=report['refused_tool_calls'],
        wire_schema_validated=True,frozen_artifact_hashes_valid=True,protected_inputs_unchanged=len(seal['protected'])+len(seal['models']),
        source_presentations_checked=presentations,source_scope_valid=True,blind_packet_records=len(packet),
        final_abstain_flags=sum(r['final']['abstain'] for r in rows),
        requested_and_response_models=dict(Counter(r['model'] for r in responses)),usage=usage,cost_usd=None,
        actual_reranker_pairs=sum(r['ranking']['pair_count'] for r in retrieval),
        retrieval_seconds=sum(r['elapsed_seconds'] for r in retrieval),model_response_seconds=sum(r['elapsed_seconds'] for r in modeltraces),
        task_wall_seconds_median=statistics.median(r['elapsed_seconds'] for r in rows),
        task_wall_seconds_max=max(r['elapsed_seconds'] for r in rows),
        owned_port_closed=port_closed,owned_pid_absent=pid_absent,
        semantic_success='PENDING independent parent; no implementing-agent semantic score')


if __name__=='__main__':
    run=Path(sys.argv[1]).resolve()
    receipt=verify(run)
    dump(run/'postrun-verification.json',receipt)
    print(json.dumps(receipt,indent=2))
