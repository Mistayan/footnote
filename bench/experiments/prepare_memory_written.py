"""Reproduce the published synthetic fixture locally, not a new blinded evaluation."""
import datetime
import hashlib
import json
from pathlib import Path

from memory_written_fixture import source_rows
from memory_written_questions import questions

ROOT = Path(__file__).resolve().parents[2]
PREFIX = ROOT / 'bench/work/memory-written-v2'


def prepare():
    paths = [Path(str(PREFIX) + suffix) for suffix in
             ('.sources.json', '.sources.freeze.json', '.questions.json', '.questions.freeze.json')]
    if any(p.exists() for p in paths):
        raise FileExistsError('fixture already exists; preserve existing frozen evidence')
    PREFIX.parent.mkdir(parents=True, exist_ok=True)
    sources, source_freeze, queries, query_freeze = paths
    rows = source_rows()
    sources.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    source_files = [sources, Path(__file__).with_name('memory_written_fixture.py'),
                    Path(__file__).with_name('MEMORY-WRITTEN.md')]
    record = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        stage='reproduction_source_file_saved_before_question_file', rows=600, fact_families=300,
        projects=30, questions_exist=False, purpose='reproduction, not fresh independent data',
        hashes={str(p.relative_to(ROOT)): digest(p) for p in source_files})
    source_freeze.write_text(json.dumps(record, indent=2), encoding='utf-8')
    queries.write_text(json.dumps(questions(rows), ensure_ascii=False, indent=2), encoding='utf-8')
    query_freeze.write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        stage='reproduction_questions_saved_after_source_file', source_freeze_sha256=digest(source_freeze),
        source_freeze_utc=record['utc'], questions=1200, purpose='reproduction, not fresh independent data',
        hashes={str(p.relative_to(ROOT)): digest(p) for p in
                [queries, Path(__file__).with_name('memory_written_questions.py')]}), indent=2), encoding='utf-8')
    print('Recreated 600 memories and 1200 questions from the published templates.')


if __name__ == '__main__':
    prepare()
