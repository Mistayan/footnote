"""Frozen Qdrant-pool replay, not fresh-server end-to-end retrieval."""
from pathlib import Path


def build_inputs(query, language, candidates, documents):
    """Label-free ranker input; no query rewriting, pooling or document edits."""
    if len(candidates) > 20 or len(set(candidates)) != len(candidates):
        raise ValueError('unique frozen candidate20 required')
    return dict(query=query, language=language,
                documents=[documents[name] for name in candidates])


def combine_scores(original, pivot, language):
    """Predeclared .5 original + .5 pivot raw logits, never fit to labels."""
    import math
    if original.keys() != pivot.keys() or not all(math.isfinite(x) for x in [*original.values(), *pivot.values()]):
        raise ValueError('matched finite score maps required')
    if language != 'fr':
        pivot = original
    return dict(original=dict(original), pivot=dict(pivot),
                combined={n: .5 * original[n] + .5 * pivot[n] for n in original})


def order_scores(scores):
    return sorted(scores, key=lambda name: (-scores[name], name))


REPO = Path(__file__).resolve().parents[1]
SEED = REPO / 'artifacts/pivot-language/run-20261019-a1'
MODEL = REPO / 'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model'
VARIANTS = ('original', 'pivot', 'combined')


def experiment(run):
    """One finite tranche. Actual CPU ranker, frozen historical Qdrant pools."""
    import datetime
    import hashlib
    import json
    import os
    import shutil
    import subprocess
    import time
    import psutil
    from pivot_language_experiment import RESEARCH
    from retrieval_ablation import CrossEncoder
    from retrieval_budget_benchmark import eligibility, select_candidates, present
    from accuracy_stepping_stone import metrics
    from tokenizers import Tokenizer

    run = Path(run).resolve()
    if not run.is_relative_to(REPO / 'artifacts/pivot-rerank') or any(p.is_symlink() for p in (run, *run.parents)):
        raise ValueError('new owned nonsymlink artifact directory required')
    run.mkdir(parents=True, exist_ok=False)
    def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    def save(name, value):
        (run / name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    load = lambda path: json.loads(path.read_bytes())
    frozen = load(SEED / 'freeze.json')
    for name, sha in frozen['inputs'].items():
        assert digest(REPO / name) == sha, ('changed seed input',name)
    for name, sha in frozen['artifacts'].items():
        assert digest(SEED / name) == sha, ('changed seed artifact',name)
    seeds = load(SEED / 'raw-results.json')
    base = [r for r in seeds if r['variant'] == 'baseline']
    assert len(base) == 60 and len({(r['dataset'],r['id']) for r in base}) == 60
    paths = [SEED / 'freeze.json', SEED / 'raw-results.json', Path(__file__), REPO / 'tests/pivot_rerank_experiment_test.py']
    paths += [REPO / name for name in frozen['inputs']]
    for label in ('old','reused','fresh_go'):
        shutil.copytree(SEED / label, run / label)
        paths += [p for p in (SEED / label).rglob('*') if p.is_file()]
    hashes = {p.relative_to(REPO).as_posix():digest(p) for p in paths}
    (run / 'code').mkdir()
    for p in paths:
        if p.suffix == '.py': shutil.copyfile(p,run / 'code' / p.name)
    save('freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),inputs=hashes,
        mode='FROZEN ACTUAL QDRANT ORIGINAL-BRANCH POOL REPLAY; NOT FRESH SERVER E2E',
        variants=VARIANTS,combination='0.5 original raw logit + 0.5 translated raw logit; fixed a priori, no development/test selection',
        unchanged='Original dense vectors/server results/lexical acquisition/pool20/candidate order, original query gates, full original parents and citation bytes. No pool refill.',
        english='Identity; reuse actual original scores for exact equality, no duplicate inference or independent latency claim',
        translation='Existing pinned offline OPUS natural-span worker; French only; failclosed original on error',
        evaluation='All sets reused diagnostics, including now-observed Go. Incomplete implementing-agent selected labels, UNKNOWN is not wrong.',
        targets=dict(first_p1=.8,higher_p1=.9,answerable_coverage_floor=.8),
        abstention='NONE; no calibrated no-answer false-acceptance bound; cannot certify acceptance',
        stopping='60 frozen question pools x 3 score variants, at most120 actual calls; no weight/model/pool sweep',
        pools=[dict(dataset=r['dataset'],id=r['id'],pool20=r['pool20'],candidates=r['candidates'],eligibility=r['eligibility']) for r in base]))
    report = dict(mode='QDRANT FROZEN POOL REPLAY',questions=60,result_rows=0,baseline_mismatches=[],english_mismatches=[],
                  actual_calls=0,actual_pairs=0,translation_calls=0,translation_failclosed=0,summaries=[])
    rows=[]; worker=None; log=None
    started=time.perf_counter(); cpu_started=time.process_time()
    try:
        env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(RESEARCH/'hf-offline'),PYTHONIOENCODING='utf-8')
        log=(run/'translator-stderr.log').open('w',encoding='utf8')
        worker=subprocess.Popen([str(RESEARCH/'translation-env/Scripts/python.exe'),'-B',str(REPO/'tools/pivot_language_experiment.py'),'--worker'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf8',env=env,cwd=REPO)
        ready=worker.stdout.readline()
        if not ready: raise RuntimeError('existing offline translator initialization failed')
        report['translator_init']=json.loads(ready); report['translator_pid']=worker.pid
        ranker=CrossEncoder(MODEL)
        assert ranker.session.get_providers() == ['CPUExecutionProvider']
        counter=Tokenizer.from_str(ranker.tokenizer.to_str()); counter.no_padding(); counter.no_truncation()
        report['cold_validate_load_ms']=(time.perf_counter()-started)*1000
        report['first_inference_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        measured=time.perf_counter()
        data={label:({d['id']:d for d in load(run/label/'corpus.json')},load(run/label/'source-receipts.json')) for label in ('old','reused','fresh_go')}
        with (run/'raw-results.jsonl').open('w',encoding='utf8') as output:
            for seed in base:
                if time.perf_counter()-measured > 1200: raise TimeoutError('finite1200s measured bound')
                docs,sources=data[seed['dataset']]
                states=eligibility(seed['query'],docs,sources)
                assert states == seed['eligibility']
                assert select_candidates(seed['pool20'],states,True,20) == seed['candidates']
                inputs=build_inputs(seed['query'],seed['language'],seed['candidates'],docs)
                t=time.perf_counter(); c=time.process_time()
                translated=dict(pivot=inputs['query'],ok=True,fragments=[],cpu_s=0,wall_ms=0,reason='identity non-French')
                if inputs['language']=='fr':
                    worker.stdin.write(json.dumps(dict(query=inputs['query'],language='fr'),ensure_ascii=False)+'\n'); worker.stdin.flush()
                    reply=worker.stdout.readline()
                    if not reply: raise RuntimeError('translator exited during French query')
                    translated=json.loads(reply); report['translation_calls']+=1
                    report['translation_failclosed']+=int(not translated['ok'])
                translation_rpc_ms=(time.perf_counter()-t)*1000
                translations_cpu=time.process_time()-c+translated['cpu_s']
                maps={}; timings={}; cpus={}; lengths={}; limits={}
                for mode,query in [('original',inputs['query']),('pivot',translated['pivot'])]:
                    if mode=='pivot' and inputs['language']!='fr':
                        maps[mode]=maps['original']; timings[mode]=0; cpus[mode]=0; lengths[mode]=lengths['original']; limits[mode]=0
                        continue
                    lengths[mode]={d['id']:len(counter.encode(query,d['text']).ids) for d in inputs['documents']}
                    t=time.perf_counter(); c=time.process_time(); before=ranker.at_limit
                    ranked,scores=ranker.rank(query,inputs['documents'])
                    timings[mode]=(time.perf_counter()-t)*1000; cpus[mode]=time.process_time()-c
                    limits[mode]=ranker.at_limit-before; maps[mode]=scores
                    report['actual_calls']+=1; report['actual_pairs']+=len(inputs['documents'])
                old_delta=max((abs(maps['original'][n]-seed['logits'][n]) for n in seed['candidates']),default=0)
                if old_delta > 1e-5 or order_scores(maps['original'])!=seed['ranked']:
                    report['baseline_mismatches'].append(dict(id=seed['id'],max_delta=old_delta))
                variants=combine_scores(maps['original'],maps['pivot'],inputs['language'])
                if inputs['language']!='fr' and not variants['original']==variants['pivot']==variants['combined']:
                    report['english_mismatches'].append(seed['id'])
                for variant,scores in variants.items():
                    ranked=order_scores(scores); top=present(ranked,eligibility(inputs['query'],docs,sources),True)
                    evidence=[docs[n] | dict(url=sources[docs[n]['source']]['url'],source_raw_sha256=sources[docs[n]['source']]['sha256'],
                        judgment='SELECTED' if n in seed['relevant'] else 'INCOMPATIBLE' if n in seed['incompatible'] else 'UNKNOWN') for n in top]
                    row={k:seed[k] for k in ('id','query','language','split','dataset','relevant','incompatible')}
                    row.update(variant=variant,pool20=seed['pool20'],candidates=seed['candidates'],eligibility=states,
                        dense=seed['dense'],query_vector=seed['query_vector'],translation=translated,logits=scores,ranked=ranked,top5=top,evidence=evidence,
                        metrics=metrics(top,seed,seed['candidates']),baseline_logit_max_delta=old_delta,
                        component_ms=dict(original_rerank=timings['original'],pivot_rerank=timings['pivot'],translation_rpc=translation_rpc_ms),
                        component_cpu_s=dict(original_rerank=cpus['original'],pivot_rerank=cpus['pivot'],translation=translations_cpu),
                        untruncated_pair_tokens=lengths,actual_at_limit_pairs=limits)
                    rows.append(row); output.write(json.dumps(row,ensure_ascii=False)+'\n'); output.flush()
                print(seed['dataset'],seed['id'],[int(rows[-3+i]['metrics']['p1']) for i in range(3)],flush=True)
        report['measured_seconds']=time.perf_counter()-measured
        report['harness_cpu_s']=time.process_time()-cpu_started
        report['harness_end_rss_bytes']=psutil.Process().memory_info().rss
        report['result_rows']=len(rows)
        assert len(rows)==180 and not report['baseline_mismatches'] and not report['english_mismatches']
        save('raw-results.json',rows)
        report.update(summarize(rows))
        write_review(run, rows)
    except BaseException as exc:
        save('failure.json',dict(type=type(exc).__name__,message=str(exc),completed_rows=len(rows)))
        raise
    finally:
        cleanup={}
        if worker:
            if worker.stdin: worker.stdin.close()
            try: worker.wait(timeout=15)
            except subprocess.TimeoutExpired: worker.kill(); worker.wait(timeout=15)
            if worker.stdout: worker.stdout.close()
            cleanup=dict(translator_pid=worker.pid,translator_exit_code=worker.returncode,translator_exited=worker.poll() is not None)
        if log: log.close()
        report['cleanup']=cleanup
        report['inputs_unchanged']=all(digest(REPO/name)==sha for name,sha in hashes.items())
        save('report.json',report)
        save('evidence-sha256.json',{p.relative_to(run).as_posix():digest(p) for p in run.rglob('*') if p.is_file() and p.name!='evidence-sha256.json'})
    assert report['inputs_unchanged']
    return report


def summarize(rows):
    import statistics
    groups=[]
    for dataset,split in [('old','development'),('old','holdout'),('reused','development'),('reused','holdout'),('fresh_go','holdout')]:
        for variant in VARIANTS:
            for language in ('all','fr','en','en_or_mixed'):
                chosen=[r for r in rows if r['dataset']==dataset and r['split']==split and r['variant']==variant and (language=='all' or r['language']==language)]
                if not chosen: continue
                yes=[r for r in chosen if r['relevant']]; no=[r for r in chosen if not r['relevant']]
                item=dict(dataset=dataset,split=split,variant=variant,language=language,n=len(chosen),answerable=len(yes),
                    correct_top1=sum(r['metrics']['p1'] for r in yes),answerable_accepted=sum(bool(r['top5']) for r in yes),
                    answerable_rejected=sum(not r['top5'] for r in yes),noanswer=len(no),noanswer_false_accept=sum(bool(r['top5']) for r in no),
                    incompatible_top1=sum(r['metrics']['incompatible_top1'] for r in chosen),incompatible_top5=sum(r['metrics']['incompatible_top5'] for r in chosen),
                    unknown_top1=sum(bool(r['evidence']) and r['evidence'][0]['judgment']=='UNKNOWN' for r in chosen),
                    unknown_top5=sum(e['judgment']=='UNKNOWN' for r in chosen for e in r['evidence']))
                item.update({key:statistics.mean(r['metrics'][key] for r in yes) if yes else None for key in ('p1','p3','p5','mrr','recall5','candidate_recall')})
                groups.append(item)
    paired=[]
    originals={(r['dataset'],r['id']):r for r in rows if r['variant']=='original'}
    for variant in ('pivot','combined'):
        gains=[]; losses=[]
        for r in rows:
            if r['variant']!=variant or not r['relevant']: continue
            old=originals[r['dataset'],r['id']]
            change=r['metrics']['p1']-old['metrics']['p1']
            if change: (gains if change>0 else losses).append(dict(dataset=r['dataset'],id=r['id']))
        paired.append(dict(variant=variant,gains=gains,losses=losses))
    original=list(originals.values())
    compute=dict(actual_original_pairs=sum(len(r['candidates']) for r in original),
        actual_pivot_pairs=sum(len(r['candidates']) for r in original if r['language']=='fr'),
        translation_worker_cpu_s=sum(r['translation']['cpu_s'] for r in original),
        cpu_s={k:sum(r['component_cpu_s'][k] for r in original) for k in ('original_rerank','pivot_rerank','translation')},
        at_limit_pairs={k:sum(r['actual_at_limit_pairs'][k] for r in original) for k in ('original','pivot')},
        p50_ms={k:statistics.median(r['component_ms'][k] for r in original if k=='original_rerank' or r['language']=='fr') for k in ('original_rerank','pivot_rerank','translation_rpc')})
    return dict(summaries=groups,paired=paired,compute=compute)


def write_review(run, rows):
    lines=['# Frozen-pool per-query review', '', 'ALL questions are reused diagnostics. SELECTED labels are incomplete; UNKNOWN is not irrelevant. Original full parent bytes below. Pool replay, not fresh-server E2E.', '']
    for r in rows:
        lines += [f"## {r['dataset']} / {r['id']} / {r['variant']}",r['query'],
            'Language: '+r['language']+'; pivot: '+r['translation']['pivot'],
            'Selected: '+str(r['relevant'])+'; incompatible: '+str(r['incompatible']),
            'Metrics: '+str(r['metrics']),
            'Candidates (unchanged): '+str(r['candidates']),
            'Selected full rerank positions: '+str({n:r['ranked'].index(n)+1 if n in r['ranked'] else None for n in r['relevant']}),
            'Incompatible full rerank positions: '+str({n:r['ranked'].index(n)+1 if n in r['ranked'] else None for n in r['incompatible']})]
        for i,e in enumerate(r['evidence'],1):
            lines += [f"### {i}. {e['id']} — {e['judgment']} — logit {r['logits'][e['id']]}",
                f"{e['url']} | chars {e['start']}:{e['end']} | text SHA256 {e['sha256']} | raw SHA256 {e['source_raw_sha256']}",e['text'],'']
    (run/'PER-QUERY-REVIEW.md').write_text('\n'.join(lines),encoding='utf8')


def verify_run(run):
    """Read-only exact seed identity, provenance, scores, arithmetic and gates."""
    import hashlib
    import json
    from retrieval_budget_benchmark import eligibility, present
    from accuracy_stepping_stone import metrics
    run=Path(run); load=lambda p:json.loads(p.read_bytes())
    for name,sha in load(run/'evidence-sha256.json').items():
        assert hashlib.sha256((run/name).read_bytes()).hexdigest()==sha,name
    freeze=load(run/'freeze.json'); report=load(run/'report.json'); rows=load(run/'raw-results.json')
    assert freeze['utc'] <= report['first_inference_utc']
    seed={(r['dataset'],r['id']):r for r in load(SEED/'raw-results.json') if r['variant']=='baseline'}
    indexed={(r['dataset'],r['id'],r['variant']):r for r in rows}
    assert len(indexed)==len(rows)==180
    for r in rows:
        old=seed[r['dataset'],r['id']]
        for key in ('candidates','pool20','query','query_vector','dense','eligibility','relevant','incompatible'):
            assert r[key]==old[key],(r['id'],key)
        docs={d['id']:d for d in load(run/r['dataset']/'corpus.json')}
        sources=load(run/r['dataset']/'source-receipts.json')
        states=eligibility(r['query'],docs,sources)
        assert states==r['eligibility']
        assert r['ranked']==order_scores(r['logits']) and r['top5']==present(r['ranked'],states,True)
        assert r['metrics']==metrics(r['top5'],r,r['candidates'])
        maps={v:indexed[r['dataset'],r['id'],v]['logits'] for v in VARIANTS}
        assert maps==combine_scores(maps['original'],maps['pivot'],r['language'])
        for e in r['evidence']:
            d=docs[e['id']]
            for key in d: assert e[key]==d[key]
            text=(run/r['dataset']/'sources'/(d['source']+'.txt')).read_text(encoding='utf8')
            assert text[d['start']:d['end']]==e['text']
            assert hashlib.sha256(e['text'].encode()).hexdigest()==e['sha256']
            assert e['url']==sources[d['source']]['url']
    summary=summarize(rows)
    assert all(report[k]==v for k,v in summary.items())
    assert report['inputs_unchanged'] and report['cleanup']['translator_exited']
    return True


if __name__=='__main__':
    import argparse
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args()
    if args.verify: print(json.dumps(dict(verified=verify_run(args.verify))))
    elif args.run: print(json.dumps(experiment(args.run),ensure_ascii=False))
    else: parser.error('--run NEW-DIRECTORY or --verify EXISTING-DIRECTORY required')
