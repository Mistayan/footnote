"""Frozen label-free query evaluator over caller's admissible candidate20.

Usage: evaluate=create_evaluator(json_config_path); evaluate(query, candidates).
Candidates are original dictionaries {id,text,...}; this callable neither loads
judgments nor changes acquisition. Caller must apply uniform version eligibility
before and after ranking. Query/corpus-specific tuning is not performed here.
"""
from pathlib import Path
import json,time,hashlib
from tools.accuracy_iteration.ranker import ResidentRanker

def create_evaluator(config):
    if not isinstance(config,dict): config=json.loads(Path(config).read_bytes())
    rankers=[]
    for spec in config['models']:
        path=Path(spec['path'])
        if spec.get('receipt_sha256') and hashlib.sha256((path/'receipt.json').read_bytes()).hexdigest()!=spec['receipt_sha256']: raise ValueError('config model receipt hash mismatch')
        rankers.append(ResidentRanker(path,spec['cap']))
    def evaluate(query,candidates):
        if len(candidates)>20: raise ValueError('fixed candidate20 budget exceeded')
        start=time.perf_counter()
        documents=candidates
        if config.get('preprocess')=='strip_frontmatter':
            from tools.accuracy_iteration.preparation import strip_frontmatter
            documents=[d|{'text':strip_frontmatter(d['text'])} for d in candidates]
        elif config.get('preprocess') not in (None,'identity'):
            raise ValueError('unknown frozen input transform')
        results=[r.evaluate(query,documents) for r in rankers]
        if len(results)==1:
            scores=results[0]['scores']; kind='uncalibrated raw logit'
        else:
            scores={d['id']:sum(1/(61+result['ranked'].index(d['id'])) for result in results) for d in candidates}; kind='reciprocal-rank fusion, not confidence'
        ranked=sorted(scores,key=lambda n:(-scores[n],n)); threshold=config.get('threshold')
        accepted=bool(ranked) and (threshold is None or scores[ranked[0]]>=threshold)
        return dict(ranked=ranked,scores=scores,top5=ranked[:config.get('top_k',5)] if accepted else [],accepted=accepted,score_kind=kind,wall_ms=(time.perf_counter()-start)*1000,pair_tokens=[r['pair_tokens'] for r in results],variant=config['variant'])
    return evaluate
