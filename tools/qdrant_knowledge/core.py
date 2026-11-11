"""Pinned sparse Okapi recipe; collision-free corpus vocabulary, native dot product."""
from collections import Counter
import math
import re
import json
import os
import uuid
import http.client
from pathlib import Path, PurePosixPath
from contextlib import closing
from tools.agent_knowledge_runtime import Encoder, Qdrant, digest, no_links
from tools.vault_knowledge.core import Vault
from tools.knowledge_runtime.metadata import validate_fields

RECIPE='qtext-v1-okapi-k1=1.2-b=.75-uniquequery-rrf60'
MAX_PAYLOAD=8*1024*1024

def canonical(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
def save(path,value):
    temp=Path(str(path)+'.new');temp.write_bytes(canonical(value));os.replace(temp,path)
def policy(path):
    p=PurePosixPath(path)
    return 'instruction' if p.name.casefold() in ('agents.md','claude.md','skill.md','ai-coding-rules.md') or {v.casefold() for v in p.parts}&{'skills','.agents','.claude','.hermes'} else 'knowledge'

def route_scope(query):
    """Route intent, never execute retrieved instructions or infer source authority.

    Ambiguous presentation requests keep both pools; explicit callers can always
    override this heuristic with knowledge/instruction/all.
    """
    text=query.casefold()
    ui=bool(re.search(r'\b(?:ui|ux|qloop|skill|skills|interface|refonte)\b',text))
    mixed=bool(re.search(r'\b(?:bp|process|processus|baseline|next\.js|jira)\b',text))
    presentation=bool(re.search(r'\b(?:statistiques|statistics|scores|presenter|présenter)\b',text))
    if ui:return 'all' if mixed else 'instruction'
    return 'all' if presentation else 'knowledge'

class Remote(Qdrant):
    def __init__(self,url,collection,trace):
        super().__init__(url,collection);self.trace=trace
    def request(self,method,path='',body=None):
        data=canonical(body) if body is not None else None
        if data is not None and len(data)>16*1024*1024:raise ValueError('request exceeds 16MiB bound')
        connection=http.client.HTTPConnection(self.host,self.port,timeout=60)
        try:
            connection.request(method,self.base+path,data,{'Content-Type':'application/json'})
            response=connection.getresponse();raw=response.read(64*1024*1024+1)
            if len(raw)>64*1024*1024:raise ValueError('response exceeds 64MiB bound')
            if response.status>=300:raise RuntimeError('Qdrant HTTP '+str(response.status)+': '+raw[:256].decode(errors='replace'))
            value=json.loads(raw)
            if path=='/points/query':
                with self.trace.open('a',encoding='utf-8') as f:f.write(json.dumps(dict(method=method,path=self.base+path,request=body,response=value))+'\n')
            return value['result']
        finally:connection.close()

class Store:
    """Single explicit writer; metadata registry + Qdrant are sufficient for reads.

    Import is fail-closed and restartable, not an atomic cross-system transaction.
    All source validation delegates to the proven bounded read-only Vault reader.
    """
    read=Vault.read
    def __init__(self,*,state,root=None,model=None,qdrant_url=None,collection=None,create=False):
        self.state=no_links(state)
        if create:
            if self.state.exists():raise ValueError('state exists; explicit reopen required')
            self.state.parent.mkdir(parents=True,exist_ok=True)
            self.root=no_links(root);self.encoder=Encoder(model)
            if not self.root.is_dir() or self.state.is_relative_to(self.root):raise ValueError('state outside existing source root required')
            self.config=dict(root=str(self.root),model=str(no_links(model)),qdrant_url=qdrant_url,collection=collection,model_identity=self.encoder.identity,recipe=RECIPE)
            self.registry=dict(config=self.config,owner=str(uuid.uuid4()),status='empty',sources={},snapshot=None,bm25=None,completed=[])
            self.remote=Remote(qdrant_url,collection,self.state.parent/'network.jsonl')
            try:self.remote.request('GET')
            except RuntimeError as e:
                if not str(e).startswith('Qdrant HTTP 404:'):raise
            else:raise ValueError('collection exists; refusing takeover')
            save(self.state,self.registry)
            self.remote.request('PUT',body=dict(vectors={'dense':{'size':384,'distance':'Cosine'}},sparse_vectors={'sparse':{'index':{'on_disk':False}}},on_disk_payload=True))
            self.remote.request('PUT','/points?wait=true',dict(points=[self.control()]))
            for key in ('kind','owner','scope'):
                self.remote.request('PUT','/index?wait=true',dict(field_name=key,field_schema='keyword'))
        else:
            self.registry=json.loads(self.state.read_bytes());self.config=self.registry['config']
            if self.config['recipe']!=RECIPE:raise ValueError('recipe mismatch')
            for key,value in dict(root=root,model=model,qdrant_url=qdrant_url,collection=collection).items():
                if value is not None and str(value)!=self.config[key]:raise ValueError('configuration mismatch: '+key)
            self.root=no_links(self.config['root']);self.encoder=Encoder(self.config['model'])
            if self.encoder.identity!=self.config['model_identity']:raise ValueError('model identity mismatch')
            self.remote=Remote(self.config['qdrant_url'],self.config['collection'],self.state.parent/'network.jsonl')
        self.max_file_bytes=64*1024*1024
        self.verify_owner()
    @property
    def owner(self):return self.registry['owner']
    def control(self):
        return dict(id=self.owner,vector={},payload=dict(kind='control',owner=self.owner,config_sha=digest(canonical(self.config)),recipe=RECIPE))
    def verify_owner(self):
        rows=self.remote.request('POST','/points',dict(ids=[self.owner],with_payload=True))
        if len(rows)!=1 or rows[0]['payload']!=self.control()['payload']:raise ValueError('foreign/missing owner; refusing collection')
    def ready(self):
        current=json.loads(self.state.read_bytes())
        if current!=self.registry:raise ValueError('registry changed; reopen resident reader after writer completes')
        self.verify_owner()
        if self.registry['status']!='ready':raise ValueError('incomplete import; resume writer before reads')
        rows=self.remote.request('POST','/points',dict(ids=[self.snapshot_id()],with_payload=True))
        if len(rows)!=1 or rows[0]['payload']!=self.seal()['payload']:raise ValueError('snapshot registry/collection mismatch')
    def snapshot_id(self):return str(uuid.uuid5(uuid.UUID(self.owner),'snapshot-control'))
    def seal(self):
        return dict(id=self.snapshot_id(),vector={},payload=dict(kind='control',owner=self.owner,snapshot=self.registry['snapshot'],registry_sha=digest(canonical({k:v for k,v in self.registry.items() if k not in ('status','completed')}))))
    def source_id(self,path,revision):return str(uuid.uuid5(uuid.UUID(self.owner),f'source\0{path}\0{revision}'))
    def chunk_id(self,row):return str(uuid.uuid5(uuid.UUID(self.owner),f'chunk\0{row["path"]}\0{row["revision"]}\0{row["start"]}\0{row["stop"]}'))
    def archive_rows(self,archive):
        import sqlite3
        path=no_links(archive);before=digest(path.read_bytes())
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            db.row_factory=sqlite3.Row
            sources=[dict(r) for r in db.execute("SELECT s.*,r.original FROM sources s JOIN revisions r ON r.path=s.path AND r.revision=s.revision WHERE s.status='active' ORDER BY s.path")]
            chunks=[dict(r) for r in db.execute('SELECT * FROM chunks WHERE active=1 ORDER BY path,start,id')]
        if digest(path.read_bytes())!=before:raise ValueError('archive changed during read')
        names={r['path']:r for r in sources}
        for s in sources:
            data=s['original']
            if digest(data)!=s['sha'] or len(data)!=s['size'] or self.read(s['path'])!=data:raise ValueError('archive/current source hash mismatch: '+s['path'])
            s['text']=data.decode('utf-8-sig');s['metadata']=validate_fields(json.loads(s['metadata']))
        for c in chunks:
            s=names.get(c['path'])
            if s is None or c['revision']!=s['revision'] or c['sha']!=s['sha'] or not 0<=c['start']<c['stop']<=len(s['text']) or c['text']!=s['text'][c['start']:c['stop']]:raise ValueError('archive chunk offset/hash mismatch')
        return sources,chunks,before
    def payload(self,row,source,archive_sha,kind):
        common=dict(kind=kind,owner=self.owner,model=self.encoder.identity,recipe=RECIPE,path=source['path'],revision=source['revision'],sha=source['sha'],bytes=source['size'],metadata=source['metadata'],scope=policy(source['path']),encoding='utf-8-sig',offset_unit='decoded-unicode-character',archive_sha=archive_sha,archived_revision=source['revision'],source_id=self.source_id(source['path'],source['revision']))
        if kind=='source':common.update(text=source['text'],text_sha=digest(source['text'].encode('utf-8')),bom=source['original'].startswith(b'\xef\xbb\xbf'))
        else:common.update(text=row['text'],start=row['start'],stop=row['stop'],heading=row['heading'],text_sha=digest(row['text'].encode('utf-8')))
        if len(canonical(common))>MAX_PAYLOAD:raise ValueError('payload exceeds 8MiB bound')
        return common
    def valid_vector(self,point,bm25):
        p=point['payload'];v=point.get('vector',{})
        if p['kind']=='source':return not v
        dense=v.get('dense',[]);sparse=v.get('sparse',{});expected=bm25.document(p['text'])
        return len(dense)==384 and all(math.isfinite(x) for x in dense) and abs(sum(x*x for x in dense)-1)<.001 and sparse.get('indices')==expected['indices'] and len(sparse.get('values',[]))==len(expected['values']) and all(math.isclose(a,b,rel_tol=2e-6,abs_tol=1e-7) for a,b in zip(sparse['values'],expected['values']))
    def import_archive(self,archive):
        self.verify_owner()
        # Exclusive OS lock is released by process death; no stale lock takeover.
        lock=open(str(self.state)+'.lock','a+b')
        try:
            if os.name=='nt':
                import msvcrt
                lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            return self._import_archive(archive)
        finally:lock.close()
    def _import_archive(self,archive):
        sources,chunks,archive_sha=self.archive_rows(archive)
        bm25=BM25.fit([r['text'] for r in chunks]);names={s['path']:s for s in sources}
        snapshot=digest(canonical(dict(archive_sha=archive_sha,sources=[(s['path'],s['revision'],s['sha']) for s in sources],chunks=[(c['id'],c['sha'],c['start'],c['stop'],digest(c['text'].encode())) for c in chunks],bm25=bm25.state)))
        if self.registry['snapshot']!=snapshot:self.registry['completed']=[]
        self.registry.update(status='importing',snapshot=snapshot,bm25=bm25.state,archive=dict(path=str(no_links(archive)),sha=archive_sha),sources={s['path']:dict(revision=s['revision'],sha=s['sha'],bytes=s['size'],metadata=s['metadata'],source_id=self.source_id(s['path'],s['revision'])) for s in sources})
        save(self.state,self.registry)
        expected={self.owner,self.snapshot_id()}
        points=[]
        for s in sources:
            point=dict(id=self.source_id(s['path'],s['revision']),vector={},payload=self.payload(None,s,archive_sha,'source'));points.append(point);expected.add(point['id'])
        # Batches stay below request bound even for complete long source strings.
        batches=[];batch=[];size=0
        for p in points:
            n=len(canonical(p))
            if batch and (len(batch)>=16 or size+n>12*1024*1024):batches.append(batch);batch=[];size=0
            batch.append(p);size+=n
        if batch:batches.append(batch)
        for i in range(0,len(chunks),32):
            batch=chunks[i:i+32];ids=[self.chunk_id(c) for c in batch];expected.update(ids)
            # Lazy encoding allows restart to avoid already acknowledged batches.
            batches.append((batch,ids))
        done=set(self.registry['completed'])
        for index,batch in enumerate(batches):
            ids=[p['id'] for p in batch] if isinstance(batch,list) else batch[1]
            if index in done:
                actual=self.remote.request('POST','/points',dict(ids=ids,with_payload=True,with_vector=True))
                if len(actual)==len(ids):
                    expected_payloads={self.source_id(s['path'],s['revision']):self.payload(None,s,archive_sha,'source') for s in sources if self.source_id(s['path'],s['revision']) in ids} if isinstance(batch,list) else {self.chunk_id(c):self.payload(c,names[c['path']],archive_sha,'chunk') for c in batch[0]}
                    if {p['id']:p['payload'] for p in actual}==expected_payloads and all(self.valid_vector(p,bm25) for p in actual):continue
            if not isinstance(batch,list):
                rows,ids=batch;vectors=self.encoder.encode([c['text'] for c in rows],'passage')
                batch=[dict(id=cid,vector=dict(dense=v,sparse=bm25.document(c['text'])),payload=self.payload(c,names[c['path']],archive_sha,'chunk')) for cid,c,v in zip(ids,rows,vectors)]
            self.remote.request('PUT','/points?wait=true',dict(points=batch))
            actual=self.remote.request('POST','/points',dict(ids=ids,with_payload=True,with_vector=True))
            if {p['id']:p['payload'] for p in actual}!={p['id']:p['payload'] for p in batch}:raise ValueError('payload write/readback mismatch')
            done.add(index);self.registry['completed']=sorted(done);save(self.state,self.registry)
        # Tombstones/superseded chunks are removed only after current snapshot writes.
        obsolete=[];offset=None
        while True:
            body=dict(limit=32,with_payload=False,with_vector=False)
            if offset is not None:body['offset']=offset
            page=self.remote.request('POST','/points/scroll',body)
            obsolete.extend(p['id'] for p in page['points'] if p['id'] not in expected)
            offset=page['next_page_offset']
            if offset is None:break
        for i in range(0,len(obsolete),128):self.remote.request('POST','/points/delete?wait=true',dict(points=obsolete[i:i+128]))
        self.remote.request('PUT','/points?wait=true',dict(points=[self.seal()]))
        if self.remote.request('POST','/points',dict(ids=[self.snapshot_id()],with_payload=True))[0]['payload']!=self.seal()['payload']:raise ValueError('seal readback mismatch')
        # Revalidate every source after encoding, before publishing read availability.
        for s in sources:
            if digest(self.read(s['path']))!=s['sha']:raise ValueError('source changed during import')
        if digest(no_links(archive).read_bytes())!=archive_sha:raise ValueError('archive changed during import')
        self.registry['status']='ready';save(self.state,self.registry)
        counts=self.stats()
        if counts['source']!=len(sources) or counts['chunk']!=len(chunks) or counts['total']!=len(expected):raise ValueError('exact collection count mismatch')
        return counts
    def _present(self,point,cache):
        p=point.get('payload',{});s=self.registry['sources'].get(p.get('path'))
        if not s or p.get('kind') not in ('source','chunk') or p.get('owner')!=self.owner or p.get('recipe')!=RECIPE or p.get('model')!=self.encoder.identity:return None
        if any(p.get(k)!=s[k] for k in ('revision','sha','metadata','source_id','bytes')) or p.get('scope')!=policy(p['path']) or p.get('archive_sha')!=self.registry['archive']['sha']:return None
        if p['path'] not in cache:
            try:cache[p['path']]=self.read(p['path'])
            except (ValueError,OSError,UnicodeError):cache[p['path']]=None
        data=cache[p['path']]
        if data is None or digest(data)!=p['sha']:return None
        text=data.decode('utf-8-sig')
        if p['kind']=='source':
            if point['id']!=s['source_id'] or p.get('text')!=text:return None
        else:
            if type(p.get('start')) is not int or type(p.get('stop')) is not int or not 0<=p['start']<p['stop']<=len(text) or p.get('text')!=text[p['start']:p['stop']] or point['id']!=self.chunk_id(p):return None
        if p.get('text_sha')!=digest(p['text'].encode('utf-8')):return None
        return dict(id=point['id'],**p)
    def get(self,cid,*,start=0,max_chars=None):
        if type(start) is not int or start<0 or max_chars is not None and (type(max_chars) is not int or not 1<=max_chars<=65536):raise ValueError('get window bounds')
        uuid.UUID(cid);self.ready()
        rows=self.remote.request('POST','/points',dict(ids=[cid],with_payload=True))
        point=self._present(rows[0],{}) if len(rows)==1 else None
        if point is not None and (max_chars is not None or start):
            text=point['text'];stop=min(len(text),start+(max_chars or 65536))
            if start>len(text):raise ValueError('get window outside text')
            point['text']=text[start:stop]
            point['view']=dict(start=start,stop=stop,total_characters=len(text),truncated=start!=0 or stop!=len(text),text_sha=digest(point['text'].encode('utf-8')))
        return point
    def search(self,query,limit=5,mode='hybrid',scope='auto',constraints=None,dedup=True):
        if not isinstance(query,str) or not query.strip() or len(query)>8192 or type(limit) is not int or not 1<=limit<=20:raise ValueError('query/limit bounds')
        if scope=='auto':scope=route_scope(query)
        if mode not in ('bm25','dense','hybrid') or scope not in ('knowledge','instruction','all'):raise ValueError('unknown mode/scope')
        constraints=validate_fields(constraints or {});self.ready()
        must=[dict(key='kind',match=dict(value='chunk')),dict(key='owner',match=dict(value=self.owner))]
        if scope!='all':must.append(dict(key='scope',match=dict(value=scope)))
        must.extend(dict(key='metadata.'+k,match=dict(value=v)) for k,v in constraints.items())
        filter_=dict(must=must);branches=[]
        if mode!='bm25':branches.append(dict(query=self.encoder.encode([query],'query')[0],using='dense',limit=60,filter=filter_))
        sparse=BM25(self.registry['bm25']).query(query)
        if mode!='dense' and sparse['indices']:branches.append(dict(query=sparse,using='sparse',limit=60,filter=filter_))
        if not branches:return []
        body=dict(prefetch=branches,query={'rrf':{'k':60}},limit=60,with_payload=True,filter=filter_) if len(branches)>1 else dict(branches[0],with_payload=True)
        rows=self.remote.request('POST','/points/query',body)['points'];cache={};hits=[];seen=set()
        # Native fusion remains authoritative. Resolve only equal-score order
        # within the bounded returned pool before source deduplication.
        for point in sorted(rows,key=lambda p:(-p['score'],p['id'])):
            p=self._present(point,cache)
            if not p or any(p['metadata'].get(k)!=v for k,v in constraints.items()) or scope!='all' and p['scope']!=scope:continue
            if dedup and p['path'] in seen:continue
            seen.add(p['path']);p['score']=point['score'];hits.append(p)
            if len(hits)>=limit:break
        return hits
    def stats(self):
        self.ready();counts={}
        for kind in ('source','chunk','control'):
            counts[kind]=self.remote.request('POST','/points/count',dict(exact=True,filter={'must':[{'key':'kind','match':{'value':kind}}]}))['count']
        counts['total']=self.remote.request('POST','/points/count',dict(exact=True))['count']
        return counts
    def verify_archive(self,archive):
        sources,chunks,sha=self.archive_rows(archive);self.ready()
        if sha!=self.registry['archive']['sha']:raise ValueError('archive binding mismatch')
        expected={self.source_id(s['path'],s['revision']):self.payload(None,s,sha,'source') for s in sources};names={s['path']:s for s in sources}
        expected.update({self.chunk_id(c):self.payload(c,names[c['path']],sha,'chunk') for c in chunks})
        ids=list(expected)
        for i in range(0,len(ids),16):
            rows=self.remote.request('POST','/points',dict(ids=ids[i:i+16],with_payload=True,with_vector=True))
            if not all(self.valid_vector(p,BM25(self.registry['bm25'])) for p in rows):raise ValueError('vector verification mismatch')
            if {p['id']:p['payload'] for p in rows}!={cid:expected[cid] for cid in ids[i:i+16]}:raise ValueError('archive full payload verification mismatch')
        covered=0;gaps=0
        for s in sources:
            spans=sorted((c['start'],c['stop']) for c in chunks if c['path']==s['path']);end=0
            for a,b in spans:
                if a>end:gaps+=a-end
                covered+=max(0,b-max(a,end));end=max(end,b)
            gaps+=max(0,len(s['text'])-end)
        return dict(sources_verified=len(sources),chunks_verified=len(chunks),source_decoded_characters=sum(len(s['text']) for s in sources),chunk_span_union_characters=covered,characters_outside_old_chunks=gaps,full_source_payloads_preserve_all_characters=True,original_bytes=sum(s['size'] for s in sources),archive_sha=sha)

TOKEN=re.compile(r'->>|->|#>>|#>|::|\w+(?:[._:/-]\w+)*(?:\+\+|#)?',re.UNICODE)
def terms(text):return [t.casefold() for t in TOKEN.findall(text)]

class BM25:
    def __init__(self,state):self.state=state
    @classmethod
    def fit(cls,texts):
        counts=[Counter(terms(t)) for t in texts]
        vocab={t:i for i,t in enumerate(sorted({t for c in counts for t in c}))}
        df=[0]*len(vocab)
        for c in counts:
            for t in c:df[vocab[t]]+=1
        return cls(dict(vocabulary=vocab,df=df,n=len(counts),avgdl=sum(sum(c.values()) for c in counts)/max(1,len(counts)),k1=1.2,b=.75,query_tf='unique',idf='log1p((N-df+.5)/(df+.5))',tokenizer='technical-casefold-v1'))
    def document(self,text):
        c=Counter(terms(text));dl=sum(c.values());s=self.state;v=s['vocabulary']
        pairs=sorted((v[t],f*2.2/(f+1.2*(.25+.75*dl/max(s['avgdl'],1e-12)))) for t,f in c.items() if t in v)
        return dict(indices=[i for i,w in pairs],values=[w for i,w in pairs])
    def query(self,text):
        s=self.state;ids=sorted({s['vocabulary'][t] for t in terms(text) if t in s['vocabulary']})
        return dict(indices=ids,values=[math.log1p((s['n']-s['df'][i]+.5)/(s['df'][i]+.5)) for i in ids])
