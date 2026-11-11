"""Explicit one-off import of the two authorized scoped BorgInvestor findings.
Copies evidence bytes unchanged; leaves all records proposals, not production acceptance.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import zipfile

REPO=Path(__file__).resolve().parents[1]
SOURCE=Path('D:/Projets/BorgInvestor/reports/evidence/archperf-20261016')
DEST=REPO/'evidence/archperf-20261016'
DB=REPO/'artifacts/demo/knowledge.db'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    DEST.mkdir(parents=True,exist_ok=True);DB.parent.mkdir(parents=True,exist_ok=True)
    names=['optimization-candidates.json','acceptance.json','summary.json','raw.zip']
    before={n:digest(SOURCE/n) for n in names}
    for n in names:
        if (DEST/n).exists() and digest(DEST/n)!=before[n]:raise RuntimeError('refuse evidence overwrite')
        if not (DEST/n).exists():shutil.copyfile(SOURCE/n,DEST/n)
        assert digest(DEST/n)==before[n]
    with zipfile.ZipFile(DEST/'raw.zip') as z:assert z.testzip() is None
    source=json.loads((DEST/'optimization-candidates.json').read_text(encoding='utf-8'))
    selected=[c for c in source['candidates'] if c['promotion_status']=='READY_CONFIRMED_SCOPED']
    assert len(selected)==2
    imports=[]
    for candidate in selected:
        versions={k:v for k,v in candidate['measured_versions'].items() if isinstance(v,str)}
        versions.update(candidate['measured_versions']['packages'])
        record={
            'technology':candidate['technology'],'project':'BorgInvestor','tested_versions':versions,
            'environment':'Windows; isolated synthetic fixtures; dirty working tree '+candidate['source_revision_context'],
            'symptom':candidate['root_cause'],'root_cause':candidate['root_cause'],'root_cause_status':'proven',
            'remediation':candidate['remediation_actual'],'applicability':candidate['applicability'],
            'exclusions':'Not production health or global performance. Campaign preservation NOT_CERTIFIED; writer UNKNOWN.',
            'protocol':'Retain exact original measurements, regression descriptions, raw evidence members and caveats in details; synthetic scale only.',
            'tradeoffs':'; '.join(candidate['caveats']),
            'rollback':'Restore baseline source expression/controller cancellation; re-run scoped parity and ownership regressions before deployment.',
            'last_verified':'2026-10-16','evidence':[{'path':str(DEST/n),'sha256':before[n]} for n in names],
            'details':candidate,'campaign_preservation_caveat':source['preservation_caveat'],
            'origin':{'path':str(SOURCE/'optimization-candidates.json'),'sha256':before['optimization-candidates.json']}
        }
        file=DEST/(candidate['id']+'.record.json')
        file.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        result=subprocess.run([str(REPO/'target/release/borg-knowledge.exe'),'--db',str(DB),'propose','--file',str(file),'--allow',str(DEST)],capture_output=True,text=True,check=True)
        value=json.loads(result.stdout)
        imports.append({k:value[k] for k in ['id','status','revision','technology','payload_sha256','evidence_freshness']})
    assert before=={n:digest(SOURCE/n) for n in names}
    report={'source_bytes_preserved':True,'copies_verified':before,'records':imports,'database':str(DB),'production_health':'UNKNOWN','campaign_preservation':'NOT_CERTIFIED'}
    (REPO/'artifacts/import-receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
