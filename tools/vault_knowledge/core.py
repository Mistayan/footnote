"""Manifest-driven, reversible local vault authority. Sources are read-only."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import uuid
from tools.agent_knowledge_runtime import Encoder, Qdrant, digest, no_links
from tools.knowledge_runtime.lexical import tokens, RECIPE as LEXICAL_RECIPE
from tools.acquisition_repair.core import source_slices
from tools.knowledge_runtime.metadata import validate_fields

APP_ID = 0x564B5231
RECIPE = 'vault-v1-source96-overlap24-' + LEXICAL_RECIPE
DENIED = {'.git', '.hg', '.svn', '.ssh', '.aws', '.azure', '.gnupg', 'node_modules', '__pycache__', '.venv', 'credentials', 'credentials.json', 'secrets', 'secrets.json', 'id_rsa', 'id_ed25519'}

def source_path(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('invalid relative source path')
    parts = name.split('/')
    if any(p in ('', '.', '..') or p.rstrip(' .') != p or p.casefold() in DENIED or p.casefold().startswith('.env') for p in parts):
        raise ValueError('traversal/credentials/excluded path denied')
    p = PurePosixPath(name)
    if p.is_absolute():
        raise ValueError('absolute source path denied')
    target = no_links(Path(root).joinpath(*parts))
    if not target.is_relative_to(Path(root)):
        raise ValueError('source escapes root')
    return target


class Vault:
    """Single writer, persistent indexed reads; no incumbent authority mutations."""
    recipe = RECIPE
    archive_only = False

    def __init__(self, *, state, root, model, qdrant_url, collection, write=False, max_file_bytes=64*1024*1024, recover_index=False):
        if recover_index and not write:raise ValueError('index recovery requires writer')
        self.db = self.lock = None
        self.write = write
        self.root = no_links(root)
        self.path = no_links(state)
        if not self.root.is_dir() or self.path.is_relative_to(self.root):
            raise ValueError('existing explicit root and state outside root required')
        self.max_file_bytes = max_file_bytes
        if not 65537 <= max_file_bytes <= 1024*1024*1024:
            raise ValueError('max-file-bytes must be 65537..1073741824')
        exists = self.path.exists()
        if not exists and not write:
            raise ValueError('authority missing; ingest explicitly first')
        if exists:
            probe = sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
            try:
                if probe.execute('pragma application_id').fetchone()[0] != APP_ID:
                    raise ValueError('foreign authority refused')
            finally: probe.close()
        self.remote = Qdrant(qdrant_url, collection)
        try:
            if write:
                self.path.parent.mkdir(parents=True,exist_ok=True)
                self.lock = open(no_links(str(self.path)+'.lock'),'a+b')
                if os.name == 'nt':
                    import msvcrt
                    self.lock.write(b'0');self.lock.flush();self.lock.seek(0)
                    msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(self.lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.encoder = Encoder(model)
            from tokenizers import Tokenizer
            self.tokenizer = Tokenizer.from_str(self.encoder.tokenizer.to_str())
            self.tokenizer.no_truncation(); self.tokenizer.no_padding()
            if len(self.tokenizer.encode(self.encoder.m['passage_prefix']).ids)+96 > self.encoder.m['max_length']:
                raise ValueError('model passage prefix leaves insufficient token budget')
            config = dict(root=str(self.root), model=self.encoder.identity, url=qdrant_url.rstrip('/'),collection=collection,recipe=self.recipe,max_file_bytes=max_file_bytes)
            self.db = sqlite3.connect(self.path if write else self.path.as_uri()+'?mode=ro',uri=not write)
            self.db.row_factory = sqlite3.Row
            self.db.execute('pragma busy_timeout=5000')
            if not exists:
                self.owner = str(uuid.uuid4())
                self.db.executescript('''
                    CREATE TABLE meta(config TEXT, owner TEXT);
                    CREATE TABLE sources(path TEXT PRIMARY KEY,revision INTEGER,sha TEXT,size INTEGER,status TEXT,metadata TEXT);
                    CREATE TABLE revisions(path TEXT,revision INTEGER,sha TEXT,size INTEGER,status TEXT,original BLOB,PRIMARY KEY(path,revision));
                    CREATE TABLE chunks(id TEXT UNIQUE,path TEXT,revision INTEGER,sha TEXT,start INTEGER,stop INTEGER,text TEXT,heading TEXT,active INTEGER);
                    CREATE INDEX chunks_source ON chunks(path,active);
                    CREATE INDEX chunks_active ON chunks(active);
                    CREATE TABLE jobs(id TEXT PRIMARY KEY,action TEXT,pending INTEGER);
                    CREATE INDEX jobs_pending ON jobs(pending,action);
                    CREATE TABLE manifests(sha TEXT PRIMARY KEY,complete INTEGER,status TEXT,processed INTEGER DEFAULT 0);
                    CREATE TABLE manifest_entries(manifest TEXT,path TEXT,sha TEXT,size INTEGER,status TEXT,metadata TEXT,PRIMARY KEY(manifest,path));
                ''')
                if not self.archive_only:self.db.execute('CREATE VIRTUAL TABLE lexical USING fts5(body)')
                self.db.execute('insert into meta values(?,?)',(json.dumps(config,sort_keys=True),self.owner))
                self.db.execute(f'pragma application_id={APP_ID}'); self.db.execute('pragma user_version=1');self.db.commit()
            else:
                stored,self.owner=self.db.execute('select config,owner from meta').fetchone()
                if json.loads(stored)!=config or self.db.execute('pragma user_version').fetchone()[0]!=1:
                    raise ValueError('root/model/collection/recipe/bounds mismatch')
            if not exists: self._create_remote()
            elif recover_index:
                try:self.remote.request('GET')
                except RuntimeError as e:
                    if not str(e).startswith('Qdrant HTTP 404:'):raise
                    self._create_remote()
                    with self.db:
                        self.db.execute("update jobs set pending=1,action=case when id in (select id from chunks where active=1) then 'upsert' else 'delete' end")
            self.verify_owner()
        except BaseException:
            self.close();raise

    def close(self):
        if self.db is not None:self.db.close();self.db=None
        if self.lock is not None:self.lock.close();self.lock=None

    def _writer(self):
        if not self.write:raise ValueError('explicit writer operation required')

    def _create_remote(self):
        try:self.remote.request('GET')
        except RuntimeError as e:
            if not str(e).startswith('Qdrant HTTP 404:'):raise
        else:raise ValueError('collection exists; refusing takeover')
        self.remote.request('PUT',body={'vectors':{'size':384,'distance':'Cosine'}})
        self.remote.request('PUT','/points?wait=true',{'points':[{'id':self.owner,'vector':[1.0]+[0.0]*383,'payload':self.owner_payload()}]})

    def owner_payload(self):
        return dict(owner=self.owner,model=self.encoder.identity,recipe=RECIPE,role='owner')

    def verify_owner(self):
        result=self.remote.request('POST','/points',{'ids':[self.owner],'with_payload':True})
        if len(result)!=1 or result[0]['payload']!=self.owner_payload():raise ValueError('foreign/missing collection owner')

    def read(self,name):
        from tools.vault_migration_inventory import safe_bytes, identity, SECRET, SENSITIVE, EXCLUDED
        path=source_path(self.root,name)
        for parent in (path.parent, *path.parent.parents):
            if parent == self.root.parent:break
            if parent != self.root and os.path.lexists(parent / '.git'):raise ValueError('repository source denied')
            if parent != self.root and (parent.name.casefold() in EXCLUDED or SENSITIVE.search(parent.name)):
                raise ValueError('excluded source directory')
        if SENSITIVE.search(path.name):raise ValueError('sensitive source name denied')
        info=path.lstat()
        if info.st_nlink != 1:raise ValueError('hardlink source denied')
        if not stat.S_ISREG(info.st_mode) or info.st_size>self.max_file_bytes:raise ValueError('nonregular/oversize source')
        data=safe_bytes(self.root,dict(path=name,identity=identity(info),size=info.st_size),self.max_file_bytes)
        source_path(self.root,name)
        text=data.decode('utf-8-sig')
        if '\x00' in text:raise ValueError('binary source denied')
        if SECRET.search(text):raise ValueError('secret heuristic quarantine')
        return data

    def _manifest(self,path,complete):
        path=no_links(path)
        if path.is_relative_to(self.root) or path==self.path:raise ValueError('manifest must be separate from source/state')
        inventory_manifest = path.name == 'manifest.jsonl' and (path.parent/'summary.json').is_file()
        if inventory_manifest:
            summary=json.loads(no_links(path.parent/'summary.json').read_bytes())
            if not summary.get('import_ready') or Path(summary['source_root'])!=self.root:
                raise ValueError('inventory is not import-ready for this root')
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        identity=h.hexdigest()
        previous=self.db.execute('select complete from manifests where sha=?',(identity,)).fetchone()
        if previous and previous[0]!=int(complete):
            # Same inventory may intentionally be promoted from partial to complete.
            with self.db:self.db.execute('update manifests set complete=?,status=? where sha=?',(int(complete),'staged',identity))
        with self.db:
            self.db.execute('insert or ignore into manifests(sha,complete,status) values(?,?,?)',(identity,int(complete),'staged'))
            self.db.execute('delete from manifest_entries where manifest=?',(identity,))
            h=hashlib.sha256()
            with path.open('rb') as f:
                for line in f:
                    h.update(line)
                    if len(line)>1024*1024:raise ValueError('manifest row exceeds 1MiB')
                    if not line.strip():continue
                    e=json.loads(line)
                    name=e['path']
                    status=e.get('status','eligible')
                    # Opaque exclusions are receipts, never paths to open or follow.
                    if inventory_manifest and status!='eligible':continue
                    source_path(self.root,name)
                    size=e.get('size',e.get('bytes'))
                    if type(size) is not int or size<0:raise ValueError('expected nonnegative byte count required')
                    sha=e.get('sha256')
                    eligible=status in ('eligible','candidate','supported') and Path(name).suffix.casefold() in ('.md','.txt')
                    if eligible and (not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha)):raise ValueError('eligible source requires sha256')
                    # Inventory role hints are descriptive provenance, not authority or applicability.
                    metadata=json.dumps(validate_fields({} if inventory_manifest else e.get('metadata',{})),sort_keys=True)
                    self.db.execute('insert into manifest_entries values(?,?,?,?,?,?)',(identity,name,sha,size,'eligible' if eligible else 'unsupported',metadata))
            if h.hexdigest()!=identity:raise ValueError('manifest changed during staging')
        return identity

    def _deactivate(self,name):
        for row in self.db.execute('select rowid,id from chunks where path=? and active=1',(name,)).fetchall():
            if not self.archive_only:self.db.execute('delete from lexical where rowid=?',(row['rowid'],))
            self.db.execute('insert into jobs values(?,?,1) on conflict(id) do update set action=excluded.action,pending=1',(row['id'],'delete'))
        self.db.execute('update chunks set active=0 where path=? and active=1',(name,))

    def ingest(self,manifest,complete=False,progress=None):
        self._writer(); self.verify_owner()
        identity=self._manifest(manifest,complete)
        result=dict(manifest_sha256=identity,ingested=0,unchanged=0,skipped=0,deleted=0)
        # Indexed keyset paging, not an in-memory all-corpus materialization.
        last=''
        while True:
            rows=self.db.execute('select * from manifest_entries where manifest=? and path>? order by path limit 64',(identity,last)).fetchall()
            if not rows:break
            for e in rows:
                last=e['path'];name=e['path']
                if e['status']!='eligible':result['skipped']+=1;continue
                data=self.read(name)
                if len(data)!=e['size'] or digest(data)!=e['sha']:raise ValueError('source hash/byte mismatch: '+name)
                old=self.db.execute('select * from sources where path=?',(name,)).fetchone()
                if old and old['status']=='active' and old['sha']==e['sha'] and old['metadata']==e['metadata']:
                    result['unchanged']+=1;continue
                try:text=data.decode('utf-8-sig')
                except UnicodeDecodeError as error:raise ValueError('unsupported non UTF-8 source: '+name) from error
                revision=old['revision']+1 if old else 1
                children=source_slices({name:text},[dict(source=name,id=name,start=0,end=len(text),text=text)],self.tokenizer,96,24)
                headings=[(m.start(),m.group(1)) for m in re.finditer(r'^#{1,6}\s+(.+)$',text,re.M)]
                with self.db:
                    self._deactivate(name)
                    self.db.execute('insert into revisions values(?,?,?,?,?,?)',(name,revision,e['sha'],len(data),'active',data))
                    self.db.execute('insert or replace into sources values(?,?,?,?,?,?)',(name,revision,e['sha'],len(data),'active',e['metadata']))
                    heading_index=-1
                    for c in children:
                        while heading_index+1<len(headings) and headings[heading_index+1][0]<=c['start']:heading_index+=1
                        heading=headings[heading_index][1] if heading_index>=0 else ''
                        cid=str(uuid.uuid5(uuid.UUID(self.owner),f'{name}\0{revision}\0{c["start"]}\0{c["end"]}'))
                        cur=self.db.execute('insert into chunks values(?,?,?,?,?,?,?,?,1)',(cid,name,revision,e['sha'],c['start'],c['end'],c['text'],heading))
                        if not self.archive_only:self.db.execute('insert into lexical(rowid,body) values(?,?)',(cur.lastrowid,' '.join(tokens(c['text']))))
                        self.db.execute('insert into jobs values(?,?,1)',(cid,'upsert'))
                    self.db.execute('update manifests set processed=processed+1 where sha=?',(identity,))
                result['ingested']+=1
                if progress:progress(dict(result,path=name,pending=self.stats()['pending']))
                # Flush medium batches across files; the encoder stays resident.
                if self.stats()['pending']>=128:self.sync()
        if complete:
            # Only a fully validated explicit complete inventory may infer deletion.
            missing=self.db.execute("select path,revision from sources s where status='active' and not exists(select 1 from manifest_entries e where e.manifest=? and e.path=s.path)",(identity,)).fetchall()
            with self.db:
                for row in missing:
                    self._deactivate(row['path'])
                    rev=row['revision']+1
                    self.db.execute('insert into revisions values(?,?,NULL,0,?,NULL)',(row['path'],rev,'deleted'))
                    self.db.execute("update sources set revision=?,sha=NULL,size=0,status='deleted' where path=?",(rev,row['path']))
                    result['deleted']+=1
        self.sync()
        with self.db:self.db.execute("update manifests set status='completed' where sha=?",(identity,))
        return result

    def sync(self):
        self._writer();self.verify_owner()
        while True:
            rows=self.db.execute('select j.id,j.action,c.* from jobs j join chunks c on c.id=j.id where pending=1 order by action,id limit 32').fetchall()
            if not rows:break
            deletes=[r['id'] for r in rows if r['action']=='delete' or not r['active']]
            upserts=[r for r in rows if r['action']=='upsert' and r['active']]
            if deletes:self.remote.request('POST','/points/delete?wait=true',{'points':deletes})
            if upserts:
                vectors=self.encoder.encode([r['text'] for r in upserts],'passage')
                points=[dict(id=r['id'],vector=v,payload=self.chunk_payload(r)) for r,v in zip(upserts,vectors)]
                self.remote.request('PUT','/points?wait=true',{'points':points})
                actual=self.remote.request('POST','/points',{'ids':[p['id'] for p in points],'with_payload':True})
                if {p['id']:p['payload'] for p in actual}!={p['id']:p['payload'] for p in points}:raise RuntimeError('remote readback mismatch')
            if deletes:
                if self.remote.request('POST','/points',{'ids':deletes,'with_payload':True}):raise RuntimeError('remote deletion readback failed')
            with self.db:self.db.executemany('update jobs set pending=0 where id=?',[(r['id'],) for r in rows])

    def chunk_payload(self,row):
        metadata=json.loads(self.db.execute('select metadata from sources where path=?',(row['path'],)).fetchone()[0])
        return dict(owner=self.owner,path=row['path'],revision=row['revision'],sha=row['sha'],role='chunk',metadata=metadata)

    def get(self,cid,cache=None,constraints=None):
        row=self.db.execute("select c.* from chunks c join sources s on s.path=c.path and s.revision=c.revision and s.sha=c.sha where c.id=? and c.active=1 and s.status='active'",(cid,)).fetchone()
        if not row:return None
        cache={} if cache is None else cache
        if row['path'] not in cache:
            try:cache[row['path']]=digest(self.read(row['path']))
            except (OSError,ValueError):cache[row['path']]=None
        if cache[row['path']]!=row['sha']:return None
        metadata=json.loads(self.db.execute('select metadata from sources where path=?',(row['path'],)).fetchone()[0])
        if any(metadata.get(k)!=v for k,v in validate_fields(constraints or {}).items()):return None
        return dict({k:row[k] for k in ('id','path','revision','sha','start','stop','text','heading')},source_metadata=metadata,offset_unit='utf8-sig-decoded-character')

    def search(self,query,limit=5,mode='hybrid',constraints=None,reranker=None,query_view=False):
        if not isinstance(query,str) or not query.strip() or len(query)>8192 or type(limit) is not int or not 1<=limit<=20:raise ValueError('query/limit bounds')
        if mode not in ('hybrid','bm25','dense'):raise ValueError('unknown search mode')
        constraints=validate_fields(constraints or {})
        representation=query
        if query_view:
            from tools.request_scope_repair.compiler import compile_scope
            from tools.rank_input_repair.core import query_view as make_query_view
            scope=compile_scope(query,{})
            if scope['fail_closed']:return []
            for k,v in scope['constraints'].items():
                field='language' if k=='source_language' else k
                if field in constraints and constraints[field]!=v:return []
                constraints[field]=v
            representation=make_query_view(query,scope,enforced=True)['text']
        self.verify_owner(); branches={}; budget=60
        if mode!='dense':
            terms=tokens(representation)
            if terms:
                match=' OR '.join('"'+t+'"' for t in sorted(set(terms)))
                filters=''.join(' AND json_extract(s.metadata,?)=?' for _ in constraints)
                args=[match]+[x for k,v in constraints.items() for x in ('$.'+k,v)]+[budget]
                rows=self.db.execute('select c.id,bm25(lexical) as score from lexical join chunks c on c.rowid=lexical.rowid join sources s on s.path=c.path where lexical match ?'+filters+' order by score,c.id limit ?',args).fetchall()
                branches['bm25']=[r['id'] for r in rows]
        if mode!='bm25':
            vector=self.encoder.encode([representation],'query')[0]
            must=[{'key':'owner','match':{'value':self.owner}},{'key':'role','match':{'value':'chunk'}}]+[{'key':'metadata.'+k,'match':{'value':v}} for k,v in constraints.items()]
            points=self.remote.request('POST','/points/query',dict(query=vector,limit=budget,with_payload=True,filter={'must':must},params={'hnsw_ef':128}))['points']
            branches['dense']=[]
            for p in points:
                row=self.db.execute('select path,revision,sha from chunks where id=? and active=1',(p['id'],)).fetchone()
                if row and p['payload']==self.chunk_payload(row):branches['dense'].append(p['id'])
        ranks={}
        for branch,ids in branches.items():
            for rank,cid in enumerate(ids,1):ranks.setdefault(cid,{})[branch]=rank
        order=sorted(ranks,key=lambda cid:(-sum(1/(60+r) for r in ranks[cid].values()),cid))
        cache={}; candidates=[]
        for cid in order:
            hit=self.get(cid,cache,constraints)
            if hit:
                hit['branch_ranks']=ranks[cid];hit['rrf_score']=sum(1/(60+r) for r in ranks[cid].values());candidates.append(hit)
            if len(candidates)>=20:break
        if reranker and candidates:
            docs=[dict(id=h['id'],text=h['text']) for h in candidates]
            _,scores=reranker.rank(representation,docs)
            candidates.sort(key=lambda h:(-scores[h['id']],h['id']))
        for h in candidates:
            h['excerpt']=h.pop('text')[:512]
        return candidates[:limit]

    def stats(self,verify_sources=False):
        result={name:self.db.execute(sql).fetchone()[0] for name,sql in dict(sources="select count(*) from sources where status='active'",chunks='select count(*) from chunks where active=1',revisions='select count(*) from revisions',pending='select count(*) from jobs where pending=1').items()}
        result.update(owner=self.owner,model=self.encoder.identity,recipe=RECIPE)
        if verify_sources:
            fresh=stale=0
            for row in self.db.execute("select path,sha from sources where status='active'"):
                try:valid=digest(self.read(row['path']))==row['sha']
                except (OSError,ValueError):valid=False
                fresh+=int(valid);stale+=int(not valid)
            result.update(fresh_sources=fresh,stale_sources=stale)
        return result

    def backup(self,target):
        target=no_links(target)
        if target.exists() or target.is_relative_to(self.root):raise ValueError('new backup outside root required')
        dest=sqlite3.connect(target)
        try:self.db.backup(dest)
        finally:dest.close()

    def rebuild_index(self):
        self._writer()
        try:self.verify_owner()
        except RuntimeError as e:
            if not str(e).startswith('Qdrant HTTP 404:'):raise
            self._create_remote()
        with self.db:
            self.db.execute('delete from lexical')
            for row in self.db.execute('select rowid,text from chunks where active=1'):
                self.db.execute('insert into lexical(rowid,body) values(?,?)',(row['rowid'],' '.join(tokens(row['text']))))
            self.db.execute("update jobs set pending=1,action=case when id in (select id from chunks where active=1) then 'upsert' else 'delete' end")
        self.sync()
