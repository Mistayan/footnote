"""Development-only max-logit calibration; no semantic diagnostic labels here."""
import math

FAMILY = dict(pipeline='query2', score='max parent logit', operator='>=',
              minimum_answerable_coverage=.8, maximum_noanswer_false_acceptance=.1,
              objective=['minimize wrong accepted selected-positive answerables',
                         'maximize balanced accuracy: selected-correct accept / all answerables and noanswer rejection',
                         'highest threshold'], candidates='distinct finite development top1 scores plus nextafter(max,+infinity)',
              labels='incomplete development selected-positive identities only; not semantic accuracy')


def metrics(rows, threshold):
    a = [r for r in rows if r['answerable']]
    n = [r for r in rows if not r['answerable']]
    accepted = lambda r: r['score'] is not None and r['score'] >= threshold
    correct = sum(accepted(r) and r['top1_label'] for r in a)
    aa = sum(accepted(r) for r in a)
    na = sum(accepted(r) for r in n)
    return dict(answerable_total=len(a), noanswer_total=len(n), answerable_accepted=aa,
                correct_accepted=correct, wrong_accepted=aa-correct,
                noanswer_accepted=na, answerable_rejected=len(a)-aa,
                accuracy=correct/len(a) if a else None,
                coverage=aa/len(a) if a else None,
                balanced_accuracy=(correct/len(a)+(len(n)-na)/len(n))/2 if a and n else None)


def assert_rounds(rounds, pool, count):
    """Require original candidate batch cohorts, never interleaved duplicates."""
    assert len(rounds) == count
    for slot, batch in enumerate(rounds):
        assert [p['parent'] for p in batch] == pool
        assert all(p['slot'] == slot for p in batch)


def select_threshold(rows):
    scores = sorted({float(r['score']) for r in rows if r['score'] is not None})
    if not scores or not all(math.isfinite(s) for s in scores):
        raise ValueError('finite development scores required')
    options = []
    for threshold in scores+[math.nextafter(scores[-1], math.inf)]:
        m = metrics(rows, threshold)
        if not m['answerable_total'] or not m['noanswer_total']:
            raise ValueError('both development strata required')
        if m['answerable_accepted']*5 >= m['answerable_total']*4 and m['noanswer_accepted']*10 <= m['noanswer_total']:
            options.append(dict(threshold=threshold, metrics=m))
    best = max(options, key=lambda r: (-r['metrics']['wrong_accepted'], r['metrics']['balanced_accuracy'], r['threshold'])) if options else None
    return dict(feasible=best is not None, **(best or dict(threshold=None, metrics=None)), candidates_evaluated=len(scores)+1)
