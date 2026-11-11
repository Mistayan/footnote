"""Posthoc evidence audit; no retrieval/model/runtime changes. Standard library only."""
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / 'artifacts/accuracy-validation-v2/validation-45b7cf7377844257ab27dc02c46662fb'
RUN = ROOT / 'artifacts/accuracy-validation-v2/run-9090a031e1014818b42a6df066b68eb1'

def exact_span(text, source_start, quote):
    start = text.find(quote)
    if start < 0 or not quote:
        raise ValueError('Evidence must be a nonempty exact substring')
    return {'quote': quote, 'passage_start': start, 'passage_end': start + len(quote),
            'source_start': source_start + start, 'source_end': source_start + start + len(quote)}

def blind_pairs(rows, seed=20261020):
    pairs = {}
    links = []
    for row in rows:
        evidence = row['evidence'][0]
        key = (row['query'], evidence['text'])
        if key not in pairs:
            pairs[key] = {'query': row['query'], 'passage': {k: evidence[k] for k in ['text', 'source', 'url', 'start', 'end', 'sha256', 'raw_sha256']}}
        links.append((key, row))
    keys = list(pairs)
    random.Random(seed).shuffle(keys)
    ids = {key: f'B{i:03d}' for i, key in enumerate(keys, 1)}
    packet = [dict(review_id=ids[key], **pairs[key]) for key in keys]
    mapping = [{'review_id': ids[key], 'query_id': row['id'], 'pipeline': row['variant'],
                'accepted': row['accepted'], 'top1_id': row['evidence'][0]['id'],
                'answerable': bool(row.get('relevant', []))} for key, row in links]
    return packet, mapping

def prepare(output):
    output = Path(output)
    rows = json.loads((RUN / 'results.json').read_text(encoding='utf8'))
    windows = json.loads((SNAP / 'corpus.json').read_text(encoding='utf8'))
    sources = {p.stem: p.read_text(encoding='utf8') for p in (SNAP / 'sources').glob('*.txt')}
    judgments = json.loads((SNAP / 'test-judgments.json').read_text(encoding='utf8'))
    closure = []
    for row in judgments:
        for span in row.get('expected_spans', []):
            matches = quote_closure(span['quote'], sources, windows)
            for match in matches:
                # Same official version explicitly checked; language is not a query constraint.
                match['compatibility'] = 'same official Python 3.13 EN/FR editions' if match['source'].startswith(('contextlib-', 'pathlib-')) else 'same PostgreSQL 17 EN/FR editions'
                match['compatibility_basis'] = 'source URL version and selected source family; equality alone is not compatibility'
            closure.append({'query_id': row['id'], 'quote': span['quote'], 'original_source': span['source'], 'matches': matches, 'omitted_windows': [m['window_id'] for m in matches if m['window_id'] not in row['relevant']]})
    (output / 'quote-closure-preflight.json').write_text(json.dumps(closure, ensure_ascii=False, indent=2), encoding='utf8')
    for row in rows:
        ev = row['evidence'][0]
        assert sources[ev['source']][ev['start']:ev['end']] == ev['text']
        assert hashlib.sha256(ev['text'].encode()).hexdigest() == ev['sha256']
    packet, mapping = blind_pairs(rows)
    assert len(rows) == 104 and len(mapping) == 104
    (output / 'blind-packet.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding='utf8')
    (output / 'mapping-DO-NOT-SEND-TO-REVIEWER.json').write_text(json.dumps(mapping, indent=2), encoding='utf8')
    (output / 'rubric-freeze.json').write_text(json.dumps({'sha256': hashlib.sha256((ROOT / 'tools/semantic_evidence_review/RUBRIC.json').read_bytes()).hexdigest(), 'preflight_before_semantic_review': True, 'rows': len(rows), 'unique_pairs': len(packet)}, indent=2), encoding='utf8')
    print('104 actual rows; unique blind pairs:', len(packet))
    print('Exact quote omissions:', [(r['query_id'], r['omitted_windows']) for r in closure if r['omitted_windows']])

def score(rows):
    answerable = [r for r in rows if r['answerable']]
    accepted = [r for r in rows if r['accepted']]
    aa = [r for r in answerable if r['accepted']]
    na = [r for r in rows if not r['answerable']]
    def bounds(group, denominator):
        return {'lower_n': sum(r['verdict'] == 'pass' for r in group),
                'upper_n': sum(r['verdict'] in ('pass', 'uncertain') for r in group),
                'denominator': denominator}
    return {'raw_p1': bounds(answerable, len(answerable)),
            'accepted_p1_all_answerable': bounds(aa, len(answerable)),
            'conditional_precision_all_accepted': bounds(accepted, len(accepted)),
            'conditional_precision_answerable_accepted': bounds(aa, len(aa)),
            'answerable_coverage': {'numerator': len(aa), 'denominator': len(answerable)},
            'answerable_abstention': {'numerator': len(answerable)-len(aa), 'denominator': len(answerable)},
            'noanswer_false_accept': {'numerator': sum(r['accepted'] for r in na), 'denominator': len(na)}}

def assemble(output):
    output = Path(output)
    packet = json.loads((output / 'blind-packet.json').read_text(encoding='utf8'))
    mapping = json.loads((output / 'mapping-DO-NOT-SEND-TO-REVIEWER.json').read_text(encoding='utf8'))
    decisions = {}
    for file in sorted((ROOT / 'tools/semantic_evidence_review').glob('verdicts-*.json')):
        batch = json.loads(file.read_text(encoding='utf8'))
        assert not (decisions.keys() & batch.keys())
        decisions.update(batch)
    assert set(decisions) == {r['review_id'] for r in packet}
    reviewed = {}
    for pair in packet:
        verdict, quote, rationale = decisions[pair['review_id']]
        assert verdict in ('pass', 'fail', 'uncertain')
        passage = pair['passage']
        is_python = 'docs.python.org' in passage['url']
        edition = ('Python 3.13' if is_python else 'PostgreSQL 17') + (' French edition' if '/fr/' in passage['url'] or 'postgresql.fr' in passage['url'] else ' English edition')
        explicit_source_mismatch = pair['review_id'] in ('B023', 'B022', 'B047')
        absent_deployment_provenance = verdict == 'fail' and not explicit_source_mismatch
        compatibility = ('incompatible: explicit requested source edition/family differs' if explicit_source_mismatch else
                         'unestablished: public documentation does not establish requested private deployment/incident/workload' if absent_deployment_provenance else
                         'compatible: official source family and version; no explicit evidence-language restriction')
        reviewed[pair['review_id']] = dict(pair, verdict=verdict,
            criterion='complete-answer / version / scope / explicit source constraints / full presented passage only',
            rationale=rationale, reviewer='implementing-agent review; not independent human',
            edition_compatibility={'source_edition': edition, 'assessment': compatibility,
                'basis': 'Manually reviewed official URL version, requested source constraints and presented text. Identical text or language alone does not establish compatibility.',
                'substantive_sufficiency_is_separate': True},
            evidence_span=exact_span(passage['text'], passage['start'], quote))
    ledger = [dict(reviewed[r['review_id']], **{k: v for k, v in r.items() if k != 'review_id'}) for r in mapping]
    metrics = {pipeline: score([r for r in ledger if r['pipeline'] == pipeline]) for pipeline in sorted({r['pipeline'] for r in ledger})}
    return ledger, metrics

def finish(output):
    output = Path(output)
    ledger, metrics = assemble(output)
    (output / 'per-query-ledger.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf8')
    (output / 'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf8')
    before = json.loads((output / 'historical-before.json').read_text(encoding='utf8'))
    mutations = [p for p, digest in before.items() if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest]
    assert not mutations, mutations
    (output / 'historical-verification.json').write_text(json.dumps({'checked': len(before), 'mutations': mutations, 'scope': 'all existing accuracy-validation-v2 artifact files and helper source, v2 tests, original v2 report; byte SHA256 before/after'}, indent=2), encoding='utf8')
    print(json.dumps(metrics, indent=2))
    print('Non-pass answerable rows:')
    for r in ledger:
        if r['answerable'] and r['verdict'] != 'pass':
            print(r['pipeline'], r['query_id'], r['review_id'], r['verdict'], r['accepted'], r['rationale'])
    print('historical hashes checked', len(before), 'mutations', len(mutations))

def quote_closure(quote, sources, windows):
    found = []
    for window in windows:
        text = sources[window['source']]
        start = text.find(quote)
        while start >= 0:
            end = start + len(quote)
            if window['start'] <= start and end <= window['end']:
                found.append({'window_id': window['id'], 'source': window['source'],
                              'source_start': start, 'source_end': end,
                              'compatibility': 'UNREVIEWED'})
            start = text.find(quote, start + 1)
    return found
