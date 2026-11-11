"""Isolated Python resident-inference benchmark, not the Rust CLI."""
import argparse
import concurrent.futures
import hashlib
import http.client
import json
import math
import os
import platform
import re
import socket
import sqlite3
import statistics
import subprocess
import threading
import time
import uuid
from pathlib import Path

import numpy as np
import onnxruntime as ort
import psutil
from tokenizers import Tokenizer

from hybrid_dataset import DOCS, QUERIES

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / 'artifacts/server-provision/qdrant-1.19.2/qdrant.exe'
MODEL = REPO / 'artifacts/models/minilm'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def percentile(values, p):
    return sorted(values)[math.ceil(len(values) * p) - 1]


def source_hashes():
    # Bind actual execution inputs, not a parallel worker's unrelated new scripts.
    paths = [REPO / p for p in ('tools/server_benchmark.py', 'tests/server_benchmark_test.py',
                               'tools/embed.py', 'tools/hybrid_dataset.py', 'requirements-hybrid.lock')]
    paths += [MODEL / p for p in ('manifest.json', 'model.onnx', 'tokenizer.json')]
    paths += [SERVER, REPO / '.git/index']
    return {str(p.relative_to(REPO)): sha(p) for p in paths if p.is_file()}


class ResidentEncoder:
    """Same verified ONNX recipe as embed.py, one session/tokenizer per run."""
    def __init__(self, model=MODEL):
        self.manifest = json.loads((model / 'manifest.json').read_bytes())
        m = self.manifest
        if m['pooling'] != 'attention-mask-mean-l2' or m['dimension'] != 384 or not 1 <= m['max_length'] <= 512:
            raise ValueError('unsupported embedding recipe')
        for name in ('model.onnx', 'tokenizer.json'):
            if (model / name).is_symlink() or sha(model / name) != m['files'][name]['sha256']:
                raise ValueError('model artifact hash mismatch: ' + name)
        self.tokenizer = Tokenizer.from_file(str(model / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=m['max_length'])
        self.tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model / 'model.onnx'), sess_options=options,
                                           providers=['CPUExecutionProvider'])
        self.lock = threading.Lock()

    def encode(self, texts, kind='query'):
        queued = time.perf_counter()
        with self.lock:
            started = time.perf_counter()
            result = []
            prefix = self.manifest['query_prefix' if kind == 'query' else 'passage_prefix']
            for offset in range(0, len(texts), 8):
                tokens = self.tokenizer.encode_batch([prefix + t for t in texts[offset:offset + 8]])
                ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
                mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
                inputs = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)}
                output = self.session.run(None, {i.name: inputs[i.name] for i in self.session.get_inputs()})[0]
                vectors = (output * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
                vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
                if vectors.shape[1] != 384 or not np.isfinite(vectors).all():
                    raise ValueError('invalid embedding output')
                result.extend(vectors.tolist())
            return result, {'inference_queue_ms': (started - queued) * 1000,
                            'encode_ms': (time.perf_counter() - started) * 1000}


class Server:
    """Own exactly one process; never connect to or stop an existing service."""
    def __init__(self, run):
        self.run = run
        self.process = None
        self.log = None
        self.local = threading.local()
        self.connections = []
        self.connections_lock = threading.Lock()
        self.reservation = socket.socket()
        self.reservation.bind(('127.0.0.1', 0))
        self.port = self.reservation.getsockname()[1]
        self.config = {'storage': {'storage_path': str(run / 'storage'),
                                   'snapshots_path': str(run / 'snapshots'),
                                   'temp_path': str(run / 'temp')},
                       'service': {'host': '127.0.0.1', 'http_port': self.port,
                                   'grpc_port': None, 'max_workers': 4},
                       'cluster': {'enabled': False}, 'telemetry_disabled': True,
                       'log_level': 'INFO'}

    def start(self):
        config_path = self.run / 'server.yaml'
        save(config_path, self.config)
        self.log = (self.run / 'server.log').open('wb')
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith('QDRANT_')}
        self.reservation.close()
        self.process = subprocess.Popen([str(SERVER), '--config-path', str(config_path), '--disable-telemetry'],
                                        cwd=self.run, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('spawned Qdrant exited; inspect ' + str(self.run / 'server.log'))
            try:
                self.request('GET', '/readyz', raw=True)
                return
            except (OSError, http.client.HTTPException):
                time.sleep(.1)
        raise TimeoutError('Qdrant did not become ready')

    def request(self, method, path, body=None, raw=False):
        conn = getattr(self.local, 'connection', None)
        if conn is None:
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
            self.local.connection = conn
            with self.connections_lock:
                self.connections.append(conn)
        payload = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, payload, {'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = response.read()
        if response.status >= 300:
            raise RuntimeError(f'Qdrant HTTP {response.status}: {data[:1000]!r}')
        return data.decode() if raw else json.loads(data)

    def query(self, vector, exact=False):
        response = self.request('POST', '/collections/comparison/points/query',
                                {'query': vector, 'limit': 60, 'with_payload': False,
                                 'with_vector': False, 'params': {'exact': exact, 'hnsw_ef': 128}})
        points = sorted(response['result']['points'], key=lambda p: (-p['score'], p['id']))
        return points, response

    def close(self):
        self.reservation.close()
        for conn in self.connections:
            conn.close()
        code = None
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=20)
            code = self.process.returncode
        if self.log:
            self.log.close()
        with socket.socket() as probe:
            probe.settimeout(.5)
            closed = probe.connect_ex(('127.0.0.1', self.port)) != 0
        result = {'pid': self.process.pid if self.process else None, 'port': self.port,
                  'process_exited': self.process is None or self.process.poll() is not None,
                  'port_closed': closed, 'returncode': code,
                  'shutdown': 'owned Popen terminate/wait; no other PID touched'}
        save(self.run / 'cleanup.json', result)
        return result


class ResourceSampler:
    def __init__(self, server):
        self.processes = {'harness': psutil.Process(), 'server': psutil.Process(server.process.pid)}
        self.rows = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        while not self.stop.is_set():
            row = {'time': time.perf_counter()}
            for name, process in self.processes.items():
                info = process.memory_info()
                cpu = process.cpu_times()
                row[name] = {'rss': info.rss, 'cpu_s': cpu.user + cpu.system,
                             'threads': process.num_threads()}
            self.rows.append(row)
            self.stop.wait(.01)

    def __enter__(self):
        self.before = {name: sum(p.cpu_times()[:2]) for name, p in self.processes.items()}
        self.started = time.perf_counter()
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self.report = {'wall_s': time.perf_counter() - self.started, 'sample_interval_s': .01}
        for name, process in self.processes.items():
            self.report[name] = {'cpu_s': sum(process.cpu_times()[:2]) - self.before[name],
                                 'peak_rss_sampled': max(r[name]['rss'] for r in self.rows),
                                 'max_threads_sampled': max(r[name]['threads'] for r in self.rows)}


class Pipeline:
    def __init__(self, db, encoder, server):
        self.db, self.encoder, self.server = db, encoder, server
        self.local = threading.local()
        self.connections = []
        self.lock = threading.Lock()

    def connection(self):
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(f'file:{self.db.as_posix()}?mode=ro', uri=True,
                                                    check_same_thread=False)
            with self.lock:
                self.connections.append(self.local.connection)
        return self.local.connection

    def lexical(self, query):
        terms = re.findall(r'[^\W_]+(?:_[^\W_]+)*', query, re.UNICODE)
        expr = ' OR '.join('"' + t.replace('"', '""') + '"' for t in terms)
        if not expr:
            return []
        return [r[0] for r in self.connection().execute(
            'SELECT rowid FROM texts_fts WHERE texts_fts MATCH ? ORDER BY bm25(texts_fts),rowid LIMIT 20', (expr,))]

    def sqlite_semantic(self, vector):
        started = time.perf_counter()
        rows = self.connection().execute('SELECT id,vector FROM vectors ORDER BY id').fetchall()
        identifiers = [r[0] for r in rows]
        matrix = np.asarray([json.loads(r[1]) for r in rows], dtype=np.float64)
        decoded = time.perf_counter()
        scores = np.einsum('ij,j->i', matrix, vector)
        order = sorted(range(len(rows)), key=lambda i: (-scores[i], identifiers[i]))[:60]
        return [{'id': identifiers[i], 'score': float(scores[i])} for i in order], {
            'sqlite_read_decode_ms': (decoded - started) * 1000,
            'sqlite_dot_sort_ms': (time.perf_counter() - decoded) * 1000}

    def request(self, engine, query, submitted=None):
        started = time.perf_counter()
        vectors, stages = self.encoder.encode([query['query']])
        vector = vectors[0]
        before = time.perf_counter()
        lexical = self.lexical(query['query'])
        stages['lexical_ms'] = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        if engine == 'sqlite_json_exact':
            semantic, extra = self.sqlite_semantic(vector)
            stages.update(extra)
        else:
            semantic, raw = self.server.query(vector)
            stages['server_reported_ms'] = raw['time'] * 1000
        stages['vector_ms'] = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        ids = fuse([p['id'] for p in semantic], lexical)
        stages['rrf_ms'] = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        results = []
        for identifier in ids:
            row = self.connection().execute('SELECT path,sha256,text FROM documents WHERE id=?', (identifier,)).fetchone()
            path, digest, text = row
            results.append({'id': identifier, 'path': path, 'sha256': digest, 'revision': 1,
                            'heading': text.splitlines()[0].lstrip('# '), 'page': None, 'line': 1,
                            'text': text[:500], 'freshness': 'current' if sha(path) == digest else 'stale'})
        serialized = json.dumps({'results': results, 'answerability': 'not_estimated'},
                                ensure_ascii=False, separators=(',', ':'))
        stages['hydrate_hash_serialize_ms'] = (time.perf_counter() - before) * 1000
        done = time.perf_counter()
        return {'engine': engine, 'query_id': query['id'], 'query': query['query'],
                'e2e_ms': (done - started) * 1000,
                'submit_to_done_ms': (done - (submitted if submitted is not None else started)) * 1000,
                'query_vector_sha256': hashlib.sha256(np.asarray(vector, dtype=np.float64).tobytes()).hexdigest(),
                'qdrant_raw': raw if engine == 'qdrant_server_ann' else None,
                'stages': stages, 'lexical': lexical, 'semantic': semantic, 'ids': ids,
                'response_json': serialized, 'response_bytes': len(serialized.encode()),
                'citations_current': sum(r['freshness'] == 'current' for r in results)}

    def close(self):
        for conn in self.connections:
            conn.close()


def benchmark(document_count=1000, repeats=3, queries=None, concurrency=4):
    if not len(DOCS) <= document_count <= 10000 or not 1 <= repeats <= 20 or not 1 <= concurrency <= 16:
        raise ValueError('bounded document_count/repeats/concurrency required')
    queries = QUERIES if queries is None else queries
    run = new_run(REPO / 'artifacts/server-benchmark')
    before = source_hashes()
    save(run / 'source-before.json', before)
    save(run / 'judgments.json', queries)
    server = Server(run)
    pipeline = None
    report = {'run': run.as_posix(), 'label': 'Python harness; NOT Rust CLI',
              'documents': document_count, 'queries': len(queries), 'repeats': repeats,
              'concurrency': concurrency, 'summaries': []}
    try:
        server.start()
        save(run / 'server-identity.json', server.request('GET', '/'))
        report['server'] = {'identity': server.request('GET', '/'), 'binary_sha256': sha(SERVER),
                            'pid': server.process.pid, 'port': server.port, 'config': server.config}
        started = time.perf_counter()
        encoder = ResidentEncoder()
        report['model_load_validate_ms'] = (time.perf_counter() - started) * 1000
        from embed import encode
        old = encode(MODEL, {'kind': 'query', 'texts': [queries[0]['query']]})['vectors']
        new = encoder.encode([queries[0]['query']])[0]
        report['resident_recipe_matches_existing_helper'] = bool(np.allclose(old, new, atol=1e-12, rtol=0))
        assert report['resident_recipe_matches_existing_helper']
        notes = run / 'notes'
        notes.mkdir()
        corpus = dict(DOCS)
        for i in range(document_count - len(corpus)):
            corpus[f'distractor-{i:04}'] = (f'# Garden fixture {i}\nPlant flowers, water vegetables and prune fruit trees. '
                                             f'Unrelated synthetic fixture {i}.')
        documents = []
        for identifier, (name, text) in enumerate(corpus.items(), 1):
            path = notes / (name + '.md')
            path.write_text(text, encoding='utf-8')
            documents.append((identifier, str(path), sha(path), text))
        save(run / 'corpus.json', [dict(zip(('id', 'path', 'sha256', 'text'), d)) for d in documents])
        started = time.perf_counter()
        vectors = encoder.encode([d[3] for d in documents], 'passage')[0]
        report['embed_documents_ms'] = (time.perf_counter() - started) * 1000
        save(run / 'vectors.json', vectors)
        db = run / 'knowledge.db'
        with sqlite3.connect(db) as conn:
            conn.executescript('CREATE TABLE documents(id INTEGER PRIMARY KEY,path TEXT,sha256 TEXT,text TEXT);'
                               'CREATE TABLE vectors(id INTEGER PRIMARY KEY,vector TEXT);'
                               "CREATE VIRTUAL TABLE texts_fts USING fts5(body,tokenize='unicode61 remove_diacritics 2');")
            conn.executemany('INSERT INTO documents VALUES(?,?,?,?)', documents)
            conn.executemany('INSERT INTO texts_fts(rowid,body) VALUES(?,?)', [(d[0], d[3]) for d in documents])
            conn.executemany('INSERT INTO vectors VALUES(?,?)', [(d[0], json.dumps(v)) for d, v in zip(documents, vectors)])
        config = {'vectors': {'size': 384, 'distance': 'Cosine', 'on_disk': False},
                  'shard_number': 1, 'hnsw_config': {'m': 16, 'ef_construct': 100, 'full_scan_threshold': 10},
                  'optimizers_config': {'indexing_threshold': 1, 'default_segment_number': 1}}
        save(run / 'collection-create.json', config)
        server.request('PUT', '/collections/comparison', config)
        started = time.perf_counter()
        for offset in range(0, len(vectors), 128):
            server.request('PUT', '/collections/comparison/points?wait=true', {'points': [
                {'id': documents[i][0], 'vector': vectors[i]} for i in range(offset, min(offset + 128, len(vectors)))]})
        deadline = time.monotonic() + 120
        while True:
            collection = server.request('GET', '/collections/comparison')['result']
            if collection.get('indexed_vectors_count', 0) == document_count and collection['status'] == 'green':
                break
            if time.monotonic() > deadline:
                save(run / 'collection-index-timeout.json', collection)
                raise TimeoutError('Actual HNSW index did not reach all points')
            time.sleep(.2)
        report['server_seed_and_index_ms'] = (time.perf_counter() - started) * 1000
        report['collection'] = collection
        save(run / 'collection-ready.json', collection)
        # Verify all seeded vectors after the server's documented float32 conversion.
        retrieved = []
        for offset in range(0, len(vectors), 128):
            retrieved.extend(server.request('POST', '/collections/comparison/points', {
                'ids': [d[0] for d in documents[offset:offset + 128]],
                'with_payload': False, 'with_vector': True})['result'])
        retrieved.sort(key=lambda p: p['id'])
        error = float(np.max(np.abs(np.asarray([p['vector'] for p in retrieved]) - np.asarray(vectors))))
        assert len(retrieved) == document_count and error < 1e-6
        report['server_vector_readback_max_abs_error'] = error
        save(run / 'server-vector-readback.json', retrieved)
        pipeline = Pipeline(db, encoder, server)
        recalls = []
        qvectors = {}
        for query in queries:
            vector = encoder.encode([query['query']])[0][0]
            qvectors[query['id']] = vector
            exact, _ = pipeline.sqlite_semantic(vector)
            ann, ann_raw = server.query(vector)
            qexact, qexact_raw = server.query(vector, exact=True)
            exact_ids, ann_ids = {p['id'] for p in exact}, {p['id'] for p in ann}
            qexact_ids = {p['id'] for p in qexact}
            cutoff = exact[-1]['score']
            all_scores = np.einsum('ij,j->i', np.asarray(vectors), vector)
            tolerant = sum(all_scores[p['id'] - 1] >= cutoff - 1e-6 for p in ann) / len(exact)
            recalls.append({'query_id': query['id'], 'strict_ann_vs_sqlite_recall60': len(exact_ids & ann_ids) / len(exact),
                            'strict_ann_vs_qdrant_exact_recall60': len(qexact_ids & ann_ids) / len(exact),
                            'tie_tolerant_ann_vs_sqlite_recall60': tolerant,
                            'sqlite_exact': exact, 'qdrant_ann_raw': ann_raw, 'qdrant_exact_raw': qexact_raw})
        save(run / 'recall.json', recalls)
        save(run / 'query-vectors.json', qvectors)
        report['recall'] = {key: statistics.mean(r[key] for r in recalls) for key in recalls[0] if key.endswith('recall60')}
        for query in queries:
            for engine in ('sqlite_json_exact', 'qdrant_server_ann'):
                pipeline.request(engine, query)
        raw = []
        blocks = []
        for mode, workers in (('sequential', 1), ('concurrent', concurrency)):
            for repeat in range(repeats):
                engines = ['sqlite_json_exact', 'qdrant_server_ann']
                if repeat % 2:
                    engines.reverse()
                for engine in engines:
                    with ResourceSampler(server) as resources:
                        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                            for offset in range(0, len(queries), workers):
                                futures = [pool.submit(pipeline.request, engine, q, time.perf_counter())
                                           for q in queries[offset:offset + workers]]
                                for future in futures:
                                    row = future.result()
                                    row.update(mode=mode, repeat=repeat)
                                    raw.append(row)
                    block = {'mode': mode, 'repeat': repeat, 'engine': engine,
                             'requests': len(queries), 'resources': resources.report,
                             'throughput_rps': len(queries) / resources.report['wall_s']}
                    blocks.append(block)
                    save(run / f'resources-{mode}-{engine}-{repeat}.json', resources.rows)
                    save(run / 'raw-results.json', raw)
                    save(run / 'blocks.json', blocks)
        for mode in ('sequential', 'concurrent'):
            for engine in ('sqlite_json_exact', 'qdrant_server_ann'):
                rows = [r for r in raw if r['mode'] == mode and r['engine'] == engine]
                summary = {'mode': mode, 'engine': engine, 'samples': len(rows),
                           'citations_current': sum(r['citations_current'] for r in rows)}
                for field in ('e2e_ms', 'submit_to_done_ms'):
                    summary[field] = {'p50': statistics.median(r[field] for r in rows),
                                      'p95': percentile([r[field] for r in rows], .95)}
                summary['stages'] = {stage: {'p50': statistics.median(r['stages'][stage] for r in rows),
                                             'p95': percentile([r['stages'][stage] for r in rows], .95)}
                                     for stage in rows[0]['stages']}
                bs = [b for b in blocks if b['mode'] == mode and b['engine'] == engine]
                summary['throughput_rps'] = sum(b['requests'] for b in bs) / sum(b['resources']['wall_s'] for b in bs)
                summary['resource_blocks'] = bs
                report['summaries'].append(summary)
        lexical = {}
        for row in raw:
            key = row['query_id']
            if key in lexical:
                assert lexical[key] == row['lexical'], 'lexical candidates changed between engines'
            lexical[key] = row['lexical']
        report['identical_lexical_candidates'] = True
        expected_qhash = {key: hashlib.sha256(np.asarray(v, dtype=np.float64).tobytes()).hexdigest()
                          for key, v in qvectors.items()}
        assert all(r['query_vector_sha256'] == expected_qhash[r['query_id']] for r in raw)
        report['identical_query_vectors'] = True
        report['paired_top5_equal'] = sum(
            next(r for r in raw if r['engine'] == 'sqlite_json_exact' and r['query_id'] == q['id'])['ids'] ==
            next(r for r in raw if r['engine'] == 'qdrant_server_ann' and r['query_id'] == q['id'])['ids']
            for q in queries)
        # The main thread was idle during worker blocks; discard its expired HTTP keepalive.
        server.local.connection.close()
        del server.local.connection
        save(run / 'server-telemetry.json', server.request('GET', '/telemetry?details_level=3'))
        (run / 'server-metrics.txt').write_text(server.request('GET', '/metrics', raw=True), encoding='utf-8')
        report['environment'] = {'python': platform.python_version(), 'platform': platform.platform(),
                                 'numpy': np.__version__, 'onnxruntime': ort.__version__,
                                 'sqlite': sqlite3.sqlite_version, 'logical_cpus': psutil.cpu_count(),
                                 'physical_cpus': psutil.cpu_count(logical=False),
                                 'total_memory_bytes': psutil.virtual_memory().total}
    except Exception as error:
        save(run / 'failure.json', {'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        if pipeline:
            pipeline.close()
        report['cleanup'] = server.close()
        after = source_hashes()
        save(run / 'source-after.json', after)
        report['sources_stable'] = before == after
        report['source_changes'] = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        save(run / 'partial-report.json', report)
    assert report['sources_stable'], 'sources changed during benchmark: ' + str(report['source_changes'])
    assert report['cleanup']['process_exited'] and report['cleanup']['port_closed']
    report['storage_bytes'] = {'sqlite': db.stat().st_size,
                               'server_storage_after_forced_shutdown': sum(p.stat().st_size for p in (run / 'storage').rglob('*') if p.is_file())}
    save(run / 'report.json', report)
    manifest = {str(p.relative_to(run)): sha(p) for p in run.rglob('*') if p.is_file()}
    save(run / 'evidence-sha256.json', manifest)
    print(json.dumps({'run': run.as_posix(), 'samples': sum(s['samples'] for s in report['summaries']),
                      'report_sha256': sha(run / 'report.json'), 'sources_stable': report['sources_stable'],
                      'cleanup': report['cleanup']}, indent=2), flush=True)
    return report


def new_run(base):
    base = Path(base).resolve()
    if base.name != 'server-benchmark' or base.parent.name != 'artifacts':
        raise ValueError('run root must be artifacts/server-benchmark')
    if any(p.is_symlink() for p in (base, *base.parents)):
        raise ValueError('run root must not traverse symlinks')
    run = base / uuid.uuid4().hex
    run.mkdir(parents=True, exist_ok=False)
    return run



def fuse(semantic, lexical, limit=5):
    scores = {}
    for candidates in (semantic, lexical):
        for rank, identifier in enumerate(candidates, 1):
            scores[identifier] = scores.get(identifier, 0) + 1 / (60 + rank)
    return sorted(scores, key=lambda identifier: (-scores[identifier], identifier))[:limit]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--documents', type=int, default=1000)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--concurrency', type=int, default=4)
    args = parser.parse_args()
    benchmark(document_count=args.documents, repeats=args.repeats, concurrency=args.concurrency)

