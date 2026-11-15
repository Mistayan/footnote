"""Run the frozen bilingual memory-writing fixture through resident Footnote MCP."""
import argparse
import hashlib
import json
import math
import os
import platform
import queue
import random
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from contextlib import closing
from pathlib import Path

import memory_cutoff_collect as engine

PREFIX = engine.ROOT / 'bench/work/memory-written-v2'
VARIANTS = ('original', 'qualified', 'full')


def path_of(suffix):
    return Path(str(PREFIX) + suffix)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_data():
    source_freeze = json.loads(path_of('.sources.freeze.json').read_text())
    question_freeze = json.loads(path_of('.questions.freeze.json').read_text())
    for freeze in (source_freeze, question_freeze):
        for name, expected in freeze['hashes'].items():
            if sha(engine.ROOT / name) != expected:
                raise ValueError('frozen input changed: ' + name)
    if question_freeze['source_freeze_sha256'] != sha(path_of('.sources.freeze.json')):
        raise ValueError('questions bound to another source freeze')
    if source_freeze['utc'] >= question_freeze['utc']:
        raise ValueError('source memories must be frozen before questions')
    sources = json.loads(path_of('.sources.json').read_text(encoding='utf-8'))
    questions = json.loads(path_of('.questions.json').read_text(encoding='utf-8'))
    families = {r['family'] for r in sources}
    if len(sources) != 600 or len(families) != 300 or len({r['id'] for r in sources}) != 600:
        raise ValueError('expected 600 distinct translated memories, 300 facts')
    if any(len([s for s in sources if s['family'] == f]) != 2 for f in families):
        raise ValueError('each fact needs exactly two translations')
    splits = {}
    for r in sources + questions:
        group = r['project_group']
        splits.setdefault(group, r['split'])
        if splits[group] != r['split']:
            raise ValueError('project leaks across splits')
    if len(questions) != 1200 or len({q['id'] for q in questions}) != 1200:
        raise ValueError('expected 1200 distinct questions')
    if any(not set(q['gold']) <= families or len(q['query'].encode()) > 512 for q in questions):
        raise ValueError('invalid gold or query')
    return sources, questions


class MCP:
    def __init__(self, db, state):
        self.messages, self.identifier = queue.Queue(), 0
        self.log = (state / 'mcp.stderr.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen([str(engine.BIN), '--db', str(db), 'serve', '--mcp'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True, encoding='utf-8',
            env=dict(os.environ, FOOTNOTE_STATE_DIR=str(state)),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        def read():
            for line in self.process.stdout:
                self.messages.put(line)
            self.messages.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            self.request('initialize', dict(protocolVersion='2025-06-18', capabilities={},
                                           clientInfo=dict(name='memory-written-pilot', version='1')))
            self.process.stdin.write(json.dumps(dict(jsonrpc='2.0', method='notifications/initialized')) + '\n')
            self.process.stdin.flush()
        except Exception:
            self.close()
            raise

    def request(self, method, params):
        self.identifier += 1
        ident = self.identifier
        request = dict(jsonrpc='2.0', id=ident, method=method, params=params)
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        while True:
            line = self.messages.get(timeout=120)
            if line is None:
                raise RuntimeError('MCP server closed; inspect stderr log')
            reply = json.loads(line)
            if reply.get('id') != ident:
                continue
            if 'error' in reply:
                raise RuntimeError(reply['error'])
            return reply['result']

    def recall(self, query, mode):
        args = dict(query=query, project='written-pilot', limit=5)
        if mode == 'hybrid':
            args['model'] = [str(m) for m in engine.MODELS]
        result = self.request('tools/call', dict(name='footnote_memory_recall', arguments=args))
        if result.get('isError'):
            raise RuntimeError(result)
        return json.loads(result['content'][0]['text'])['memories']

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        self.reader.join(timeout=2)
        self.process.stdout.close()
        self.log.close()


def footprint(db):
    with closing(sqlite3.connect(db)) as c:
        vectors = c.execute('SELECT sum(length(vector)) FROM embeddings').fetchone()[0]
    sqlite_bytes = sum(p.stat().st_size for p in db.parent.glob(db.name + '*') if p.is_file())
    index = Path(str(db) + '.tantivy')
    tantivy_bytes = sum(p.stat().st_size for p in index.rglob('*') if p.is_file())
    return dict(sqlite_bytes=sqlite_bytes, tantivy_bytes=tantivy_bytes,
                total_bytes=sqlite_bytes + tantivy_bytes, vector_payload_bytes=vectors)


def run(args):
    sources, questions = frozen_data()
    files = [Path(__file__), Path(engine.__file__), engine.BIN,
             path_of('.sources.json'), path_of('.sources.freeze.json'), path_of('.questions.json'),
             path_of('.questions.freeze.json'), engine.ROOT / 'bench/experiments/MEMORY-WRITTEN.md',
             *[m / n for m in engine.MODELS for n in ('manifest.json', 'model.onnx', 'tokenizer.json')]]
    identity = dict(hashes={str(p.relative_to(engine.ROOT)): sha(p) for p in files},
                    python=sys.version, platform=platform.platform(), smoke=args.smoke,
                    variants=VARIANTS, source_memories=len(sources), underlying_facts=300)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'manifest.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
    if args.smoke:
        questions = questions[:8]
    random.Random(20261115).shuffle(questions)
    for variant in VARIANTS[:1] if args.smoke else VARIANTS:
        print(f'{variant}: building {len(sources)} memories', flush=True)
        with tempfile.TemporaryDirectory(dir=args.output) as tmp:
            state = Path(tmp)
            db = state / 'memory.db'
            batch = [dict(text=s[variant], kind=s['kind'], scope='written-pilot', observed_at='2026-11-15', session=s['id']) for s in sources]
            for start in range(0, len(batch), 50):
                report = engine.call(db, ['remember'], state, json.dumps(batch[start:start + 50]))
                if report['duplicates']:
                    raise ValueError('unexpected duplicate memories')
            engine.call(db, ['rebuild-embeddings', *[v for m in engine.MODELS for v in ('--model', str(m))]], state)
            by_id = {s['id']: s for s in sources}
            with closing(sqlite3.connect(db)) as c:
                session_of = dict(c.execute('SELECT c.id,m.session FROM memories m JOIN chunks c ON c.source_id=m.source_id'))
            if len(session_of) != 600:
                raise ValueError('corpus size changed')
            client = MCP(db, state)
            cold = {}
            try:
                for mode in ('keyword', 'hybrid'):
                    started = time.perf_counter()
                    client.recall(questions[0]['query'], mode)
                    cold[mode] = (time.perf_counter() - started) * 1000
                    for q in questions[:5]:
                        client.recall(q['query'], mode)
                reference = {}
                deterministic, max_score_drift = True, 0.0
                with (args.output / f'{variant}.jsonl').open('x', encoding='utf-8') as output:
                    for repeat in range(2):
                        for index, q in enumerate(questions):
                            for mode in ('keyword', 'hybrid'):
                                started = time.perf_counter()
                                raw = client.recall(q['query'], mode)
                                elapsed = (time.perf_counter() - started) * 1000
                                hits = []
                                for hit in raw:
                                    s = by_id[session_of[hit['id']]]
                                    if mode == 'hybrid' and (not isinstance(hit.get('score'), (int, float)) or not math.isfinite(hit['score'])):
                                        raise ValueError('missing hybrid score')
                                    hits.append(dict(document=s['id'], family=s['family'], language=s['language'], score=hit.get('score')))
                                key = (q['id'], mode)
                                if repeat == 0:
                                    reference[key] = hits
                                else:
                                    before = reference[key]
                                    deterministic &= [h['document'] for h in hits] == [h['document'] for h in before]
                                    if mode == 'hybrid':
                                        max_score_drift = max(max_score_drift, max((abs(a['score'] - b['score']) for a, b in zip(before, hits)), default=0))
                                output.write(json.dumps(dict(query_id=q['id'], repeat=repeat, mode=mode, latency_ms=elapsed, hits=hits)) + '\n')
                            if (index + 1) % 200 == 0:
                                output.flush()
                                print(f'{variant}: pass {repeat + 1}, {index + 1}/{len(questions)}', flush=True)
            finally:
                client.close()
            metadata = dict(variant=variant, memories=600, characters=sum(len(x['text']) for x in batch),
                utf8_bytes=sum(len(x['text'].encode()) for x in batch), footprint=footprint(db),
                cold_first_call_ms=cold, repeated_rankings_identical=deterministic,
                max_score_drift=max_score_drift, queries=len(questions), repeats=2)
            (args.output / f'{variant}.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            print(f'{variant}: done, deterministic={deterministic}', flush=True)


def fit_cutoff(rows):
    scores = sorted({r['hits'][0]['score'] for r in rows if r['hits']})
    if not scores:
        return None
    candidates = sorted(set(scores + [math.nextafter(s, math.inf) for s in scores]))
    return next(c for c in candidates if sum(bool(r['hits']) and r['hits'][0]['score'] >= c for r in rows) / len(rows) <= .20)


def accepted(row, cutoff):
    return bool(row['hits']) and cutoff is not None and row['hits'][0]['score'] >= cutoff


def relevant(row, q, k):
    return any(h['family'] in q['gold'] for h in row['hits'][:k])


def percentile(values, p):
    values = sorted(values)
    return values[round((len(values) - 1) * p)]


def metrics(rows, qs, cutoff=None):
    positive = [r for r in rows if qs[r['query_id']]['gold']]
    negative = [r for r in rows if not qs[r['query_id']]['gold']]
    out = dict(positive_queries=len(positive), negative_queries=len(negative),
               recall3=sum(relevant(r, qs[r['query_id']], 3) for r in positive) / len(positive),
               recall5=sum(relevant(r, qs[r['query_id']], 5) for r in positive) / len(positive),
               precision5=sum(sum(h['family'] in qs[r['query_id']]['gold'] for h in r['hits'][:5]) / 5 for r in positive) / len(positive),
               mrr5=sum(next((1 / (i + 1) for i, h in enumerate(r['hits'][:5]) if h['family'] in qs[r['query_id']]['gold']), 0) for r in positive) / len(positive),
               p50_ms=percentile([r['latency_ms'] for r in rows], .5), p95_ms=percentile([r['latency_ms'] for r in rows], .95))
    if cutoff is not None:
        out.update(cutoff=cutoff, gated_recall3=sum(accepted(r, cutoff) and relevant(r, qs[r['query_id']], 3) for r in positive) / len(positive),
                   false_injection_rate=sum(accepted(r, cutoff) for r in negative) / len(negative),
                   injected_irrelevant_per_prompt=sum(sum(h['family'] not in qs[r['query_id']]['gold'] for h in r['hits'][:3]) for r in rows if accepted(r, cutoff)) / len(rows))
    return out


def paired_interval(a, b, qs, cutoff_a=None, cutoff_b=None):
    groups = defaultdict(list)
    for key, row in a.items():
        q = qs[key]
        if q['split'] != 'heldout' or not q['gold']:
            continue
        va = relevant(row, q, 3) and (cutoff_a is None or accepted(row, cutoff_a))
        vb = relevant(b[key], q, 3) and (cutoff_b is None or accepted(b[key], cutoff_b))
        groups[q['project_group']].append(int(vb) - int(va))
    units = list(groups.values())
    rng = random.Random(20261115)
    draws = []
    for _ in range(10000):
        values = [v for _ in units for v in rng.choice(units)]
        draws.append(sum(values) / len(values))
    return [percentile(draws, .025), percentile(draws, .975)]


def analyse(directory):
    _, questions = frozen_data()
    qs = {q['id']: q for q in questions}
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['smoke']:
        raise ValueError('smoke runs cannot establish results')
    for name, expected in manifest['hashes'].items():
        if sha(engine.ROOT / name) != expected:
            raise ValueError('run input changed: ' + name)
    loaded, cutoffs = {}, {}
    # Fit all thresholds on dev negatives before computing held-out summaries.
    for variant in VARIANTS:
        records = [json.loads(line) for line in (directory / f'{variant}.jsonl').read_text().splitlines()]
        if len(records) != len(qs) * 4 or len({(r['query_id'], r['mode'], r['repeat']) for r in records}) != len(records):
            raise ValueError('incomplete or duplicated measurements')
        rows = [r for r in records if r['repeat'] == 0]
        hybrid = [r for r in rows if r['mode'] == 'hybrid']
        cutoffs[variant] = fit_cutoff([r for r in hybrid if qs[r['query_id']]['split'] == 'dev' and not qs[r['query_id']]['gold']])
        loaded[variant] = records
    frozen_thresholds = directory / 'dev_cutoffs.json'
    threshold_text = json.dumps(cutoffs, indent=2)
    if frozen_thresholds.exists() and json.loads(frozen_thresholds.read_text()) != cutoffs:
        raise ValueError('dev thresholds changed')
    frozen_thresholds.write_text(threshold_text, encoding='utf-8')
    out = dict(scope='SYNTHETIC CONTROLLED PILOT', memories_per_language=300, fact_families=300,
               heldout_project_groups=20, variants={})
    for variant, records in loaded.items():
        first = [r for r in records if r['repeat'] == 0 and qs[r['query_id']]['split'] == 'heldout']
        metadata = json.loads((directory / f'{variant}.metadata.json').read_text())
        out['variants'][variant] = dict(metadata=metadata, cutoff=cutoffs[variant])
        for mode in ('keyword', 'hybrid'):
            rows = [r for r in first if r['mode'] == mode]
            out['variants'][variant][mode] = metrics(rows, qs, cutoffs[variant] if mode == 'hybrid' else None)
            out['variants'][variant][mode]['languages'] = {lang: metrics([r for r in rows if qs[r['query_id']]['language'] == lang], qs,
                cutoffs[variant] if mode == 'hybrid' else None) for lang in ('en', 'fr')}
    indices = {v: {r['query_id']: r for r in rr if r['repeat'] == 0 and r['mode'] == 'hybrid'} for v, rr in loaded.items()}
    base, qualified = (out['variants'][v] for v in ('original', 'qualified'))
    raw_ci = paired_interval(indices['original'], indices['qualified'], qs)
    gated_ci = paired_interval(indices['original'], indices['qualified'], qs, cutoffs['original'], cutoffs['qualified'])
    out.update(raw_recall3_gain=qualified['hybrid']['recall3'] - base['hybrid']['recall3'], raw_gain_ci95=raw_ci,
               gated_gain_ci95=gated_ci,
               qualified_text_ratio=qualified['metadata']['characters'] / base['metadata']['characters'],
               qualified_to_full_text_ratio=qualified['metadata']['characters'] / out['variants']['full']['metadata']['characters'],
               qualified_disk_ratio=qualified['metadata']['footprint']['total_bytes'] / base['metadata']['footprint']['total_bytes'])
    out['raw_ranking_improves_in_pilot'] = raw_ci[0] > 0
    out['automatic_injection_pilot_gates_pass'] = gated_ci[0] > 0 and qualified['hybrid']['false_injection_rate'] <= .25 and qualified['hybrid']['false_injection_rate'] <= base['hybrid']['false_injection_rate'] + .05
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('run')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--smoke', action='store_true')
    p = sub.add_parser('analyse')
    p.add_argument('directory', type=Path)
    args = parser.parse_args()
    if args.command == 'run':
        run(args)
    else:
        print(json.dumps(analyse(args.directory), indent=2))
