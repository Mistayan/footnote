"""Opt-in declared source applicability; never inferred or vector payload authority."""
import json
import os
import re
from pathlib import Path
from tools.agent_knowledge_runtime import digest, no_links

FIELDS = {'technology', 'documented_version', 'language', 'status'}


def validate_fields(value):
    if not isinstance(value, dict) or set(value) - FIELDS:
        raise ValueError('metadata constraints permit only technology/documented_version/language/status')
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_+.#-]{0,63}', v) for v in value.values()):
        raise ValueError('metadata values must be explicit bounded labels, not paths/null')
    return dict(value)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate metadata field')
        result[key] = value
    return result


class MetadataIndex:
    def __init__(self, authority, manifest):
        self.authority = authority
        self.manifest = no_links(manifest)
        self.path = no_links(str(authority.path) + '.metadata.json')
        if (self.manifest == self.path or self.manifest == Path(authority.path).resolve()
                or hasattr(authority, 'root') and self.manifest.is_relative_to(authority.root)):
            raise ValueError('manifest must be separate from runtime state and source root')
        self.snapshot()  # validate before observing source contents

    def snapshot(self):
        raw = no_links(self.manifest).read_bytes()
        if len(raw) > 16384:
            raise ValueError('metadata manifest exceeds 16 KiB')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=strict_object)
        if not isinstance(value, dict) or set(value) != {'schema_version', 'sources'} or type(value['schema_version']) is not int or value['schema_version'] != 1:
            raise ValueError('metadata manifest schema_version 1 required')
        sources = value['sources']
        if not isinstance(sources, dict) or set(sources) - set(self.authority.allowed):
            raise ValueError('metadata sources must be startup allow-files')
        sources = {name: validate_fields(fields) for name, fields in sources.items()}
        rows = [dict(row) for row in self.authority.db.execute('SELECT id,path,revision,sha FROM chunks WHERE active=1 ORDER BY id')]
        return {'schema_version': 1, 'owner': self.authority.generation, 'model': self.authority.encoder.identity,
                'manifest_sha256': digest(raw), 'sources': sources, 'chunks': rows}

    def reconcile(self):
        if not self.authority.write:
            raise ValueError('metadata sync requires writer')
        snapshot = self.snapshot()
        if self.path.exists():
            stored = json.loads(no_links(self.path).read_text(encoding='utf-8'))
            if any(stored.get(key) != snapshot[key] for key in ('schema_version', 'owner', 'model')):
                raise ValueError('metadata sidecar ownership mismatch')
        temporary = no_links(str(self.path) + '.tmp')
        # Exclusive creation refuses abandoned/foreign temp state; no silent takeover.
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(snapshot, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, no_links(self.path))

    def current(self):
        snapshot = self.snapshot()
        if not self.path.exists() or json.loads(no_links(self.path).read_text(encoding='utf-8')) != snapshot:
            raise ValueError('metadata snapshot missing/stale; explicit writer sync required')
        return snapshot

    def eligible(self, constraints):
        constraints = validate_fields(constraints)
        state = self.current()
        return [row['id'] for row in state['chunks'] if all(
            state['sources'].get(row['path'], {}).get(key) == value for key, value in constraints.items())]

    def present(self, hit, constraints):
        state = self.current()
        row = next((row for row in state['chunks'] if row['id'] == hit['id']), None)
        if row is None:
            raise ValueError('metadata evidence obsolete')
        fields = state['sources'].get(row['path'], {})
        if any(fields.get(key) != value for key, value in validate_fields(constraints).items()):
            raise ValueError('metadata constraints mismatch; unknown is not compatible')
        return dict(hit, source_metadata=fields, metadata_basis='explicit_source_manifest')
