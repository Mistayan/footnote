"""Sealed fresh public validation: no test-driven method selection or relabeling."""
import json,time,math,statistics,uuid,shutil
from pathlib import Path
from collections import Counter
from tools.acquisition_repair.evaluator import ROOT,f
from tools.accuracy_validation_v2.protocol import expected_windows,seal,verify_seal,summarize
from tools.accuracy_validation_v2.session import CorpusIdentitySession
SNAPSHOT=ROOT/'artifacts/accuracy-validation-v2/validation-45b7cf7377844257ab27dc02c46662fb'
REFUSAL=ROOT/'artifacts/accuracy-validation-v2/replay-9afbb1909b3d4677abe8899b859b8a6d/refusal-frozen.json'

def prepare():
    from server_benchmark import SERVER
    if (SNAPSHOT/'freeze.json').exists():raise ValueError('already sealed')
    sources=f.load(SNAPSHOT/'source-receipts.json');texts={s:(SNAPSHOT/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources}
    corpus=[]
    for source,text in sorted(texts.items()):
        assert text and f.sha(SNAPSHOT/'sources'/(source+'.raw'))==sources[source]['sha256']
        corpus+=f.windows(source,text,1800,900)
    f.save(SNAPSHOT/'corpus.json',corpus)
    gold=f.load(ROOT/'tools/accuracy_validation_v2/gold-spec.json');questions=[]
    for i,fact in enumerate(gold['facts'],1):
        source=fact['source'];quote=fact['quote'];start=texts[source].index(quote)
        for language in ('en','fr'):
            questions.append(dict(id=f'v2-{i:03d}-{language}',query=fact[language],language=language,evidence_language=sources[source]['language'],tags=fact['tags'],relevant=expected_windows(corpus,source,quote),expected_spans=[dict(source=source,start=start,end=start+len(quote),quote=quote)],judgment=gold['annotation'],incompatible=[]))
    for i,q in enumerate(gold['noanswer'],1):questions.append(dict(id=f'v2-no-{i:03d}',**q,evidence_language='none',tags=['noanswer'],relevant=[],expected_spans=[],incompatible=[],judgment='author-made corpus-wide no-answer; not independently human judged'))
    directions=Counter(q['language']+'_'+q['evidence_language'] for q in questions if q['relevant'])
    assert len(questions)==52 and all(directions[k]==10 for k in ['en_en','fr_en','en_fr','fr_fr'])
    f.save(SNAPSHOT/'test-judgments.json',questions)
    refusal=f.load(REFUSAL);assert refusal['cutoff']==2.5
    paths=list((ROOT/'tools/accuracy_validation_v2').glob('*.py'))+list((ROOT/'tests').glob('test_accuracy_validation_v2*.py'))
    paths += [ROOT/'tools'/p for p in ['acquisition_repair/identity_evaluator.py','acquisition_repair/evaluator.py','acquisition_repair/core.py','technical_quality.py','retrieval_ablation.py','qdrant_quality.py','server_benchmark.py','fresh_retrieval_evaluation.py','hybrid_dataset.py']]
    paths += [ROOT/'artifacts/models/minilm'/n for n in ['manifest.json','model.onnx','tokenizer.json']]+[f.RANKER/'receipt.json']+[f.RANKER/n for n in f.load(f.RANKER/'receipt.json')['files']]
    paths += [SERVER,ROOT/'requirements-hybrid.lock',REFUSAL,ROOT/'tools/accuracy_validation_v2/gold-spec.json',ROOT/'artifacts/acquisition-repair/identity-callable-291d5b8e58d24f50b91a34b97a8a473c/selected-config.json']
    files={p.relative_to(ROOT).as_posix():f.sha(p) for p in paths}
    config=dict(method='CorpusIdentitySession inherits EXACT IdentitySearchSession.search; constructor-only new label-free corpus binding; verified old-dev21 exact pool/logit/rank parity',slice_cap=96,overlap=24,parent_windows=dict(width=1800,stride=900,unicode_codepoints=True),dense=dict(model='original pretrained pinned multilingual MiniLM128',point_limit=400,parent_limit=100,ef=512),lexical='original full-parent FTS5 BM25 OR top10; original+identity .5+.5 mass; no translation',rrf_k=60,pool=20,ranker='original pinned mMARCO512 longest-first CPU2/1 batch4',refusal=dict(rule='accept iff nonempty ranking and max raw ranker logit >= cutoff',cutoff=refusal['cutoff'],fit_file=str(REFUSAL),fit_sha256=f.sha(REFUSAL),selection='dev only predeclared finite cutoffs; balanced accepted-correct/ALL answerable and noanswer rejection'),baseline='original full-parent MiniLM128 top60 ef128 + FTS5 BM25 OR20 + RRF60 + mMARCO pool20; NONE refusal; same model/source/evidence bytes; actual independent E2E requests',metric='exact selected-quote P@1 over ALL40 answerable; abstentions miss; UNKNOWN is not false; raw and accepted precision separate',acceptance=dict(point_estimate=.8,stretch=.9,coverage_minimum=.8,noanswer_falseaccept_max=.1,gate_status='coverage/noanswer are experimental assistant-proposed limits, not user industrial approval'),labels=gold['annotation'],independence='6 official public snapshots, 3 topics not in old dev/diagnostic. 20 fact families, 40 bilingual query paraphrases; multilingual source translations correlated. Not personal-vault certification or independently human judged.',resource_bound_seconds=2100)
    f.save(SNAPSHOT/'candidate.json',dict(name='identity96_original10_pool20_dev-maxlogit2.5',selection_used_development_only=True,config=config,files=files))
    f.save(SNAPSHOT/'counts.json',dict(sources=len(sources),parents=len(corpus),questions=len(questions),answerable=40,noanswer=12,directions=dict(directions)))
    for p in paths:
        if p.suffix=='.py':
            target=SNAPSHOT/'code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    names=[p.relative_to(SNAPSHOT).as_posix() for p in SNAPSHOT.rglob('*') if p.is_file()]
    seal(SNAPSHOT,names)
    print('FROZEN',SNAPSHOT,json.dumps(f.load(SNAPSHOT/'counts.json')),f.sha(SNAPSHOT/'freeze.json'),flush=True)
    return True


def baseline(session,query):
    from qdrant_quality import fresh_connection,rank_parents
    from retrieval_ablation import lexical_or
    from technical_quality import fuse
    start=time.perf_counter();vector=session.encoder.encode([query],'query')[0];fresh_connection(session.server)
    response=session.server.request('POST','/collections/baseline/points/query',dict(query=vector.tolist(),limit=60,with_payload=True,with_vector=False,params=dict(exact=False,hnsw_ef=128)))
    dense=rank_parents(response['result']['points'],list(session.docs.values()));lexical=lexical_or(session.db,query);pool=fuse(dense,lexical)[:20]
    acquired=time.perf_counter();ranking,scores=session.ranker.rank(query,[session.docs[n] for n in pool]);ranked=time.perf_counter()
    evidence=[session.docs[n]|dict(url=session.sources[session.docs[n]['source']]['url'],raw_sha256=session.sources[session.docs[n]['source']]['sha256']) for n in ranking[:5]]
    json.dumps(evidence,ensure_ascii=False).encode('utf8');end=time.perf_counter()
    return dict(query=query,pool=pool,ranked=ranking,scores=scores,top5=ranking[:5],evidence=evidence,dense=dense,lexical=lexical,server_response=response,query_vector=vector.tolist(),timing_ms=dict(acquisition=(acquired-start)*1000,rerank=(ranked-acquired)*1000,evidence_serialization=(end-ranked)*1000,e2e=(end-start)*1000))


def run():
    import numpy as np
    verify_seal(SNAPSHOT)
    if (SNAPSHOT/'release-test.json').exists():raise ValueError('fresh test already exposed; no rerun/reselection as fresh')
    candidate=f.load(SNAPSHOT/'candidate.json');cutoff=candidate['config']['refusal']['cutoff']
    release=dict(utc=f.now(),authority='parent delegated conditional authorization: release only after complete frozen config',snapshot_freeze_sha256=f.sha(SNAPSHOT/'freeze.json'),candidate_sha256=f.sha(SNAPSHOT/'candidate.json'),status='EXPOSED now; any later selection diagnostic')
    f.save(SNAPSHOT/'release-test.json',release)
    questions=f.load(SNAPSHOT/'test-judgments.json');run=SNAPSHOT/'runs'/uuid.uuid4().hex
    f.save(SNAPSHOT/'first-inference.json',dict(utc=f.now(),run=str(run),release_sha256=f.sha(SNAPSHOT/'release-test.json')))
    assert f.load(SNAPSHOT/'freeze.json')['utc']<=release['utc']<=f.load(SNAPSHOT/'first-inference.json')['utc']
    rows=[];started=time.perf_counter();report=dict(snapshot=str(SNAPSHOT),run=str(run),verified=False)
    with CorpusIdentitySession(SNAPSHOT,run) as session:
        report['startup_encode_index_ms']=(time.perf_counter()-started)*1000
        report['server_identity']=session.server.request('GET','/');assert report['server_identity']['version']=='1.19.2'
        parents=list(session.docs.values());matrix=session.encoder.encode([d['text'] for d in parents],'passage');np.save(run/'baseline-vectors.npy',matrix)
        report['baseline_index']=session.index('baseline',parents,matrix);report['selected_index']=session.index_info
        # Verify uniform source coverage and all child->parent mappings without labels.
        texts={s:(SNAPSHOT/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in session.sources};coverage=[]
        for source,text in texts.items():
            end=0
            for child in [r for r in session.records if r['source']==source]:
                assert child['start']<=end and child['text']==text[child['start']:child['end']]
                expected=sorted(p['id'] for p in parents if p['source']==source and p['start']<=child['start'] and child['end']<=p['end'])
                assert child['parent_ids']==expected and expected and child['token_count']<=96;end=max(end,child['end'])
            assert end==len(text);coverage.append(dict(source=source,chars=len(text),covered=end))
        f.save(run/'source-coverage-and-mapping.json',coverage)
        with (run/'results.jsonl').open('w',encoding='utf8') as stream:
            for q in questions:
                if time.perf_counter()-started>2100:raise TimeoutError('35min bound')
                for variant in ['selected','baseline']:
                    r=session.search(q['query'],q['language']) if variant=='selected' else baseline(session,q['query'])
                    row=dict(q,variant=variant,**{k:v for k,v in r.items() if k not in q})
                    row['accepted']=bool(r['ranked']) and (variant=='baseline' or max(r['scores'].values())>=cutoff)
                    row['raw_hit1']=bool(r['ranked']) and r['ranked'][0] in q['relevant'];row['accepted_hit1']=row['accepted'] and row['raw_hit1']
                    row['p_at_3']=sum(n in q['relevant'] for n in r['top5'][:3])/3;row['p_at_5']=sum(n in q['relevant'] for n in r['top5'])/5
                    row['recall5']=len(set(r['top5'])&set(q['relevant']))/len(q['relevant']) if q['relevant'] else None
                    row['reciprocal_rank']=next((1/(i+1) for i,n in enumerate(r['ranked']) if n in q['relevant']),0)
                    row['expected_pool_hit']=bool(set(q['relevant'])&set(r['pool']))
                    row['returned_child_wholequote']=None if variant=='baseline' or not q['relevant'] else any(c['source']==s['source'] and c['start']<=s['start'] and s['end']<=c['end'] and set(c['parent_ids'])&set(r['pool']) for pt in r['server_response']['result']['points'] for c in [session.records[pt['id']-1]] for s in q['expected_spans'])
                    for e in row['evidence']:e['judgment']='EXPECTED_QUOTE_HIT' if e['id'] in q['relevant'] else 'UNKNOWN; not a negative'
                    rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                print(q['id'],'paired completed',flush=True)
        report['reranker_pairs_at_limit']=session.ranker.at_limit
    report['cleanup']=session.cleanup;verify_seal(SNAPSHOT)
    selected=[r for r in rows if r['variant']=='selected'];base=[r for r in rows if r['variant']=='baseline']
    report.update(selected=summarize(selected,cutoff),selected_without_refusal=summarize(selected,-100),baseline=summarize(base,-100),refusal_cutoff=cutoff,rows=len(rows),wall_seconds=time.perf_counter()-started)
    report['directions']={a+b:dict(selected=summarize([r for r in selected if r['language']==a and r['evidence_language']==b],cutoff),raw=summarize([r for r in selected if r['language']==a and r['evidence_language']==b],-100),baseline=summarize([r for r in base if r['language']==a and r['evidence_language']==b],-100)) for a,b in [('en','en'),('fr','en'),('en','fr'),('fr','fr')]}
    report['latency_ms']={v:{k:dict(p50=statistics.median(r['timing_ms'][k] for r in group),p95=sorted(r['timing_ms'][k] for r in group)[math.ceil(.95*len(group))-1]) for k in group[0]['timing_ms']} for v,group in [('selected',selected),('baseline',base)]}
    report['paired']=dict(raw_gains=[r['id'] for r,b in zip(selected,base) if r['relevant'] and r['raw_hit1'] and not b['raw_hit1']],raw_losses=[r['id'] for r,b in zip(selected,base) if r['relevant'] and not r['raw_hit1'] and b['raw_hit1']])
    report['failure_categories']=dict(acquisition_missing=sum(bool(r['relevant']) and not r['expected_pool_hit'] for r in selected),pool_present_top1_UNKNOWN=sum(bool(r['relevant']) and r['expected_pool_hit'] and not r['raw_hit1'] for r in selected),refusal_lost_correct=sum(r['raw_hit1'] and not r['accepted'] for r in selected))
    report['objective80_pointestimate_met']=report['selected']['p1_all_answerable']>=.8
    report['stretch90_pointestimate_met']=report['selected']['p1_all_answerable']>=.9
    report['experimental_coverage_noanswer_gates_met']=report['selected']['answerable_coverage']>=.8 and report['selected']['noanswer_falseaccept_rate']<=.1
    f.save(run/'results.json',rows)
    lines=['# Per-query frozen evidence review','Author-made exact selected quote labels; UNKNOWN is not negative. No posthoc changes. Full normalized originals and pinned raw bytes in ../../sources.']
    for r in rows:
        lines += [f"## {r['id']} — {r['variant']}",r['query'],f"Direction {r['language']}→{r['evidence_language']}; expected {r['relevant']}; accepted={r['accepted']}; raw hit1={r['raw_hit1']}; accepted hit1={r['accepted_hit1']}",f"P3={r['p_at_3']}; P5={r['p_at_5']}; recall5={r['recall5']}; RR={r['reciprocal_rank']}",json.dumps(r['expected_spans'],ensure_ascii=False)]
        for i,e in enumerate(r['evidence'],1):lines += [f"### {i}. {e['id']} — {e['judgment']}",f"{e['url']} raw SHA256 {e['raw_sha256']}; normalized Unicode chars [{e['start']},{e['end']}); excerpt SHA256 {e['sha256']}",'> '+e['text'].replace('\n','\n> ')]
    (run/'PER-QUERY-REVIEW.md').write_text('\n\n'.join(lines),encoding='utf8')
    assert len(rows)==104 and report['cleanup']['server']['process_exited'] and report['cleanup']['server']['port_closed']
    report['verified']=True;f.save(run/'report.json',report)
    f.save(run/'artifact-sha256.json',{p.relative_to(run).as_posix():f.sha(p) for p in run.rglob('*') if p.is_file() and not any(k in p.parts for k in ['storage','snapshots','temp']) and p.name!='artifact-sha256.json'})
    print(json.dumps(report,indent=2),flush=True);return report

if __name__=='__main__':
    import sys
    prepare() if '--prepare' in sys.argv else run()
