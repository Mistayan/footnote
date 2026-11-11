"""Read-only post-run reconciliation. No semantic grade and no inference."""
import collections
import json
import socket
import statistics
import sys
from pathlib import Path
from .core import MODEL, TOOLS, validate_evidence, validate_final
from .retrieval import SNAP, sha, load
from .runner import ROOT, dump, summarize_usage


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines()]


def verify(run):
    run=Path(run).resolve()
    seal=load(run/'FREEZE.json')
    manifest=load(run/'artifact-sha256.json')
    for name,h in manifest.items():
        assert sha(run/name)==h,name
    for name,h in seal['protected'].items():
        assert sha(name)==h,name
    for name,h in seal['models'].items():
        assert sha(ROOT/name)==h,name
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
    assert len(rows)==16
    assert not any(e['kind'] in ('failure','startup_failure') for e in events)
    assert len({r['task_id'] for r in rows})==8
    tasks={q['id']:q for q in seal['tasks']}
    for i,(w,response,t) in enumerate(zip(wire,responses,modeltraces)):
        assert w['url']=='https://chatgpt.com/backend-api/codex/responses'
        assert w['body']==dispatches[i]['request']==t['request']
        assert w['body']['model']==response['model']==MODEL
        assert w['body']['tools']==TOOLS and w['body']['max_output_tokens']==4096
        assert response['status']=='completed'
        assert response['id']==terminals[i]['response_id']
        assert response['usage']==terminals[i]['usage']
        assert (response.get('usage') or {}).get('output_tokens',0)<=4096
        assert t['response']==response
    from tools.request_scope_repair.compiler import build_catalog, compile_scope, eligible
    sources=load(SNAP/'source-receipts.json')
    raw={s:(SNAP/'sources'/(s+'.raw')).read_text(encoding='utf8') for s in sources}
    catalog=build_catalog(sources,raw)
    texts={s:(SNAP/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources}
    presentations=0
    scope_checks=0
    for row in rows:
        assert row['query']==tasks[row['task_id']]['query']
        tasktools=[t for t in tooltraces if t['task_id']==row['task_id'] and t['arm']==row['arm']]
        searches=[t for t in tasktools if t['call']['name']=='search']
        gets=[t for t in tasktools if t['call']['name']=='get']
        assert len(tasktools)==len(searches)+len(gets)
        assert len(searches)==row['searches']<= (1 if row['arm']=='single' else 3)
        assert len(gets)==row['gets']<=(0 if row['arm']=='single' else 5)
        assert row['model_turns']<=(2 if row['arm']=='single' else 4)
        assert all('error' not in t['result'] for t in tasktools)
        hits=[h for t in searches for h in t['result']['candidates']]
        assert all(len(t['result']['candidates'])<=5 and t['result']['trust']=='untrusted_source_data' for t in searches)
        handles={h['handle'] for h in hits}
        assert validate_final(row['raw_final'],handles)==row['final']
        for hit in hits:
            validate_evidence(hit,texts)
            assert sha(SNAP/'sources'/(hit['source']+'.txt'))==hit['source_sha256']
            constraints=hit['scope']
            compiled=compile_scope(row['query'],catalog)
            assert constraints==compiled['constraints']
            assert eligible([dict(source=hit['source'])],catalog,compiled)
            assert hit['provenance']==sources[hit['source']]
            if 'source_language' in constraints:
                assert hit['provenance']['language']==constraints['source_language']
            assert constraints.get('documented_version')=='3.13'
            presentations+=1
        taskretrieval=[r for r in retrieval if r['task_id']==row['task_id'] and r['arm']==row['arm']]
        assert len(taskretrieval)==len(searches)
        for r,t in zip(taskretrieval,searches):
            assert r['hits']==t['result']['candidates']
            assert r['ranking']['variant']=='query2'
            assert len(r['ranking']['pairs'])==2*len(r['acquisition']['pool'])
            assert [h['scope'] for h in r['hits']]==[r['scope']['constraints']]*len(r['hits'])
            scope_checks+=1
    usage=summarize_usage(responses)
    assert usage==report['usage']
    start=load(run/'resident-start.json')
    cleanup=load(run/'cleanup.json')
    assert cleanup['sdk']['process_exited']
    assert cleanup['resident']['server']['process_exited'] and cleanup['resident']['server']['port_closed']
    sock=socket.socket()
    try:
        sock.settimeout(2)
        port_closed=sock.connect_ex(('127.0.0.1',start['port']))!=0
    finally:
        sock.close()
    assert port_closed
    import psutil
    pid_absent=not psutil.pid_exists(start['pid'])
    assert pid_absent
    packet=load(run/'blind-answer-packet.json')
    mapping=load(run/'mapping-DO-NOT-SEND.json')
    assert len(packet)==len(mapping)==16
    for entry,identity in zip(packet,mapping):
        assert entry['review_id']==identity['review_id']
        row=next(r for r in rows if r['task_id']==identity['task_id'] and r['arm']==identity['arm'])
        assert entry['question']==row['query'] and entry['final_answer']==row['final']
        assert {h['handle'] for h in entry['source_passages']}=={h['handle'] for h in row['evidence']}
        for key in ['arm','task_id','expected_ids','accepted','scores','ranked']:
            assert key not in entry
    details=[(r.get('usage') or {}).get('input_tokens_details') for r in responses]
    cached=None if any(d is None or 'cached_tokens' not in d for d in details) else sum(d['cached_tokens'] for d in details)
    outdetails=[(r.get('usage') or {}).get('output_tokens_details') for r in responses]
    reasoning=None if any(d is None or 'reasoning_tokens' not in d for d in outdetails) else sum(d['reasoning_tokens'] for d in outdetails)
    arms={}
    for arm in ['single','iterative']:
        rr=[r for r in rows if r['arm']==arm]
        tt=[t for t in modeltraces if t['arm']==arm]
        arms[arm]=dict(executions=len(rr),model_turns=sum(r['model_turns'] for r in rr),
                       searches=sum(r['searches'] for r in rr),gets=sum(r['gets'] for r in rr),
                       final_abstain_flags=sum(r['final']['abstain'] for r in rr),
                       wall_seconds_sum=sum(r['elapsed_seconds'] for r in rr),
                       wall_seconds_median=statistics.median(r['elapsed_seconds'] for r in rr),
                       usage=summarize_usage([t['response'] for t in tt]))
    return dict(task_executions=len(rows),wire_requests=len(wire),terminal_completions=len(terminals),actual_searches=len(retrieval),actual_gets=sum(r['gets'] for r in rows),
                source_presentations_checked=presentations,source_scope_checks=presentations,source_scope_valid=scope_checks==len(retrieval),
                frozen_artifact_hashes_valid=True,protected_inputs_unchanged=len(seal['protected'])+len(seal['models']),
                endpoint='https://chatgpt.com/backend-api/codex/responses',requested_and_response_models=dict(collections.Counter(r['model'] for r in responses)),
                sdk_max_retries=load(run/'route.json')['sdk_max_retries'],max_output_tokens=4096,
                usage=usage,cached_input_tokens=cached,reasoning_output_tokens=reasoning,cost_usd=None,
                retrieval_reranker_actual_pairs=sum(r['ranking']['pair_count'] for r in retrieval),
                retrieval_seconds=sum(r['elapsed_seconds'] for r in retrieval),
                model_response_seconds=sum(r['elapsed_seconds'] for r in modeltraces),
                prompt_calls=len(wire),prompt_tokens=usage['input_tokens_known_sum'],retrieval_tool_calls=len(tooltraces),
                arms=arms,blind_packet_records=len(packet),owned_port_closed=port_closed,owned_pid_absent=pid_absent,
                iterative_observation='Model voluntarily used one search and no get for every task; no reformulation/get behavior exercised online. No adaptive prompting or additional inference performed.',
                semantic_success='PENDING independent reviewer')


if __name__=='__main__':
    run=Path(sys.argv[1]).resolve()
    receipt=verify(run)
    dump(run/'postrun-verification.json',receipt)
    print(json.dumps(receipt,indent=2))
