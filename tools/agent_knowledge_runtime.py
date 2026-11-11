"""Opt-in, local-only JSONL knowledge adapter. No vault or incumbent DB access.

SQLite revisions/original bytes are authoritative; Qdrant is disposable derived data.
Source text is untrusted data, never interpreted as commands or instructions.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time
import uuid
from urllib.parse import urlsplit

MAX_FILE = 65536
MAX_LINE = 16384
APP_ID = 0x414B5231
RECIPE = 'akr-v1-char400-mean-l2'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('links/reparse points denied')
    return path


class Encoder:
    """Pinned local ONNX recipe, loaded once per resident runtime."""
    def __init__(self, model):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np = np
        model = no_links(model)
        manifest = no_links(model / 'manifest.json').read_bytes()
        self.identity = digest(manifest)
        self.m = json.loads(manifest)
        m = self.m
        if m['pooling'] != 'attention-mask-mean-l2' or m['dimension'] != 384 or not 1 <= m['max_length'] <= 512:
            raise ValueError('unsupported model recipe')
        for name in ('model.onnx', 'tokenizer.json'):
            if digest(no_links(model / name).read_bytes()) != m['files'][name]['sha256']:
                raise ValueError('model artifact hash mismatch: ' + name)
        self.tokenizer = Tokenizer.from_file(str(model / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=m['max_length'])
        self.tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model / 'model.onnx'), sess_options=options,
                                           providers=['CPUExecutionProvider'])
        self.truncated = 0

    def encode(self, texts, kind):
        np = self.np
        tokens = self.tokenizer.encode_batch([self.m[kind + '_prefix'] + t for t in texts])
        ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
        mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
        self.truncated += int((mask.sum(axis=1) >= self.m['max_length']).sum())
        inputs = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)}
        output = self.session.run(None, {i.name: inputs[i.name] for i in self.session.get_inputs()})[0]
        vectors = (output * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        if vectors.shape[1] != 384 or not np.isfinite(vectors).all():
            raise ValueError('invalid embedding output')
        return vectors.tolist()


class Qdrant:
    def __init__(self, url, collection):
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or not parsed.port:
            raise ValueError('explicit loopback HTTP Qdrant URL with port required')
        if parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
            raise ValueError('invalid Qdrant URL')
        if not re.fullmatch(r'akr_[0-9a-f]{32}', collection):
            raise ValueError('owned collection must be akr_ plus 32 lowercase hex characters')
        self.host, self.port = parsed.hostname, parsed.port
        self.base = '/collections/' + collection

    def request(self, method, path='', body=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        try:
            connection.request(method, self.base + path, json.dumps(body) if body is not None else None,
                               {'Content-Type': 'application/json'})
            response = connection.getresponse()
            data = response.read(2_000_000)
            if response.status >= 300:
                raise RuntimeError('Qdrant HTTP ' + str(response.status) + ': ' + data[:256].decode(errors='replace'))
            return json.loads(data)['result']
        except OSError as error:
            raise RuntimeError('Qdrant unavailable at explicit URL: ' + str(error)) from error
        finally:
            connection.close()


class Runtime:
    def __init__(self, *, db, model, qdrant_url, collection, allow_root, allow_files, write=False, create=False,
                 recover_index=False):
        self.db = None
        self.lock = None
        self.write = write
        if recover_index and (not write or create):
            raise ValueError('--recover-index requires --write and an existing authority DB')
        self.root = no_links(allow_root)
        if not self.root.is_dir() or not 1 <= len(allow_files) <= 32:
            raise ValueError('existing root and 1..32 explicit allow-files required')
        self.allowed = sorted(set(allow_files))
        if len(self.allowed) != len(allow_files):
            raise ValueError('duplicate allow-file')
        for name in self.allowed:
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.(md|txt)', name):
                raise ValueError('allow-file must be a plain Markdown/text basename')
            no_links(self.root / name)
        self.path = no_links(db)
        if create and (not write or self.path.exists()):
            raise ValueError('create requires writes and a nonexistent dedicated DB')
        if not create and not self.path.is_file():
            raise ValueError('dedicated runtime DB missing; explicit --create required')
        # Do not open arbitrary existing SQLite databases for mutation.
        if not create:
            probe = sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)
            try:
                if probe.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
                    raise ValueError('not an agent knowledge runtime DB; incumbent DB denied')
            finally:
                probe.close()
        self.remote = Qdrant(qdrant_url, collection)
        try:
            self.lock = open(no_links(str(self.path) + '.lock'), 'a+b')
            self.lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                self.lock.write(b'0')
                self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = time.perf_counter()
            self.encoder = Encoder(model)
            self.model_load_ms = (time.perf_counter() - started) * 1000
            config = {'root': str(self.root), 'files': self.allowed, 'model': self.encoder.identity,
                      'url': qdrant_url.rstrip('/'), 'collection': collection, 'recipe': RECIPE}
            if create:
                # PUT is only allowed after 404. Never overwrite/attach existing collections.
                try:
                    self.remote.request('GET')
                except RuntimeError as error:
                    if not str(error).startswith('Qdrant HTTP 404:'):
                        raise
                else:
                    raise ValueError('collection exists; refusing takeover')
                generation = str(uuid.uuid4())
                self.remote.request('PUT', body={'vectors': {'size': 384, 'distance': 'Cosine'}})
                self.remote.request('PUT', '/points?wait=true', {'points': [
                    {'id': generation, 'vector': [1.0] + [0.0] * 383,
                     'payload': {'owner': generation, 'model': self.encoder.identity, 'role': 'owner'}}]})
                self.db = sqlite3.connect(self.path)
                self.db.executescript('''
                    CREATE TABLE meta(config TEXT NOT NULL, generation TEXT NOT NULL);
                    CREATE TABLE sources(path TEXT PRIMARY KEY, revision INTEGER NOT NULL, sha TEXT, status TEXT NOT NULL);
                    CREATE TABLE revisions(path TEXT NOT NULL, revision INTEGER NOT NULL, sha TEXT, status TEXT NOT NULL,
                        original BLOB, PRIMARY KEY(path,revision));
                    CREATE TABLE chunks(id TEXT PRIMARY KEY, path TEXT NOT NULL, revision INTEGER NOT NULL,
                        sha TEXT NOT NULL, start INTEGER NOT NULL, stop INTEGER NOT NULL, text TEXT NOT NULL, active INTEGER NOT NULL);
                    CREATE TABLE jobs(id TEXT PRIMARY KEY REFERENCES chunks(id), action TEXT NOT NULL, pending INTEGER NOT NULL);
                ''')
                self.db.execute('INSERT INTO meta VALUES(?,?)', (json.dumps(config, sort_keys=True), generation))
                self.db.execute(f'PRAGMA application_id={APP_ID}')
                self.db.execute('PRAGMA user_version=1')
                self.db.commit()
            else:
                self.db = sqlite3.connect(self.path)
                stored, generation = self.db.execute('SELECT config,generation FROM meta').fetchone()
                if json.loads(stored) != config or self.db.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise ValueError('runtime config/model/schema mismatch; use original config or a new DB/collection')
            self.generation = generation
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA busy_timeout=5000')
            if recover_index:
                if not write or create:
                    raise ValueError('--recover-index requires --write and an existing authority DB')
                try:
                    self.remote.request('GET')
                except RuntimeError as error:
                    if not str(error).startswith('Qdrant HTTP 404:'):
                        raise
                    self.remote.request('PUT', body={'vectors': {'size': 384, 'distance': 'Cosine'}})
                    self.remote.request('PUT', '/points?wait=true', {'points': [
                        {'id': generation, 'vector': [1.0] + [0.0] * 383,
                         'payload': {'owner': generation, 'model': self.encoder.identity, 'role': 'owner'}}]})
                self.verify_owner()
                with self.db:
                    self.db.execute("UPDATE jobs SET pending=1,action=CASE WHEN id IN "
                                    "(SELECT id FROM chunks WHERE active=1) THEN 'upsert' ELSE 'delete' END")
            self.verify_owner()
        except Exception:
            self.close()
            raise

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.lock is not None:
            self.lock.close()
            self.lock = None

    def verify_owner(self):
        result = self.remote.request('POST', '/points', {'ids': [self.generation], 'with_payload': True})
        if len(result) != 1 or result[0]['payload'] != {
                'owner': self.generation, 'model': self.encoder.identity, 'role': 'owner'}:
            raise ValueError('derived collection ownership/model missing or mismatched')

    def read_source(self, name):
        if name not in self.allowed:
            raise ValueError('nonallowlisted source denied')
        path = no_links(self.root / name)
        try:
            with path.open('rb') as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ValueError('not a regular source')
                data = source.read(MAX_FILE + 1)
        except FileNotFoundError:
            return None
        if len(data) > MAX_FILE:
            raise ValueError('source exceeds 65536 bytes')
        return data

    def fresh(self, row):
        data = self.read_source(row['path'])
        return data is not None and digest(data) == row['sha']

    def ingest(self, expected):
        if not isinstance(expected, dict) or set(expected) != set(self.allowed):
            raise ValueError('expected hashes must exactly cover explicit allow-files')
        snapshots = {}
        for name, sha in expected.items():
            if sha is not None and (not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha)):
                raise ValueError('expected SHA-256 or explicit null required')
            data = self.read_source(name)
            if (digest(data) if data is not None else None) != sha:
                raise ValueError('source hash drift; ingestion refused: ' + name)
            if data is not None:
                data.decode('utf-8')
            snapshots[name] = data
        changed = 0
        with self.db:
            for name, data in snapshots.items():
                old = self.db.execute('SELECT * FROM sources WHERE path=?', (name,)).fetchone()
                sha = expected[name]
                if old is not None and old['sha'] == sha:
                    continue
                if old is None and data is None:
                    continue
                revision = old['revision'] + 1 if old is not None else 1
                status = 'current' if data is not None else 'deleted'
                # Source pointer, immutable revision, invalidation and outbox are one transaction.
                self.db.execute('UPDATE jobs SET action=\'delete\',pending=1 WHERE id IN '
                                '(SELECT id FROM chunks WHERE path=? AND active=1)', (name,))
                self.db.execute('UPDATE chunks SET active=0 WHERE path=?', (name,))
                self.db.execute('INSERT OR REPLACE INTO sources VALUES(?,?,?,?)', (name, revision, sha, status))
                self.db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)', (name, revision, sha, status, data))
                changed += 1
                if data is None:
                    continue
                text = data.decode('utf-8')
                for start in range(0, len(text), 400):
                    stop = min(start + 400, len(text))
                    identity = str(uuid.uuid5(uuid.UUID(self.generation),
                                   f'{self.encoder.identity}:{name}:{revision}:{sha}:{start}:{RECIPE}'))
                    self.db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,1)',
                                    (identity, name, revision, sha, start, stop, text[start:stop]))
                    self.db.execute('INSERT INTO jobs VALUES(?,?,1)', (identity, 'upsert'))
        return {'changed': changed, 'pending': self.pending()}

    def pending(self):
        return self.db.execute('SELECT count(*) FROM jobs WHERE pending=1').fetchone()[0]

    def sync(self):
        for row in self.db.execute("SELECT * FROM sources WHERE status='current'"):
            if not self.fresh(row):
                raise ValueError('source hash drift; sync refused before remote writes: ' + row['path'])
        self.verify_owner()
        rows = self.db.execute('SELECT c.*,j.action FROM chunks c JOIN jobs j ON j.id=c.id '
                               'WHERE j.pending=1 ORDER BY j.action,c.id').fetchall()
        for row in rows:
            if row['action'] == 'delete' or not row['active']:
                self.remote.request('POST', '/points/delete?wait=true', {'points': [row['id']]})
                if self.remote.request('POST', '/points', {'ids': [row['id']]}):
                    raise RuntimeError('derived delete readback failed')
            else:
                if not self.fresh(row):
                    raise ValueError('source hash drift before encoding')
                vector = self.encoder.encode([row['text']], 'passage')[0]
                if not self.fresh(row):
                    raise ValueError('source hash drift during encoding')
                self.remote.request('PUT', '/points?wait=true', {'points': [
                    {'id': row['id'], 'vector': vector, 'payload': self.signature(row)}]})
                readback = self.remote.request('POST', '/points', {'ids': [row['id']], 'with_payload': True})
                if len(readback) != 1 or readback[0]['payload'] != self.signature(row):
                    raise RuntimeError('derived upsert readback failed')
                if not self.fresh(row):
                    raise ValueError('source hash drift after remote write; pending retained')
            self.db.execute('UPDATE jobs SET pending=0 WHERE id=?', (row['id'],))
            self.db.commit()
        return {'pending': self.pending()}

    def signature(self, row):
        return {'owner': self.generation, 'model': self.encoder.identity, 'id': row['id'],
                'revision': row['revision'], 'sha256': row['sha']}

    def hydrate(self, identity):
        row = self.db.execute('SELECT * FROM chunks WHERE id=? AND active=1', (identity,)).fetchone()
        if row is None:
            raise ValueError('chunk absent or obsolete revision')
        if not self.fresh(row):
            raise ValueError('source stale/missing; ingest and sync explicitly')
        return dict(self.signature(row), path=row['path'], text=row['text'],
                    start=row['start'], stop=row['stop'], freshness='current', usable=True,
                    trust='untrusted_source_data', applicability='not_estimated')

    def search(self, query, limit, mode='semantic'):
        if not isinstance(query, str) or not 1 <= len(query) <= 1024 or type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError('query bound 1..1024 characters; limit 1..8')
        if mode not in ('semantic', 'lexical'):
            raise ValueError('mode must be semantic or explicit lexical')
        if mode == 'lexical':
            terms = set(re.findall(r'\w+', query.casefold()))
            ranked = []
            for row in self.db.execute('SELECT id,text FROM chunks WHERE active=1'):
                score = len(terms & set(re.findall(r'\w+', row['text'].casefold())))
                if score:
                    ranked.append((score, row['id']))
            hits = []
            for score, identity in sorted(ranked, key=lambda item: (-item[0], item[1])):
                try:
                    hits.append(dict(self.hydrate(identity), score=score))
                except ValueError:
                    continue
                if len(hits) == limit:
                    break
            return {'hits': hits, 'mode': mode, 'answerability': 'not_estimated', 'pending': self.pending()}
        vector = self.encoder.encode([query], 'query')[0]
        candidates = self.remote.request('POST', '/points/query', {
            'query': vector, 'limit': 64, 'with_payload': True, 'with_vector': False})['points']
        hits = []
        for point in candidates:
            try:
                hit = self.hydrate(point['id'])
            except ValueError:
                continue
            if point['payload'] != {k: hit[k] for k in ('owner', 'model', 'id', 'revision', 'sha256')}:
                continue
            hits.append(dict(hit, score=point['score']))
            if len(hits) == limit:
                break
        return {'hits': hits, 'mode': 'semantic', 'answerability': 'not_estimated', 'pending': self.pending()}

    def stats(self):
        self.verify_owner()
        count = self.remote.request('POST', '/points/count', {'exact': True})['count']
        sources = self.db.execute("SELECT * FROM sources WHERE status='current'").fetchall()
        fresh_paths = {row['path'] for row in sources if self.fresh(row)}
        chunks = self.db.execute('SELECT * FROM chunks WHERE active=1').fetchall()
        valid = 0
        for start in range(0, len(chunks), 64):
            batch = chunks[start:start + 64]
            points = self.remote.request('POST', '/points', {
                'ids': [row['id'] for row in batch], 'with_payload': True, 'with_vector': False})
            by_id = {point['id']: point for point in points}
            valid += sum(row['path'] in fresh_paths and row['id'] in by_id and
                         by_id[row['id']]['payload'] == self.signature(row) for row in batch)
        return {'encoder_loads': 1, 'model_load_ms': self.model_load_ms, 'model': self.encoder.identity,
                'generation': self.generation, 'current_chunks': len(chunks),
                'current_sources': len(sources), 'stale_sources': len(sources) - len(fresh_paths),
                'revision_snapshots': self.db.execute('SELECT count(*) FROM revisions').fetchone()[0],
                'valid_vectors': valid, 'missing_or_invalid_current_vectors': len(chunks) - valid,
                'invalid_or_orphan_points': max(0, count - 1 - valid),
                'coverage_basis': 'current source hash + point identity/payload; not vector-value attestation',
                'pending': self.pending(), 'qdrant_points': count - 1,
                'embedding_inputs_at_token_limit': self.encoder.truncated}

    def handle(self, request):
        if not isinstance(request, dict):
            raise ValueError('JSON object required')
        op = request.get('op')
        fields = {'ingest': {'expected'}, 'sync': set(), 'stats': set(),
                  'search': {'query', 'limit', 'mode'}, 'get': {'id', 'revision', 'sha256'}}
        if not isinstance(op, str) or op not in fields or set(request) - fields[op] - {'op', 'request_id'}:
            raise ValueError('unknown operation or fields')
        request_id = request.get('request_id', '')
        if not isinstance(request_id, str) or len(request_id) > 64:
            raise ValueError('request_id must be a string of at most 64 characters')
        if op == 'get' and (not isinstance(request.get('id'), str) or
                           not re.fullmatch(r'[0-9a-f-]{36}', request['id'])):
            raise ValueError('revision-bound chunk UUID required; path reads denied')
        if op == 'ingest':
            if not self.write:
                raise ValueError('writes not authorized; --write required')
            return self.ingest(request.get('expected'))
        if op == 'sync':
            if not self.write:
                raise ValueError('writes not authorized; --write required')
            return self.sync()
        if op == 'search':
            return self.search(request.get('query'), request.get('limit', 5), request.get('mode', 'semantic'))
        if op == 'get':
            hit = self.hydrate(request.get('id'))
            if request.get('revision') != hit['revision'] or request.get('sha256') != hit['sha256']:
                raise ValueError('expected revision/hash mismatch')
            return hit
        if op == 'stats':
            return self.stats()
        raise ValueError('unknown operation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('db', 'model', 'qdrant-url', 'collection', 'allow-root'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--allow-file', action='append', required=True)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--create', action='store_true')
    parser.add_argument('--recover-index', action='store_true')
    args = parser.parse_args()
    runtime = None
    try:
        runtime = Runtime(db=args.db, model=args.model, qdrant_url=args.qdrant_url,
                          collection=args.collection, allow_root=args.allow_root,
                          allow_files=args.allow_file, write=args.write, create=args.create, recover_index=args.recover_index)
        print(json.dumps({'ready': True, 'model': runtime.encoder.identity, 'encoder_loads': 1,
                          'generation': runtime.generation, 'model_load_ms': runtime.model_load_ms}), flush=True)
        while True:
            line = sys.stdin.buffer.readline(MAX_LINE + 1)
            if not line:
                break
            if len(line) > MAX_LINE:
                print(json.dumps({'ok': False, 'error': 'JSONL input exceeds 16384 bytes; closing'}), flush=True)
                return 2
            started = time.perf_counter()
            request = None
            try:
                request = json.loads(line)
                result = runtime.handle(request)
                response = {'ok': True, 'result': result}
            except (ValueError, TypeError, KeyError, OSError, RuntimeError, sqlite3.Error) as error:
                response = {'ok': False, 'error': str(error)[:512]}
            response['elapsed_ms'] = (time.perf_counter() - started) * 1000
            if isinstance(request, dict) and isinstance(request.get('request_id'), str) and len(request['request_id']) <= 64:
                response['request_id'] = request['request_id']
            serialized = json.dumps(response, ensure_ascii=True, allow_nan=False)
            if len(serialized.encode()) > 65535:
                serialized = json.dumps({'ok': False, 'error': 'response exceeds 64 KiB'})
            print(serialized, flush=True)
        return 0
    except Exception as error:
        print(json.dumps({'ready': False, 'error': str(error)[:512]}), flush=True)
        return 1
    finally:
        if runtime is not None:
            runtime.close()


if __name__ == '__main__':
    sys.exit(main())
