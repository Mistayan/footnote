"""Frozen 8x2 diagnostic pilot. Project interpreter owns retrieval; Hermes owns SDK.
Run: .venv/Scripts/python.exe -m tools.agent_search_pilot.runner
"""
import datetime
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from .core import MODEL, SYSTEM, TOOLS, ToolGate, DispatchBudget, run_task
from .retrieval import PublicRetrieval, SNAP, load, sha

ROOT = Path(__file__).resolve().parents[2]
IDS = ['Q02','Q07','Q25','Q12','Q18','Q33','Q41','Q42']
HERMES_PYTHON = 'C:/Users/johan/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe'
RUBRIC = dict(
    status='PENDING independent parent review; no implementing-agent semantic score',
    task_success='Answerable: final answer must correctly answer EVERY requested part, preserve negation, and be fully supported by the actual cited eligible source passages. Abstention on an answerable task is a miss. No-answer: explicit abstention without inventing the absent API/guarantee is success.',
    citations='Every material answer claim must have a returned citation handle and be entailed by the corresponding presented passage; correct source language, Python version and family are mandatory. Topical overlap is insufficient. Unjudged alternatives can support an answer; selected expected IDs are not correctness.',
    outputs=dict(review_id='string', verdict='pass|fail|uncertain', answer_supported='boolean', citation_complete='boolean', rationale='brief', supporting_quotes='verbatim cited-source substrings'),
    metrics='final task success /8 per arm; answerable success/6; answerable answered/6; no-answer false-answer/2; abstention count; paired differences. 80/90 refer to final task success, NOT first passage. This exposed 8-task diagnostic cannot establish fresh acceptance or vault generalization.',
    blindness='Review final answer + actual passages only; no arm, tool budgets, expected IDs, ranking or old report scores. Freeze reviewer verdicts before joining mapping.')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def append(path, value):
    with path.open('a', encoding='utf8') as out:
        out.write(json.dumps(value, ensure_ascii=False)+'\n')


def freeze(run):
    target = run/'FREEZE.json'
    if target.exists():
        raise ValueError('freeze already exists; never silently rerun exposed outputs')
    requests = {q['id']:q for q in load(SNAP/'requests.json')}
    tasks = [requests[n] for n in IDS]
    code = list((ROOT/'tools/agent_search_pilot').glob('*.py')) + list((ROOT/'tests').glob('test_agent_search_pilot*.py'))
    dependencies = [p for folder in ['request_scope_repair','rank_input_repair','acquisition_repair','evidence_completion','final_multilingual_confirmation','accuracy_validation_v2'] for p in (ROOT/'tools'/folder).glob('*.py')]
    dependencies += [ROOT/'tools'/n for n in ['server_benchmark.py','qdrant_quality.py','technical_quality.py','retrieval_ablation.py','fresh_retrieval_evaluation.py']]
    inputs = [SNAP/n for n in ['requests.json','corpus.json','source-receipts.json','protocol.json','live/slice96-records.json','live/slice96-vectors.npy']]
    inputs += [p for p in (SNAP/'sources').glob('*') if p.is_file()]
    protected = {str(p):sha(p) for p in code+dependencies+inputs}
    # Exact model/server byte identities inherited from the frozen public protocol.
    model_hashes = load(SNAP/'protocol.json')['models']
    for p,h in model_hashes.items():
        if sha(ROOT/p) != h: raise ValueError('frozen model/server mismatch: '+p)
    value = dict(utc=now(),tasks=tasks, strata=dict(answerable=6,noanswer=2,question_language=dict(en=4,fr=4),multipart=['return or raise','ClassVar or InitVar'],negation=['ensure_ascii=False','weakref_slot without slots','maxsize=0']),
                 model=MODEL,route='openai-codex via existing Hermes authorized account; no fallback',
                 limits=dict(model_requests=64,max_output_tokens=4096,concurrency=1,sdk_max_retries=0,single=dict(search=1,get=0,model_turns=2),iterative=dict(search=3,get=5,model_turns=4),top_k=5),
                 arm_order='per task alternating which arm first; identical frozen question, fresh history, shared read-only corpus resident sessions',
                 tools=TOOLS,system=SYSTEM,rubric=RUBRIC,protected=protected,models=model_hashes,
                 retrieval='Standalone actual isolated Qdrant frozen scoped-query2 pipeline; original request scope pinned across reformulation; two original-order inference rounds; raw untrusted top5; no inherited top1 hard cutoff; not shipped runtime.',
                 visibility='Model sees only instructions, current task, returned tool data; no file/terminal/web tools, gold, old reports or other task histories. Existing author judgments are never loaded/copied; outside worker cwd.',
                 diagnostic_only=True,fresh_acceptance=False)
    dump(target,value)
    dump(run/'TASKS.json',tasks)
    dump(run/'RUBRIC.json',RUBRIC)
    for p in code:
        dst=run/'code'/p.relative_to(ROOT)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,dst)
    return value


def summarize_usage(responses):
    names=['input_tokens','output_tokens','total_tokens']
    result={n+'_known_sum':sum((r.get('usage') or {}).get(n) or 0 for r in responses) for n in names}
    result.update(calls=len(responses),missing_usage_calls=sum(r.get('usage') is None for r in responses),cost_usd=None,
                  cost_status='provider billed cost not supplied; known token sums are lower bounds if usage missing')
    return result


class SDKProcess:
    def __init__(self, run, budget):
        self.run,self.budget=run,budget
        self.responses=[]
        self.events=[]
        worker=run/'worker'
        worker.mkdir()
        self.stderr=(run/'sdk-stderr.log').open('w',encoding='utf8')
        env=os.environ.copy()
        env['HERMES_DISABLE_LAZY_INSTALLS']='1'
        env['PYTHONIOENCODING']='utf-8'
        self.process=subprocess.Popen([HERMES_PYTHON,str(ROOT/'tools/agent_search_pilot/transport.py')],
                                      cwd=worker,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,
                                      text=True,encoding='utf8')
        ready=self.read()
        if ready.get('kind')!='ready':
            self.close()
            raise RuntimeError('SDK startup failed: '+json.dumps(ready))
        self.ready=ready
        dump(run/'route.json',ready)

    def read(self):
        line=self.process.stdout.readline()
        if not line: raise RuntimeError('SDK process exited without result; see sdk-stderr.log')
        event=json.loads(line)
        self.events.append(event)
        append(self.run/'sdk-events.jsonl',event)
        return event

    def __call__(self, request):
        serialized=json.dumps(request,ensure_ascii=True)
        self.budget.claim()
        append(self.run/'dispatches.jsonl',dict(number=self.budget.used,utc=now(),request=request))
        self.process.stdin.write(serialized+'\n')
        self.process.stdin.flush()
        while True:
            event=self.read()
            if event['kind']=='result':
                self.responses.append(event['response'])
                return event['response']
            if event['kind'] in ('failure','startup_failure'):
                self.responses.append(dict(usage=None))
                raise RuntimeError('inference blocked: '+json.dumps(event,ensure_ascii=False))

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=10)
        self.stderr.close()
        return dict(process_exited=self.process.poll() is not None,returncode=self.process.returncode)


def main():
    start=time.perf_counter()
    run=ROOT/'artifacts/agent-search-pilot'/('diagnostic-'+uuid.uuid4().hex)
    run.mkdir(parents=True)
    print('RUN',str(run),flush=True)
    seal=freeze(run)
    budget=DispatchBudget(64)
    adapter=sdk=None
    rows=[]
    blocker=None
    context={}
    def record(item):
        append(run/'traces.jsonl',dict(**context,**item))
    cleanup={}
    try:
        adapter=PublicRetrieval(run,record)
        dump(run/'resident-start.json',dict(index=adapter.session.index_info,port=adapter.session.server.port,pid=adapter.session.server.process.pid,encoder_loads=1,reranker_loads=1))
        sdk=SDKProcess(run,budget)
        for index,task in enumerate(seal['tasks']):
            for arm in (['single','iterative'] if index%2==0 else ['iterative','single']):
                context.clear()
                context.update(task_id=task['id'],arm=arm)
                bound=adapter.bind(task['query'])
                gate=ToolGate(arm,bound.search,bound.get)
                row=dict(task_id=task['id'],query=task['query'],arm=arm,**run_task(task['query'],arm,gate,sdk,record))
                rows.append(row)
                append(run/'answers.jsonl',row)
                print(task['id'],arm,row['status'],row['model_turns'],row['searches'],row['gets'],flush=True)
    except Exception as error:
        blocker=dict(type=type(error).__name__,message=str(error),context=dict(context),utc=now())
        dump(run/'BLOCKER.json',blocker)
        print('BLOCKER',json.dumps(blocker,ensure_ascii=True),flush=True)
    finally:
        if sdk is not None:cleanup['sdk']=sdk.close()
        if adapter is not None:
            adapter.close()
            cleanup['resident']=adapter.session.cleanup
        dump(run/'cleanup.json',cleanup)
    # Packet is constructed from actual outputs only; never fabricate missing executions.
    ordered=list(rows)
    random.Random(2026102077).shuffle(ordered)
    packet,mapping=[],[]
    for i,row in enumerate(ordered,1):
        review_id=f'A{i:03}'
        packet.append(dict(review_id=review_id,question=row['query'],final_answer=row['final'],raw_final=row['raw_final'],
                           source_passages=[{k:v for k,v in h.items() if k not in ['scope','trust','boundary_complete']} for h in row['evidence']]))
        mapping.append(dict(review_id=review_id,task_id=row['task_id'],arm=row['arm'],status=row['status']))
    dump(run/'blind-answer-packet.json',packet)
    dump(run/'mapping-DO-NOT-SEND.json',mapping)
    changed=[p for p,h in seal['protected'].items() if sha(p)!=h]
    changed += [p for p,h in seal['models'].items() if sha(ROOT/p)!=h]
    responses=sdk.responses if sdk else []
    report=dict(run=str(run),status='BLOCKED' if blocker else 'COMPLETED_PENDING_INDEPENDENT_REVIEW',
                blocker=blocker,planned_task_executions=16,actual_task_executions=len(rows),
                completed_structurally=sum(r['status']=='completed' for r in rows),model_dispatches=budget.used,
                model_turns_with_responses=sum(r['model_turns'] for r in rows),
                searches=sum(r['searches'] for r in rows),gets=sum(r['gets'] for r in rows),
                usage=summarize_usage(responses),wall_seconds=time.perf_counter()-start,protected_changed=changed,
                cleanup=cleanup,semantic_success='PENDING independent parent; no 80/90/fresh-acceptance claim',
                objective='overall final task success, NOT first-passage top1',diagnostic_only=True)
    dump(run/'report.json',report)
    dump(run/'artifact-sha256.json',{str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file() and not any(n in p.parts for n in ['storage','temp','snapshots','__pycache__'])})
    print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
    return run


if __name__=='__main__':
    main()
