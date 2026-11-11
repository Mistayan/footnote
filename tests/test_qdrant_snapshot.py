"""Fresh archive snapshot never modifies the completed historical authority."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

class SnapshotTests(unittest.TestCase):
    def test_refresh_reuses_unchanged_chunks_and_versions_changed_originals(self):
        from tools.qdrant_knowledge.migrate import refresh_archive
        from tools.agent_knowledge_runtime import digest
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo/'artifacts/qdrant-text') as folder:
            out=Path(folder);root=out/'root';root.mkdir()
            archive=out/'old.sqlite'
            db=sqlite3.connect(archive)
            db.executescript('CREATE TABLE sources(path TEXT PRIMARY KEY,revision,sha,size,status,metadata); CREATE TABLE revisions(path,revision,sha,size,status,original,PRIMARY KEY(path,revision)); CREATE TABLE chunks(id,path,revision,sha,start,stop,text,heading,active);')
            for name,text in [('note.md','# Original\nOld text.'),('keep.txt','Keep this original.')]:
                data=text.encode('utf-8-sig');(root/name).write_bytes(data);sha=digest(data)
                db.execute('insert into sources values(?,1,?,?,\'active\',\'{}\')',(name,sha,len(data)))
                db.execute('insert into revisions values(?,1,?,?,\'active\',?)',(name,sha,len(data),data))
                db.execute('insert into chunks values(?,?,1,?,0,?,?,\'\',1)',(name,name,sha,len(text),text))
            db.commit();db.close();before=digest(archive.read_bytes())
            newer=b'\xef\xbb\xbf# Updated\nNew original full text.\n \t'
            (root/'note.md').write_bytes(newer)
            result=refresh_archive(archive=archive,root=root,model=repo/'artifacts/models/minilm',output=out/'fresh')
            self.assertEqual(digest(archive.read_bytes()),before)
            self.assertEqual(result['changed'],['note.md'])
            self.assertEqual(result['sources'],2)
            db=sqlite3.connect(result['archive'])
            try:
                self.assertEqual(db.execute('select count(*) from revisions').fetchone()[0],3)
                self.assertEqual(db.execute("select original from revisions where path='note.md' and revision=2").fetchone()[0],newer)
                self.assertEqual(db.execute("select id from chunks where path='keep.txt' and active=1").fetchone()[0],'keep.txt')
                self.assertEqual(db.execute("select revision from sources where path='note.md'").fetchone()[0],2)
                self.assertFalse(db.execute("select name from sqlite_master where name='lexical'").fetchall())
            finally:db.close()
            with self.assertRaises(FileExistsError):refresh_archive(archive=archive,root=root,model=repo/'artifacts/models/minilm',output=out/'fresh')
            from tools.qdrant_knowledge.migrate import run
            tasks=out/'tasks.json';tasks.write_text(json.dumps(dict(tasks=[dict(id='smoke',origin='fixture',benchmark_question='original full text')])))
            report=run(archive=result['archive'],root=root,model=repo/'artifacts/models/minilm',executable=repo/'artifacts/server-provision/qdrant-1.19.2/qdrant.exe',output_parent=repo/'artifacts/qdrant-text',tasks=tasks)
            self.assertEqual(report['status'],'completed')
            self.assertTrue(report['fresh_subprocess_sqlite_guard'])
            self.assertTrue(report['cleanup']['process_exited'])
            self.assertTrue(report['cleanup']['port_closed'])

if __name__=='__main__':unittest.main()
