"""Fresh public multilingual frozen evidence benchmark; never production activation."""
import argparse, datetime, hashlib, json, math, re, time, uuid
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
BASE=REPO/'artifacts/fresh-multilingual-evaluation'
def windows(source,text,width=1400,stride=900):
    if not 0<stride<=width:raise ValueError('invalid boundaries')
    return [dict(id=f'{source}-{i:04d}',source=source,start=s,end=min(s+width,len(text)),text=text[s:s+width],sha256=hashlib.sha256(text[s:s+width].encode()).hexdigest()) for i,s in enumerate(range(0,len(text),stride))]
def annotate(identifier,query,anchors,corpus,texts,split,language,evidence_language,tags=None):
    spans=[]; relevant=[]
    for source,quote in anchors.items():
        start=texts[source].find(quote)
        if start<0:raise ValueError('missing evidence quote '+identifier)
        spans.append(dict(source=source,start=start,end=start+len(quote),quote=quote))
        relevant.extend(d['id'] for d in corpus if d['source']==source and quote in d['text'])
    if anchors and not relevant:raise ValueError('no complete uniform-window proof '+identifier)
    return dict(id=identifier,query=query,split=split,language=language,evidence_language=evidence_language,tags=tags or [],relevant=sorted(set(relevant)),expected_spans=spans,incompatible=[],judgment='implementing-agent exact selected quote; all other windows UNKNOWN, not independently judged')
def authorize_split(snapshot,split):
    if split=='development':return None
    if split!='test':raise ValueError('unknown split')
    release=Path(snapshot)/'release-test.json'
    if not release.exists():raise ValueError('SEALED: parent must release test with frozen challenger config first')
    r=load(release)
    if r['snapshot_freeze_sha256']!=sha(Path(snapshot)/'freeze.json'):raise ValueError('snapshot differs')
    for name,h in r['candidate_files'].items():
        if sha(REPO/name)!=h:raise ValueError('challenger file changed '+name)
    return r

def release_test(snapshot,candidate):
    snapshot=Path(snapshot); verify_snapshot(snapshot)
    if (snapshot/'release-test.json').exists():raise ValueError('test release already exists; never reselect on this test')
    c=load(candidate)
    if not c.get('name') or not c.get('config') or not c.get('files'):raise ValueError('candidate JSON needs name, full config, files {repo-relative:path sha256}')
    if not c.get('selection_used_development_only'):raise ValueError('development-only selection attestation required')
    for n,h in c['files'].items():
        p=(REPO/n).resolve()
        if not p.is_relative_to(REPO) or sha(p)!=h:raise ValueError('invalid candidate input '+n)
    save(snapshot/'release-test.json',dict(utc=now(),snapshot_freeze_sha256=sha(snapshot/'freeze.json'),candidate_name=c['name'],candidate_config=c['config'],candidate_files=c['files'],candidate_declaration_sha256=sha(candidate),warning='Final test becomes diagnostic after exposure. Do not send test outcomes to candidate selection worker. No further selection on this test.'))

def verify_snapshot(snapshot):
    snapshot=Path(snapshot); freeze=load(snapshot/'freeze.json')
    for name,h in freeze['files'].items():
        p=(snapshot/name).resolve()
        if not p.is_relative_to(snapshot.resolve()) or sha(p)!=h:raise ValueError('frozen input changed '+name)
    corpus=load(snapshot/'corpus.json'); sources=load(snapshot/'source-receipts.json')
    texts={n:(snapshot/'sources'/(n+'.txt')).read_text(encoding='utf8') for n in sources}
    for n,s in sources.items():
        if sha(snapshot/'sources'/(n+'.raw'))!=s['sha256']:raise ValueError('original changed '+n)
        if hashlib.sha256(texts[n].encode()).hexdigest()!=s['text_sha256']:raise ValueError('normalized changed '+n)
    for d in corpus:
        if texts[d['source']][d['start']:d['end']]!=d['text'] or hashlib.sha256(d['text'].encode()).hexdigest()!=d['sha256']:raise ValueError('source span mismatch '+d['id'])
    # Development verification intentionally never opens final test judgments.
    return freeze

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v): Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def load(p): return json.loads(Path(p).read_bytes())
def wilson(k,n):
    if not n:return None
    z=1.959963984540054; p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]
RANKER=REPO/'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model'
VARIANTS=['dense','fts5_and','equal_and_rrf','equal_or_rrf_control','mmarco_or_pool20']

def freeze_snapshot(snapshot):
    import shutil
    snapshot=Path(snapshot).resolve()
    if not snapshot.is_relative_to(BASE) or (snapshot/'freeze.json').exists():raise ValueError('new owned snapshot required')
    protocol=dict(utc=now(),status='SEALED TEST; development baseline only until challenger frozen',metric='exact expected evidence hit@1; denominator ALL answerable including rejected; UNKNOWN not semantically wrong',thresholds={'p1':.8,'stretch':.9,'answerable_coverage':.8,'noanswer_falseaccept_max':.1},criteria_status='proposed strict experiment criteria, NOT user-approved industrial certification',judgments='implementing-agent selected exact quotes, NOT independent human or exhaustive relevance; no posthoc labels',selection='No new-test selection. Candidate development selection and all code/model/gate hashes must be frozen before release-test.',abstention='baselines NONE; no threshold fit on test; nonempty retrieved list counts accepted; no generated answers',segmentation='uniform 1800 Unicode chars, stride900, no heading prefixes, no query labels in chunk creation; width increased from1400 during pre-inference quote-containment preflight',ranking={'variants':VARIANTS,'dense':'MiniLM multilingual manifest128 cosine ANN top60 ef128','fts':'incumbent whitespace literal AND top20; control OR technical terms20','fusion':'equal RRF k60 rank1 document-id ties','reranker':'existing pinned mMARCO cap512 longest-first CPU2/1 batch4, OR-RRF pool20; raw logits descending ID ties; no applicability gate added'},labels='all windows containing complete selected quote; generic collections behavior labeled in both retained releases; version-specific questions require 3.13 source; all other windows UNKNOWN',independence='dev Git log and itertools vs test HTTP caching, collections, argparse, Rust Result; Git/Rust source families previously used but these topics new; multiple questions/source and bilingual version paraphrase correlated; no IID certification',sources='official originals retained; immutable releases/commit/RFC; French HTML mutable URL frozen by exact bytes+hash (not immutable upstream revision)',counts=load(snapshot/'counts.json'),pooling='No post-retrieval relevance pooling performed; claim exact expected-evidence hits ONLY',budget='all corpus indexed; development21 queries and five baselines; final63 sealed queries; resident CPU models; isolated loopback Qdrant1.19.2, new UUID storage;1200s query-work bound')
    save(snapshot/'protocol.json',protocol)
    code=snapshot/'code';code.mkdir()
    shutil.copyfile(Path(__file__),code/'fresh_retrieval_evaluation.py')
    shutil.copyfile(REPO/'tests/fresh_retrieval_evaluation_test.py',code/'fresh_retrieval_evaluation_test.py')
    files={p.relative_to(snapshot).as_posix():sha(p) for p in snapshot.rglob('*') if p.is_file()}
    save(snapshot/'freeze.json',dict(utc=now(),before_any_ranked_outputs=True,files=files))
    verify_snapshot(snapshot)
    return sha(snapshot/'freeze.json')

def queries_for(snapshot,split):
    authorize_split(snapshot,split)
    if split=='test' and not (Path(snapshot)/'test-exposure.json').exists():
        save(Path(snapshot)/'test-exposure.json',dict(utc=now(),status='EXPOSED; diagnostic for any future selection',release_sha256=sha(Path(snapshot)/'release-test.json')))
    return load(Path(snapshot)/(split+'-judgments.json'))

def decorate_rows(rows,documents,sources):
    for r in rows:
        r['evidence']=[documents[n]|{'url':sources[documents[n]['source']]['url'],'raw_sha256':sources[documents[n]['source']]['sha256'],'judgment':'EXPECTED_QUOTE_HIT' if n in r['relevant'] else 'UNKNOWN/unjudged'} for n in r['top5']]
    return rows

def summaries(rows):
    out=[]
    for variant in sorted({r['variant'] for r in rows}):
        group=[r for r in rows if r['variant']==variant]
        for lang,evidence in [('all','all'),('en','all'),('fr','all'),('en','en'),('fr','en'),('en','fr'),('fr','fr')]:
            chosen=[r for r in group if (lang=='all' or r['language']==lang) and (evidence=='all' or r['evidence_language']==evidence)]
            if chosen:out.append(dict(variant=variant,language=lang,evidence_language=evidence,**summarize(chosen)))
    return out

def write_outputs(run,rows,report):
    save(run/'raw-results.json',rows)
    report['summaries']=summaries(rows);report['rows']=len(rows);save(run/'report.json',report)
    lines=['# Per-query exact expected-evidence review','','Implementing-agent incomplete selected quotes. UNKNOWN is not negative. No independent semantic precision or generated-answer claim. No posthoc label changes.','']
    for r in rows:
        lines += [f"## {r['id']} / {r['variant']}",r['query'],f"Expected IDs {r['relevant']}; ordered top5 {r['top5']}",json.dumps(summarize([r]),ensure_ascii=False)]
        for i,e in enumerate(r['evidence'],1):lines += [f"### {i}. {e['id']} — {e['judgment']}",f"{e['url']} original SHA256 {e['raw_sha256']} normalized chars[{e['start']},{e['end']}) excerpt SHA256 {e['sha256']}",'> '+e['text'].replace('\n','\n> ')]
    (run/'PER-QUERY-REVIEW.md').write_text('\n\n'.join(lines)+'\n',encoding='utf8')
    save(run/'evidence-sha256.json',{p.relative_to(run).as_posix():sha(p) for p in run.rglob('*') if p.is_file() and not any(x in p.parts for x in ('storage','snapshots','temp')) and p.name!='evidence-sha256.json'})

def evaluate(snapshot,split='development'):
    import shutil, numpy as np
    import technical_quality as tq
    from qdrant_quality import fresh_connection,rank_parents
    from retrieval_ablation import CrossEncoder,lexical_or
    from server_benchmark import Server,SERVER
    snapshot=Path(snapshot).resolve();verify_snapshot(snapshot);release=authorize_split(snapshot,split)
    # Query labels are loaded only after test release validation.
    queries=queries_for(snapshot,split);corpus=load(snapshot/'corpus.json');sources=load(snapshot/'source-receipts.json');documents={d['id']:d for d in corpus}
    run=BASE/'runs'/uuid.uuid4().hex;run.mkdir(parents=True,exist_ok=False)
    paths=[Path(__file__),REPO/'tests/fresh_retrieval_evaluation_test.py',SERVER,REPO/'requirements-hybrid.lock']+[REPO/'tools'/n for n in ('technical_quality.py','qdrant_quality.py','retrieval_ablation.py','server_benchmark.py','hybrid_dataset.py')]
    paths += [REPO/'artifacts/models/minilm'/n for n in ('manifest.json','model.onnx','tokenizer.json')]+[RANKER/'receipt.json']+[RANKER/n for n in load(RANKER/'receipt.json')['files']]
    inputs={p.relative_to(REPO).as_posix():sha(p) for p in paths}
    (run/'code').mkdir()
    for p in paths:
        if p.suffix=='.py':shutil.copyfile(p,run/'code'/p.name)
    save(run/'execution-freeze.json',dict(utc=now(),snapshot=str(snapshot),snapshot_freeze_sha256=sha(snapshot/'freeze.json'),split=split,inputs=inputs,variants=VARIANTS,release=release,expected_rows=len(queries)*len(VARIANTS),before_inference=True))
    report=dict(run=str(run),snapshot=str(snapshot),split=split,metric='exact expected-evidence hit@1, not exhaustive semantic precision',test_status='SEALED, NOT INFERRED' if split=='development' else 'EXPOSED; future selection diagnostic',blockers=[])
    rows=[];server=None;db=None
    try:
        start=time.perf_counter();encoder=tq.ResidentEncoder(REPO/'artifacts/models/minilm');ranker=CrossEncoder(RANKER)
        report['model_load_validate_ms']=(time.perf_counter()-start)*1000;report['first_inference_utc']=now()
        assert load(run/'execution-freeze.json')['utc']<=report['first_inference_utc']
        start=time.perf_counter();matrix=encoder.encode([d['text'] for d in corpus],'passage');np.save(run/'passage-vectors.npy',matrix)
        report['passage_token_counts']=[encoder.token_count(d['text'],'passage') for d in corpus]
        report['passage_at_or_above_model_cap']=sum(n>=encoder.manifest['max_length'] for n in report['passage_token_counts'])
        db=tq.lexical_index(corpus);server=Server(run);server.start();report['server_identity']=server.request('GET','/');assert report['server_identity']['version']=='1.19.2'
        cfg={'vectors':{'size':384,'distance':'Cosine','on_disk':False},'shard_number':1,'hnsw_config':{'m':16,'ef_construct':100,'full_scan_threshold':10},'optimizers_config':{'indexing_threshold':1,'default_segment_number':1}}
        server.request('PUT','/collections/fresh',cfg)
        for offset in range(0,len(corpus),128):
            server.request('PUT','/collections/fresh/points?wait=true',{'points':[dict(id=i+1,vector=matrix[i].tolist(),payload={'document_id':corpus[i]['id']}) for i in range(offset,min(offset+128,len(corpus)))]})
        deadline=time.monotonic()+120
        while True:
            info=server.request('GET','/collections/fresh')['result']
            if info['status']=='green' and info['indexed_vectors_count']==len(corpus):break
            if time.monotonic()>deadline:raise TimeoutError('actual HNSW index not complete')
            time.sleep(.2)
        back=server.request('POST','/collections/fresh/points',{'ids':list(range(1,len(corpus)+1)),'with_vector':True,'with_payload':True})['result'];back.sort(key=lambda p:p['id'])
        assert len(back)==len(corpus) and all(p['payload']['document_id']==corpus[i]['id'] for i,p in enumerate(back))
        error=float(np.max(np.abs(np.asarray([p['vector'] for p in back])-matrix)));assert error<1e-6
        save(run/'server-readback.json',dict(collection=info,max_abs_error=error,points=back));report['offline_encoding_indexing_ms']=(time.perf_counter()-start)*1000
        measurement=time.monotonic()
        with (run/'raw-results.jsonl').open('w',encoding='utf8') as stream:
            for q in queries:
                for variant in VARIANTS:
                    if time.monotonic()-measurement>1200:raise TimeoutError('bounded query workload exceeded')
                    start=time.perf_counter();fresh_connection(server)
                    vector=encoder.encode([q['query']],'query')[0]
                    response=server.request('POST','/collections/fresh/points/query',dict(query=vector.tolist(),limit=60,with_payload=True,with_vector=False,params={'exact':False,'hnsw_ef':128}))
                    dense=rank_parents(response['result']['points'],corpus)
                    lexical=(lexical_or(db,q['query']) if variant in ('equal_or_rrf_control','mmarco_or_pool20') else tq.lexical_search(db,q['query']))
                    fused=tq.fuse(dense,lexical);pool=fused[:20];logits={}
                    acquired=time.perf_counter()
                    if variant=='dense':ranking=dense
                    elif variant=='fts5_and':ranking=lexical
                    elif variant=='mmarco_or_pool20':ranking,logits=ranker.rank(q['query'],[documents[n] for n in pool])
                    else:ranking=fused
                    top=ranking[:5];reranked=time.perf_counter()
                    row=dict(q,variant=variant,top5=top,ranking=ranking,pool20=pool,dense=dense,lexical=lexical,logits=logits,server_response=response,query_vector=vector.tolist(),utc=now())
                    decorate_rows([row],documents,sources);json.dumps(row['evidence'],ensure_ascii=False).encode('utf8');end=time.perf_counter()
                    row['timing_ms']={'acquisition':(acquired-start)*1000,'rerank':(reranked-acquired)*1000,'citations_serialization':(end-reranked)*1000,'e2e':(end-start)*1000}
                    rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                print(q['id'],'complete five resident baselines',flush=True)
        report['measurement_seconds']=time.monotonic()-measurement;assert len(rows)==len(queries)*len(VARIANTS)
        report['reranker_at_limit']=ranker.at_limit;report['resident_sessions']={'encoders':1,'rankers':1}
        assert all(sha(REPO/n)==h for n,h in inputs.items());verify_snapshot(snapshot);report['frozen_inputs_unchanged']=True
    except Exception as e:
        report['blockers'].append(repr(e));raise
    finally:
        if server is not None:report['cleanup']=server.close()
        if db is not None:db.close()
        write_outputs(run,rows,report)
    print(json.dumps({'run':str(run),'summaries':[s for s in report['summaries'] if s['language']=='all']},indent=2),flush=True)
    return report

def verify_run(run):
    import numpy as np
    import technical_quality as tq
    run=Path(run);manifest=load(run/'evidence-sha256.json')
    for n,h in manifest.items():assert sha(run/n)==h,n
    freeze=load(run/'execution-freeze.json');snapshot=Path(freeze['snapshot']);verify_snapshot(snapshot);assert sha(snapshot/'freeze.json')==freeze['snapshot_freeze_sha256']
    rows=load(run/'raw-results.json');assert len(rows)==freeze['expected_rows'];keys=set()
    corpus=load(snapshot/'corpus.json');documents={d['id']:d for d in corpus};sources=load(snapshot/'source-receipts.json')
    queries={q['id']:q for q in load(snapshot/(freeze['split']+'-judgments.json'))}
    for r in rows:
        assert (r['id'],r['variant']) not in keys;keys.add((r['id'],r['variant']))
        assert r['relevant']==queries[r['id']]['relevant'] and r['query']==queries[r['id']]['query']
        assert r['pool20']==tq.fuse(r['dense'],r['lexical'])[:20]
        expected=r['dense'] if r['variant']=='dense' else r['lexical'] if r['variant']=='fts5_and' else sorted(r['logits'],key=lambda n:(-r['logits'][n],n)) if r['variant']=='mmarco_or_pool20' else tq.fuse(r['dense'],r['lexical'])
        assert r['ranking']==expected and r['top5']==expected[:5]
        copy=dict(r);decorate_rows([copy],documents,sources);assert copy['evidence']==r['evidence']
    report=load(run/'report.json');assert summaries(rows)==report['summaries']
    back=load(run/'server-readback.json');matrix=np.load(run/'passage-vectors.npy');assert np.max(np.abs(matrix-np.asarray([p['vector'] for p in back['points']])))<1e-6
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    return True

def score_predictions(snapshot,predictions,split='development'):
    snapshot=Path(snapshot);verify_snapshot(snapshot);queries=queries_for(snapshot,split)
    records=load(predictions);byid={r['id']:r for r in records}
    if len(byid)!=len(records) or set(byid)!={q['id'] for q in queries}:raise ValueError('predictions must cover every query exactly once')
    corpus=load(snapshot/'corpus.json');docs={d['id']:d for d in corpus};sources=load(snapshot/'source-receipts.json');rows=[]
    for q in queries:
        p=byid[q['id']];top=p['top5']
        if not isinstance(top,list) or len(top)>5 or len(set(top))!=len(top) or any(n not in docs for n in top):raise ValueError('invalid evidence IDs')
        rows.append(dict(q,variant='external_frozen_candidate',top5=top,raw_prediction=p))
    decorate_rows(rows,docs,sources);run=BASE/'scores'/uuid.uuid4().hex;run.mkdir(parents=True,exist_ok=False)
    save(run/'execution-freeze.json',dict(utc=now(),snapshot_freeze_sha256=sha(snapshot/'freeze.json'),predictions_sha256=sha(predictions),split=split,release=authorize_split(snapshot,split)))
    write_outputs(run,rows,dict(run=str(run),snapshot=str(snapshot),split=split,status='external ranks scored, not proof of live pipeline execution'))
    return str(run)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['freeze','verify','run','release-test','score','verify-run']);p.add_argument('--snapshot',type=Path);p.add_argument('--split',choices=['development','test'],default='development');p.add_argument('--candidate',type=Path);p.add_argument('--predictions',type=Path);p.add_argument('--run',type=Path);a=p.parse_args()
    if a.action=='freeze':print(freeze_snapshot(a.snapshot))
    elif a.action=='verify':print(json.dumps(verify_snapshot(a.snapshot),indent=2))
    elif a.action=='run':evaluate(a.snapshot,a.split)
    elif a.action=='release-test':release_test(a.snapshot,a.candidate)
    elif a.action=='score':print(score_predictions(a.snapshot,a.predictions,a.split))
    elif a.action=='verify-run':print(verify_run(a.run))

def summarize(rows):
    yes=[r for r in rows if r['relevant']]; no=[r for r in rows if not r['relevant']]
    correct=sum(bool(r['top5']) and r['top5'][0] in r['relevant'] for r in yes)
    accepted=sum(bool(r['top5']) for r in yes); false=sum(bool(r['top5']) for r in no)
    p=correct/len(yes) if yes else None; coverage=accepted/len(yes) if yes else None; fa=false/len(no) if no else None
    return dict(n=len(rows),answerable=len(yes),correct_top1=correct,p1=p,p1_wilson95=wilson(correct,len(yes)),answerable_accepted=accepted,answerable_rejected=len(yes)-accepted,answerable_coverage=coverage,accepted_correct_precision=correct/accepted if accepted else None,noanswer=len(no),noanswer_falseaccept_count=false,noanswer_falseaccept=fa,noanswer_wilson95=wilson(false,len(no)),proposed_gate_pass=bool(p is not None and p>=.8 and coverage>=.8 and fa is not None and fa<=.1),stretch_observed=bool(p is not None and p>=.9),p3=sum(sum(n in r['relevant'] for n in r['top5'][:3])/3 for r in yes)/len(yes) if yes else None,p5=sum(sum(n in r['relevant'] for n in r['top5'][:5])/5 for r in yes)/len(yes) if yes else None,mrr5=sum(next((1/(i+1) for i,n in enumerate(r['top5'][:5]) if n in r['relevant']),0) for r in yes)/len(yes) if yes else None,recall5=sum(len(set(r['top5'][:5])&set(r['relevant']))/len(r['relevant']) for r in yes)/len(yes) if yes else None)

if __name__=='__main__': main()

