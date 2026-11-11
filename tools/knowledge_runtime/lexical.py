"""Disposable FTS5 BM25 index; immutable authority rows remain the only evidence."""
import hashlib
import json
import re
import sqlite3

from tools.agent_knowledge_runtime import no_links

RECIPE = 'technical-hex-casefold-v1'
TOKEN = re.compile(r'->>|->|#>>|#>|::|\w+(?:[._:/-]\w+)*(?:\+\+|#)?', re.UNICODE)
APP_ID = 0x4B4C5831


def tokens(text):
    # Hex-encode entire technical tokens so unicode61 cannot split identifiers,
    # strip accents or conflate operators. Frequencies/lengths remain unchanged.
    return ['x' + token.casefold().encode('utf-8').hex() for token in TOKEN.findall(text)]


class LexicalIndex:
    def __init__(self, authority):
        self.authority = authority
        path = no_links(str(authority.path) + '.lexical.sqlite')
        exists = path.exists()
        if exists:
            from contextlib import closing
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as probe:
                if probe.execute('PRAGMA application_id').fetchone()[0] != APP_ID:
                    raise ValueError('not an owned derived lexical index')
        elif not authority.write:
            raise ValueError('lexical index missing; explicit writer bm25_or/hybrid_rrf search required')
        self.db = sqlite3.connect(path if authority.write else path.as_uri() + '?mode=ro', uri=not authority.write)
        try:
            if not exists:
                with self.db:
                    self.db.execute('CREATE TABLE binding(owner TEXT,model TEXT,recipe TEXT,snapshot TEXT)')
                    self.db.execute('INSERT INTO binding VALUES(?,?,?,NULL)',
                                    (authority.generation, authority.encoder.identity, RECIPE))
                    self.db.execute('CREATE VIRTUAL TABLE lexical USING fts5(id UNINDEXED, body)')
                    self.db.execute(f'PRAGMA application_id={APP_ID}')
            stored = self.db.execute('SELECT owner,model,recipe FROM binding').fetchall()
            if stored != [(authority.generation, authority.encoder.identity, RECIPE)]:
                raise ValueError('lexical ownership/model/recipe mismatch')
        except Exception:
            self.db.close()
            raise

    def reconcile(self):
        rows = self.authority.db.execute('SELECT id,path,revision,sha,start,stop,text FROM chunks WHERE active=1 ORDER BY id').fetchall()
        frozen = json.dumps([list(row) for row in rows], ensure_ascii=True, separators=(',', ':')).encode()
        snapshot = hashlib.sha256(frozen).hexdigest()
        if self.db.execute('SELECT snapshot FROM binding').fetchone()[0] == snapshot:
            return
        if not self.authority.write:
            raise ValueError('lexical snapshot stale; explicit writer search/sync required')
        with self.db:
            self.db.execute('DELETE FROM lexical')
            self.db.executemany('INSERT INTO lexical(id,body) VALUES(?,?)',
                                [(row['id'], ' '.join(tokens(row['text']))) for row in rows])
            self.db.execute('UPDATE binding SET snapshot=?', (snapshot,))

    def search(self, query, limit=20, *, eligible=None):
        terms = sorted(set(tokens(query)))
        if len(terms) > 128:
            raise ValueError('lexical query exceeds 128 unique technical tokens')
        self.reconcile()
        if not terms:
            return []
        expression = ' OR '.join('"' + term + '"' for term in terms)
        predicate = ' AND id IN (SELECT value FROM json_each(?))' if eligible is not None else ''
        parameters = (expression, json.dumps(eligible), limit) if eligible is not None else (expression, limit)
        return self.db.execute('SELECT id,bm25(lexical) AS score FROM lexical WHERE lexical MATCH ? ' + predicate +
                               ' ORDER BY score ASC,id ASC LIMIT ?', parameters).fetchall()

    def close(self):
        self.db.close()
