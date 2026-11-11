"""Exact-source evidence intervention. Offsets are Unicode codepoints, end-exclusive."""
import hashlib
import re


def complete(source,start,end,max_chars=2500):
    if not 0<=start<end<=len(source) or end-start>max_chars:raise ValueError('invalid or oversized original span')
    boundaries={0,len(source)}
    for m in re.finditer(r'[.!?](?=\s|$)|\n\s*\n',source):
        boundaries.add(m.end())
        after=m.end()
        while after<len(source) and source[after].isspace():after+=1
        boundaries.add(after)
    # Protect fenced blocks and contiguous REPL examples including their outputs.
    blocks=[(m.start(),m.end()) for m in re.finditer(r'(?m)^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*(?:\n|$)',source)]
    lines=list(re.finditer(r'[^\n]*(?:\n|$)',source));i=0
    while i<len(lines):
        if lines[i].group().startswith('>>> '):
            begin=lines[i].start();j=i+1
            while j<len(lines) and re.match(r'^(?:>>> |\.\.\. |True\s*$|False\s*$|None\s*$|[\[\{\(\x27\x22]|[A-Z]\w*\(|-?\d)',lines[j].group()):j+=1
            blocks.append((begin,lines[j-1].end()));i=j
        else:i+=1
    for a,b in blocks:
        boundaries={x for x in boundaries if not a<x<b};boundaries.update((a,b))
    left=max(x for x in boundaries if x<=start)
    right=min(x for x in boundaries if x>=end)
    ok=right-left<=max_chars
    if not ok:left,right=start,end
    return dict(version=2,start=left,end=right,text=source[left:right],sha256=hashlib.sha256(source[left:right].encode()).hexdigest(),original_start=start,original_end=end,boundary_complete=ok,budget_exceeded=not ok,max_chars=max_chars)


def request_metadata(query):
    """Deliberately narrow generic explicit source-edition grammar; no query IDs."""
    en=re.search(r'\baccording to the (French|English)\b[^,?.!]*\bdocumentation\b',query,re.I)
    fr=re.search(r'\bselon la documentation (française|anglaise)\b',query,re.I)
    match=en or fr
    return {} if not match else {'source_language':'fr' if match.group(1).casefold() in ('french','française') else 'en'}


def eligible(documents,sources,request):
    language=request.get('source_language')
    if language is not None and language not in ('en','fr'):raise ValueError('unsupported explicit source language')
    return [d for d in documents if language is None or sources.get(d['source'],{}).get('language')==language]


def get_evidence(document,texts,sources,request,completed):
    if not eligible([document],sources,request):raise ValueError('source constraint violation')
    source=texts[document['source']]
    assert source[document['start']:document['end']]==document['text']
    view=complete(source,document['start'],document['end']) if completed else dict(version=1,start=document['start'],end=document['end'],text=document['text'],sha256=hashlib.sha256(document['text'].encode()).hexdigest())
    return dict(original=dict(document),presentation=view,provenance=sources[document['source']])
