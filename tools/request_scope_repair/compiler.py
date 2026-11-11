"""Label-free request scope compilation. Never changes the retrieval query."""
import re
import html
import hashlib
from urllib.parse import urlparse


def build_catalog(sources, raw):
    """Source edition is receipt metadata, never mixed body language detection.

    Family aliases come from authoritative HTML title and URL document namespace.
    No selected windows or labels enter catalog construction.
    """
    catalog={}
    for source, receipt in sources.items():
        body=raw.get(source,'')
        match=re.search(r'<title[^>]*>(.*?)</title>',body,re.I|re.S)
        title=html.unescape(match[1]).strip() if match else ''
        slug=urlparse(receipt.get('url','')).path.rsplit('/',1)[-1].removesuffix('.html')
        title_namespace=re.match(r'([a-z][a-z0-9_.]*)\s*(?:—|---|–)',title)
        family=title_namespace[1] if title_namespace else slug
        aliases=set()
        if title_namespace:aliases.add(title_namespace[1])
        if family:
            aliases.add(family)
            aliases.update(family.split('-'))
        version_match=re.search(r'\bPython\s+(\d+\.\d+(?:\.\d+)?)\b',title or receipt.get('version',''),re.I)
        catalog[source]=dict(family=family or None,aliases=sorted(aliases),title=title,title_span=[match.start(1),match.end(1)] if match else None,raw_sha256=hashlib.sha256(body.encode()).hexdigest(),language=receipt.get('language'),documented_version=version_match[1] if version_match else None,receipt=dict(receipt))
    return catalog


def compile_scope(query, catalog, formal=None):
    spans=[];constraints={};ambiguities=[]
    def record(field,value,m):
        spans.append(dict(field=field,value=value,start=m.start(),end=m.end(),text=m.group(),reason='explicit request syntax'))
    languages=[]
    output_spans=[(m.start(),m.end()) for m in re.finditer(r'\b(?:answer|reply|respond|write|translate)\s+(?:in|into)\s+(?:French|English)\b|\b(?:réponds|répondez|répondre|traduis|traduisez|écris|écrivez)\s+en\s+(?:français|anglais)\b',query,re.I)]
    patterns=[r'\b(?:English|French)\b(?=[^,;?!]{0,90}\b(?:documentation|docs|edition|source)\b)',r'\b(?:documentation|docs|edition|source)\s+(?:in\s+)?(?:English|French)\b',r'\b(?:documentation|édition|source)\s+(?:anglaise|française|en anglais|en français)\b']
    for pattern in patterns:
        for m in re.finditer(pattern,query,re.I):
            if any(a<=m.start()<b for a,b in output_spans):continue
            language='fr' if re.search(r'French|française|français',m.group(),re.I) else 'en'
            languages.append(language);record('source_language',language,m)
    if len(set(languages))==1:constraints['source_language']=languages[0]
    elif languages:ambiguities.append('conflicting explicit source languages')
    versions=[]
    for m in re.finditer(r'\bPython\s+(\d+\.\d+(?:\.\d+)?)\b',query,re.I):
        versions.append(m[1]);record('documented_version',m[1],m)
    if len(set(versions))==1:constraints['documented_version']=versions[0]
    elif versions:ambiguities.append('multiple documented versions require relational scope')
    families=set()
    alias_families={}
    for metadata in catalog.values():
        for alias in metadata['aliases']:
            alias_families.setdefault(alias.casefold(),set()).add(metadata['family'])
    for alias, targets in alias_families.items():
        # Case-fold exact catalog namespace/title tokens, never body-topic expansion.
        suffix='es' if alias.endswith('sses') else 's'
        stem=alias[:-len(suffix)] if alias.endswith(suffix) and len(alias)>3 else alias
        pattern=r'(?<![\w.])'+re.escape(stem)+(r'(?:'+suffix+r')?' if stem!=alias else '')+r'(?!\w)'
        for m in re.finditer(pattern,query,re.I):
            if len(targets)>1:ambiguities.append('ambiguous catalog alias: '+m.group())
            families.update(targets);record('source_families',sorted(targets),m)
    if families:constraints['source_families']=sorted(families)
    # Formal arguments represent user structured input, not automatic understanding.
    for key,value in (formal or {}).items():
        if key not in ('source_language','documented_version','source_families'):raise ValueError('unknown formal scope field')
        valid=(key=='source_language' and value in ('en','fr')) or (key=='documented_version' and isinstance(value,str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?',value)) or (key=='source_families' and isinstance(value,list) and bool(value) and all(isinstance(v,str) and bool(v) for v in value))
        if not valid:ambiguities.append('invalid formal '+key)
        constraints[key]=value
        spans.append(dict(field=key,value=value,start=None,end=None,text=None,reason='supplied formal user constraint overrides parser'))
        if key=='source_language':ambiguities=[a for a in ambiguities if a!='conflicting explicit source languages']
        if key=='documented_version':ambiguities=[a for a in ambiguities if a!='multiple documented versions require relational scope']
    return dict(request=query,constraints=constraints,spans=spans,ambiguities=ambiguities,fail_closed=bool(ambiguities),formal_constraints=dict(formal or {}))


def eligible(documents,catalog,request):
    if request.get('fail_closed'):return []
    constraints=request.get('constraints',{})
    result=[]
    for document in documents:
        metadata=catalog.get(document['source'],{})
        language=constraints.get('source_language')
        version=constraints.get('documented_version')
        families=constraints.get('source_families')
        if language is not None and metadata.get('language')!=language:continue
        actual=metadata.get('documented_version')
        if version is not None and (not actual or not (actual==version or actual.startswith(version+'.'))):continue
        if families is not None and metadata.get('family') not in families:continue
        result.append(document)
    return result


def get_evidence(document,texts,catalog,request):
    if not eligible([document],catalog,request):raise ValueError('source scope violation at get/presentation')
    from tools.evidence_completion.core import get_evidence as original
    sources={name:metadata.get('receipt',{}) for name,metadata in catalog.items()}
    return original(document,texts,sources,{},True)


def lexical_filtered(db,query,allowed,limit=10):
    """Exact incumbent FTS5 BM25 OR, admissibility SQL predicate BEFORE limit."""
    from tools.retrieval_ablation import technical_tokens
    terms=technical_tokens(query)
    if not terms or not allowed:return []
    db.execute('CREATE TEMP TABLE IF NOT EXISTS request_scope_ids (id TEXT PRIMARY KEY)')
    db.execute('DELETE FROM request_scope_ids')
    db.executemany('INSERT INTO request_scope_ids VALUES (?)',[(n,) for n in sorted(allowed)])
    expression=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
    return [r[0] for r in db.execute('SELECT id FROM documents WHERE documents MATCH ? AND id IN (SELECT id FROM request_scope_ids) ORDER BY bm25(documents), id LIMIT ?', (expression,limit))]

