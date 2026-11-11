"""New-artifact, development-first resident rank-input experiment. No runtime changes."""
import sys,json,time,uuid,random,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.request_scope_repair.runner import Resident,SNAP,sha,dump
from tools.request_scope_repair.compiler import build_catalog,compile_scope,get_evidence
from tools.request_scope_repair.retrieval import scoped_search
from tools.rank_input_repair.core import query_view,make_pairs,aggregate,visibility,pair_rounds,passage_views
from tools.acquisition_repair.evaluator import SEED,SNAPSHOT as DEV,f
from tools.final_multilingual_confirmation.runner import Candidate
VARIANTS={'full2':(None,2,False),'query2':(None,2,True),'window256x2':(256,2,True),'full3':(None,3,False),'window384x3':(384,3,True)}

def append(path,value):
    with path.open('a',encoding='utf8') as out:out.write(json.dumps(value,ensure_ascii=False)+'\n')

class DevResident(Resident):
    def __init__(self,run):
        import numpy as np
        from technical_quality import ResidentEncoder,lexical_index
        from retrieval_ablation import CrossEncoder
        from server_benchmark import Server
        self.run=run;run.mkdir();self.server=None;self.translator=None;self.db=None
        self.docs={d['id']:d for d in f.load(DEV/'corpus.json')};self.sources=f.load(DEV/'source-receipts.json');self.records=f.load(SEED/'slice96-records.json')
        self.encoder=ResidentEncoder(ROOT/'artifacts/models/minilm');self.ranker=CrossEncoder(f.RANKER);self.db=lexical_index(list(self.docs.values()))
        try:self.server=Server(run);self.server.start();self.index_info=self.index('selected',self.records,np.load(SEED/'slice96-vectors.npy'))
        except Exception:self.close();raise

class NoRank:
    def rank(self,query,documents):return [],{}

def acquire(session,query,catalog,scope):
    # Use the existing exact constrained acquisition, suppress ONLY its rerank.
    ranker=session.ranker
    try:
        session.ranker=NoRank()
        vector=session.encoder.encode([query],'query')[0]
        return scoped_search(session,query,catalog,scope,vector)
    finally:session.ranker=ranker

def rerank(session,q,scope,pool,variant):
    from tokenizers import Tokenizer
    cap,count,compact=VARIANTS[variant]
    tokenizer=Tokenizer.from_str(session.ranker.tokenizer.to_str());tokenizer.no_truncation();tokenizer.no_padding()
    view=query_view(q,scope,True) if compact else dict(text=q,removed=[])
    pairs=make_pairs(q,[session.docs[n] for n in pool],tokenizer,cap,count)
    t=time.perf_counter();scores={}
    for batch_round in pair_rounds(pairs):
        _,round_scores=session.ranker.rank(view['text'],batch_round);scores.update(round_scores)
    seconds=time.perf_counter()-t
    ranking,parent_scores=aggregate(pairs,scores)
    return dict(variant=variant,query_view=view,pairs=pairs,pair_scores=scores,pair_count=len(pairs),ranked=ranking,scores=parent_scores,accepted=bool(ranking) and parent_scores[ranking[0]]>=2.5,rerank_seconds=seconds)

def main(development_receipt=None):
    start=time.perf_counter();run=ROOT/'artifacts/rank-input-repair'/('diagnostic-'+uuid.uuid4().hex);run.mkdir(parents=True)
    history=[]
    prior=ROOT/'artifacts/request-scope-repair/diagnostic-75f19087167340f3b8d23ed91a1d5947'
    for base in [SNAP,DEV,prior]:
        history.extend(p for p in base.rglob('*') if p.is_file() and not any(x in p.parts for x in ['storage','temp','snapshots','__pycache__']))
    history.extend([SEED/'slice96-records.json',SEED/'slice96-vectors.npy'])
    if development_receipt:
        history.extend(p for p in Path(development_receipt).rglob('*') if p.is_file() and not any(x in p.parts for x in ['storage','temp','snapshots','__pycache__']))
    before={str(p.relative_to(ROOT)):sha(p) for p in history};dump(run/'historical-before.json',before)
    code=list((ROOT/'tools/rank_input_repair').glob('*.py'))+[ROOT/'tests/test_rank_input_repair.py']
    for p in code:
        target=run/'code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    freeze=dict(utc=f.now(),before_development=development_receipt is None,development_receipt=str(development_receipt) if development_receipt else None,variants=VARIANTS,selection='old dev16+5 selected-positive top1 then MRR; baseline tie preference; templates mechanical only, never selection/generalization; no old52 inference until selection freeze',scope='original query dense/FTS/tool protocol/evidence; compact rank-only after prelimit hard constraints and independent get',windows='source sentence/paragraph greedy token bounded windows; original-query lexical overlap ordering; no labels; no title enrichment',budget='full2/query2/256x2 each 2 actual model pairs per original candidate; full3/384x3 each 3; duplicate slots when fewer windows; max logit parent; <=20 original parents',refusal='2.5 frozen, NOT assumed calibrated across views; unthresholded primary, frozen cutoff secondary',code={str(p.relative_to(ROOT)):sha(p) for p in code},models=f.load(SNAP/'protocol.json')['models'],diagnostic_only=True)
    dump(run/'execution-freeze.json',freeze)
    dev=f.load(DEV/'development-judgments.json');devrows=[]
    if development_receipt is None:
        sources=f.load(DEV/'source-receipts.json');raw={s:(DEV/'sources'/(s+'.raw')).read_text(encoding='utf8') for s in sources};catalog=build_catalog(sources,raw)
        with DevResident(run/'development-live') as session:
            for q in dev:
                scope=dict(request=q['query'],constraints={},spans=[],fail_closed=False)
                acquisition=acquire(session,q['query'],catalog,scope)
                for variant in VARIANTS:
                    result=rerank(session,q['query'],scope,acquisition['pool'],variant)
                    ranks=[i+1 for i,n in enumerate(result['ranked']) if n in q['relevant']]
                    row=dict(id=q['id'],query=q['query'],answerable=bool(q['relevant']),top1_label=bool(ranks and ranks[0]==1),rr=1/min(ranks) if ranks else 0,pool=acquisition['pool'],**result)
                    devrows.append(row);append(run/'development-results-DO-NOT-SEND.jsonl',row)
                print('DEV',q['id'],flush=True)
            # Controlled template checks use the SAME two development questions.
            for old in dev[8:10]:
                query='According to the English Python 3.13 documentation, '+old['query']
                scope=compile_scope(query,catalog);acquisition=acquire(session,query,catalog,scope)
                for variant in ['full2','query2','window256x2']:
                    result=rerank(session,query,scope,acquisition['pool'],variant)
                    assert bool(result['query_view']['removed'])==(variant!='full2')
                    append(run/'controlled-templates-DO-NOT-SEND.jsonl',dict(parent_dev_id=old['id'],query=query,scope=scope,pool=acquisition['pool'],not_generalization=True,**result))
        dump(run/'development-cleanup.json',session.cleanup)
    else:
        receipt=Path(development_receipt).resolve()
        assert receipt.is_relative_to(ROOT/'artifacts/rank-input-repair')
        # Scoring implementation must be EXACTLY the completed dev recipe.
        import inspect
        archived=(receipt/'code/tools/rank_input_repair/runner.py').read_text(encoding='utf8')
        assert inspect.getsource(rerank).strip() in archived
        archive_core=(receipt/'code/tools/rank_input_repair/core.py').read_text(encoding='utf8')
        for func in [query_view,make_pairs,aggregate,pair_rounds,passage_views]:assert inspect.getsource(func).strip() in archive_core
        for name in ['development-results-DO-NOT-SEND.jsonl','controlled-templates-DO-NOT-SEND.jsonl','development-cleanup.json']:
            (run/name).write_bytes((receipt/name).read_bytes())
        devrows=[json.loads(line) for line in (run/'development-results-DO-NOT-SEND.jsonl').read_text(encoding='utf8').splitlines()]
        assert len(devrows)==len(dev)*len(VARIANTS)
        dump(run/'development-reuse-receipt.json',dict(source=str(receipt),selection_sha256=sha(receipt/'selection-freeze.json'),results_sha256=sha(receipt/'development-results-DO-NOT-SEND.jsonl'),model_scoring_code_exact=True,only_change='session-scope reusable untruncated tokenizer for postscore visibility audit; no scoring change'))
    summaries=[]
    for name in VARIANTS:
        rows=[r for r in devrows if r['variant']==name and r['answerable']]
        summaries.append(dict(variant=name,top1=sum(r['top1_label'] for r in rows),answerable=len(rows),mrr=sum(r['rr'] for r in rows)/len(rows),pairs=sum(r['pair_count'] for r in devrows if r['variant']==name),seconds=sum(r['rerank_seconds'] for r in devrows if r['variant']==name)))
    # No-answer cutoff untouched, no diagnostic or templates enter selection.
    winner=max(summaries,key=lambda r:(r['top1'],r['mrr'],r['variant']=='full2',r['variant']=='full3',-VARIANTS[r['variant']][1],r['variant']))['variant']
    if development_receipt:assert winner==f.load(Path(development_receipt)/'selection-freeze.json')['selected']
    dump(run/'selection-freeze.json',dict(utc=f.now(),before_old52=True,selected=winner,summaries=summaries,code=freeze['code']))
    # Always exercise the proposed input repair even if dev chooses original control.
    challenger=winner if VARIANTS[winner][0] else 'window256x2'
    count=VARIANTS[challenger][1];baseline='full'+str(count)
    diagnostics=list(dict.fromkeys([baseline,'query2' if count==2 else baseline,challenger]))
    dump(run/'diagnostic-plan-freeze.json',dict(utc=f.now(),selected=winner,challenger=challenger,variants=diagnostics,reason='development selection plus prespecified repair diagnostic; never select again from old52'))
    sources=f.load(SNAP/'source-receipts.json');raw={s:(SNAP/'sources'/(s+'.raw')).read_text(encoding='utf8') for s in sources};texts={s:(SNAP/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources};catalog=build_catalog(sources,raw)
    requests=f.load(SNAP/'requests.json');gold={q['id']:q for q in f.load(SNAP/'gold-DO-NOT-SEND.json')};rows=[];allvisibility=[]
    oldrows={r['id']:r for r in [json.loads(l) for l in (prior/'actual-records-DO-NOT-SEND.jsonl').read_text(encoding='utf8').splitlines()]}
    with Resident(run/'diagnostic-live') as session:
        from tokenizers import Tokenizer
        full_tokenizer=Tokenizer.from_str(session.ranker.tokenizer.to_str());full_tokenizer.no_truncation();full_tokenizer.no_padding()
        for q in requests:
            scope=compile_scope(q['query'],catalog);t=time.perf_counter();acquisition=acquire(session,q['query'],catalog,scope);acqseconds=time.perf_counter()-t
            assert acquisition['pool']==oldrows[q['id']]['retrieval']['pool'],q['id']
            for variant in diagnostics:
                result=rerank(session,q['query'],scope,acquisition['pool'],variant)
                if variant==baseline:
                    assert result['ranked']==oldrows[q['id']]['retrieval']['ranked']
                    assert result['scores']==oldrows[q['id']]['retrieval']['scores']
                evidence=[get_evidence(session.docs[n],texts,catalog,scope) for n in result['ranked'][:5]]
                row=dict(**q,scope=scope,pool=acquisition['pool'],acquisition=acquisition,acquisition_seconds=acqseconds,evidence=evidence,**result);rows.append(row);append(run/'diagnostic-results-DO-NOT-SEND.jsonl',row)
                for p in result['pairs']:
                    d=session.docs[p['parent']];anchors=[];sourceanchors=[]
                    for a in gold[q['id']].get('acceptable_quotes',[]):
                        if a['source']==d['source'] and d['start']+p['start']<=a['start'] and a['end']<=d['start']+p['end']:
                            anchors.append((a['start']-d['start']-p['start'],a['end']-d['start']-p['start']));sourceanchors.append(a)
                    v=visibility(session.ranker.tokenizer,result['query_view']['text'],p['text'],anchors,full_tokenizer=full_tokenizer)
                    entry=dict(id=q['id'],variant=variant,parent=p['parent'],slot=p['slot'],duplicate_slot=p['duplicate_slot'],source=d['source'],source_start=d['start']+p['start'],source_end=d['start']+p['end'],source_anchors=sourceanchors,**v)
                    allvisibility.append(entry);append(run/'token-visibility-DO-NOT-SEND.jsonl',entry)
            print('DIAG',q['id'],flush=True)
    dump(run/'diagnostic-cleanup.json',session.cleanup)
    order=list(rows);random.Random(2026102021).shuffle(order);packet=[];mapping=[]
    for i,row in enumerate(order,1):
        rid=f'V{i:03}';e=row['evidence'][0] if row['evidence'] else None;v=e['presentation'] if e else {}
        packet.append(dict(review_id=rid,query=row['query'],text=v.get('text',''),source=e['provenance'] if e else None,start=v.get('start'),end=v.get('end'),excerpt_sha256=v.get('sha256')))
        mapping.append(dict(review_id=rid,id=row['id'],variant=row['variant'],accepted=row['accepted'],answerable=gold[row['id']]['answerable']))
    dump(run/'blind-packet.json',packet);dump(run/'mapping-DO-NOT-SEND.json',mapping);dump(run/'RUBRIC.json',f.load(SNAP/'RUBRIC.json'))
    report=dict(run=str(run),semantic_status='PENDING BLIND PARENT REVIEW; no80 claim; reused diagnostics only',development=summaries,selected=winner,diagnostic_variants=diagnostics,requests=len(requests),packet_entries=len(packet),wall_seconds=time.perf_counter()-start,variants=[])
    for variant in diagnostics:
        rr=[r for r in rows if r['variant']==variant];vv=[v for v in allvisibility if v['variant']==variant];a=[r for r in rr if gold[r['id']]['answerable']];n=[r for r in rr if not gold[r['id']]['answerable']]
        report['variants'].append(dict(variant=variant,actual_pairs=sum(r['pair_count'] for r in rr),unique_parent_pairs=sum(len(r['pool']) for r in rr),rerank_seconds=sum(r['rerank_seconds'] for r in rr),unthresholded_top1_present=sum(bool(r['ranked']) for r in rr),answerable_accepted=sum(r['accepted'] for r in a),answerable_total=len(a),noanswer_accepted=sum(r['accepted'] for r in n),noanswer_total=len(n),at_limit=sum(v['at_limit'] for v in vv),actually_truncated=sum(v['actually_truncated'] for v in vv),anchors_contained=sum(len(v['anchors']) for v in vv),anchors_fully_visible=sum(x['fully_visible'] for v in vv for x in v['anchors']),raw_expected_id_diagnostic=sum(bool(r['ranked']) and r['ranked'][0] in gold[r['id']]['expected_ids'] for r in a)))
    for p,h in before.items():assert sha(ROOT/p)==h,p
    for p,h in freeze['code'].items():assert sha(ROOT/p)==h,p
    for cleanup in [f.load(run/'development-cleanup.json'),f.load(run/'diagnostic-cleanup.json')]:assert cleanup['server']['port_closed'] and cleanup['server']['process_exited']
    dump(run/'verification.json',dict(historical_files_unchanged=len(before),code_frozen=True,pools_equal_historical=True,baseline_ranks_equal=True,baseline_scores_exact=True,cleanup_verified=True))
    dump(run/'report.json',report)
    manifest={str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file() and not any(x in p.parts for x in ['storage','temp','snapshots'])};dump(run/'artifact-sha256.json',manifest)
    print(json.dumps(report,indent=2),flush=True)
    return run
if __name__=='__main__':main(Path(sys.argv[1]) if len(sys.argv)>1 else None)
