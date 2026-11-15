"""Rebuild the historical keyword-extraction baseline and collect recall scores.

This is an isolated approximation of agent-written memories, not a product-quality
claim. Writes one JSONL record per question to allow an interrupted run to resume.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'bench/.cache/longmemeval_s/longmemeval_s_cleaned.json'
BIN = ROOT / 'target/release/footnote.exe'
MODELS = [ROOT / 'artifacts/models/bekko-a8m', ROOT / 'artifacts/models/gte-small']
PREF = re.compile(r"\b(always|never|i prefer|i'd rather|i like|i want|please (?:use|don't|do not)|don't|do not)\b", re.I)
FIX = re.compile(r'\b(the fix was|fixed by|root cause|the problem was|turns out)\b', re.I)


def split(qid):
    # Keep abstention variants and their answerable counterparts in the same split.
    family = qid.removesuffix('_abs')
    return 'dev' if int(hashlib.sha256(family.encode()).hexdigest(), 16) % 2 == 0 else 'heldout'


def memories(q):
    batch = []
    for sid, date, session in zip(q['haystack_session_ids'], q['haystack_dates'], q['haystack_sessions']):
        extracted = []
        for turn in session:
            for sentence in re.split(r'(?<=[.!?])\s+|\n', turn.get('content') or ''):
                sentence = sentence.strip()
                if not 20 <= len(sentence) <= 300:
                    continue
                kind = 'preference' if turn['role'] == 'user' and PREF.search(sentence) else (
                    'fix' if turn['role'] == 'assistant' and FIX.search(sentence) else None)
                if kind:
                    extracted.append({'text': sentence, 'kind': kind, 'scope': 'global' if kind == 'preference' else 'longmem',
                                      'observed_at': date[:10].replace('/', '-'), 'session': sid[:200]})
        batch.extend(extracted[:10])
    return batch


def call(db, args, state, stdin=None):
    env = dict(os.environ, FOOTNOTE_STATE_DIR=str(state))
    p = subprocess.run([str(BIN), '--db', str(db), *args], input=stdin, capture_output=True,
                       text=True, encoding='utf-8', timeout=600, env=env,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if p.returncode:
        raise RuntimeError(f'{args[0]}: {p.stderr[-1000:]} {p.stdout[-1000:]}')
    result = json.loads(p.stdout)
    if 'error' in result:
        raise RuntimeError(str(result['error']))
    return result


def query_text(q):
    return q['question'].encode('utf-8')[:500].decode('utf-8', 'ignore')


def collect(q, other, directory):
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        temp = Path(temp)
        db = temp / 'memory.db'
        batch = memories(q)
        if not batch:
            raise ValueError('no memories for ' + q['question_id'])
        for i in range(0, len(batch), 50):
            call(db, ['remember'], temp, json.dumps(batch[i:i + 50]))
        model_args = [v for m in MODELS for v in ('--model', str(m))]
        call(db, ['rebuild-embeddings', *model_args], temp)
        with closing(sqlite3.connect(db)) as c:
            sessions = dict(c.execute('SELECT c.id,m.session FROM memories m JOIN chunks c ON c.source_id=m.source_id'))
        def recall(query, hybrid):
            return call(db, ['memory-recall', '--project', 'longmem', '--limit', '3',
                             *(model_args if hybrid else []), '--', query_text(query)], temp)['memories']
        answer = set(q['answer_session_ids'])
        def hits(raw, gold):
            if any(not isinstance(h.get('score'), (int, float)) for h in raw):
                raise ValueError('hybrid recall did not return numeric fusion scores')
            return [{'score': h['score'], 'relevant': sessions.get(h['id']) in gold} for h in raw]
        keyword = recall(q, False)
        original = {'question_id': q['question_id'], 'split': split(q['question_id']),
                    'label': 'negative' if q['question_id'].endswith('_abs') else 'positive',
                    'keyword_hit': any(sessions.get(h['id']) in answer for h in keyword),
                    'hybrid': hits(recall(q, True), answer)}
        negative = {'question_id': other['question_id'], 'split': split(other['question_id']),
                    'label': 'negative', 'source_question_id': q['question_id'],
                    'hybrid': hits(recall(other, True), set())}
        return [original, negative]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--limit', type=int, default=0, help='first N questions, for smoke tests only')
    p.add_argument('--workers', type=int, default=2)
    args = p.parse_args()
    data = json.loads(DATA.read_text(encoding='utf-8'))
    data.sort(key=lambda q: q['question_id'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    inputs = [Path(__file__), DATA, BIN, *[m / name for m in MODELS for name in ('model.onnx', 'manifest.json', 'tokenizer.json')]]
    identity = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    identity['limit'] = args.limit
    manifest = args.output.with_suffix(args.output.suffix + '.manifest.json')
    if manifest.exists():
        if json.loads(manifest.read_text(encoding='utf-8')) != identity:
            raise ValueError('inputs changed since this collection began')
    elif args.output.exists():
        raise ValueError('refusing to resume an output without its manifest')
    else:
        manifest.write_text(json.dumps(identity, indent=2), encoding='utf-8')
    done = set()
    if args.output.exists():
        for line in args.output.read_text(encoding='utf-8').splitlines():
            done.add(json.loads(line)['source_id'])
    selected = data[:args.limit] if args.limit else data
    def run(q):
        # Pair within the same split and exclude any answer session in this database.
        options = [x for x in data if x['question_id'] != q['question_id'] and split(x['question_id']) == split(q['question_id'])
                   and not set(x['answer_session_ids']) & set(q['haystack_session_ids']) and not x['question_id'].endswith('_abs')]
        if not options:
            raise ValueError('no disjoint negative for ' + q['question_id'])
        other = options[int(hashlib.sha256(q['question_id'].encode()).hexdigest(), 16) % len(options)]
        return {'source_id': q['question_id'], 'rows': collect(q, other, args.output.parent)}
    remaining = [q for q in selected if q['question_id'] not in done]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, result in enumerate(pool.map(run, remaining), len(done) + 1):
            with args.output.open('a', encoding='utf-8') as f:
                f.write(json.dumps(result) + '\n')
            print(f'{index}/{len(selected)} {result["source_id"]}', flush=True)


if __name__ == '__main__':
    main()
