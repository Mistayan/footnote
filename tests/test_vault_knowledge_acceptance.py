"""Real local Qdrant/ONNX acceptance. All mutable data is UUID scratch-owned."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import uuid

REPO = Path(__file__).resolve().parents[1]

class RuntimeAcceptance(unittest.TestCase):
    def test_persisted_recursive_ingest_restart_update_delete_recovery(self):
        from tools.vault_knowledge.core import Vault
        import sys
        sys.path.insert(0,str(REPO/'tools'))
        from tools.server_benchmark import Server
        scratch_base=Path.home()/'AppData/Local/hermes/cache/scratch'
        scratch_base.mkdir(parents=True,exist_ok=True)
        scratch = Path(tempfile.mkdtemp(prefix='vault-accept-', dir=scratch_base))
        receipt = REPO/'tools/vault_knowledge/receipts'/uuid.uuid4().hex
        receipt.mkdir(parents=True)
        server = Server(scratch)
        vault = None
        try:
            server.start()
            root = scratch/'sources'; root.mkdir()
            entries = []
            for i in range(40):
                path = root/f'folder{i%5}/note{i}.md'; path.parent.mkdir(exist_ok=True)
                body = f'# Section {i}\nTechnical source {i} about sqlite transactional persistence.\n'
                if i == 0: body += ('The vault keeps immutable originals with durable outbox checkpoints.\n'*1200)
                path.write_text(body, encoding='utf-8')
                data = path.read_bytes()
                entries.append(dict(path=path.relative_to(root).as_posix(),size=len(data),sha256=hashlib.sha256(data).hexdigest(),status='eligible'))
            (root/'unsupported.pdf').write_bytes(b'%PDF-not-extracted')
            entries.append(dict(path='unsupported.pdf',size=18,status='unsupported'))
            manifest = scratch/'manifest.jsonl'
            def save(): manifest.write_text(''.join(json.dumps(e)+'\n' for e in entries),encoding='utf-8')
            save()
            config = dict(state=scratch/'authority.sqlite', root=root, model=REPO/'artifacts/models/minilm', qdrant_url=f'http://127.0.0.1:{server.port}',collection='akr_'+uuid.uuid4().hex)
            started = time.perf_counter()
            vault = Vault(**config, write=True)
            result = vault.ingest(manifest, complete=True)
            elapsed = time.perf_counter()-started
            self.assertEqual(result['ingested'],40)
            self.assertEqual(result['skipped'],1)
            self.assertGreater(vault.stats()['chunks'],40)
            self.assertEqual(vault.stats()['pending'],0)
            hits = vault.search('immutable originals durable outbox',limit=5)
            self.assertTrue(hits)
            self.assertIn('excerpt',hits[0]); self.assertNotIn('text',hits[0])
            full = vault.get(hits[0]['id'])
            self.assertEqual(full['text'],(root/full['path']).read_bytes().decode('utf-8-sig')[full['start']:full['stop']])
            from tools.vault_migration_inventory import inventory
            inventory(root, scratch/'inventory', max_bytes=64*1024*1024)
            inventory_result=vault.ingest(scratch/'inventory/manifest.jsonl')
            self.assertEqual(inventory_result['unchanged'],40)
            self.assertEqual(vault.ingest(manifest,complete=True)['ingested'],0)
            old = entries[0].copy()
            (root/old['path']).write_text('# Changed\nNovel checkpoint recovery phrase.',encoding='utf-8')
            self.assertIsNone(vault.get(full['id']))
            data=(root/old['path']).read_bytes(); entries[0].update(size=len(data),sha256=hashlib.sha256(data).hexdigest());save()
            original_encode=vault.encoder.encode
            def fail(*a,**kw): raise RuntimeError('injected embedding failure')
            vault.encoder.encode=fail
            with self.assertRaisesRegex(RuntimeError,'injected'):vault.ingest(manifest,complete=True)
            self.assertGreater(vault.stats()['pending'],0)
            vault.close();vault=Vault(**config,write=True)
            vault.ingest(manifest,complete=True)
            self.assertEqual(vault.stats()['pending'],0)
            # Real remote write succeeds, acknowledgment is then lost.
            entries[1]['sha256']=hashlib.sha256(b'# Lostack\nAcknowledgment recovery.').hexdigest();entries[1]['size']=len(b'# Lostack\nAcknowledgment recovery.')
            (root/entries[1]['path']).write_bytes(b'# Lostack\nAcknowledgment recovery.');save()
            request=vault.remote.request
            def lost(method,path='',body=None):
                result=request(method,path,body)
                if method=='PUT' and path.startswith('/points?'):raise RuntimeError('lost acknowledgment')
                return result
            vault.remote.request=lost
            with self.assertRaisesRegex(RuntimeError,'lost acknowledgment'):vault.ingest(manifest,complete=True)
            vault.close();vault=Vault(**config,write=True)
            vault.ingest(manifest,complete=True)
            self.assertEqual(vault.stats()['pending'],0)
            # Partial omissions never delete. Complete omissions explicitly tombstone.
            removed=entries.pop(2);save()
            vault.ingest(manifest,complete=False)
            self.assertEqual(vault.stats()['sources'],40)
            vault.ingest(manifest,complete=True)
            self.assertEqual(vault.stats()['sources'],39)
            self.assertTrue((root/removed['path']).exists())
            backup=scratch/'backup.sqlite';vault.backup(backup)
            self.assertTrue(backup.is_file())
            vault.rebuild_index();self.assertTrue(vault.search('checkpoint recovery'))
            # Scope constraints are enforced before branch cutoffs, not inferred labels.
            entries[0]['metadata']={'language':'en','documented_version':'3.12','technology':'Python'}
            save();vault.ingest(manifest)
            scoped=vault.search('checkpoint',constraints={'documented_version':'3.12'})
            self.assertTrue(scoped)
            self.assertTrue(all(h['source_metadata']['documented_version']=='3.12' for h in scoped))
            self.assertEqual(vault.search('checkpoint',constraints={'documented_version':'9.99'}),[])
            self.assertEqual(vault.search('According to the English Python 3.12 documentation, checkpoint',query_view=True)[0]['path'],entries[0]['path'])
            # Real CLI path uses a fresh process and resident JSONL requests.
            import subprocess
            argv=[str(REPO/'.venv/Scripts/python.exe'),'-m','tools.vault_knowledge','serve','--state',str(config['state']),'--root',str(root),'--model',str(config['model']),'--qdrant-url',config['qdrant_url'],'--collection',config['collection']]
            protocol='\n'.join(json.dumps(r) for r in [{'op':'search','query':'checkpoint','limit':2},{'op':'stats','verify_sources':True}])+'\n'
            cli=subprocess.run(argv,input=protocol,text=True,capture_output=True,cwd=REPO,timeout=60)
            self.assertEqual(cli.returncode,0,cli.stderr)
            responses=[json.loads(line) for line in cli.stdout.splitlines()]
            self.assertTrue(responses[0]['result']);self.assertEqual(responses[1]['result']['stale_sources'],0)
            (receipt/'transport.json').write_text(json.dumps(dict(argv=argv,stdin=protocol,stdout=cli.stdout,stderr=cli.stderr,returncode=cli.returncode),indent=2))
            # Scoped get refuses wrong/unknown metadata and deleted live paths.
            self.assertIsNone(vault.get(scoped[0]['id'],constraints={'documented_version':'9.99'}))
            source_hashes={e['path']:hashlib.sha256((root/e['path']).read_bytes()).hexdigest() for e in entries if e.get('sha256')}
            # Golden backup restore: open the backed-up authority after its index is lost.
            vault.close();vault=None
            request('DELETE')
            restored=dict(config,state=backup)
            vault=Vault(**restored,write=True,recover_index=True)
            vault.rebuild_index()
            self.assertTrue(vault.search('checkpoint'))
            self.assertEqual(vault.stats()['sources'],39)
            self.assertTrue(all(hashlib.sha256((root/p).read_bytes()).hexdigest()==sha for p,sha in source_hashes.items()))
            # Optional real pinned resident reranker runs on the bounded candidate pool.
            from tools.knowledge_runtime.rerank import ResidentReranker
            ranker=ResidentReranker(REPO/'artifacts/retrieval-ablations/c43fdc89538747999b78e90236bd3c2e/reranker-model')
            reranked=vault.search('checkpoint recovery',reranker=ranker)
            self.assertTrue(reranked)
            self.assertEqual(ranker.loads,1)
            (receipt/'recovery.json').write_text(json.dumps(dict(restored_sources=vault.stats()['sources'],original_hashes_preserved=True,reranked_count=len(reranked),ranker_receipt=ranker.identity),indent=2))
            stats=vault.stats()
            vault.close();vault=None
            reader=Vault(**config,write=False)
            try:self.assertTrue(reader.search('checkpoint'));self.assertEqual(reader.stats()['sources'],39)
            finally:reader.close()
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(backup)) as db:self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')
            (receipt/'acceptance.json').write_text(json.dumps(dict(initial=result,stats=stats,seconds=elapsed,initial_bytes=sum(e['size'] for e in entries),files_per_second=40/elapsed,fixture_files=41,large_file_bytes=old['size'],model_loads_per_instance=1),indent=2))
        finally:
            if vault:vault.close()
            cleanup=server.close()
            for name in ('server.yaml','server.log','cleanup.json'):
                p=scratch/name
                if p.exists():shutil.copy2(p,receipt/name)
            shutil.rmtree(scratch)
            self.assertTrue(cleanup['process_exited']);self.assertTrue(cleanup['port_closed'])

class MigrationRunnerAcceptance(unittest.TestCase):
    def test_real_finite_runner_preserves_sources_and_stops_owned_service(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory(dir=Path.home()/'AppData/Local/hermes/cache/scratch') as d:
            base=Path(d);root=base/'source';root.mkdir()
            note=root/'note.md';note.write_text('# SQLite\nDurable database recovery originals.',encoding='utf-8')
            before=hashlib.sha256(note.read_bytes()).hexdigest()
            tasks=base/'tasks.json';tasks.write_text(json.dumps({'tasks':[{'id':'S1','origin':'reconstructed_fixture','benchmark_question':'database recovery','ready_for_scoring':False}]}))
            result=subprocess.run([sys.executable,'-m','tools.vault_knowledge.migrate','--root',str(root),'--output',str(base/'run'),'--tasks',str(tasks)],cwd=REPO,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((base/'run/report.json').read_text())
            self.assertEqual(report['stats']['sources'],1)
            self.assertEqual(report['idempotency']['ingested'],0)
            self.assertTrue(report['cleanup']['process_exited'])
            self.assertTrue(report['cleanup']['port_closed'])
            self.assertEqual(before,hashlib.sha256(note.read_bytes()).hexdigest())
            self.assertEqual(report['replay']['scoring_ready_tasks'],0)

if __name__=='__main__':unittest.main()
