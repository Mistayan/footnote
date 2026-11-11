"""Opt-in archive-backed, Qdrant-only dense/sparse/text runtime. No downloads."""
from collections import Counter
import math
import re
import json
import uuid
from pathlib import PurePosixPath
from tools.vault_knowledge.core import Vault
from tools.agent_knowledge_runtime import digest
from tools.knowledge_runtime.metadata import validate_fields

RECIPE = 'qdrant-text-v1-source96-overlap24-okapi-1.2-.75-unique-query-rrf60'

def source_policy(path):
    """Path provenance only; never a semantic claim of authority or relevance."""
    p=PurePosixPath(path); parts={part.casefold() for part in p.parts}
    instruction = p.name.casefold() in ('agents.md','claude.md','skill.md','ai-coding-rules.md') or bool(parts & {'skills','.agents','.claude','.hermes'})
    return 'instruction' if instruction else 'knowledge'

class TextVault(Vault):
    recipe=RECIPE
    archive_only=True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            if self.write:
                with self.db:self.db.execute('CREATE TABLE IF NOT EXISTS sparse_state(state TEXT)')
            row=self.db.execute('SELECT state FROM sparse_state').fetchone()
            self.sparse=SparseRecipe(json.loads(row[0])) if row else SparseRecipe.fit([])
        except BaseException:
            self.close();raise

    def owner_payload(self):
        return dict(owner=self.owner,model=self.encoder.identity,recipe=self.recipe,role='owner')

    def _create_remote(self):
        try:self.remote.request('GET')
        except RuntimeError as e:
            if not str(e).startswith('Qdrant HTTP 404:'):raise
        else:raise ValueError('collection exists; refusing takeover')
        self.remote.request('PUT',body=dict(vectors={'dense':{'size':384,'distance':'Cosine'}},sparse_vectors={'sparse':{'index':{'on_disk':False}}}))
        self.remote.request('PUT','/points?wait=true',{'points':[dict(id=self.owner,vector={'dense':[1.]+[0.]*383},payload=self.owner_payload())]})
        for key in ('owner','role','source_policy'):
            self.remote.request('PUT','/index?wait=true',dict(field_name=key,field_schema='keyword'))

    def chunk_payload(self,row):
        metadata=json.loads(self.db.execute('select metadata from sources where path=?',(row['path'],)).fetchone()[0])
        return dict(owner=self.owner,model=self.encoder.identity,recipe=self.recipe,role='chunk',source_policy=source_policy(row['path']),metadata=metadata,**{k:row[k] for k in ('path','revision','sha','start','stop','text','heading')})

    def sync(self):
        self._writer();self.verify_owner()
        if not self.db.execute('select 1 from jobs where pending=1 limit 1').fetchone():return
        # Recompute corpus DF/avgdl and all document weights together. Outbox is only
        # acknowledged after all writes+readbacks; crash/lost ack replays the full snapshot.
        rows=self.db.execute('select * from chunks where active=1 order by id').fetchall()
        self.sparse=SparseRecipe.fit([r['text'] for r in rows])
        with self.db:
            self.db.execute('delete from sparse_state')
            self.db.execute('insert into sparse_state values(?)',(json.dumps(self.sparse.state,sort_keys=True),))
            self.db.execute("update jobs set pending=1,action=case when id in (select id from chunks where active=1) then 'upsert' else 'delete' end")
        deletes=[r[0] for r in self.db.execute("select id from jobs where action='delete' and pending=1")]
        for i in range(0,len(deletes),128):
            ids=deletes[i:i+128];self.remote.request('POST','/points/delete?wait=true',dict(points=ids))
            if self.remote.request('POST','/points',dict(ids=ids,with_payload=True)):raise RuntimeError('delete readback mismatch')
        for i in range(0,len(rows),32):
            batch=rows[i:i+32];vectors=self.encoder.encode([r['text'] for r in batch],'passage')
            points=[dict(id=r['id'],vector=dict(dense=v,sparse=self.sparse.document(r['text'])),payload=self.chunk_payload(r)) for r,v in zip(batch,vectors)]
            self.remote.request('PUT','/points?wait=true',dict(points=points))
            actual=self.remote.request('POST','/points',dict(ids=[p['id'] for p in points],with_payload=True))
            if {p['id']:p['payload'] for p in actual}!={p['id']:p['payload'] for p in points}:raise RuntimeError('payload readback mismatch')
        with self.db:self.db.execute('update jobs set pending=0')

    def rebuild_index(self):
        self._writer();self.verify_owner()
        with self.db:self.db.execute('update jobs set pending=1')
        self.sync()

    def _present(self,point,cache,constraints,scope):
        p=point.get('payload',{})
        required={'owner','model','recipe','role','path','revision','sha','start','stop','text','heading','metadata','source_policy'}
        if set(p)!=required or p['owner']!=self.owner or p['model']!=self.encoder.identity or p['recipe']!=self.recipe or p['role']!='chunk':return None
        if not isinstance(p['path'],str) or p['source_policy']!=source_policy(p['path']):return None
        if scope!='all' and p['source_policy']!=scope:return None
        if type(p['revision']) is not int or type(p['start']) is not int or type(p['stop']) is not int or not isinstance(p['text'],str) or not isinstance(p['heading'],str):return None
        if p['start']<0 or p['stop']<=p['start']:return None
        expected=str(uuid.uuid5(uuid.UUID(self.owner),f'{p["path"]}\0{p["revision"]}\0{p["start"]}\0{p["stop"]}'))
        if point['id']!=expected:return None
        # Only source identity/freshness SQL; never text acquisition or lexical ranking.
        row=self.db.execute("select revision,sha,metadata from sources where path=? and status='active'",(p['path'],)).fetchone()
        if not row or row['revision']!=p['revision'] or row['sha']!=p['sha'] or json.loads(row['metadata'])!=p['metadata']:return None
        if any(p['metadata'].get(k)!=v for k,v in constraints.items()):return None
        if p['path'] not in cache:
            try:cache[p['path']]=self.read(p['path'])
            except (OSError,ValueError):cache[p['path']]=None
        data=cache[p['path']]
        if data is None or digest(data)!=p['sha']:return None
        text=data.decode('utf-8-sig')
        if p['stop']>len(text) or text[p['start']:p['stop']]!=p['text']:return None
        return dict(id=point['id'],**{k:p[k] for k in ('path','revision','sha','start','stop','text','heading')},source_metadata=p['metadata'],source_policy=p['source_policy'],offset_unit='utf8-sig-decoded-character')

    def get(self,cid,cache=None,constraints=None,scope='all'):
        self.verify_owner()
        points=self.remote.request('POST','/points',dict(ids=[cid],with_payload=True))
        return self._present(points[0],{} if cache is None else cache,validate_fields(constraints or {}),scope) if len(points)==1 else None

    def search(self,query,limit=5,mode='hybrid',constraints=None,reranker=None,query_view=False,scope='all'):
        if not isinstance(query,str) or not query.strip() or len(query)>8192 or type(limit) is not int or not 1<=limit<=20:raise ValueError('query/limit bounds')
        if mode not in ('hybrid','bm25','dense') or scope not in ('all','knowledge','instruction'):raise ValueError('unknown mode/scope')
        if query_view or reranker:raise ValueError('query-view/reranker not part of frozen text-hybrid recipe')
        constraints=validate_fields(constraints or {});self.verify_owner()
        # Refuse mixed sparse snapshots during interrupted synchronization.
        if self.db.execute('select 1 from jobs where pending=1 limit 1').fetchone():raise ValueError('pending outbox; writer sync required')
        row=self.db.execute('select state from sparse_state').fetchone()
        if row:self.sparse=SparseRecipe(json.loads(row[0]))
        must=[dict(key='owner',match=dict(value=self.owner)),dict(key='role',match=dict(value='chunk'))]
        if scope!='all':must.append(dict(key='source_policy',match=dict(value=scope)))
        must.extend(dict(key='metadata.'+k,match=dict(value=v)) for k,v in constraints.items())
        filter_={'must':must}; prefetch=[]
        if mode!='bm25':prefetch.append(dict(query=self.encoder.encode([query],'query')[0],using='dense',limit=60,filter=filter_,params={'hnsw_ef':128}))
        sparse=self.sparse.query(query)
        if mode!='dense' and sparse['indices']:prefetch.append(dict(query=sparse,using='sparse',limit=60,filter=filter_))
        if not prefetch:return []
        body=dict(prefetch=prefetch,query={'rrf':{'k':60}},limit=60,with_payload=True,filter=filter_) if len(prefetch)>1 else dict(prefetch[0],limit=60,with_payload=True)
        points=self.remote.request('POST','/points/query',body)['points'];cache={};hits=[]
        for point in points:
            hit=self._present(point,cache,constraints,scope)
            if hit:
                hit['engine_score']=point['score'];hit['excerpt']=hit.pop('text')[:512];hits.append(hit)
            if len(hits)>=limit:break
        return hits

TOKEN = re.compile(r'->>|->|#>>|#>|::|\w+(?:[._:/-]\w+)*(?:\+\+|#)?', re.UNICODE)

def terms(text):
    return [t.casefold() for t in TOKEN.findall(text)]

class SparseRecipe:
    """Exact Okapi BM25: unique query terms, k1=1.2, b=.75; no hashing collisions."""
    def __init__(self, state):
        self.state = state
        self.vocabulary = state['vocabulary']
        self.df = state['df']

    @classmethod
    def fit(cls, texts):
        counts = [Counter(terms(text)) for text in texts]
        vocabulary = {t:i for i,t in enumerate(sorted({t for c in counts for t in c}))}
        df = [0]*len(vocabulary)
        for c in counts:
            for t in c: df[vocabulary[t]] += 1
        return cls(dict(vocabulary=vocabulary, df=df, n=len(counts), avgdl=sum(sum(c.values()) for c in counts)/max(1,len(counts))))

    def document(self, text):
        counts=Counter(terms(text)); length=sum(counts.values())
        pairs=sorted((self.vocabulary[t], f*2.2/(f+1.2*(.25+.75*length/max(self.state['avgdl'],1e-12)))) for t,f in counts.items() if t in self.vocabulary)
        return dict(indices=[i for i,v in pairs],values=[v for i,v in pairs])

    def query(self, text):
        ids=sorted({self.vocabulary[t] for t in terms(text) if t in self.vocabulary})
        n=self.state['n']
        return dict(indices=ids,values=[math.log(1+(n-self.df[i]+.5)/(self.df[i]+.5)) for i in ids])

if __name__ == '__main__':
    from tools.vault_knowledge.__main__ import main
    raise SystemExit(main(runtime_class=TextVault))
