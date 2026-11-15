"""Analyse saved memory-recall results; fit on dev only, assess on held-out.

Input JSON rows have question_id, split (dev/heldout), label (positive/negative),
keyword_hit (bool for positives), and hybrid (ordered [{score, relevant}]).
Negative rows may include an empty hybrid list. All scores must be finite.
"""
import argparse
import json
import math
import random
from pathlib import Path


def analyse(rows, seed=20261115, samples=10000):
    if samples < 2:
        raise ValueError('at least two bootstrap samples required')
    question_splits = {}
    for row in rows:
        if row['split'] not in ('dev', 'heldout') or row['label'] not in ('positive', 'negative'):
            raise ValueError('invalid split or label')
        for hit in row['hybrid']:
            if not isinstance(hit['score'], (int, float)) or not math.isfinite(hit['score']):
                raise ValueError('missing or non-finite score')
        if row['label'] == 'positive' and not isinstance(row['keyword_hit'], bool):
            raise ValueError('positive requires keyword_hit')
        qid = row.get('question_id')
        if qid:
            if qid in question_splits and question_splits[qid] != row['split']:
                raise ValueError('question appears in both splits')
            question_splits[qid] = row['split']
    dev = [r for r in rows if r['split'] == 'dev' and r['label'] == 'negative']
    pos = [r for r in rows if r['split'] == 'heldout' and r['label'] == 'positive']
    neg = [r for r in rows if r['split'] == 'heldout' and r['label'] == 'negative']
    if not dev or not pos or not neg:
        raise ValueError('dev negatives and heldout positives and negatives required')
    scores = sorted({r['hybrid'][0]['score'] for r in dev if r['hybrid']})
    # nextafter covers tied negative scores and the reject-all boundary.
    candidates = sorted(set(scores + [math.nextafter(s, math.inf) for s in scores]))
    valid = [c for c in candidates if sum(bool(r['hybrid']) and r['hybrid'][0]['score'] >= c for r in dev) / len(dev) <= .20]
    if not valid:
        raise ValueError('no finite cutoff can be fitted')
    cutoff = valid[0]
    accepted = lambda r: bool(r['hybrid']) and r['hybrid'][0]['score'] >= cutoff
    hybrid = [bool(accepted(r) and any(h['relevant'] for h in r['hybrid'][:3])) for r in pos]
    keyword = [r['keyword_hit'] for r in pos]
    diffs = [int(h) - int(k) for h, k in zip(hybrid, keyword)]
    rng = random.Random(seed)
    boots = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(samples))
    interval = [boots[int(.025 * (samples - 1))], boots[int(.975 * (samples - 1))]]
    rate = sum(accepted(r) for r in neg) / len(neg)
    return {'cutoff': cutoff, 'dev_negatives': len(dev), 'heldout_positives': len(pos),
            'heldout_negatives': len(neg), 'keyword_any3': sum(keyword)/len(pos),
            'hybrid_any3': sum(hybrid)/len(pos), 'difference_ci95': interval,
            'negative_injection_rate': rate, 'pass': interval[0] > 0 and rate <= .25,
            'bootstrap_seed': seed, 'bootstrap_samples': samples}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    content = args.input.read_text(encoding='utf-8')
    if args.input.suffix == '.jsonl':
        rows = [row for line in content.splitlines() for row in json.loads(line)['rows']]
    else:
        rows = json.loads(content)
    print(json.dumps(analyse(rows), indent=2))
