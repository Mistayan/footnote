"""Read-only existing-evidence depth audit. No model inference or new questions."""
import hashlib
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'artifacts/rank-input-repair/diagnostic-75b0e124f04445c4a55c1e7cbe481c19'
SNAP = ROOT/'artifacts/final-multilingual-confirmation/fresh-c6cfd7b5ae4149e7b9f76484e52bf863'
REVIEW = ROOT/'artifacts/rank-input-blind-review/bfe70d15-f920-49f0-992a-0db441281c7a'


def anchor_rank(evidence, quotes):
    """First complete exact selected quote in an original-source presentation.

    A quote is an incomplete selected proof label, NOT an exhaustive semantic gold.
    """
    for rank, e in enumerate(evidence[:5], 1):
        v = e['presentation']
        for a in quotes:
            if e['original']['source'] == a['source'] and v['start'] <= a['start'] and a['end'] <= v['end']:
                if v['text'][a['start']-v['start']:a['end']-v['start']] == a['quote']:
                    return rank
    return None


def main():
    load = lambda p: json.loads(p.read_text(encoding='utf8'))
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    run = ROOT/'artifacts/query-view-calibration'/('paused-depth-audit-'+uuid.uuid4().hex)
    run.mkdir(parents=True)
    dump = lambda name, value: (run/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    files = [OLD/'diagnostic-results-DO-NOT-SEND.jsonl', OLD/'mapping-DO-NOT-SEND.json', OLD/'blind-packet.json', REVIEW/'verdicts.json', SNAP/'gold-DO-NOT-SEND.json']
    files += list((SNAP/'sources').glob('*.txt'))
    before = {str(p.relative_to(ROOT)): sha(p) for p in files}
    dump('historical-before.json', before)
    gold = {q['id']:q for q in load(SNAP/'gold-DO-NOT-SEND.json')}
    texts = {p.stem:p.read_text(encoding='utf8') for p in (SNAP/'sources').glob('*.txt')}
    rows = [json.loads(l) for l in (OLD/'diagnostic-results-DO-NOT-SEND.jsonl').read_text(encoding='utf8').splitlines()]
    packet = {r['review_id']:r for r in load(OLD/'blind-packet.json')}
    verdicts = {r['review_id']:r for r in load(REVIEW/'verdicts.json')}
    mapping = {(r['id'],r['variant']):r for r in load(OLD/'mapping-DO-NOT-SEND.json')}
    assert len(rows) == len(mapping) == len(packet) == len(verdicts) == 156
    perquery = []
    verified_evidence = 0
    for row in rows:
        q = gold[row['id']]
        m = mapping[(row['id'], row['variant'])]
        p = packet[m['review_id']]
        v = verdicts[m['review_id']]
        assert row['query'] == p['query'] == q['query']
        assert row['ranked'][:5] == [e['original']['id'] for e in row['evidence']]
        for e in row['evidence']:
            x = e['presentation']; s = e['original']['source']
            assert texts[s][x['start']:x['end']] == x['text']
            assert hashlib.sha256(x['text'].encode()).hexdigest() == x['sha256']
            verified_evidence += 1
        first = row['evidence'][0]
        x = first['presentation']
        assert p['text'] == x['text'] and p['source'] == first['provenance']
        assert p['start'] == x['start'] and p['end'] == x['end'] and p['excerpt_sha256'] == x['sha256']
        assert v['excerpt_sha256'] == x['sha256']
        # Reviewer preserved identity fields, not HTTP/license receipt extras.
        assert all(first['provenance'][key] == value for key, value in v['source'].items())
        assert {'url', 'sha256', 'text_sha256'} <= set(v['source'])
        assert v['excerpt_start'] == x['start'] and v['excerpt_end'] == x['end']
        assert row['accepted'] == m['accepted'] and q['answerable'] == m['answerable']
        for a in q.get('acceptable_quotes', []):
            assert texts[a['source']][a['start']:a['end']] == a['quote']
        ar = anchor_rank(row['evidence'], q.get('acceptable_quotes', []))
        ids = q.get('expected_ids', [])
        iranks = [i+1 for i,n in enumerate(row['ranked'][:5]) if n in ids]
        perquery.append(dict(id=row['id'], variant=row['variant'], query=row['query'], answerable=q['answerable'], accepted=row['accepted'],
                             top1_semantic_verdict=v['verdict'], selected_complete_quote_first_rank=ar,
                             selected_expected_id_first_rank=min(iranks) if iranks else None,
                             selected_id_recall5=len(set(row['ranked'][:5]) & set(ids))/len(set(ids)) if ids else None,
                             top5_ids=row['ranked'][:5], review_id=m['review_id']))
    summaries = []
    for variant in sorted({r['variant'] for r in rows}):
        rr = [r for r in perquery if r['variant'] == variant]
        a = [r for r in rr if r['answerable']]; n = [r for r in rr if not r['answerable']]
        summaries.append(dict(variant=variant, answerable_total=len(a), noanswer_total=len(n),
                             raw_top1_semantic_pass=sum(r['top1_semantic_verdict']=='pass' for r in a),
                             accepted_top1_semantic_pass=sum(r['accepted'] and r['top1_semantic_verdict']=='pass' for r in a),
                             uncertain_top1=sum(r['top1_semantic_verdict']=='uncertain' for r in a),
                             answerable_accepted=sum(r['accepted'] for r in a), noanswer_accepted=sum(r['accepted'] for r in n),
                             complete_selected_quote_hit1=sum(r['selected_complete_quote_first_rank']==1 for r in a),
                             complete_selected_quote_hit5=sum(r['selected_complete_quote_first_rank'] is not None for r in a),
                             accepted_complete_selected_quote_hit5=sum(r['accepted'] and r['selected_complete_quote_first_rank'] is not None for r in a),
                             complete_selected_quote_mrr5=sum(1/r['selected_complete_quote_first_rank'] if r['selected_complete_quote_first_rank'] else 0 for r in a)/len(a),
                             selected_id_hit5=sum(r['selected_expected_id_first_rank'] is not None for r in a),
                             selected_id_mean_recall5=sum(r['selected_id_recall5'] or 0 for r in a)/len(a),
                             selected_id_mrr5=sum(1/r['selected_expected_id_first_rank'] if r['selected_expected_id_first_rank'] else 0 for r in a)/len(a)))
    dump('per-query-depth-DO-NOT-SEND.json', perquery)
    report = dict(status='PAUSED BEFORE NEW DEVELOPMENT OR FRESH INFERENCE ON USER STEERING',
                  new_model_inference_requests=0, new_fresh_questions=0, learned_threshold=None,
                  old_rule='2.5 unchanged; not transferred as calibrated query-view rule',
                  evidence='Existing exposed diagnostic only. Complete selected quote retrieval is not exhaustive semantic Hit@5/Recall@5. No agent generated answer or iterative retrieval has been executed.',
                  semantic_depth='Only top1 has independent semantic judgments; top2..5 remain semantically unjudged outside complete selected quote checks.',
                  denominator='All40 answerable, including rejected queries; 12 noanswer separate.',
                  variants=summaries)
    dump('report.json', report)
    assert all(sha(ROOT/p)==h for p,h in before.items())
    dump('verification.json', dict(historical_files_unchanged=len(before), exact_presentations_verified=verified_evidence,
                                   exact_existing_top1_review_packets_verified=len(rows), rank_order_from_existing_archive_verified=True,
                                   new_rank_inference_parity_asserted=False, no_inference=True, no_server_started=True))
    for p in list((ROOT/'tools/query_view_calibration').glob('*.py'))+[ROOT/'tests/test_query_view_calibration.py']:
        target = run/'code'/p.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(p.read_bytes())
    dump('artifact-sha256.json', {str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file()})
    print(json.dumps(dict(run=str(run), **report), ensure_ascii=False, indent=2))
    return run


if __name__ == '__main__':
    main()
