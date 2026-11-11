"""Final single-exposure confirmation: corpus transport only; original methods reused."""
import sys,json,time,hashlib,random,datetime,inspect,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from tools.evidence_completion.experiment import Session
from tools.evidence_completion.core import get_evidence,request_metadata
from tools.acquisition_repair.core import source_slices
from tools.acquisition_repair.evaluator import f
CONFIG=dict(slice_cap=96,overlap=24,point_limit=400,dense_parent_limit=100,fts_limit=10,rrf_k=60,pool=20,ranker='pinned mMARCO512 longest_first CPU2/1 batch4',cutoff=2.5,completion_max_chars=2500,source_constraint='unchanged request_metadata + eligible + constrained + get_evidence',translation=False)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

class Candidate(Session):
    # ONLY constructor corpus/transport binding changes. Both ranking methods inherited.
    def __init__(self,snapshot,run):
        import numpy as np
        from technical_quality import ResidentEncoder,lexical_index
        from retrieval_ablation import CrossEncoder
        from server_benchmark import Server
        from tokenizers import Tokenizer
        self.run=run;run.mkdir();self.server=None;self.translator=None;self.db=None
        self.docs={d['id']:d for d in f.load(snapshot/'corpus.json')};self.sources=f.load(snapshot/'source-receipts.json')
        self.encoder=ResidentEncoder(ROOT/'artifacts/models/minilm');self.ranker=CrossEncoder(f.RANKER)
        texts={s:(snapshot/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in self.sources}
        tok=Tokenizer.from_file(str(ROOT/'artifacts/models/minilm/tokenizer.json'));tok.no_truncation();tok.no_padding()
        self.records=source_slices(texts,list(self.docs.values()),tok,96,24)
        dump(run/'slice96-records.json',self.records)
        matrix=self.encoder.encode([r['text'] for r in self.records],'passage');np.save(run/'slice96-vectors.npy',matrix)
        self.db=lexical_index(list(self.docs.values()))
        try:self.server=Server(run);self.server.start();self.index_info=self.index('selected',self.records,matrix)
        except Exception:self.close();raise

def freeze(run):
    if (run/'freeze.json').exists():raise ValueError('Never rerun exposed test')
    requests=f.load(run/'requests.json');gold=f.load(run/'gold-DO-NOT-SEND.json');assert len(requests)==len(gold)==52
    sources=f.load(run/'source-receipts.json')
    for s,r in sources.items():
        assert sha(run/'sources'/(s+'.raw'))==r['sha256']
        assert sha(run/'sources'/(s+'.txt'))==r['text_sha256']
    codepaths=[ROOT/'tools'/n for n in ['evidence_completion/core.py','evidence_completion/experiment.py','accuracy_validation_v2/session.py','acquisition_repair/identity_evaluator.py','acquisition_repair/evaluator.py','acquisition_repair/core.py','technical_quality.py','retrieval_ablation.py','server_benchmark.py','qdrant_quality.py','fresh_retrieval_evaluation.py']]
    codepaths+=list((ROOT/'tools/final_multilingual_confirmation').glob('*.py'))+[ROOT/'tests/test_final_multilingual_confirmation.py']
    modelpaths=[p for d in [ROOT/'artifacts/models/minilm',f.RANKER] for p in d.rglob('*') if p.is_file() and '.cache' not in p.parts]
    from server_benchmark import SERVER
    modelpaths.append(SERVER)
    dump(run/'baseline-config.json',dict(CONFIG,completion=False,explicit_source_constraint=False,method='IdentitySearchSession.search unchanged',status='frozen comparator, optional inference omitted for budget'))
    dump(run/'selected-config.json',dict(CONFIG,completion=True,explicit_source_constraint=True,method='evidence_completion.experiment.Session.constrained + core.get_evidence unchanged'))
    rubric=dict(status='INDEPENDENT SEMANTIC JUDGMENT PENDING; not milestone accepted',criterion='Judge ONLY full presented actual evidence. pass if it completely answers the question with correct scope/version and explicitly required source edition; fail for topical-only, invented parameters, missing requested result, wrong edition, or unavailable private facts; uncertain only genuine ambiguity. Do not use outside knowledge to repair an excerpt.',output_schema={'review_id':'string','verdict':'pass|fail|uncertain','support_quote':'verbatim Unicode substring from presented text; empty for fail','rationale':'brief explanation covering all requested aspects'},blindness='Packet excludes query ID, gold, expectedIDs, ranks, scores, accepted flag, pipeline. All actual top1 including refused/no-answer shown. Parent must freeze independent verdicts before opening mapping/gold.',metric='After join: accepted-correct / ALL 40 answerable, abstentions miss; accepted precision and answerable coverage separately; no-answer false accepts /12. 80 first, 90 higher; no implementing-agent semantic score.',limits='Public official corpus not private-vault certification. Four directions use official source edition; some French edition paragraphs remain untranslated English. Author-selected quotes incomplete: any eligible source excerpt genuinely answering is acceptable, IDs never establish semantic correctness.')
    dump(run/'RUBRIC.json',rubric)
    protocol=dict(utc=now(),before_any_fresh_ranking=True,source_gold_edition_closure=True,requests=52,answerable=40,noanswer=12,directions={a+'->'+b:10 for a in ['en','fr'] for b in ['en','fr']},new_topics=['Python json','dataclasses','asyncio queues'],source_version='Official Python 3.13 bytes (mutable upstream URLs pinned by hashes)',segmentation='uniform width1800 stride900 source codepoints, no titles, no gold-derived boundaries',selected=CONFIG,baseline='same identity retrieval no constraints no completion, config frozen; full52 baseline optional omitted for budget',relevance='Independent parent reviewer only; exact-ID diagnostic separate; never fit cutoff on this test',gold='40 distinct facts, no bilingual same-fact duplicates; explicit source edition restricts corpuswide eligible list. Selected quote IDs are incomplete diagnostic only.',noanswer_design='10 hard-near-miss absent API/guarantee plus 2 private-unavailable, all corpuswide absence judged before ranking',olddev_parity='No old per-query artifacts accessed. Exact inherited functions, plus label-free live no-constraint identity comparison. Not claiming olddev21 replay.',source_license='Retained official Python license bytes; PSF v2 documentation, examples additionally 0BSD as stated there',models={str(p.relative_to(ROOT)):sha(p) for p in modelpaths},code={str(p.relative_to(ROOT)):sha(p) for p in codepaths})
    dump(run/'protocol.json',protocol)
    inputs={str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file()}
    dump(run/'freeze.json',dict(utc=now(),before_ranking=True,files=inputs,code=protocol['code'],models=protocol['models']))
    return f.load(run/'freeze.json')

def verify(run,seal):
    for n,h in seal['files'].items():assert sha(run/n)==h,n
    for group in ['code','models']:
        for n,h in seal[group].items():assert sha(ROOT/n)==h,n

def main(run):
    run=Path(run).resolve();seal=freeze(run);verify(run,seal)
    requests=f.load(run/'requests.json');sources=f.load(run/'source-receipts.json');texts={s:(run/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources}
    rows=[];started=time.perf_counter();dump(run/'first-exposure.json',dict(utc=now(),warning='After this exposure diagnostic only; no retuning this test',freeze_sha256=sha(run/'freeze.json')))
    from server_benchmark import ResourceSampler
    with Candidate(run,run/'live') as session:
        sampler=ResourceSampler(session.server);sampler.thread.start()
        try:
            # Label-free live mechanical parity, not historical per-query failure review.
            q='json document serializer';original=session.search(q,'en');bound=session.constrained(q,{},session.encoder.encode([q],'query')[0])
            parity=dict(query=q,exact_pool=original['pool']==bound['pool'],exact_ranking=original['ranked']==bound['ranked'],exact_scores=original['scores']==bound['scores'],method_identity=Candidate.constrained is Session.constrained,scope='one neutral no-language-constraint request, not olddev replay')
            assert all(parity[k] for k in ['exact_pool','exact_ranking','exact_scores','method_identity']);dump(run/'mechanical-parity.json',parity)
            for req in requests:
                t=time.perf_counter();metadata=request_metadata(req['query']);vector=session.encoder.encode([req['query']],'query')[0]
                result=session.constrained(req['query'],metadata,vector)
                evidence=[get_evidence(session.docs[n],texts,sources,metadata,True) for n in result['ranked'][:5]]
                accepted=bool(result['ranked']) and max(result['scores'].values(),default=float('-inf'))>=2.5
                row=dict(**req,request_constraints=metadata,accepted=accepted,evidence=evidence,retrieval=result,elapsed_seconds=time.perf_counter()-t)
                rows.append(row)
                with (run/'actual-records-DO-NOT-SEND.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
                print(req['id'],'completed',round(row['elapsed_seconds'],3),flush=True)
        finally:
            sampler.stop.set();sampler.thread.join();dump(run/'resource-samples.json',sampler.rows)
    dump(run/'cleanup.json',session.cleanup);assert session.cleanup['server']['port_closed'] and session.cleanup['server']['process_exited']
    assert len(rows)==52
    gold={q['id']:q for q in f.load(run/'gold-DO-NOT-SEND.json')}
    packet=[];mapping=[];diagnostic=[];checks=0
    order=list(rows);random.Random(2026102007).shuffle(order)
    for i,row in enumerate(order,1):
        rid=f'B{i:03}';e=row['evidence'][0] if row['evidence'] else None
        view=e['presentation'] if e else None;prov=e['provenance'] if e else None
        packet.append(dict(review_id=rid,query=row['query'],request_constraints=row['request_constraints'],text=view['text'] if view else '',source=prov,start=view['start'] if view else None,end=view['end'] if view else None,excerpt_sha256=view['sha256'] if view else None))
        mapping.append(dict(review_id=rid,id=row['id'],accepted=row['accepted'],answerable=gold[row['id']]['answerable'],direction=row['language']+'->'+gold[row['id']].get('evidence_language','NA')))
        diagnostic.append(dict(id=row['id'],accepted=row['accepted'],exact_expected_id_hit=bool(e) and e['original']['id'] in gold[row['id']]['expected_ids'],semantic_correctness='UNKNOWN, not inferred from ID'))
        for e in row['evidence']:
            d=e['original'];v=e['presentation'];assert texts[d['source']][v['start']:v['end']]==v['text'];assert hashlib.sha256(v['text'].encode()).hexdigest()==v['sha256'];assert v['start']<=d['start']<d['end']<=v['end'];assert v['end']-v['start']<=2500;assert not row['request_constraints'] or e['provenance']['language']==row['request_constraints']['source_language'];checks+=1
    dump(run/'blind-packet.json',packet);dump(run/'mapping-DO-NOT-SEND.json',mapping);dump(run/'exact-ID-diagnostic-DO-NOT-SEND.json',diagnostic)
    answerable=[r for r in rows if gold[r['id']]['answerable']];noanswer=[r for r in rows if not gold[r['id']]['answerable']]
    report=dict(status='PRELIMINARY STRUCTURAL ONLY; semantic judgment pending; no 80/90 claim',actual_requests=len(rows),blind_records=len(packet),answerable=40,noanswer=12,answerable_accepted=sum(r['accepted'] for r in answerable),answerable_rejected=sum(not r['accepted'] for r in answerable),answerable_coverage=sum(r['accepted'] for r in answerable)/40,noanswer_accepted=sum(r['accepted'] for r in noanswer),noanswer_false_acceptance_rate=sum(r['accepted'] for r in noanswer)/12,verified_top5_snippets=checks,boundary_incomplete=sum(e['presentation']['budget_exceeded'] for r in rows for e in r['evidence']),cleanup=session.cleanup,index=session.index_info,wall_seconds=time.perf_counter()-started,baseline='frozen config, not full52 executed',olddev_parity='not replayed; original methods inherited and one live neutral exact parity',packet='blind-packet.json',rubric='RUBRIC.json',mapping='mapping-DO-NOT-SEND.json')
    verify(run,seal);dump(run/'verification.json',dict(frozen_inputs_unchanged=True,source_offsets_hashes_constraints_verified=checks,actual_requests=52,semantic_judgment='pending'))
    dump(run/'report.json',report)
    manifest={str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file() and not any(x in p.parts for x in ['storage','temp','snapshots'])}
    dump(run/'artifact-sha256.json',manifest);assert all(sha(run/n)==h for n,h in manifest.items())
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main(sys.argv[1])
