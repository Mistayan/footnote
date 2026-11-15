"""Paired, source-only memory contextualization experiment. See MEMORY-CONTEXT.md."""
import argparse
import concurrent.futures
import hashlib
import json
import math
import random
import re
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import memory_cutoff_collect as old

ROOT = old.ROOT
CUTOFF = 2.341051842888992
SENTENCES = re.compile(r'(?<=[.!?])\s+|\n')
VARIANTS = ('baseline', 'context')


def build_memories(sessions, session_ids, dates):
    """Accept source history only. No evaluation query or labels are accessible here."""
    result, seen = [], set()
    for sid, date, session in zip(session_ids, dates, sessions, strict=True):
        extracted, last_user = [], ''
        for turn_index, turn in enumerate(session):
            text = turn.get('content') or ''
            sentences = [s.strip() for s in SENTENCES.split(text)]
            for index, sentence in enumerate(sentences):
                if not 20 <= len(sentence) <= 300:
                    continue
                kind = 'preference' if turn['role'] == 'user' and old.PREF.search(sentence) else (
                    'fix' if turn['role'] == 'assistant' and old.FIX.search(sentence) else None)
                if kind is None:
                    continue
                before = sentences[index - 1][:240] if index else ''
                after = sentences[index + 1][:240] if index + 1 < len(sentences) else ''
                context = []
                if kind == 'fix' and last_user:
                    context.append('Earlier user context: ' + last_user[:240])
                if before:
                    context.append('Source context: ' + before)
                context.append('Memory: ' + sentence)
                if after:
                    context.append('Source continuation: ' + after)
                item = dict(text=sentence, kind=kind, scope='global' if kind == 'preference' else 'longmem',
                            observed_at=date[:10].replace('/', '-'), session=sid[:200])
                enriched = '\n'.join(context) if len(context) > 1 else sentence
                extracted.append((item, enriched, dict(session=sid, turn=turn_index, sentence=index)))
            if turn['role'] == 'user':
                last_user = text
        for item, enriched, source in extracted[:10]:
            key = (item['kind'], item['scope'], item['text'])
            if key in seen:
                continue
            seen.add(key)
            result.append((item, enriched, source))
    return result


def load_data():
    data = json.loads(old.DATA.read_text(encoding='utf-8'))
    return sorted((q for q in data if old.split(q['question_id']) == 'dev'), key=lambda q: q['question_id'])


def negative_for(q, data):
    candidates = [x for x in data if x['question_id'] != q['question_id']
                  and not x['question_id'].endswith('_abs')
                  and not set(x['answer_session_ids']) & set(q['haystack_session_ids'])]
    if not candidates:
        raise ValueError('no disjoint development negative')
    return candidates[int(hashlib.sha256(q['question_id'].encode()).hexdigest(), 16) % len(candidates)]


def collect_one(q, other, directory):
    items = build_memories(q['haystack_sessions'], q['haystack_session_ids'], q['haystack_dates'])
    if not items:
        raise ValueError('empty extraction: ' + q['question_id'])
    result = dict(source_id=q['question_id'], negative_id=other['question_id'], variants={})
    # Verify exact baseline identity/order independently against the historical helper.
    unique = {}
    for item in old.memories(q):
        unique.setdefault((item['kind'], item['scope'], item['text']), item)
    if list(unique.values()) != [item for item, _, _ in items]:
        raise ValueError('baseline extraction changed')
    for variant in VARIANTS:
        with tempfile.TemporaryDirectory(dir=directory) as temp:
            temp = Path(temp)
            db = temp / 'memory.db'
            batch = [item | dict(text=enriched) if variant == 'context' else item for item, enriched, _ in items]
            for start in range(0, len(batch), 50):
                old.call(db, ['remember'], temp, json.dumps(batch[start:start + 50]))
            models = [v for model in old.MODELS for v in ('--model', str(model))]
            old.call(db, ['rebuild-embeddings', *models], temp)
            with closing(sqlite3.connect(db)) as c:
                session_of = dict(c.execute('SELECT c.id,m.session FROM memories m JOIN chunks c ON c.source_id=m.source_id'))
            if len(session_of) != len(items):
                raise ValueError('stored identity count differs')
            rows = []
            for query, label in ((q, 'abstention' if q['question_id'].endswith('_abs') else 'positive'), (other, 'cross')):
                gold = set(q['answer_session_ids']) if label == 'positive' else set()
                row = dict(question_id=query['question_id'], label=label)
                for mode, extra in (('keyword', []), ('hybrid', models)):
                    raw = old.call(db, ['memory-recall', '--project', 'longmem', '--limit', '3',
                                        *extra, '--', old.query_text(query)], temp)['memories']
                    if mode == 'hybrid' and any(not isinstance(h.get('score'), (float, int))
                                              or not math.isfinite(h['score']) for h in raw):
                        raise ValueError('missing numeric hybrid score')
                    row[mode] = [dict(score=h.get('score'), relevant=session_of.get(h['id']) in gold) for h in raw]
                rows.append(row)
            result['variants'][variant] = dict(rows=rows, stored=len(session_of),
                                              chars=sum(len(item['text']) for item in batch))
    result['changed_memories'] = sum(item['text'] != text for item, text, _ in items)
    result['memory_count'] = len(items)
    return result


def identities():
    files = [Path(__file__), Path(old.__file__), old.DATA, old.BIN,
             Path(__file__).with_name('MEMORY-CONTEXT.md'),
             *[m / name for m in old.MODELS for name in ('model.onnx', 'manifest.json', 'tokenizer.json')]]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def collect(args):
    data = load_data()
    selected = data[:args.limit] if args.limit else data
    manifest = args.output.with_suffix('.manifest.json')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    identity = dict(hashes=identities(), limit=args.limit, count=len(selected), source_ids=[q['question_id'] for q in selected])
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != identity:
            raise ValueError('inputs changed: use another output')
    elif args.output.exists():
        raise ValueError('output without manifest')
    else:
        manifest.write_text(json.dumps(identity, indent=2), encoding='utf-8')
    done = set()
    if args.output.exists():
        done = {json.loads(line)['source_id'] for line in args.output.read_text(encoding='utf-8').splitlines()}
    def run(q):
        return collect_one(q, negative_for(q, data), args.output.parent)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        remaining = [q for q in selected if q['question_id'] not in done]
        for index, result in enumerate(pool.map(run, remaining), len(done) + 1):
            with args.output.open('a', encoding='utf-8') as f:
                f.write(json.dumps(result) + '\n')
            print(f'{index}/{len(selected)} {result["source_id"]}', flush=True)


def hit(row, mode='hybrid', gated=False):
    hits = row[mode]
    accepted = bool(hits) and (not gated or hits[0]['score'] >= CUTOFF)
    return bool(accepted and any(h['relevant'] for h in hits))


def interval(groups):
    values = list(groups.values())
    if not values:
        raise ValueError('no paired groups')
    rng = random.Random(20261115)
    samples = []
    for _ in range(10000):
        resampled = [d for _ in values for d in rng.choice(values)]
        samples.append(sum(resampled) / len(resampled))
    samples.sort()
    return [samples[249], samples[9749]]


def analyse(path):
    results = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if len(results) != manifest['count'] or {r['source_id'] for r in results} != set(manifest['source_ids']):
        raise ValueError('incomplete or duplicated collection')
    out = dict(scope='DEVELOPMENT ONLY', questions=len(results), cutoff=CUTOFF, variants={})
    for variant in VARIANTS:
        rows = [row for r in results for row in r['variants'][variant]['rows']]
        positive = [r for r in rows if r['label'] == 'positive']
        neg = [r for r in rows if r['label'] != 'positive']
        out['variants'][variant] = dict(positives=len(positive), negatives=len(neg),
            keyword_any3=sum(hit(r, 'keyword') for r in positive) / len(positive),
            hybrid_any3=sum(hit(r) for r in positive) / len(positive),
            gated_any3=sum(hit(r, gated=True) for r in positive) / len(positive),
            keyword_negative_injection=sum(bool(r['keyword']) for r in neg) / len(neg),
            gated_negative_injection=sum(bool(r['hybrid']) and r['hybrid'][0]['score'] >= CUTOFF for r in neg) / len(neg),
            stored=sum(r['variants'][variant]['stored'] for r in results),
            chars=sum(r['variants'][variant]['chars'] for r in results))
        out['variants'][variant]['negative_groups'] = {
            label: dict(n=len(group), gated_injection=sum(bool(r['hybrid']) and r['hybrid'][0]['score'] >= CUTOFF for r in group) / len(group))
            for label in ('abstention', 'cross') if (group := [r for r in neg if r['label'] == label])}
    groups = defaultdict(list)
    for r in results:
        a, b = (r['variants'][v]['rows'][0] for v in VARIANTS)
        if a['label'] == 'positive':
            groups[r['source_id'].removesuffix('_abs')].append(int(hit(b)) - int(hit(a)))
    out['hybrid_difference_ci95'] = interval(groups)
    a, b = (out['variants'][v] for v in VARIANTS)
    out['hybrid_difference'] = b['hybrid_any3'] - a['hybrid_any3']
    out['gated_negative_difference'] = b['gated_negative_injection'] - a['gated_negative_injection']
    out['changed_memory_share'] = sum(r['changed_memories'] for r in results) / sum(r['memory_count'] for r in results)
    out['promising_for_fresh_confirmation'] = out['hybrid_difference_ci95'][0] > 0 and out['gated_negative_difference'] <= .05
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('collect')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--limit', type=int, default=0, help='smoke test only')
    p = sub.add_parser('analyse')
    p.add_argument('input', type=Path)
    args = parser.parse_args()
    if args.command == 'collect':
        collect(args)
    else:
        print(json.dumps(analyse(args.input), indent=2))
