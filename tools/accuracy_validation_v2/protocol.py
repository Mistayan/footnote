"""Exact-positive, UNKNOWN-preserving evaluation contracts."""

def seal(root,names):
    from tools.acquisition_repair.evaluator import f
    if (root/'freeze.json').exists():raise ValueError('never reseal exposed inputs')
    f.save(root/'freeze.json',dict(utc=f.now(),before_any_new_corpus_inference=True,files={n:f.sha(root/n) for n in names}))
    return verify_seal(root)


def verify_seal(root):
    from tools.acquisition_repair.evaluator import f,ROOT
    freeze=f.load(root/'freeze.json')
    for n,h in freeze['files'].items():
        if f.sha(root/n)!=h:raise ValueError('frozen input changed '+n)
    declaration=root/'candidate.json'
    if declaration.exists():
        for n,h in f.load(declaration)['files'].items():
            if f.sha(ROOT/n)!=h:raise ValueError('frozen method changed '+n)
    return True


def expected_windows(documents,source,quote):
    if not quote:raise ValueError('nonempty quote required')
    labels=sorted(d['id'] for d in documents if d['source']==source and quote in d['text'])
    if not labels:raise ValueError('no original window contains complete proof')
    return labels


def summarize(rows,cutoff):
    import math
    from tools.acquisition_repair.evaluator import f
    answerable=[r for r in rows if r['relevant']]; noanswer=[r for r in rows if not r['relevant']]
    def accepted(r):return bool(r['ranked']) and max(r['scores'].values(),default=-math.inf)>=cutoff
    def hit(r):return bool(r['ranked']) and r['ranked'][0] in r['relevant']
    raw=sum(hit(r) for r in answerable);correct=sum(accepted(r) and hit(r) for r in answerable)
    ac=sum(accepted(r) for r in answerable);na=sum(accepted(r) for r in noanswer); total=ac+na
    return dict(answerable=len(answerable),noanswer=len(noanswer),raw_correct=raw,raw_p1=raw/len(answerable) if answerable else None,raw_wilson95=f.wilson(raw,len(answerable)),accepted_correct=correct,p1_all_answerable=correct/len(answerable) if answerable else None,p1_wilson95=f.wilson(correct,len(answerable)),accepted_total=total,accepted_precision=correct/total if total else None,accepted_precision_wilson95=f.wilson(correct,total),answerable_accepted=ac,answerable_coverage=ac/len(answerable) if answerable else None,coverage_wilson95=f.wilson(ac,len(answerable)),answerable_rejected=len(answerable)-ac,noanswer_falseaccepts=na,noanswer_falseaccept_rate=na/len(noanswer) if noanswer else None,noanswer_falseaccept_wilson95=f.wilson(na,len(noanswer)))


def fit_refusal(rows,cutoffs):
    trials=[]
    for cutoff in cutoffs:
        score=summarize(rows,cutoff)
        balanced=(score['p1_all_answerable']+1-score['noanswer_falseaccept_rate'])/2
        trials.append(dict(cutoff=cutoff,balanced=balanced,**score))
    winner=max(trials,key=lambda r:(r['balanced'],r['answerable_coverage'],-r['cutoff']))
    return dict(cutoff=winner['cutoff'],selection='max balanced(accepted-correct/ALL answerable, noanswer rejection); ties coverage then lower cutoff; development ONLY',trials=trials)
