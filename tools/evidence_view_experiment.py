"""Finite development-only evidence view experiment. No runtime integration."""
import hashlib
import re


def aggregate(logits, mapping):
    scores={}
    for key,score in logits.items():
        parent=mapping[key]
        scores[parent]=max(scores.get(parent,float('-inf')),score)
    return sorted(scores,key=lambda p:(-scores[p],p)),scores


def measure(rows, threshold=float('-inf')):
    answerable=[r for r in rows if r['relevant']]
    noanswer=[r for r in rows if not r['relevant']]
    def accepted(r): return bool(r['ranking']) and r['scores'][r['ranking'][0]] >= threshold
    def correct(r): return bool(r['ranking']) and r['ranking'][0] in r['relevant']
    n=sum(accepted(r) for r in answerable)
    return dict(answerable=len(answerable),correct=sum(correct(r) for r in answerable),accepted_answerable=n,accepted_correct=sum(accepted(r) and correct(r) for r in answerable),rejected_answerable=len(answerable)-n,noanswer=len(noanswer),false_accepts=sum(accepted(r) for r in noanswer))

VARIANTS = ('raw', 'heading_spare', 'crop320', 'crop640', 'heading_crop', 'paragraph_max')

def build_views(query, parent, source, variant):
    if variant not in VARIANTS:
        raise ValueError('unknown frozen variant')
    start, end = parent['start'], parent['end']
    if source[start:end] != parent['text']:
        raise ValueError('parent not original source')
    def view(spans, kind):
        return dict(text='\n\n'.join(source[a:b] for a,b in spans),
                    spans=[dict(start=a,end=b) for a,b in spans], kind=kind)
    raw = view([(start,end)], 'parent')
    # Source-derived generic section markers: Markdown, RST directives/underlines,
    # AsciiDoc option definitions. Unsupported formats yield only source first line.
    lines=list(re.finditer(r'[^\n]+', source))
    headings=[]
    for i,line in enumerate(lines):
        text=line.group()
        if re.match(r'^#{1,6}\s|^\s*\.\.\s+[\w-]+::|^\S.*::$|^\d+(?:\.\d+)+\.?\s',text) or (i+1<len(lines) and re.fullmatch(r'[=~^\-]{3,}',lines[i+1].group().strip())):
            if line.start() <= start: headings.append((line.start(),line.end()))
    context = [(lines[0].start(),lines[0].end())] if lines else []
    context += headings[-2:]
    context = list(dict.fromkeys((a,b) for a,b in context if b <= start))
    # Candidate crops start/end only at paragraph/sentence or parent boundaries.
    boundaries={start,end}
    for match in re.finditer(r'\n\s*\n|(?<=[.!?])\s+', source[start:end]):
        boundaries.update((start+match.start(),start+match.end()))
    bounds=sorted(boundaries)
    terms=set(re.findall(r'\w+',query.casefold()))
    def crop(budget):
        candidates=[]
        for a in bounds[:-1]:
            ends=[b for b in bounds if a < b <= a+budget]
            if not ends: continue
            b=max(ends)
            words=set(re.findall(r'\w+',source[a:b].casefold()))
            candidates.append((len(terms & words), b-a, -a, a,b))
        if not candidates:
            # Indivisible long paragraph/sentence remains intact, never cut mid-proof.
            return [(start,end)]
        *_,a,b=max(candidates)
        return [(a,b)]
    if variant=='raw': return [raw]
    if variant=='heading_spare': return [raw | {'context_spans':[dict(start=a,end=b) for a,b in context]}]
    if variant in ('crop320','crop640'): return [view(crop(int(variant[4:])),variant)]
    if variant=='heading_crop': return [view(context+crop(640),'heading_crop')]
    spans=[]
    for match in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)',source[start:end]):
        a,b=start+match.start(),start+match.end()
        spans.append((a,b))
    return [raw]+[view([span],'paragraph') for span in spans if span!=(start,end)]


class ViewRanker:
    def __init__(self, ranker, sources, variant):
        self.ranker=ranker; self.sources=sources; self.variant=variant; self.last=None

    def rank(self, query, documents):
        import time
        inputs=[]; mapping={}; details=[]
        for parent in documents:
            source=self.sources[parent['source']]
            for i,view in enumerate(build_views(query,parent,source,self.variant)):
                if self.variant=='heading_spare':
                    # Append source text only if ALL originally visible query/body
                    # tokens survive identically. No proof or label enters this check.
                    before=self.ranker.tokenizer.encode(query,view['text'])
                    for span in view.pop('context_spans',[]):
                        proposed=view['text']+'\n\n'+source[span['start']:span['end']]
                        after=self.ranker.tokenizer.encode(query,proposed)
                        original=[(sid,off,tid) for sid,off,tid,mask in zip(before.sequence_ids,before.offsets,before.ids,before.attention_mask) if mask and sid is not None]
                        retained=[(sid,off,tid) for sid,off,tid,mask in zip(after.sequence_ids,after.offsets,after.ids,after.attention_mask) if mask and sid is not None and (sid==0 or off[1]<=len(view['text']))]
                        if original==retained:
                            view['text']=proposed;view['spans'].append(span);before=after
                key=parent['id']+'::'+str(i)
                inputs.append(dict(id=key,text=view['text']));mapping[key]=parent['id']
                details.append(dict(id=key,parent=parent['id'],source=parent['source'],**view))
        started=time.perf_counter()
        _,logits=self.ranker.rank(query,inputs)
        inference_ms=(time.perf_counter()-started)*1000
        ranking,scores=aggregate(logits,mapping)
        # Visibility is recorded AFTER scoring and never used for selection.
        for d in details:
            enc=self.ranker.tokenizer.encode(query,d['text'])
            d['logit']=logits[d['id']]
            d['query_visible']=[list(o) for sid,o,mask in zip(enc.sequence_ids,enc.offsets,enc.attention_mask) if sid==0 and mask and o[1]>o[0]]
            d['document_visible']=[list(o) for sid,o,mask in zip(enc.sequence_ids,enc.offsets,enc.attention_mask) if sid==1 and mask and o[1]>o[0]]
            d['tokens']=sum(enc.attention_mask)
            d['text_sha256']=hashlib.sha256(d['text'].encode()).hexdigest()
        self.last=dict(pairs=len(inputs),inference_ms=inference_ms,views=details)
        return ranking,scores


def run_experiment():
    import json, time, uuid, statistics
    from pathlib import Path
    from tools.acquisition_repair.identity_evaluator import IdentitySearchSession, SEED, SNAPSHOT, ROOT, f
    started=time.perf_counter()
    run=ROOT/'artifacts/acquisition-repair'/('evidence-views-'+uuid.uuid4().hex)
    freeze_path=run.with_suffix('.freeze.json')
    bound=[Path(__file__),ROOT/'tests/evidence_view_experiment_test.py',SEED/'selected-config.json',SEED/'slice96-records.json',SEED/'slice96-vectors.npy',SNAPSHOT/'development-judgments.json',SNAPSHOT/'corpus.json',SNAPSHOT/'source-receipts.json']
    bound += list((SNAPSHOT/'sources').glob('*.txt'))
    # Pin existing code/model manifests; session checks actual pinned model bytes.
    bound += [ROOT/'tools/acquisition_repair/identity_evaluator.py',ROOT/'tools/acquisition_repair/evaluator.py',ROOT/'tools/retrieval_ablation.py',ROOT/'artifacts/models/minilm/manifest.json',f.RANKER/'receipt.json']
    bound=[p for p in bound if p.exists()]
    freeze=dict(utc=f.now(),before_inference=True,variants=list(VARIANTS),hashes={str(p):f.sha(p) for p in bound},pool='same slice96/dense100/original FTS10/pool20',selection='strict top1 gain over raw with no noanswer false-accept increase; tie lower pair cost, then variant order',calibration='development only: enumerate unique top1 logits plus reject-all; maximize accepted correct subject to zero noanswer false accepts, then answerable coverage, then higher threshold',paragraph_cost='all paragraph plus parent scores, max aggregation; variable pairs disclosed, not equal-compute gain',budget_seconds=1100,fresh_acceptance=False)
    f.save(freeze_path,freeze)
    queries=f.load(SNAPSHOT/'development-judgments.json')
    assert len(queries)==21 and all(q['split']=='development' for q in queries)
    sources={p.stem:p.read_text(encoding='utf8') for p in (SNAPSHOT/'sources').glob('*.txt')}
    old={r['id']:r for r in f.load(ROOT/'artifacts/acquisition-repair/identity-callable-291d5b8e58d24f50b91a34b97a8a473c/results.json')}
    rows=[];parity=0
    with IdentitySearchSession(SEED/'selected-config.json',run) as session:
        startup=(time.perf_counter()-started)*1000
        base=session.ranker
        for variant in VARIANTS:
            proxy=ViewRanker(base,sources,variant);session.ranker=proxy
            for q in queries:
                if time.perf_counter()-started>1100:raise TimeoutError('finite experiment limit')
                r=session.search(q['query'],q['language'])
                assert r['pool']==old[q['id']]['pool'],q['id']
                if variant=='raw':
                    assert r['ranked']==old[q['id']]['ranked'] and r['scores']==old[q['id']]['scores'],q['id']
                    parity+=1
                row=dict(id=q['id'],variant=variant,relevant=q['relevant'],incompatible=q['incompatible'],expected_spans=q['expected_spans'],ranking=r['ranked'],**r,**proxy.last)
                # Exact selected proof is a post-score diagnostic, not crop input.
                for view in row['views']:
                    view['whole_expected_quote_visible']=[]
                    for expected in q['expected_spans']:
                        cursor=0;visible=False
                        for span in view['spans']:
                            if view['source']==expected['source'] and span['start']<=expected['start'] and expected['end']<=span['end']:
                                a=cursor+expected['start']-span['start'];b=cursor+expected['end']-span['start']
                                vis=view['document_visible'];visible=bool(vis) and min(x[0] for x in vis)<=a and b<=max(x[1] for x in vis)
                            cursor+=span['end']-span['start']+2
                        view['whole_expected_quote_visible'].append(visible)
                rows.append(row)
                with (run/'rows.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
                print(variant,q['id'],row['pairs'],r['ranked'][0],flush=True)
        index=session.index_info
    summary={}
    for variant in VARIANTS:
        group=[r for r in rows if r['variant']==variant]
        thresholds=sorted({r['scores'][r['ranking'][0]] for r in group})+[float('inf')]
        calibration=[(t,measure(group,t)) for t in thresholds]
        t,cal=max((x for x in calibration if x[1]['false_accepts']==0),key=lambda x:(x[1]['accepted_correct'],x[1]['accepted_answerable'],x[0]))
        baseline={r['id']:r for r in rows if r['variant']=='raw'}
        gains=[r['id'] for r in group if r['relevant'] and r['ranking'][0] in r['relevant'] and baseline[r['id']]['ranking'][0] not in r['relevant']]
        losses=[r['id'] for r in group if r['relevant'] and r['ranking'][0] not in r['relevant'] and baseline[r['id']]['ranking'][0] in r['relevant']]
        summary[variant]=dict(**measure(group),pairs=sum(r['pairs'] for r in group),gains=gains,losses=losses,e2e_ms_p50=statistics.median(r['timing_ms']['e2e'] for r in group),e2e_ms_p95=sorted(r['timing_ms']['e2e'] for r in group)[19],inference_ms_per_pair=sum(r['inference_ms'] for r in group)/sum(r['pairs'] for r in group),calibration=dict(threshold=t if t!=float('inf') else 'reject_all',**cal),at_pair_limit=sum(v['tokens']>=512 for r in group for v in r['views']),proof_visible_queries=sum(any(any(v['whole_expected_quote_visible']) for v in r['views']) for r in group if r['relevant']))
    eligible=[v for v in VARIANTS if summary[v]['correct']>summary['raw']['correct'] and summary[v]['false_accepts']<=summary['raw']['false_accepts']]
    selected=min(eligible,key=lambda v:(-summary[v]['correct'],summary[v]['pairs'],VARIANTS.index(v))) if eligible else None
    for path,h in freeze['hashes'].items():assert f.sha(Path(path))==h,path
    report=dict(run=str(run),requests=len(rows),baseline_parity=parity,summary=summary,selected=selected,export_changes=False,selection_status='development only' if selected else 'REJECT ALL VIEWS: next export unchanged',startup_ms=startup,elapsed_seconds=time.perf_counter()-started,index=index,cleanup=session.cleanup,freeze_sha256=f.sha(freeze_path),fresh_acceptance=False)
    assert report['cleanup']['server']['process_exited'] and report['cleanup']['server']['port_closed']
    f.save(run/'report.json',report)
    hashes={p.name:f.sha(p) for p in run.iterdir() if p.is_file()}
    f.save(run/'artifact-sha256.json',hashes)
    print(json.dumps(report,indent=2),flush=True)
    return report

if __name__=='__main__':run_experiment()
