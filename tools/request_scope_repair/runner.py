"""Exposed52 diagnostic; unique artifacts, no historical writes or downloads."""
import sys,json,time,uuid,random,hashlib,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.request_scope_repair.compiler import build_catalog,compile_scope,eligible,get_evidence
from tools.request_scope_repair.retrieval import scoped_search
from tools.final_multilingual_confirmation.runner import Candidate,CONFIG
from tools.evidence_completion.experiment import Session
from tools.acquisition_repair.evaluator import f
SNAP=ROOT/'artifacts/final-multilingual-confirmation/fresh-c6cfd7b5ae4149e7b9f76484e52bf863'
REVIEW=ROOT/'artifacts/fresh-confirmation-review/c8d95379-7837-47cd-ab1a-93308bb084d1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')

class Resident(Candidate):
    def __init__(self,run):
        import numpy as np
        from technical_quality import ResidentEncoder,lexical_index
        from retrieval_ablation import CrossEncoder
        from server_benchmark import Server
        self.run=run;run.mkdir();self.server=None;self.translator=None;self.db=None
        self.docs={d['id']:d for d in f.load(SNAP/'corpus.json')};self.sources=f.load(SNAP/'source-receipts.json')
        self.records=f.load(SNAP/'live/slice96-records.json')
        self.encoder=ResidentEncoder(ROOT/'artifacts/models/minilm');self.ranker=CrossEncoder(f.RANKER)
        self.db=lexical_index(list(self.docs.values()))
        try:
            self.server=Server(run);self.server.start();self.index_info=self.index('selected',self.records,np.load(SNAP/'live/slice96-vectors.npy'))
        except Exception:self.close();raise


def main():
    started=time.perf_counter();run=ROOT/'artifacts/request-scope-repair'/('diagnostic-'+uuid.uuid4().hex);run.mkdir(parents=True)
    inputs=[p for base in [SNAP,REVIEW] for p in base.rglob('*') if p.is_file() and not any(x in p.parts for x in ['storage','temp','snapshots'])]
    before={str(p.relative_to(ROOT)):sha(p) for p in inputs};dump(run/'historical-before.json',before)
    requests=f.load(SNAP/'requests.json');sources=f.load(SNAP/'source-receipts.json');raw={s:(SNAP/'sources'/(s+'.raw')).read_text(encoding='utf8') for s in sources};texts={s:(SNAP/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources}
    catalog=build_catalog(sources,raw);dump(run/'catalog.json',catalog)
    compiled=[dict(id=q['id'],**compile_scope(q['query'],catalog)) for q in requests];dump(run/'compiled-requests.json',compiled)
    dump(run/'RUBRIC.json',f.load(SNAP/'RUBRIC.json'))
    codepaths=list((ROOT/'tools/request_scope_repair').glob('*.py'))+[ROOT/'tests/test_request_scope_repair.py']
    for p in codepaths:
        target=run/'code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    prior_verdicts={v['review_id']:v for v in f.load(REVIEW/'verdicts.json')}
    previous_review={m['id']:prior_verdicts[m['review_id']] for m in f.load(SNAP/'mapping-DO-NOT-SEND.json')}
    protocol=dict(before_inference=True,diagnostic_only=True,fresh_acceptance=False,original_failed_semantic='21/40 accepted-correct; 23/40 raw; 37/40 coverage; 4/12 noanswer false accepts',selected=CONFIG,changes='generic free-text request scope + scope before SQL BM25 limit, Qdrant point limit and independent get; corpus/models/rank input/cutoff unchanged',family='catalog HTML title namespace and URL slug tokens casefolded; generic singular morphology; unions for multi-doc, conflicts abstain; no body-based topic expansion',formal_constraints='none supplied in this run; tests simulate structured user arguments explicitly',baseline='all52 inherited IdentitySearchSession.search unconstrained plus Session.constrained({}, same vector) exact pool/ranks/scores parity; historical match additionally where previous constraints empty',limits='No language inference from query language or source body; unknown required metadata failclosed; no labels used in compiler; no 80% claim',code={str(p.relative_to(ROOT)):sha(p) for p in codepaths},inputs_sha256=sha(run/'historical-before.json'),requests_sha256=sha(run/'compiled-requests.json'),rubric_sha256=sha(run/'RUBRIC.json'),model_hashes=f.load(SNAP/'protocol.json')['models'])
    dump(run/'protocol-freeze.json',protocol)
    old={r['id']:r for r in [json.loads(line) for line in (SNAP/'actual-records-DO-NOT-SEND.jsonl').read_text(encoding='utf8').splitlines()]}
    rows=[];parity=[];historical_parity=[]
    with Resident(run/'live') as session:
        for q,scope in zip(requests,compiled):
            t=time.perf_counter();vector=session.encoder.encode([q['query']],'query')[0];encoding=time.perf_counter()-t
            t=time.perf_counter();baseline=session.search(q['query'],q['language']);baseline_seconds=time.perf_counter()-t
            neutral=Session.constrained(session,q['query'],{},vector)
            equal=all(baseline[k]==neutral[k] for k in ['pool','ranked','scores']);assert equal,q['id'];parity.append(q['id'])
            if not old[q['id']]['request_constraints']:
                match=all(baseline[k]==old[q['id']]['retrieval'][k] for k in ['pool','ranked','scores']);assert match,q['id'];historical_parity.append(q['id'])
            t=time.perf_counter();result=scoped_search(session,q['query'],catalog,scope,vector)
            evidence=[get_evidence(session.docs[n],texts,catalog,scope) for n in result['ranked'][:5]]
            selected_seconds=time.perf_counter()-t+encoding
            token_spans=[]
            for n in result['pool']:
                d=session.docs[n];encoding_pair=session.ranker.tokenizer.encode(q['query'],d['text'])
                offsets=[o for o,s in zip(encoding_pair.offsets,encoding_pair.sequence_ids) if s==1 and o[1]>o[0]]
                token_spans.append(dict(id=n,tokens=sum(encoding_pair.attention_mask),at_limit=sum(encoding_pair.attention_mask)>=512,passage_relative_start=min((a for a,b in offsets),default=None),passage_relative_end=max((b for a,b in offsets),default=None),source_start=d['start'],source_end=d['end']))
            previous=old[q['id']];oldtop=previous['retrieval']['ranked'][:1]
            oldgate=bool(oldtop) and bool(eligible([session.docs[oldtop[0]]],catalog,scope))
            row=dict(**q,scope=scope,accepted=bool(result['ranked']) and max(result['scores'].values(),default=float('-inf'))>=2.5,retrieval=result,evidence=evidence,baseline=baseline,baseline_accepted=bool(baseline['ranked']) and max(baseline['scores'].values(),default=float('-inf'))>=2.5,elapsed_seconds=selected_seconds,baseline_seconds=baseline_seconds,token_spans=token_spans,attribution=dict(previous_top1_in_scope=oldgate,previous_top1_in_new_pool=bool(oldtop) and oldtop[0] in result['pool'],previous_scope=previous['request_constraints'],eligible_sources=sorted({d['source'] for d in eligible(list(session.docs.values()),catalog,scope)}),classification='scope exclusion' if oldtop and not oldgate else 'scope retained; semantic ranking/token-span review needed'))
            for e in evidence:
                d=e['original'];v=e['presentation'];assert texts[d['source']][v['start']:v['end']]==v['text'];assert hashlib.sha256(v['text'].encode()).hexdigest()==v['sha256']
            rows.append(row)
            with (run/'actual-records-DO-NOT-SEND.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(q['id'],round(selected_seconds,3),'paired/parity',flush=True)
    dump(run/'cleanup.json',session.cleanup);assert session.cleanup['server']['port_closed'] and session.cleanup['server']['process_exited']
    gold={q['id']:q for q in f.load(SNAP/'gold-DO-NOT-SEND.json')}
    order=list(rows);random.Random(2026102011).shuffle(order);packet=[];mapping=[]
    for i,row in enumerate(order,1):
        rid=f'S{i:03}';e=row['evidence'][0] if row['evidence'] else None;v=e['presentation'] if e else {}
        packet.append(dict(review_id=rid,query=row['query'],text=v.get('text',''),source=e['provenance'] if e else None,start=v.get('start'),end=v.get('end'),excerpt_sha256=v.get('sha256')))
        mapping.append(dict(review_id=rid,id=row['id'],accepted=row['accepted'],answerable=gold[row['id']]['answerable'],direction=row['language']+'->'+gold[row['id']].get('evidence_language','NA')))
    dump(run/'blind-packet.json',packet);dump(run/'mapping-DO-NOT-SEND.json',mapping)
    dump(run/'failure-attribution-DO-NOT-SEND.json',[dict(id=r['id'],scope=r['scope'],previous_independent_verdict=previous_review[r['id']]['verdict'],previous_independent_rationale=previous_review[r['id']]['rationale'],new_semantic_judgment='PENDING',**r['attribution'],token_spans=r['token_spans'],pool=r['retrieval']['pool'],ranked=r['retrieval']['ranked']) for r in rows])
    def counts(accepted):
        a=[r for r in rows if gold[r['id']]['answerable']];n=[r for r in rows if not gold[r['id']]['answerable']]
        return dict(answerable_accepted=sum(r[accepted] for r in a),answerable_total=len(a),coverage=sum(r[accepted] for r in a)/len(a),noanswer_accepted=sum(r[accepted] for r in n),noanswer_total=len(n))
    expected_id_diagnostic=sum(bool(r['retrieval']['ranked']) and r['retrieval']['ranked'][0] in gold[r['id']]['expected_ids'] for r in rows if gold[r['id']]['answerable'])
    report=dict(run=str(run),requests=len(rows),status='EXPOSED DIAGNOSTIC ONLY; semantic counts pending independent review; ID hits are NOT semantic accuracy',selected=counts('accepted'),baseline=counts('baseline_accepted'),raw_expected_id_hit_diagnostic=expected_id_diagnostic,parsed_language=sum('source_language' in r['scope']['constraints'] for r in rows),parsed_version=sum('documented_version' in r['scope']['constraints'] for r in rows),parsed_family=sum('source_families' in r['scope']['constraints'] for r in rows),actual_parsed40=[dict(id=r['id'],constraints=r['scope']['constraints']) for r in rows if gold[r['id']]['answerable']],exact_unconstrained_live_parity=len(parity),exact_historical_unconstrained_parity=len(historical_parity),historical_parity_ids=historical_parity,latency_seconds=dict(selected_median=statistics.median(r['elapsed_seconds'] for r in rows),selected_max=max(r['elapsed_seconds'] for r in rows),baseline_median=statistics.median(r['baseline_seconds'] for r in rows)),wall_seconds=time.perf_counter()-started,cleanup=session.cleanup,blind_packet='blind-packet.json',rubric='RUBRIC.json',corpus_labels_unchanged=True)
    for p,h in before.items():assert sha(ROOT/p)==h,p
    for p,h in protocol['code'].items():assert sha(ROOT/p)==h,p
    dump(run/'verification.json',dict(historical_files_unchanged=len(before),code_frozen=True,actual_requests=len(rows),snippet_hashes_offsets_verified=True,parity_all52=True))
    dump(run/'report.json',report)
    manifest={str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file() and not any(x in p.parts for x in ['storage','temp','snapshots'])};dump(run/'artifact-sha256.json',manifest)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return run
if __name__=='__main__':main()
