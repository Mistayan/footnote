"""Compact source-only qualification, measured against frozen context controls."""
import argparse
import concurrent.futures
import hashlib
import json
import math
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import memory_context as ctx

REFERENCE = ctx.ROOT / 'bench/work/memory-context-dev-v1.jsonl'
EXTRA_LIMIT = 80
FOOTPRINT_CASES = 10


def compact(item, source, sessions):
    """Only source arrays are accepted, not the benchmark question or labels."""
    turn = sessions[source['turn']]
    sentences = [s.strip() for s in ctx.SENTENCES.split(turn.get('content') or '')]
    index = source['sentence']
    if sentences[index] != item['text']:
        raise ValueError('source statement changed')
    candidate = ''
    if item['kind'] == 'fix':
        for earlier in reversed(sessions[:source['turn']]):
            if earlier['role'] == 'user' and earlier.get('content'):
                candidate = next((s.strip() for s in ctx.SENTENCES.split(earlier['content']) if s.strip()), '')
                break
    if not candidate:
        candidate = sentences[index - 1] if index else (sentences[index + 1] if index + 1 < len(sentences) else '')
    candidate = ' '.join(candidate.split())
    if not candidate or candidate == item['text']:
        return item['text']
    budget = EXTRA_LIMIT - len('Subject: \n')
    if len(candidate) > budget:
        candidate = candidate[:budget].rsplit(' ', 1)[0] if ' ' in candidate[:budget] else candidate[:budget]
    return f'Subject: {candidate}\n{item["text"]}'


def store(batch, directory, q=None, other=None):
    with tempfile.TemporaryDirectory(dir=directory) as name:
        temp = Path(name)
        db = temp / 'memory.db'
        for start in range(0, len(batch), 50):
            ctx.old.call(db, ['remember'], temp, json.dumps(batch[start:start + 50]))
        models = [v for model in ctx.old.MODELS for v in ('--model', str(model))]
        ctx.old.call(db, ['rebuild-embeddings', *models], temp)
        with closing(sqlite3.connect(db)) as c:
            session_of = dict(c.execute('SELECT c.id,m.session FROM memories m JOIN chunks c ON c.source_id=m.source_id'))
            vector_bytes = c.execute('SELECT COALESCE(sum(length(vector)),0) FROM embeddings').fetchone()[0]
        if len(session_of) != len(batch):
            raise ValueError('stored memory count differs')
        rows = []
        if q is not None:
            for query, label in ((q, 'abstention' if q['question_id'].endswith('_abs') else 'positive'), (other, 'cross')):
                gold = set(q['answer_session_ids']) if label == 'positive' else set()
                row = dict(question_id=query['question_id'], label=label)
                for mode, extra in (('keyword', []), ('hybrid', models)):
                    raw = ctx.old.call(db, ['memory-recall', '--project', 'longmem', '--limit', '3',
                                           *extra, '--', ctx.old.query_text(query)], temp)['memories']
                    if mode == 'hybrid' and any(not isinstance(h.get('score'), (int, float)) or
                                              not math.isfinite(h['score']) for h in raw):
                        raise ValueError('missing hybrid score')
                    row[mode] = [dict(score=h.get('score'), relevant=session_of.get(h['id']) in gold) for h in raw]
                rows.append(row)
        sqlite_bytes = sum(p.stat().st_size for p in temp.glob('memory.db*') if p.is_file())
        index_dir = temp / 'memory.db.tantivy'
        tantivy_bytes = sum(p.stat().st_size for p in index_dir.rglob('*') if p.is_file())
        return dict(rows=rows, stored=len(batch), chars=sum(len(m['text']) for m in batch),
                    footprint=dict(sqlite_bytes=sqlite_bytes, tantivy_bytes=tantivy_bytes,
                                   total_bytes=sqlite_bytes + tantivy_bytes, vector_payload_bytes=vector_bytes))


def load_reference():
    manifest = json.loads(REFERENCE.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if manifest['hashes'] != ctx.identities():
        raise ValueError('reference inputs no longer match current binary/models/code')
    records = [json.loads(line) for line in REFERENCE.read_text(encoding='utf-8').splitlines()]
    if len(records) != manifest['count'] or len({r['source_id'] for r in records}) != len(records):
        raise ValueError('reference is incomplete or duplicated')
    return {r['source_id']: r for r in records}


def collect(args):
    reference = load_reference()
    data = ctx.load_data()
    selected = data[:args.limit] if args.limit else data
    inputs = [Path(__file__), Path(__file__).with_name('MEMORY-QUALIFICATION.md'), REFERENCE, REFERENCE.with_suffix('.manifest.json')]
    identity = dict(hashes=ctx.identities() | {str(p.relative_to(ctx.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                    source_ids=[q['question_id'] for q in selected], count=len(selected), limit=args.limit)
    manifest = args.output.with_suffix('.manifest.json')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != identity:
            raise ValueError('inputs changed: choose another output')
    elif args.output.exists():
        raise ValueError('output exists without manifest')
    else:
        manifest.write_text(json.dumps(identity, indent=2), encoding='utf-8')
    done = set()
    if args.output.exists():
        done = {json.loads(line)['source_id'] for line in args.output.read_text(encoding='utf-8').splitlines()}
    footprint_ids = {q['question_id'] for q in data[:FOOTPRINT_CASES]}
    def run(q):
        items = ctx.build_memories(q['haystack_sessions'], q['haystack_session_ids'], q['haystack_dates'])
        source_by_session = dict(zip(q['haystack_session_ids'], q['haystack_sessions'], strict=True))
        batch = [item | dict(text=compact(item, source, source_by_session[source['session']])) for item, _, source in items]
        previous = reference[q['question_id']]
        other = ctx.negative_for(q, data)
        if other['question_id'] != previous['negative_id']:
            raise ValueError('negative identity changed')
        result = store(batch, args.output.parent, q, other)
        if result['stored'] != previous['variants']['baseline']['stored']:
            raise ValueError('memory count changed')
        answer = dict(source_id=q['question_id'], compact=result,
                      changed=sum(m['text'] != item['text'] for m, (item, _, _) in zip(batch, items)))
        if q['question_id'] in footprint_ids:
            answer['footprint_controls'] = {
                'baseline': store([item for item, _, _ in items], args.output.parent)['footprint'],
                'context': store([item | dict(text=text) for item, text, _ in items], args.output.parent)['footprint']}
        return answer
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, result in enumerate(pool.map(run, [q for q in selected if q['question_id'] not in done]), len(done) + 1):
            with args.output.open('a', encoding='utf-8') as f:
                f.write(json.dumps(result) + '\n')
            print(f'{index}/{len(selected)} {result["source_id"]}', flush=True)


def summary(records):
    rows = [row for r in records for row in r['rows']]
    positive = [r for r in rows if r['label'] == 'positive']
    negative = [r for r in rows if r['label'] != 'positive']
    groups = {}
    for label in ('abstention', 'cross'):
        group = [r for r in negative if r['label'] == label]
        groups[label] = dict(n=len(group), injected=sum(bool(r['hybrid']) and r['hybrid'][0]['score'] >= ctx.CUTOFF for r in group))
    return dict(positives=len(positive), hybrid_any3=sum(ctx.hit(r) for r in positive) / len(positive),
                keyword_any3=sum(ctx.hit(r, 'keyword') for r in positive) / len(positive),
                gated_any3=sum(ctx.hit(r, gated=True) for r in positive) / len(positive),
                gated_negative_injection=sum(bool(r['hybrid']) and r['hybrid'][0]['score'] >= ctx.CUTOFF for r in negative) / len(negative),
                chars=sum(r['chars'] for r in records), stored=sum(r['stored'] for r in records), negative_groups=groups)


def analyse(path):
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if len(records) != manifest['count'] or {r['source_id'] for r in records} != set(manifest['source_ids']):
        raise ValueError('incomplete/duplicate collection')
    reference = load_reference()
    out = dict(scope='DEVELOPMENT ONLY', databases=len(records), variants={})
    for variant in ('baseline', 'context'):
        out['variants'][variant] = summary([reference[r['source_id']]['variants'][variant] for r in records])
    out['variants']['compact'] = summary([r['compact'] for r in records])
    groups = defaultdict(list)
    for r in records:
        a = reference[r['source_id']]['variants']['baseline']['rows'][0]
        b = r['compact']['rows'][0]
        if a['label'] == 'positive':
            groups[r['source_id'].removesuffix('_abs')].append(int(ctx.hit(b)) - int(ctx.hit(a)))
    base, full, compact_score = (out['variants'][v] for v in ('baseline', 'context', 'compact'))
    gain = compact_score['hybrid_any3'] - base['hybrid_any3']
    full_gain = full['hybrid_any3'] - base['hybrid_any3']
    out.update(hybrid_gain=gain, hybrid_gain_ci95=ctx.interval(groups),
               text_ratio=compact_score['chars'] / base['chars'], retained_full_context_gain=gain / full_gain if full_gain else None)
    out['criteria'] = dict(positive_interval=out['hybrid_gain_ci95'][0] > 0,
        retains_75_percent_gain=full_gain > 0 and gain >= .75 * full_gain,
        text_ratio_at_most_1_75=out['text_ratio'] <= 1.75,
        aggregate_noise_delta_at_most_5_points=compact_score['gated_negative_injection'] - base['gated_negative_injection'] <= .05,
        no_extra_true_abstentions=compact_score['negative_groups']['abstention']['injected'] <= base['negative_groups']['abstention']['injected'])
    out['promising_for_fresh_confirmation'] = all(out['criteria'].values())
    samples = [r for r in records if 'footprint_controls' in r]
    out['footprint_sample'] = dict(databases=len(samples), totals={})
    for variant in ('baseline', 'context', 'compact'):
        parts = [r['compact']['footprint'] if variant == 'compact' else r['footprint_controls'][variant] for r in samples]
        out['footprint_sample']['totals'][variant] = {key: sum(p[key] for p in parts) for key in ('sqlite_bytes', 'tantivy_bytes', 'total_bytes', 'vector_payload_bytes')}
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('collect')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--limit', type=int, default=0, help='smoke only')
    p = sub.add_parser('analyse')
    p.add_argument('input', type=Path)
    args = parser.parse_args()
    if args.command == 'collect':
        collect(args)
    else:
        print(json.dumps(analyse(args.input), indent=2))
