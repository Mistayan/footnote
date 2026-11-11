"""Transparent infrastructure-only retry of sealed code after Windows path failure.
No initial query/ranking occurred: first collection PUT failed HTTP500. Preserve
all original freeze/release/failed-run receipts. Execute frozen orchestration
with ONLY output-run path and separate retry receipt filenames replaced. Ranking,
questions, corpus, refusal, models, constructor, and original code stay unchanged.
"""
import hashlib
from pathlib import Path
from tools.accuracy_validation_v2 import validate
from tools.accuracy_validation_v2.protocol import verify_seal
from tools.acquisition_repair.evaluator import ROOT,f


def patched_source():
    source=Path(validate.__file__).read_text(encoding='utf8')
    edits=[("run=SNAPSHOT/'runs'/uuid.uuid4().hex","run=ROOT/'artifacts/accuracy-validation-v2'/('run-'+uuid.uuid4().hex)"),("release-test.json","recovery-release-test.json"),("first-inference.json","recovery-first-inference.json")]
    for old,new in edits:
        assert old in source;source=source.replace(old,new)
    return source,edits


def recover():
    snapshot=validate.SNAPSHOT;verify_seal(snapshot)
    failed=Path(f.load(snapshot/'first-inference.json')['run'])
    assert not (failed/'results.jsonl').exists()
    cleanup=f.load(failed/'cleanup.json');assert cleanup['server']['process_exited'] and cleanup['server']['port_closed']
    assert 'Gridstore IO error' in (failed/'server.log').read_text(encoding='utf8')
    source,edits=patched_source()
    amendment=dict(utc=f.now(),before_any_ranked_query_output=True,reason='Qdrant Windows long storage path; first collection PUT500; zero query requests/results',original_freeze_sha256=f.sha(snapshot/'freeze.json'),failed_run=str(failed),failed_cleanup_sha256=f.sha(failed/'cleanup.json'),wrapper_sha256=f.sha(Path(__file__)),test_sha256=f.sha(ROOT/'tests/test_accuracy_validation_v2_recovery.py'),executed_source_sha256=hashlib.sha256(source.encode()).hexdigest(),exact_infrastructure_edits=edits,method_changes='NONE: inherited Identity.search, corpus, original parents, slices96, weights, pool, models, refusal all unchanged')
    target=snapshot/'infrastructure-retry-freeze.json'
    if target.exists():raise ValueError('do not overwrite retry evidence')
    f.save(target,amendment);(snapshot/'retry-executed-validate.py').write_text(source,encoding='utf8')
    namespace=dict(__name__='frozen_infrastructure_retry',__file__=validate.__file__)
    exec(compile(source,str(snapshot/'retry-executed-validate.py'),'exec'),namespace)
    report=namespace['run']()
    assert f.sha(Path(__file__))==amendment['wrapper_sha256']
    assert f.sha(snapshot/'retry-executed-validate.py')==amendment['executed_source_sha256']
    f.save(snapshot/'infrastructure-retry-result.json',dict(run=report['run'],report_sha256=f.sha(Path(report['run'])/'report.json'),cleanup=report['cleanup'],verified=report['verified']))
    return report

if __name__=='__main__':recover()
