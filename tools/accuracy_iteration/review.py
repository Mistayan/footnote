"""Render original evidence without relabeling UNKNOWN passages."""
import json

def render_review(rows):
    lines=['# Reused diagnostic per-query review','','Incomplete selected-positive labels; UNKNOWN is not irrelevant. No fresh acceptance or generated-answer claim. P@k fixed denominator k; all-answerable P1 denominator never shrinks with rejection.','']
    for r in rows:
        lines += [f"## {r['id']} / {r['variant']}",r['query'],'Selected: '+str(r['relevant'])+'; incompatible: '+str(r['incompatible']),json.dumps(r['metrics']),'Full rank: '+str(r['ranked']),'Untruncated pair tokens: '+str(r['pair_tokens']),'Resident rerank ms: '+str(r['rerank_ms'])]
        for i,e in enumerate(r['evidence'],1):
            label='SELECTED' if e['id'] in r['relevant'] else 'INCOMPATIBLE' if e['id'] in r['incompatible'] else 'UNKNOWN'
            lines += [f"### {i}. {e['id']} — {label} — raw logit {r['logits'][e['id']]}",f"{e['url']} offsets {e['start']}:{e['end']} SHA256 {e['sha256']}",e['text'],'']
    return '\n\n'.join(lines)
