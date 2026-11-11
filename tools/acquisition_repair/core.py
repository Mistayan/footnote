"""Label-blind source-wide acquisition; evidence always remains original parents."""
import hashlib


def source_slices(texts, parents, tokenizer, cap, overlap=24):
    if not 0 < overlap < cap - 4:
        raise ValueError('invalid overlap/cap')
    children = []
    for source, text in sorted(texts.items()):
        source_parents = sorted((p for p in parents if p['source'] == source), key=lambda p: p['id'])
        for p in source_parents:
            if p['text'] != text[p['start']:p['end']]:
                raise ValueError('invalid frozen parent')
        start = 0
        while start < len(text):
            # Character search then exact verification: retokenization is authoritative.
            lo, hi = start + 1, min(len(text), start + cap * 12)
            if len(tokenizer.encode(text[start:lo]).ids) > cap:
                raise ValueError('one character exceeds budget')
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if len(tokenizer.encode(text[start:mid]).ids) <= cap:
                    lo = mid
                else:
                    hi = mid - 1
            end = lo
            body = text[start:end]
            tokens = tokenizer.encode(body)
            if len(tokens.ids) > cap:
                raise ValueError('slice exceeds tokenizer cap')
            mapped = [p['id'] for p in source_parents if p['start'] <= start and end <= p['end']]
            if not mapped:
                # Uniform slicing can exceed a 900-character overlap in low-token text.
                # Shorten to a containing parent boundary, without reading judgments.
                ends = [p['end'] for p in source_parents if p['start'] <= start < p['end']]
                if not ends:
                    raise ValueError('source character not in frozen corpus')
                end = min(end, max(ends)); body = text[start:end]
                tokens = tokenizer.encode(body)
                mapped = [p['id'] for p in source_parents if p['start'] <= start and end <= p['end']]
            children.append(dict(id=f'{source}::slice{cap}-{start:08d}', source=source,
                                 start=start, end=end, text=body, parent_ids=mapped,
                                 token_count=len(tokens.ids), sha256=hashlib.sha256(body.encode()).hexdigest()))
            if end == len(text):
                break
            offsets = [(a,b) for a,b in tokens.offsets if b > a]
            next_start = start + offsets[max(0, len(offsets)-overlap)][0] if offsets else end
            start = max(start+1, min(end, next_start))
    return children


def acquire(points, records, lexical, budget, dense_limit=100):
    dense = []
    for point in sorted(points, key=lambda p: (-p['score'], p['id'])):
        if not isinstance(point['id'], int) or not 1 <= point['id'] <= len(records):
            raise ValueError('unknown child point')
        record = records[point['id'] - 1]
        for name in sorted(record.get('parent_ids', [record['id']])):
            if name not in dense:
                dense.append(name)
    dense = dense[:dense_limit]
    contributions = {}
    for branch, names in [('dense', dense), ('lexical', lexical[:20])]:
        for rank, name in enumerate(names, 1):
            contributions.setdefault(name, {})[branch] = dict(rank=rank, contribution=1/(60+rank))
    union = sorted(contributions, key=lambda n: (-sum(v['contribution'] for v in contributions[n].values()), n))
    return dict(dense=dense, lexical=lexical[:20], union=union, pool=union[:budget], contributions=contributions)
