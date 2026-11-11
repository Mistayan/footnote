"""Development-only acquisition repair, actual isolated Qdrant/CPU models.
Run: python -m tools.acquisition_repair.experiment
"""
import sys, json, time, uuid, math, statistics, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'tools'))
import fresh_retrieval_evaluation as f
from tools.acquisition_repair.core import source_slices, acquire
SNAPSHOT = ROOT/'artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c'
BASE = ROOT/'artifacts/acquisition-repair'


def experiment():
    import numpy as np
    import psutil
    from tokenizers import Tokenizer
    from technical_quality import ResidentEncoder, lexical_index
    from qdrant_quality import fresh_connection
    from retrieval_ablation import CrossEncoder, lexical_or
    from server_benchmark import Server, SERVER, ResourceSampler
    from tools.accuracy_iteration.pivot_control import Translator
    from pivot_language_experiment import protect
    run = BASE/('ar-'+uuid.uuid4().hex); run.mkdir(parents=True, exist_ok=False)
    f.verify_snapshot(SNAPSHOT)
    corpus=f.load(SNAPSHOT/'corpus.json'); docs={d['id']:d for d in corpus}
    sources=f.load(SNAPSHOT/'source-receipts.json')
    texts={s:(SNAPSHOT/'sources'/(s+'.txt')).read_text(encoding='utf8') for s in sources}
    dev=f.load(SNAPSHOT/'development-judgments.json')
    # This final was ALREADY exposed: never call release/authorize or claim fresh.
    diagnostic=f.load(SNAPSHOT/'test-judgments.json')
    translation_root=ROOT/'artifacts/pivot-language/pivot-20261019-a'
    pivot_feasible=(translation_root/'translation-env/Scripts/python.exe').is_file() and (translation_root/'model-receipt.json').is_file()
    paths=[Path(__file__),ROOT/'tools/acquisition_repair/core.py',ROOT/'tests/test_acquisition_repair.py',SERVER,ROOT/'requirements-hybrid.lock']
    paths += [ROOT/'tools'/n for n in ('technical_quality.py','qdrant_quality.py','retrieval_ablation.py','server_benchmark.py','fresh_retrieval_evaluation.py','pivot_language_experiment.py','accuracy_iteration/pivot_control.py')]
    paths += [ROOT/'artifacts/models/minilm'/n for n in ('model.onnx','tokenizer.json','manifest.json')]
    paths += [f.RANKER/'receipt.json']+[f.RANKER/n for n in f.load(f.RANKER/'receipt.json')['files']]
    if pivot_feasible:
        paths += [translation_root/'model-receipt.json',translation_root/'translation-env/Scripts/python.exe']
        paths += [translation_root/'model'/n for n in f.load(translation_root/'model-receipt.json')['files']]
    inputs={str(p.relative_to(ROOT)).replace('\\','/'):f.sha(p) for p in paths}
    protocol=dict(utc=f.now(),before_inference=True,snapshot_sha=f.sha(SNAPSHOT/'freeze.json'),inputs=inputs,
        status='DEVELOPMENT SELECTION ONLY; old final diagnostic; NO fresh acceptance',fresh_acceptance=False,
        slices=dict(caps=[96,112],overlap_tokens=24,source_wide=True,query_label_blind=True,mapping='all frozen original parents fully containing slice; sorted IDs; first/highest-scoring child wins parent acquisition; original evidence untouched'),
        acquisition=dict(point_limit=400,parent_limit=100,legacy_point_limit=60,legacy_parent_limit=60,budgets=[20,50,100],fts='original full-parent FTS5 lexical_or top20',fusion='equal RRF k60 on unique dense parents + lexical20; deterministic ID ties',same_point_budget_for_parent_and_children=True),
        selection='DEV acquisition only: best slice by recall then smallest budget then cap96; matched parent budget. Rerank legacy20, matched parent, matched slice, slice20, separate bilingual matched slice. Choose by dev correct@1 then MRR then smaller budget then original-query/control tie preference. No diagnostic metric participates.',
        ranker='pinned mMARCO512 CPU2/1 batch4 original query/full original parent, no abstention. Full request batching, no incremental cache scores. Jina NOT loaded.',
        oracle='NONDEPLOYABLE: legacy20 union ALL supplied relevant parents, deterministic append. Actual mMARCO rerank. Oracle ideal pool hit is an upper bound; model top1 on supplied pool is a diagnostic, not universal model ceiling.',
        pivot=dict(enabled=pivot_feasible,model='existing pinned local OPUS fr-en only; no download',paired='original query retained dense and rerank; lexical original10 + pivot10, half weight each; duplicate slots no refill',checks='existing protect span order, identifiers/version/operator exact; French negation must map to English negation or reject translation; generated text NEVER evidence; fragment semantic quality not guaranteed'),
        limits=dict(seconds=1050,translation_requests=42,queries=84,rank_requests_max=190),labels='unchanged selected positives; all others UNKNOWN; parent relevant means complete quote somewhere in parent, NOT necessarily inside acquired child; report wholequote child separately')
    f.save(run/'execution-freeze.json',protocol)
    rows=[]; rankrows=[]; report=dict(run=str(run),fresh_acceptance=False,blockers=[],counts={'development_queries':len(dev),'diagnostic_queries':len(diagnostic)},verified=False)
    server=None; db=None; translator=None; sampler=None; started=time.monotonic()
    try:
        t=time.perf_counter(); encoder=ResidentEncoder(ROOT/'artifacts/models/minilm'); ranker=CrossEncoder(f.RANKER)
        tok=Tokenizer.from_file(str(ROOT/'artifacts/models/minilm/tokenizer.json'));tok.no_truncation();tok.no_padding()
        report['model_load_ms']=(time.perf_counter()-t)*1000; report['first_inference_utc']=f.now()
        assert protocol['utc']<=report['first_inference_utc']
        records={'parent':corpus}
        for cap in (96,112):records['slice'+str(cap)]=source_slices(texts,corpus,tok,cap)
        # Exact complete-source coverage, not inferred from lengths.
        coverage=[]
        for kind,items in records.items():
            f.save(run/(kind+'-records.json'),items)
            for s,text in texts.items():
                intervals=sorted((d['start'],d['end']) for d in items if d['source']==s);end=0
                for a,b in intervals:
                    assert a<=end,(kind,s,a,end)
                    assert texts[s][a:b] == next(d['text'] for d in items if d['source']==s and d['start']==a and d['end']==b)
                    end=max(end,b)
                assert end==len(text)
                coverage.append(dict(kind=kind,source=s,chars=len(text),covered=end,complete=True))
        f.save(run/'source-coverage.json',coverage)
        visible=[]
        for q in dev+diagnostic:
            for name in q['relevant']:
                p=docs[name]; enc=encoder.tokenizer.encode(p['text']); pair=ranker.tokenizer.encode(q['query'],p['text'])
                dend=max((b for a,b in enc.offsets),default=0)
                rend=max((b for (a,b),seq in zip(pair.offsets,pair.sequence_ids) if seq==1),default=0)
                spans=[s for s in q['expected_spans'] if s['source']==p['source'] and p['start']<=s['start'] and s['end']<=p['end']]
                visible.append(dict(id=q['id'],parent_id=name,source=p['source'],start=p['start'],end=p['end'],dense_visible_end=p['start']+dend,ranker_visible_end=p['start']+rend,dense_wholequote=any(s['end']<=p['start']+dend for s in spans),ranker_wholequote=any(s['end']<=p['start']+rend for s in spans),quote_spans=spans))
        f.save(run/'proof-input-coverage.json',visible)
        report['parent_token_counts']=[encoder.token_count(d['text'],'passage') for d in corpus]
        db=lexical_index(corpus);server=Server(run);server.start();report['server']=server.request('GET','/')
        sampler=ResourceSampler(server);sampler.__enter__()
        report['collections']={}; offline=time.perf_counter()
        for kind,items in records.items():
            matrix=encoder.encode([d['text'] for d in items],'passage');np.save(run/(kind+'-vectors.npy'),matrix)
            fresh_connection(server)
            server.request('PUT','/collections/'+kind,dict(vectors=dict(size=384,distance='Cosine',on_disk=False),shard_number=1,hnsw_config=dict(m=16,ef_construct=100,full_scan_threshold=10),optimizers_config=dict(indexing_threshold=1,default_segment_number=1)))
            for offset in range(0,len(items),128):
                server.request('PUT','/collections/'+kind+'/points?wait=true',dict(points=[dict(id=i+1,vector=matrix[i].tolist(),payload={'record_id':items[i]['id']}) for i in range(offset,min(offset+128,len(items)))]))
            deadline=time.monotonic()+90
            while True:
                info=server.request('GET','/collections/'+kind)['result']
                if info['status']=='green' and info['indexed_vectors_count']==len(items):break
                if time.monotonic()>deadline:raise TimeoutError('HNSW '+kind)
                time.sleep(.2)
            # Read back exact persisted points, offsets bound through record ID.
            back=[]
            for offset in range(0,len(items),128):
                back += server.request('POST','/collections/'+kind+'/points',dict(ids=list(range(offset+1,min(offset+128,len(items))+1)),with_vector=True,with_payload=True))['result']
            back.sort(key=lambda p:p['id']); assert len(back)==len(items)
            assert all(p['payload']['record_id']==items[i]['id'] for i,p in enumerate(back))
            err=float(np.max(np.abs(matrix-np.array([p['vector'] for p in back]))));assert err<1e-6
            f.save(run/(kind+'-readback.json'),back);report['collections'][kind]=dict(points=len(items),indexed=info['indexed_vectors_count'],max_abs_error=err)
        report['offline_encoding_indexing_ms']=(time.perf_counter()-offline)*1000
        if pivot_feasible:
            translator=Translator(run/'translation-stderr.log');report['translator_ready']=translator.ready
        measured=time.monotonic();translations={}
        with (run/'acquisition.jsonl').open('w',encoding='utf8') as stream:
            for split,queries in [('development',dev),('diagnostic',diagnostic)]:
                for q in queries:
                    if time.monotonic()-started>1050:raise TimeoutError('1050s workload bound')
                    begin=time.perf_counter();vector=encoder.encode([q['query']],'query')[0];encoded=time.perf_counter()
                    lexical=lexical_or(db,q['query']);lexed=time.perf_counter()
                    for kind,items in records.items():
                        fresh_connection(server)
                        t=time.perf_counter(); response=server.request('POST','/collections/'+kind+'/points/query',dict(query=vector.tolist(),limit=400,with_payload=True,with_vector=False,params=dict(exact=False,hnsw_ef=512)));searched=time.perf_counter()
                        points=response['result']['points']
                        for budget in (20,50,100):
                            acq=acquire(points,items,lexical,budget)
                            row=dict(q,split=split,variant=kind+'_'+str(budget),kind=kind,budget=budget,**acq)
                            row['parent_pool_hit']=bool(set(q['relevant'])&set(acq['pool']))
                            child_points=[items[p['id']-1] for p in points] if kind!='parent' else []
                            row['wholequote_child_hit']=any(c['source']==s['source'] and c['start']<=s['start'] and s['end']<=c['end'] and set(c['parent_ids'])&set(acq['pool']) for c in child_points for s in q['expected_spans']) if child_points else None
                            row['timing_ms']=dict(encode=(encoded-begin)*1000,lexical=(lexed-encoded)*1000,backend=(searched-t)*1000,fusion=(time.perf_counter()-searched)*1000)
                            row['response_key']=q['id']+'-'+kind
                            rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                        f.save(run/(q['id']+'-'+kind+'-response.json'),response)
                        if kind=='parent':
                            acq=acquire(points[:60],items,lexical,20,60)
                            row=dict(q,split=split,variant='legacy20',kind=kind,budget=20,**acq,parent_pool_hit=bool(set(q['relevant'])&set(acq['pool'])),wholequote_child_hit=None,timing_ms=dict(encode=(encoded-begin)*1000,lexical=(lexed-encoded)*1000,backend=(searched-t)*1000),response_key=q['id']+'-'+kind)
                            rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n')
                    # Paired pivot on development ONLY; no diagnostic-driven selection.
                    if split=='development' and translator:
                        tr=translator.translate(q['query']) if q['language']=='fr' else dict(pivot=q['query'],ok=True,reason='identity English',wall_ms=0)
                        original_spans=protect(q['query'])[1]
                        ok=tr['ok']; pos=0
                        for _,span in original_spans:
                            p=tr['pivot'].find(span,pos);ok=ok and p>=0;pos=max(pos,p+len(span))
                        neg=bool(re.search(r'\b(ne|pas|jamais|sans|aucun|non)\b',q['query'],re.I))
                        if neg and not re.search(r'\b(not|no|never|without|none|non)\b|n.t\b',tr['pivot'],re.I):ok=False
                        tr['preservation_checks_pass']=ok
                        if not ok:tr['pivot']=q['query'];tr['fallback']='failed preservation/negation; original retained'
                        translations[q['id']]=tr
                        pl=lexical_or(db,tr['pivot'])
                        # Matched slots and mass: no extra candidate allowance.
                        for kind in ('slice96','slice112'):
                            source_row=next(r for r in rows if r['id']==q['id'] and r['variant']==kind+'_100')
                            contribution={}
                            for branch,names,weight in [('dense',source_row['dense'],1),('original',lexical[:10],.5),('pivot',pl[:10],.5)]:
                                for rank,n in enumerate(names,1):contribution.setdefault(n,{})[branch]=dict(rank=rank,contribution=weight/(60+rank))
                            union=sorted(contribution,key=lambda n:(-sum(x['contribution'] for x in contribution[n].values()),n))
                            for budget in (20,50,100):
                                row=dict(q,split=split,variant=kind+'_pivot_'+str(budget),kind=kind,budget=budget,pool=union[:budget],union=union,dense=source_row['dense'],lexical_original=lexical[:10],lexical_pivot=pl[:10],contributions=contribution,parent_pool_hit=bool(set(q['relevant'])&set(union[:budget])),wholequote_child_hit=None,translation=tr,timing_ms=source_row['timing_ms']|dict(translation=tr.get('wall_ms',0)))
                                rows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n')
                    print(split,q['id'],'acquired',flush=True)
        f.save(run/'translations.json',translations)
        # Frozen rule: select slices by development acquisition only, matched parent budget.
        choices=[]
        for kind in ('slice96','slice112'):
            for b in (20,50,100):
                g=[r for r in rows if r['split']=='development' and r['variant']==kind+'_'+str(b) and r['relevant']]
                choices.append((sum(r['parent_pool_hit'] for r in g),-b,kind=='slice96',kind,b))
        _,_,_,chosen_kind,budget=max(choices)
        configs=list(dict.fromkeys(['legacy20','parent_'+str(budget),chosen_kind+'_'+str(budget),chosen_kind+'_20']+([chosen_kind+'_pivot_'+str(budget)] if translator else [])))
        f.save(run/'rerank-selection-freeze.json',dict(utc=f.now(),selection_split='development',choices=choices,configs=configs,diagnostic_reranking='NONE except supplied-label oracle diagnostic; no final candidate selection'))
        with (run/'rerank.jsonl').open('w',encoding='utf8') as stream:
            for split,queries in [('development',dev),('diagnostic',diagnostic)]:
                for q in queries:
                    legacy=next(r for r in rows if r['id']==q['id'] and r['variant']=='legacy20')
                    variants=configs if split=='development' else []
                    if q['relevant']:variants=variants+['oracle_supplied']
                    for variant in variants:
                        if time.monotonic()-started>1050:raise TimeoutError('1050s workload bound')
                        base=legacy if variant=='oracle_supplied' else next(r for r in rows if r['id']==q['id'] and r['variant']==variant)
                        pool=list(dict.fromkeys(base['pool']+(sorted(q['relevant']) if variant=='oracle_supplied' else [])))
                        t=time.perf_counter(); ranking,scores=ranker.rank(q['query'],[docs[n] for n in pool]);elapsed=(time.perf_counter()-t)*1000
                        row=dict(q,split=split,variant=variant,pool20=pool,pool=pool,top5=ranking[:5],ranking=ranking,logits=scores,accepted=bool(ranking),parent_pool_hit=bool(set(pool)&set(q['relevant'])),timing_ms=dict(rerank=elapsed,acquisition=sum(v for k,v in base['timing_ms'].items() if k!='translation'),translation=base['timing_ms'].get('translation',0)))
                        f.decorate_rows([row],docs,sources)
                        row['candidate_evidence']=[docs[n]|dict(url=sources[docs[n]['source']]['url'],raw_sha256=sources[docs[n]['source']]['sha256'],judgment='EXPECTED_QUOTE_HIT' if n in q['relevant'] else 'UNKNOWN') for n in pool]
                        rankrows.append(row);stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                    print(split,q['id'],'reranked',flush=True)
        groups=[]
        for split in ('development','diagnostic'):
            for variant in sorted({r['variant'] for r in rows if r['split']==split}):
                for lang,evidence in [('all','all'),('en','en'),('fr','en'),('en','fr'),('fr','fr')]:
                    g=[r for r in rows if r['split']==split and r['variant']==variant and r['relevant'] and (lang=='all' or r['language']==lang and r['evidence_language']==evidence)]
                    if g:groups.append(dict(split=split,variant=variant,language=lang,evidence_language=evidence,answerable=len(g),pool_hits=sum(r['parent_pool_hit'] for r in g),wholequote_child_hits=sum(bool(r['wholequote_child_hit']) for r in g),rrf_top1=sum(bool(r['pool']) and r['pool'][0] in r['relevant'] for r in g)))
        report['acquisition_summaries']=groups
        report['rerank_summaries']=[dict(split=split,**s) for split in ('development','diagnostic') for s in f.summaries([r for r in rankrows if r['split']==split])]
        candidates=[s for s in report['rerank_summaries'] if s['split']=='development' and s['language']=='all' and s['variant']!='oracle_supplied']
        selected=max(candidates,key=lambda s:(s['correct_top1'],s['mrr5'],-next(r['budget'] for r in rows if r['variant']==s['variant']),'pivot' not in s['variant'],s['variant']=='legacy20',s['variant']))
        config=dict(name=selected['variant'],run=str(run),status='DEVELOPMENT SELECTED EXPERIMENTAL; NOT ACCEPTED',fresh_acceptance=False,callable='tools.acquisition_repair.core.acquire(points, records, lexical, budget, dense_limit=100); original pinned CrossEncoder.rank(original_query, original_parent_candidates)',kind=next(r['kind'] for r in rows if r['variant']==selected['variant']),budget=next(r['budget'] for r in rows if r['variant']==selected['variant']),point_limit=60 if selected['variant']=='legacy20' else 400,dense_limit=60 if selected['variant']=='legacy20' else 100,code_inputs=inputs,development_summary=selected,abstention='NONE; all no-answer requests falsely accepted; not activation-ready')
        f.save(run/'selected-config.json',config)
        report['selected_config']=config;report['counts'].update(acquisition_rows=len(rows),rerank_rows=len(rankrows),rank_requests=len(rankrows),translation_requests=sum(q['language']=='fr' for q in dev) if translator else 0)
        report['measurement_seconds']=time.monotonic()-measured
        for n,h in inputs.items():assert f.sha(ROOT/n)==h,n
        f.verify_snapshot(SNAPSHOT);report['frozen_inputs_unchanged']=True
        # Exact baseline parity against historical dev. Full request grouping unchanged.
        historical=f.load(ROOT/'artifacts/fresh-challenger-bridge/fcb-20261020-acceptance-01-development/raw-results.json')
        parity=[]
        for row in [r for r in rankrows if r['variant']=='legacy20']:
            old=next(r for r in historical if r['id']==row['id'] and r['variant']=='mmarco_or_pool20')
            assert old['pool20']==row['pool']
            assert old['ranking']==row['ranking'] and old['logits']==row['logits']
            parity.append(row['id'])
        report['baseline_exact_parity_queries']=len(parity)
        f.save(run/'acquisition.json',rows);f.save(run/'rerank.json',rankrows)
        review=['# Acquisition repair per-query review','All nonpositive evidence UNKNOWN. Old final DIAGNOSTIC ONLY. Oracle uses supplied labels and is not deployable.']
        for q in dev+diagnostic:
            review += ['## '+q['id'],q['query'],'Language '+q['language']+' -> '+q['evidence_language'],'Expected '+json.dumps(q['relevant'])]
            review += [json.dumps(dict(variant=r['variant'],pool_hit=r['parent_pool_hit'],pool=r['pool'],wholequote_child=r['wholequote_child_hit']),ensure_ascii=False) for r in rows if r['id']==q['id']]
            for r in [x for x in rankrows if x['id']==q['id']]:
                review += ['### '+r['variant'],json.dumps(dict(top5=r['top5'],relevant=q['relevant'],timing=r['timing_ms']))]
                for e in r['evidence']:review += [e['id']+' '+e['judgment']+' '+e['url']+f" chars[{e['start']},{e['end']}) SHA {e['sha256']}",e['text']]
        (run/'PER-QUERY-REVIEW.md').write_text('\n\n'.join(review),encoding='utf8')
    except Exception as exc:
        report['blockers'].append(repr(exc));raise
    finally:
        if translator:report['translation_cleanup']=translator.close()
        if sampler:
            sampler.__exit__(None,None,None);report['resources']=sampler.report
        if server:report['cleanup']=server.close()
        if db:db.close()
        report['total_seconds']=time.monotonic()-started
        f.save(run/'report.json',report)
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    # Re-read exact saved outputs independently for count, identity, labels and evidence.
    saved=f.load(run/'rerank.json');assert len(saved)==report['counts']['rerank_rows']
    assert len({(r['id'],r['variant']) for r in saved})==len(saved)
    for r in saved:
        assert r['ranking']==sorted(r['logits'],key=lambda n:(-r['logits'][n],n))
        assert set(r['pool'])==set(r['logits'])
        assert all(docs[e['id']]['text']==e['text'] and texts[e['source']][e['start']:e['end']]==e['text'] for e in r['candidate_evidence'])
        q=next(q for q in dev+diagnostic if q['id']==r['id']);assert r['relevant']==q['relevant']
    report['verified']=True; f.save(run/'report.json',report)
    f.save(run/'artifact-sha256.json',{str(p.relative_to(run)).replace('\\','/'):f.sha(p) for p in run.iterdir() if p.is_file() and p.name!='artifact-sha256.json'})
    print(json.dumps(dict(run=str(run),selected=report['selected_config']['name'],verified=True,summaries=[s for s in report['rerank_summaries'] if s['language']=='all']),indent=2),flush=True)
    return report

if __name__=='__main__':experiment()
