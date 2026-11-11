"""New-task end-to-end diagnostic; no acceptance claims or historical rewrites."""
import json
import os
import random
import shutil
import subprocess
import time
import uuid
from collections import Counter
from pathlib import Path
from tools.agent_search_pilot.runner import SDKProcess as PilotSDK, HERMES_PYTHON, dump, append, now, summarize_usage
from tools.agent_search_pilot.retrieval import PublicRetrieval, SNAP, load, sha
from .expanded_core import MODEL, SYSTEM, TOOLS, FINAL_SCHEMA, ToolGate, DispatchBudget, run_task

ROOT=Path(__file__).resolve().parents[2]
OLD_IDS=['Q02','Q07','Q25','Q12','Q18','Q33','Q41','Q42','Q21','Q16','Q35','Q17','Q45','Q13','Q34','Q10']
SEED=2026102082
RUBRIC=dict(
 status='PENDING independent parent review; no implementing-agent semantic score',
 task_success='Answerable: correctly answer EVERY requested part, preserve negation/identifiers and cite applicable evidence. Abstention is a miss. No-answer: abstain=true, evidence_status=insufficient, explain the evidence limitation without inventing the absent value/API/guarantee. A correct premise rejection with abstain=false fails strict success; retain a separate semantic-only verdict.',
 citations='Every material factual claim needs a listed inline actual returned handle and support in that exact passage with requested language/edition/version/family. Topical overlap and selected expected IDs are not correctness. Unlabelled applicable evidence may support answers. Assess reason consistency too.',
 outputs=dict(review_id='string',strict_verdict='pass|fail|uncertain',semantic_verdict='pass|fail|uncertain',answer_supported='boolean',citation_complete='boolean',abstention_consistent='boolean',rationale='brief',supporting_quotes='verbatim cited-source substrings'),
 metrics='Primary strict final success/20; answerable success and coverage/16; no-answer false-answer/4; abstentions; uncertainty; four answerable directional strata of four. 80/90 refer to overall final agent task success, NOT top1. Exposed corpus diagnostic, not fresh acceptance or vault generalization.',
 blindness='Review only blind answer/evidence packet and rubric. No mapping, design strata, traces, rankings, prior reports or gold. Freeze verdicts before joining mapping.')


def select_tasks():
    requests={t['id']:t for t in load(SNAP/'requests.json')}
    metadata=[{k:t[k] for k in ['id','answerable','direction']} for t in load(SNAP/'mapping-DO-NOT-SEND.json')]
    rng=random.Random(SEED)
    picked=[]
    for direction in ['en->en','fr->en','en->fr','fr->fr']:
        pool=sorted([t for t in metadata if t['answerable'] and t['direction']==direction and t['id'] not in OLD_IDS],key=lambda t:t['id'])
        # Feature obligations fixed before inference, independent of retrieval quality.
        # Q24: direct/inherited ordering; Q20: recursive containers/other objects.
        mandatory = [t for t in pool if t['id'] in ['Q24','Q20']]
        picked.extend(mandatory + rng.sample([t for t in pool if t not in mandatory],4-len(mandatory)))
    for language in ['en','fr']:
        pool=sorted([t for t in metadata if not t['answerable'] and requests[t['id']]['language']==language and t['id'] not in OLD_IDS+['Q51','Q52']],key=lambda t:t['id'])
        picked.extend(rng.sample(pool,2))
    rng.shuffle(picked)
    # Explicit two-part expansions of the same remaining-source questions; no oracle.
    requests['Q24'] = dict(requests['Q24'], query=requests['Q24']['query']+' State both the direct-declaration and inherited-field cases.')
    requests['Q20'] = dict(requests['Q20'], query=requests['Q20']['query']+' Distinguez la conversion récursive des types listés et la copie des autres objets.')
    return [requests[t['id']] for t in picked],picked


def freeze(run):
    if (run/'FREEZE.json').exists():raise ValueError('existing freeze: refuse silent replay')
    tasks,strata=select_tasks()
    assert len(tasks)==len({t['id'] for t in tasks})==20
    assert sum(t['answerable'] for t in strata)==16
    assert not set(OLD_IDS)&{t['id'] for t in tasks}
    own=list((ROOT/'tools/agent_search_pilot').glob('*.py'))+list((ROOT/'tests').glob('test_agent_search_pilot*.py'))
    dependencies=[p for folder in ['agent_search_pilot','request_scope_repair','rank_input_repair','acquisition_repair','evidence_completion','final_multilingual_confirmation','accuracy_validation_v2'] for p in (ROOT/'tools'/folder).glob('*.py')]
    dependencies += [ROOT/'tools'/n for n in ['server_benchmark.py','qdrant_quality.py','technical_quality.py','retrieval_ablation.py','fresh_retrieval_evaluation.py']]
    inputs=[SNAP/n for n in ['requests.json','mapping-DO-NOT-SEND.json','corpus.json','source-receipts.json','protocol.json','live/slice96-records.json','live/slice96-vectors.npy']]
    inputs += [p for p in (SNAP/'sources').glob('*') if p.is_file()]
    review=ROOT/'artifacts/agent-answer-review/ab84a86d-4e9f-4342-a9b1-a263b475a764'
    inputs += [p for p in review.glob('*') if p.is_file()]
    historical=ROOT/'artifacts/agent-search-pilot/diagnostic-de868c3bac8c4d47986bc8a861189699'
    inputs += [p for p in historical.rglob('*') if p.is_file() and not any(n in p.parts for n in ['storage','temp','snapshots','__pycache__'])]
    prior=ROOT/'artifacts/agent-search-validation/diagnostic-5326b1f24b754517bbf0edbbf26c5adc'
    inputs += [prior/n for n in ['report.json','TASKS.json','answers.jsonl','FREEZE.json']]
    models=load(SNAP/'protocol.json')['models']
    for p,h in models.items():
        if sha(ROOT/p)!=h:raise ValueError('model/server identity mismatch: '+p)
    protected={str(p):sha(p) for p in own+dependencies+inputs}
    value=dict(utc=now(),tasks=tasks,selection=dict(seed=SEED,old_ids_excluded=OLD_IDS,private_questions_excluded=['Q51','Q52'],
        procedure='Sorted exposed design strata, seeded 4 per answerable direction and 2 public no-answer per language; predeclared multipart obligations Q24 and Q20 expanded to request both cases; exclude original8 and eight completed tasks from quota-blocked validation run; seeded shuffle. No rankings or answer keys used.',
        answerable=16,noanswer=4,question_language=dict(Counter(t['language'] for t in tasks)),answerable_directions=dict(Counter(t['direction'] for t in strata if t['answerable']))),
        model=MODEL,route='openai-codex existing Hermes authorized account; no fallback',
        limits=dict(model_requests=64,max_output_tokens=4096,concurrency=1,sdk_max_retries=0,search=3,get=5,model_turns=4,top_k=5,max_wall_seconds=1500),
        tools=TOOLS,system=SYSTEM,final_schema=FINAL_SCHEMA,rubric=RUBRIC,protected=protected,models=models,
        retrieval='Actual isolated Qdrant scoped-query2 adapter; resident encoder/reranker, original scope pinned across reformulations and rechecked at get. Raw untrusted top5, no top1 cutoff. Standalone not production activation.',
        visibility='Only system/current question/actual tool exchanges to model. No gold, design labels, archived ranks, judge output or other histories. Design labels never used as runtime answerability oracle.',
        changes='Versioned final schema, explicit abstain semantics, optional search auto, at most ONE mechanical repair within four turns; no prose-pattern oracle, flag mutation or historical rewriting.',
        diagnostic_only=True,fresh_acceptance=False,corpus_status='Existing exposed52 retrieval diagnostic; twenty tasks new to end-to-end inference, NOT fresh corpus')
    dump(run/'TASKS.json',tasks)
    dump(run/'TASK-STRATA-DO-NOT-SEND.json',strata)
    dump(run/'RUBRIC.json',RUBRIC)
    dump(run/'FREEZE.json',value)
    for p in own+dependencies:
        dest=run/'code'/p.relative_to(ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,dest)
    return value


class DeadlineBudget(DispatchBudget):
    def __init__(self,deadline):
        super().__init__(64)
        self.deadline=deadline

    def claim(self):
        if time.perf_counter()+190>self.deadline:raise ValueError('25-minute execution deadline reserve reached')
        super().claim()


class SDKProcess(PilotSDK):
    def __init__(self,run,budget):
        self.run,self.budget=run,budget
        self.responses,self.events=[],[]
        worker=run/'worker'
        worker.mkdir()
        self.stderr=(run/'sdk-stderr.log').open('w',encoding='utf8')
        env=os.environ.copy()
        env.update(HERMES_DISABLE_LAZY_INSTALLS='1',PYTHONIOENCODING='utf-8')
        self.process=subprocess.Popen([HERMES_PYTHON,str(ROOT/'tools/agent_search_pilot/expanded_transport.py')],cwd=worker,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,encoding='utf8')
        ready=self.read()
        if ready.get('kind')!='ready':
            self.close()
            raise RuntimeError('SDK startup failed: '+json.dumps(ready))
        self.ready=ready
        dump(run/'route.json',ready)


def export_blind(run,rows,strata):
    ordered=list(rows)
    random.Random(SEED+1).shuffle(ordered)
    byid={t['id']:t for t in strata}
    packet,mapping=[],[]
    for i,row in enumerate(ordered,1):
        rid=f'V{i:03}'
        packet.append(dict(review_id=rid,question=row['query'],final_answer=row['final'],raw_final=row['raw_final'],
            source_passages=[{k:v for k,v in h.items() if k not in ['scope','trust','boundary_complete']} for h in row['evidence']]))
        mapping.append(dict(review_id=rid,task_id=row['task_id'],status=row['status'],**{k:v for k,v in byid[row['task_id']].items() if k!='id'}))
    dump(run/'blind-answer-packet.json',packet)
    dump(run/'mapping-DO-NOT-SEND.json',mapping)


def main():
    start=time.perf_counter()
    run=ROOT/'artifacts/agent-search-expanded'/('diagnostic-'+uuid.uuid4().hex)
    run.mkdir(parents=True)
    print('RUN',str(run),flush=True)
    preflight=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-m','unittest','discover','-s','tests','-p','test_agent_search_pilot*.py','-v'],cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=240)
    (run/'offline-tests-before-inference.log').write_text(preflight.stdout+preflight.stderr,encoding='utf8')
    if preflight.returncode:raise RuntimeError('Offline prerequisite tests failed; no model dispatch allowed')
    seal=freeze(run)
    budget=DeadlineBudget(start+1500)
    adapter=sdk=None
    rows=[]
    blocker=None
    context={}
    cleanup={}
    def record(item):append(run/'traces.jsonl',dict(**context,**item))
    try:
        adapter=PublicRetrieval(run,record)
        dump(run/'resident-start.json',dict(index=adapter.session.index_info,port=adapter.session.server.port,pid=adapter.session.server.process.pid,encoder_loads=1,reranker_loads=1))
        sdk=SDKProcess(run,budget)
        for task in seal['tasks']:
            context.clear()
            context.update(task_id=task['id'],arm='expanded-adaptive-v1')
            bound=adapter.bind(task['query'])
            gate=ToolGate(bound.search,bound.get)
            row=dict(task_id=task['id'],query=task['query'],**run_task(task['query'],gate,sdk,record))
            rows.append(row)
            append(run/'answers.jsonl',row)
            print(task['id'],row['status'],row['model_turns'],row['searches'],row['gets'],flush=True)
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
    export_blind(run,rows,load(run/'TASK-STRATA-DO-NOT-SEND.json'))
    changed=[p for p,h in seal['protected'].items() if sha(p)!=h]
    changed += [p for p,h in seal['models'].items() if sha(ROOT/p)!=h]
    report=dict(run=str(run),status='BLOCKED' if blocker else 'COMPLETED_PENDING_INDEPENDENT_REVIEW',blocker=blocker,
        planned_task_executions=20,actual_task_executions=len(rows),completed_structurally=sum(r['status']=='completed' for r in rows),
        model_dispatches=budget.used,model_turns_with_responses=sum(r['model_turns'] for r in rows),searches=sum(r['searches'] for r in rows),gets=sum(r['gets'] for r in rows),
        validation_retries=sum(r['validation_retries'] for r in rows),refused_tool_calls=sum(r['refused_tool_calls'] for r in rows),
        usage=summarize_usage(sdk.responses if sdk else []),wall_seconds=time.perf_counter()-start,protected_changed=changed,cleanup=cleanup,
        semantic_success='PENDING independent parent; no self-acceptance or 80/90 claim',objective='overall final agent task success NOT top1',diagnostic_only=True)
    dump(run/'report.json',report)
    dump(run/'artifact-sha256.json',{str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file() and not any(n in p.parts for n in ['storage','temp','snapshots','__pycache__'])})
    print(json.dumps(report,ensure_ascii=True,indent=2),flush=True)
    return run


if __name__=='__main__':main()
