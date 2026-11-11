"""Bounded PUBLIC technical retrieval evaluation, never a production CLI adapter."""
import hashlib
import json
import sqlite3
import statistics
import argparse
import datetime
import html.parser
import re
import time
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def excerpt(text, anchor, length=1600):
    position = text.find(anchor)
    if position < 0:
        raise ValueError('missing official source anchor: ' + anchor)
    start = position
    end = min(len(text), start + length)
    return {'start': start, 'end': end, 'text': text[start:end]}


class ResidentEncoder:
    """Same verified recipe as embed.encode, one tokenizer/session per run."""
    def __init__(self, model):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np = np
        model = Path(model)
        raw = (model / 'manifest.json').read_bytes()
        self.manifest = json.loads(raw)
        m = self.manifest
        if m['pooling'] != 'attention-mask-mean-l2' or m['dimension'] != 384 or not 1 <= m['max_length'] <= 512:
            raise ValueError('unsupported embedding recipe')
        for name in ['model.onnx', 'tokenizer.json']:
            path = model / name
            if path.is_symlink() or digest(path.read_bytes()) != m['files'][name]['sha256']:
                raise ValueError('model artifact hash mismatch: ' + name)
        self.manifest_sha256 = digest(raw)
        self.tokenizer = Tokenizer.from_file(str(model / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=m['max_length'])
        self.tokenizer.enable_padding(pad_id=1, pad_token='<pad>')
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model / 'model.onnx'), sess_options=options, providers=['CPUExecutionProvider'])
        self.runtime = {'numpy': np.__version__, 'onnxruntime': ort.__version__}
        self.truncated = {'query': 0, 'passage': 0}

    def token_count(self, text, kind):
        # Independent untruncated view; never change the resident inference tokenizer.
        from tokenizers import Tokenizer
        if not hasattr(self, 'count_tokenizer'):
            self.count_tokenizer = Tokenizer.from_str(self.tokenizer.to_str())
            self.count_tokenizer.no_truncation()
            self.count_tokenizer.no_padding()
        return len(self.count_tokenizer.encode(self.manifest[kind + '_prefix'] + text).ids)

    def encode(self, texts, kind):
        np = self.np
        if kind not in ('query', 'passage') or not 1 <= len(texts) <= 10000 or any(not isinstance(t, str) or len(t.encode()) > 64000 for t in texts):
            raise ValueError('invalid embedding input')
        prefix = self.manifest[kind + '_prefix']
        result = []
        for start in range(0, len(texts), 8):
            tokens = self.tokenizer.encode_batch([prefix + t for t in texts[start:start + 8]])
            ids = np.asarray([t.ids for t in tokens], dtype=np.int64)
            mask = np.asarray([t.attention_mask for t in tokens], dtype=np.int64)
            self.truncated[kind] += int((mask.sum(axis=1) >= self.manifest['max_length']).sum())
            inputs = {'input_ids': ids, 'attention_mask': mask, 'token_type_ids': np.zeros_like(ids)}
            output = self.session.run(None, {i.name: inputs[i.name] for i in self.session.get_inputs()})[0]
            vectors = (output * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
            vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
            if vectors.shape[1] != 384 or not np.isfinite(vectors).all():
                raise ValueError('invalid embedding output')
            result.extend(vectors.tolist())
        return np.asarray(result)


def child_chunks(corpus, encoders):
    """Lossless nonoverlapping source slices fitting every named tokenizer.

    Keep one token below each cap so at-limit counts are unambiguous. No query,
    relevance label or observed retrieval score participates in boundary selection.
    """
    children = []
    for parent in corpus:
        offset = 0
        while offset < len(parent['text']):
            remaining = parent['text'][offset:]
            low, high = 1, len(remaining)
            fits = lambda size: all(e.token_count(remaining[:size], 'passage') < e.manifest['max_length'] for e in encoders)
            if not fits(1):
                raise ValueError('token budget cannot fit one source character')
            while low < high:
                mid = (low + high + 1) // 2
                if fits(mid):
                    low = mid
                else:
                    high = mid - 1
            text = remaining[:low]
            assert fits(low)
            start = parent['start'] + offset
            children.append(dict(id=f"{parent['id']}::child-{offset:06}", parent_id=parent['id'],
                                 source=parent['source'], start=start, end=start + low,
                                 text=text, sha256=digest(text.encode())))
            offset += low
    return children


def parent_ranking(names, corpus):
    mapping = {d['id']: d.get('parent_id', d['id']) for d in corpus}
    return list(dict.fromkeys(mapping[name] for name in names))


def lexical_index(corpus):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE VIRTUAL TABLE documents USING fts5(id UNINDEXED, text)')
    db.executemany('INSERT INTO documents VALUES (?, ?)', [(d['id'], d['text']) for d in corpus])
    return db


def lexical_search(db, query):
    # Same literal whitespace-term AND construction as app.rs, not a tuned OR baseline.
    expression = ' AND '.join('"' + term.replace('"', '""') + '"' for term in query.split())
    if not expression:
        return []
    return [r[0] for r in db.execute('SELECT id FROM documents WHERE documents MATCH ? ORDER BY bm25(documents), id LIMIT 20', (expression,))]


def fuse(semantic, lexical):
    ranking = {}
    for candidates in (semantic[:60], lexical[:20]):
        for rank, name in enumerate(candidates, 1):
            ranking[name] = ranking.get(name, 0) + 1 / (60 + rank)
    return sorted(ranking, key=lambda name: (-ranking[name], name))


def fit_threshold(rows):
    if not rows or any(r['split'] != 'development' for r in rows):
        raise ValueError('threshold fitting requires development rows only')
    positives = [r for r in rows if r['relevant']]
    negatives = [r for r in rows if not r['relevant']]
    if not positives or not negatives:
        raise ValueError('both answerable and no-answer development examples required')
    def balanced(threshold):
        return (statistics.mean(r['max_cosine'] >= threshold for r in positives) +
                statistics.mean(r['max_cosine'] < threshold for r in negatives)) / 2
    return max({-1.0, 1.000001, *(r['max_cosine'] for r in rows)}, key=lambda t: (balanced(t), t))


def score(names, judgment):
    names = list(dict.fromkeys(names))[:5]
    relevant = set(judgment['relevant'])
    incompatible = set(judgment['incompatible'])
    return {
        'top1': int(bool(names) and names[0] in relevant) if relevant else None,
        'mrr': next((1 / (i + 1) for i, name in enumerate(names) if name in relevant), 0) if relevant else None,
        'recall_at_5': len(set(names) & relevant) / len(relevant) if relevant else None,
        'no_answer_false_acceptance': int(bool(names)) if not relevant else None,
        'incompatible_at_1': int(bool(names) and names[0] in incompatible),
        'incompatible_at_5': len(set(names) & incompatible),
    }


SOURCES = {
    'py311': 'https://raw.githubusercontent.com/python/cpython/v3.11.9/Doc/library/sqlite3.rst',
    'py312': 'https://raw.githubusercontent.com/python/cpython/v3.12.3/Doc/library/sqlite3.rst',
    'async': 'https://raw.githubusercontent.com/python/cpython/v3.12.3/Doc/library/asyncio-task.rst',
    'wal': 'https://www.sqlite.org/wal.html',
    'isolation': 'https://www.sqlite.org/isolation.html',
    'fts': 'https://www.sqlite.org/fts5.html',
    'backup': 'https://www.sqlite.org/backup.html',
    **{name: 'https://raw.githubusercontent.com/qdrant/landing_page/3d4e1897a2ca017999ad3d77b1ade6f7530ca1ed/qdrant-landing/content/documentation/search/' + page + '.md'
       for name, page in [('qfilter', 'filtering'), ('qhybrid', 'hybrid-queries'), ('qsearch', 'search')]},
}

# Each passage is an exact contiguous excerpt of fetched normalized public text.
# No generated prose is inserted into the indexed passages.
PASSAGES = [
    ('wal-checkpoint', 'wal', 'Moving the WAL file transactions back into the database', 1300),
    ('wal-network', 'wal', 'All processes using a database must be on the same host computer', 900),
    ('wal-writer', 'wal', 'there can only be one writer at a time', 1100),
    ('isolation-dirty', 'isolation', 'The combined use of shared cache mode', 1200),
    ('isolation-snapshot', 'isolation', 'SQLITE_BUSY_SNAPSHOT', 1400),
    ('fts-bm25', 'fts', 'The built-in auxiliary function bm25() returns', 1700),
    ('fts-prefix', 'fts', 'A prefix index is created for each integer', 1000),
    ('backup-snapshot', 'backup', 'The Online Backup API', 1500),
    ('py311-transactions', 'py311', '.. _sqlite3-controlling-transactions:', 2000),
    ('py312-transactions', 'py312', 'Transaction control via the ``autocommit`` attribute', 2100),
    ('py312-autocommit', 'py312', '.. attribute:: autocommit', 1700),
    ('py311-backup', 'py311', '.. method:: backup(target', 1300),
    ('py312-thread', 'py312', ':param bool check_same_thread:', 1000),
    ('async-cancel', 'async', 'When a task is cancelled,', 1500),
    ('async-wait', 'async', '.. coroutinefunction:: wait_for(aw, timeout)', 1600),
    ('async-shield', 'async', '.. awaitablefunction:: shield(aw)', 1600),
    ('qfilter-must', 'qfilter', '### Must\n', 366),
    ('qfilter-should', 'qfilter', '### Should\n', 758),
    ('qfilter-not', 'qfilter', '### Must Not', 474),
    ('qfilter-range', 'qfilter', '### Range\n', 900),
    ('qsearch-threshold', 'qsearch', '### Filtering Results by Score', 1300),
    ('qhybrid-rrf', 'qhybrid', '### Reciprocal Rank Fusion (RRF)', 1200),
    ('qhybrid-dbsf', 'qhybrid', '### Distribution-Based Score Fusion (DBSF)', 1900),
    ('qhybrid-weights', 'qhybrid', '#### Weighted RRF', 1800),
]

# Authored before inference. These are evidence-location labels, not answer claims.
# Split has different questions, but related topics: NOT independent human evaluation.
DEVELOPMENT = [
    ('SQLite WAL checkpoint moves transactions database', ['wal-checkpoint'], [], 'exact'),
    ('Pourquoi SQLite WAL exige-t-il que tous les processus soient sur le même ordinateur ?', ['wal-network'], [], 'fr_to_en'),
    ('When can a SQLite reader see uncommitted changes from another connection?', ['isolation-dirty'], [], 'confusable'),
    ('FTS5 bm25 lower score better match', ['fts-bm25'], [], 'exact'),
    ('Python 3.12 recommended transaction control autocommit False', ['py312-transactions', 'py312-autocommit'], ['py311-transactions'], 'version_specific'),
    ('Comment libérer les ressources quand une tâche asyncio est annulée ?', ['async-cancel'], [], 'fr_to_en'),
    ('Qdrant must requires every filter condition', ['qfilter-must'], ['qfilter-should', 'qfilter-not'], 'confusable'),
    ('Comment exclure les résultats vectoriels trop peu similaires avec Qdrant ?', ['qsearch-threshold'], [], 'fr_to_en'),
    ('Qdrant Reciprocal Rank Fusion positions rather than raw scores', ['qhybrid-rrf'], [], 'paraphrase'),
    ('Python sqlite3 check_same_thread False concurrent writes', ['py312-thread'], [], 'exact'),
    ('Quel filtre Qdrant sélectionne un intervalle numérique ?', ['qfilter-range'], [], 'fr_to_en'),
    ('Depuis quelle version Qdrant permet-il de pondérer les branches RRF ?', ['qhybrid-weights'], [], 'version_specific'),
]
HOLDOUT = [
    ('Pourquoi deux rédacteurs SQLite WAL ne peuvent-ils pas écrire simultanément ?', ['wal-writer'], [], 'fr_to_en'),
    ('How can SQLITE_BUSY_SNAPSHOT be resolved when upgrading a read transaction?', ['isolation-snapshot'], [], 'exact_error'),
    ('Comment obtenir une sauvegarde SQLite cohérente avec la base source ?', ['backup-snapshot', 'py311-backup'], [], 'fr_to_en'),
    ('FTS5 prefix indexes integer prefix lengths', ['fts-prefix'], [], 'exact'),
    ('Python 3.11 isolation_level None explicit SQL transaction control', ['py311-transactions'], ['py312-transactions', 'py312-autocommit'], 'version_specific'),
    ('Does sqlite3 backup work while other clients access the source database?', ['py311-backup'], [], 'paraphrase'),
    ('asyncio wait_for timeout cancellation total wait exceeds timeout', ['async-wait'], [], 'exact'),
    ('Comment protéger une tâche asyncio contre l’annulation de son appelant ?', ['async-shield'], [], 'fr_to_en'),
    ('Qdrant should filter at least one condition', ['qfilter-should'], ['qfilter-must', 'qfilter-not'], 'confusable'),
    ('Quel opérateur Qdrant exclut tous les points satisfaisant une condition interdite ?', ['qfilter-not'], ['qfilter-must', 'qfilter-should'], 'fr_to_en'),
    ('Qdrant DBSF normalizes mean standard deviation scores', ['qhybrid-dbsf'], [], 'exact'),
    ('Python 3.12 autocommit isolation_level LEGACY_TRANSACTION_CONTROL', ['py312-autocommit', 'py312-transactions'], ['py311-transactions'], 'version_specific'),
]
NO_ANSWER = {
    'development': [
        'What is the SQLite database password for our deployment?',
        'Quel p99 a été mesuré sur notre serveur Qdrant de production ?',
        'Which Python sqlite3 API performs GPU HNSW indexing?',
        'Quelle est la clé de chiffrement AES du fichier WAL déployé ?',
    ],
    'holdout': [
        'What is the measured memory usage of our running Qdrant server?',
        'Quel utilisateur possède notre fichier de base SQLite en production ?',
        'Which SQLite pragma enables native distributed Raft consensus?',
        'Quel appel sqlite3 Python restaure un mot de passe utilisateur oublié ?',
    ],
}


class TextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def source_text(raw, url):
    text = raw.decode('utf-8')
    if url.endswith('.html'):
        parser = TextExtractor()
        parser.feed(text)
        return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()
    return text.replace('\r\n', '\n')


def prepare(model):
    run = REPO / 'artifacts/technical-quality' / uuid.uuid4().hex
    (run / 'sources').mkdir(parents=True)
    receipts = {}
    texts = {}
    for name, url in SOURCES.items():
        request = urllib.request.Request(url, headers={'User-Agent': 'BorgKnowledge-public-quality/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise ValueError('public source exceeds bound')
            receipts[name] = {'url': url, 'final_url': response.url, 'status': response.status,
                              'retrieved_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              'sha256': digest(raw), 'bytes': len(raw),
                              'etag': response.headers.get('ETag'), 'last_modified': response.headers.get('Last-Modified')}
        (run / 'sources' / (name + '.raw')).write_bytes(raw)
        texts[name] = source_text(raw, url)
        (run / 'sources' / (name + '.txt')).write_text(texts[name], encoding='utf-8')
        receipts[name]['text_sha256'] = digest(texts[name].encode())
        save(run / 'source-receipts.json', receipts)
    corpus = []
    for name, source, anchor, length in PASSAGES:
        doc = dict(id=name, source=source, anchor=anchor, **excerpt(texts[source], anchor, length))
        doc['sha256'] = digest(doc['text'].encode())
        corpus.append(doc)
    # Real same-domain distractors, not gardening. Exclude overlapping evidence ranges.
    for source, text in texts.items():
        kept = 0
        for start in range(0, len(text), 1000):
            end = min(start + 1000, len(text))
            if end - start < 300 or any(d['source'] == source and start < d['end'] and end > d['start'] for d in corpus):
                continue
            doc = dict(id=f'{source}-context-{kept:02}', source=source, start=start, end=end, text=text[start:end])
            doc['sha256'] = digest(doc['text'].encode())
            corpus.append(doc)
            kept += 1
            if kept == 12:
                break
    queries = []
    for split, rows in [('development', DEVELOPMENT), ('holdout', HOLDOUT)]:
        for i, (query, relevant, incompatible, category) in enumerate(rows):
            queries.append(dict(id=f'{split}-{i:02}', split=split, query=query, relevant=relevant,
                                incompatible=incompatible, category=category))
        for i, query in enumerate(NO_ANSWER[split]):
            queries.append(dict(id=f'{split}-no-answer-{i:02}', split=split, query=query,
                                relevant=[], incompatible=[], category='no_answer'))
    names = {d['id'] for d in corpus}
    assert len(names) == len(corpus)
    assert all(set(q['relevant'] + q['incompatible']) <= names for q in queries)
    save(run / 'corpus.json', corpus)
    save(run / 'judgments.json', queries)
    manifest_raw = (model / 'manifest.json').read_bytes()
    save(run / 'model-manifest.json', json.loads(manifest_raw))
    inputs = {p.relative_to(run).as_posix(): digest(p.read_bytes()) for p in run.rglob('*') if p.is_file()}
    freeze = {'frozen_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'before_inference': True, 'files': inputs,
              'model_manifest_sha256': digest(manifest_raw),
              'harness_sha256': digest(Path(__file__).read_bytes()),
              'recipe_reference_sha256': digest((REPO / 'tools/embed.py').read_bytes()),
              'ranking': 'FTS5 literal whitespace AND top20; cosine top60; equal RRF k60 rank1; id ties; top5',
              'threshold_protocol': 'optional max-cosine threshold, development balanced answerability accuracy; higher threshold wins ties; freeze before holdout inference',
              'judgment_author': 'implementing agent; NOT independent expert/human validation',
              'corpus_documents': len(corpus), 'queries': len(queries)}
    save(run / 'freeze.json', freeze)
    print(json.dumps({'snapshot': run.as_posix(), 'freeze_sha256': digest((run / 'freeze.json').read_bytes()),
                      'documents': len(corpus), 'queries': len(queries)}, indent=2))
    return run


def verify_snapshot(snapshot):
    freeze = json.loads((snapshot / 'freeze.json').read_text(encoding='utf-8'))
    for name, sha in freeze['files'].items():
        if digest((snapshot / name).read_bytes()) != sha:
            raise ValueError('frozen input changed: ' + name)
    if digest(Path(__file__).read_bytes()) != freeze['harness_sha256']:
        raise ValueError('harness changed after freeze; prepare a new snapshot')
    return freeze


def summarize(rows):
    metrics = [r['metrics'] for r in rows]
    summary = {'queries': len(rows), 'answerable_queries': sum(bool(r['relevant']) for r in rows),
               'no_answer_queries': sum(not r['relevant'] for r in rows),
               'accepted_queries': sum(bool(r['top5']) for r in rows),
               'answerable_acceptance_rate': statistics.mean(bool(r['top5']) for r in rows if r['relevant'])}
    for key in ['top1', 'mrr', 'recall_at_5', 'no_answer_false_acceptance']:
        values = [r[key] for r in metrics if r[key] is not None]
        summary[key] = statistics.mean(values) if values else None
    for key in ['incompatible_at_1', 'incompatible_at_5']:
        summary[key] = sum(r[key] for r in metrics)
    return summary


def evaluate(snapshot, model, abstain=False):
    import numpy as np
    freeze = verify_snapshot(snapshot)
    if digest((model / 'manifest.json').read_bytes()) != freeze['model_manifest_sha256']:
        raise ValueError('model differs from pre-inference freeze')
    run = snapshot / 'evaluations' / uuid.uuid4().hex
    run.mkdir(parents=True)
    corpus = json.loads((snapshot / 'corpus.json').read_text(encoding='utf-8'))
    queries = json.loads((snapshot / 'judgments.json').read_text(encoding='utf-8'))
    names = [d['id'] for d in corpus]
    db = lexical_index(corpus)
    encoder = ResidentEncoder(model)
    start = time.perf_counter()
    vectors = encoder.encode([d['text'] for d in corpus], 'passage')
    embedding_seconds = time.perf_counter() - start
    np.save(run / 'passage-vectors.npy', vectors)
    rows = []
    threshold = None
    for split in ['development', 'holdout']:
        if split == 'holdout' and abstain:
            threshold = fit_threshold([r for r in rows if r['engine'] == 'hybrid' and r['split'] == 'development'])
            save(run / 'frozen-threshold.json', {'threshold': threshold,
                 'frozen_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'development_results_sha256': digest((run / 'development-results.json').read_bytes()),
                 'rule': 'accept iff max cosine >= threshold; not a probability; no holdout inference yet'})
        split_rows = []
        for q in [q for q in queries if q['split'] == split]:
            inference_started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
            query_vector = encoder.encode([q['query']], 'query')[0]
            cosines = vectors @ query_vector
            semantic_indices = sorted(range(len(names)), key=lambda i: (-float(cosines[i]), names[i]))[:60]
            semantic = [names[i] for i in semantic_indices]
            lexical = lexical_search(db, q['query'])
            hybrid = fuse(semantic, lexical)[:5]
            max_cosine = float(cosines[semantic_indices[0]])
            rrf_scores = {name: sum(1 / (60 + candidates.index(name) + 1) for candidates in (semantic, lexical) if name in candidates) for name in hybrid}
            raw = {'query': q, 'inference_started_utc': inference_started_utc,
                   'lexical_top20': lexical, 'rrf_scores_top5': rrf_scores,
                   'semantic_top60': [{'id': names[i], 'cosine': float(cosines[i])} for i in semantic_indices],
                   'hybrid_top5': hybrid, 'query_vector': query_vector.tolist()}
            save(run / (q['id'] + '.json'), raw)
            for engine, top in [('fts5', lexical[:5]), ('hybrid', hybrid)]:
                split_rows.append(dict(q, engine=engine, top5=top, max_cosine=max_cosine, metrics=score(top, q)))
        if split == 'development':
            rows.extend(split_rows)
            save(run / 'development-results.json', split_rows)
            if abstain:
                dev_threshold = fit_threshold([r for r in split_rows if r['engine'] == 'hybrid'])
                for row in [r for r in split_rows if r['engine'] == 'hybrid']:
                    top = row['top5'] if row['max_cosine'] >= dev_threshold else []
                    rows.append(dict(row, engine='hybrid_experimental_abstention', top5=top, metrics=score(top, row)))
        else:
            rows.extend(split_rows)
            if abstain:
                for row in [r for r in split_rows if r['engine'] == 'hybrid']:
                    top = row['top5'] if row['max_cosine'] >= threshold else []
                    rows.append(dict(row, engine='hybrid_experimental_abstention', top5=top, metrics=score(top, row)))
    db.close()
    save(run / 'raw-results.json', rows)
    summaries = []
    for engine in sorted({r['engine'] for r in rows}):
        for split in ['development', 'holdout']:
            group = [r for r in rows if r['engine'] == engine and r['split'] == split]
            summaries.append(dict(engine=engine, split=split, **summarize(group)))
    verify_snapshot(snapshot)
    report = {'snapshot': snapshot.as_posix(), 'run': run.as_posix(),
              'freeze_sha256': digest((snapshot / 'freeze.json').read_bytes()),
              'corpus_documents': len(corpus), 'source_pages': len(SOURCES), 'queries': len(queries),
              'summaries': summaries, 'experimental_threshold': threshold,
              'model_manifest': encoder.manifest, 'runtime': encoder.runtime, 'sqlite_version': sqlite3.sqlite_version,
              'embedding_seconds': embedding_seconds, 'at_token_limit': encoder.truncated,
              'production_cli_changed': False, 'generated_answers_evaluated': False,
              'limitations': ['Author-made, incomplete relevance judgments; no independent human validation.',
                  'Related topics occur across splits; holdout is not topic-disjoint.',
                  'Bounded selected official excerpts, not whole documentation or user-vault certification.',
                  'FTS5/RRF standalone harness, not production binary acceptance or a storage-engine comparison.',
                  'Explicit incompatible labels mean wrong version/filter semantics for that question, not a generated recommendation.',
                  'No-answer false acceptance means any candidate survives; no generated answer measured.',
                  'Cosine threshold is an experimental development-fit heuristic, never confidence or calibrated probability.',
                  'Snippet truncation and query lexical AND are inherited limitations, not tuned on holdout.',
                  'SQLite live docs are time-bound snapshots; Python tags and Qdrant commit are pinned.']}
    save(run / 'report.json', report)
    evidence = {p.relative_to(run).as_posix(): digest(p.read_bytes()) for p in run.rglob('*') if p.is_file()}
    save(run / 'receipt.json', {'files': evidence, 'freeze_sha256': report['freeze_sha256'],
                               'snapshot_verified_before_and_after': True})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--model', type=Path, default=REPO / 'artifacts/models/minilm')
    parser.add_argument('--experimental-abstention', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.model)
    else:
        if args.snapshot is None:
            parser.error('run requires --snapshot; source/judgment freeze precedes inference')
        evaluate(args.snapshot.resolve(), args.model.resolve(), args.experimental_abstention)


if __name__ == '__main__':
    main()
