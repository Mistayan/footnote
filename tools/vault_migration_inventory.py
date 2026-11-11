"""Read-only local corpus inventory. No network, extraction, ingestion or source writes."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import stat
import re
import posixpath
from urllib.parse import unquote
import uuid
from datetime import datetime, timezone

EXCLUDED = {'.git', '.qdrant_storage', '.obsidian', 'node_modules', 'venv', '.venv', '__pycache__', '.cache', 'cache', 'target', 'dist', 'build', 'vendor', '.next', '.pytest_cache'}
ARCHIVES = {'.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz', '.whl'}
SENSITIVE = re.compile(r'(^\.env($|\.)|(?:^|[._ -])(?:passwords?|credentials?|secrets?|keys?|cards?|credit[-_ ]?cards?|card[-_ ]?numbers?|private[-_ ]?keys?)(?:$|[._ -])|^id_(rsa|ed25519|dsa))', re.I)
SECRET = re.compile(r'''(?im)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|^\s*["']?(?:password|passwd|pwd|api[_-]?key|access[_-]?token|client[_-]?secret|authorization)["']?\s*[:=]\s*["']?[^\s"'<>]{4,}|\bAKIA[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9_-]{24,}|\b[a-z]+://[^\s/:]+:[^\s/@]+@|(?:card\s*number|carte\s*bancaire)\s*[:=]\s*(?:\d[ -]?){13,19})''')


def is_link(s):
    return stat.S_ISLNK(s.st_mode) or bool(getattr(s, 'st_file_attributes', 0) & 0x400)


def identity(s):
    return [s.st_size, s.st_mtime_ns, s.st_dev, s.st_ino, s.st_nlink]


SUPPORTED = {'.md', '.txt'}


def scan(root):
    rows = []
    def visit(folder):
        try:
            entries = sorted(folder.iterdir())
        except OSError as e:
            rows.append({'path': folder.relative_to(root).as_posix(), 'size': 0, 'kind': 'directory', 'status': 'scan_error', 'error_type': type(e).__name__})
            return
        for p in entries:
            row = {'path': p.relative_to(root).as_posix(), 'extension': p.suffix.lower()}
            try:
                s = p.lstat()
                row.update(size=s.st_size, mtime_ns=s.st_mtime_ns, identity=identity(s), kind='directory' if stat.S_ISDIR(s.st_mode) else 'file')
                if is_link(s):
                    row.update(status='skip_reparse', kind='reparse')
                elif stat.S_ISDIR(s.st_mode):
                    if p.name.lower() in EXCLUDED:
                        row['status'] = 'skip_dependency_or_infrastructure'
                    elif SENSITIVE.search(p.name):
                        row['status'] = 'skip_sensitive_name'
                    elif os.path.lexists(p / '.git'):
                        row['status'] = 'skip_project_repository'
                    else:
                        row['status'] = 'traversed_directory'
                        visit(p)
                elif not stat.S_ISREG(s.st_mode):
                    row['status'] = 'skip_special'
                elif s.st_nlink > 1:
                    row['status'] = 'skip_hardlink'
                elif SENSITIVE.search(p.name) or p.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.kdbx', '.keystore'}:
                    row['status'] = 'skip_sensitive_name'
                elif p.suffix.lower() in ARCHIVES:
                    row['status'] = 'skip_archive'
                else:
                    row['status'] = 'candidate' if p.suffix.lower() in SUPPORTED else 'unsupported'
            except OSError as e:
                row.update(size=0, status='stat_error', error_type=type(e).__name__)
            rows.append(row)
    visit(root)
    return sorted(rows, key=lambda r: r['path'])


def safe_bytes(root, row, limit):
    p = root
    for part in Path(row['path']).parts:
        p = p / part
        if is_link(p.lstat()):
            raise ValueError('reparse changed')
    s = p.lstat()
    if identity(s) != row['identity'] or s.st_nlink != 1 or not stat.S_ISREG(s.st_mode):
        raise ValueError('identity changed')
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as f:
        if identity(os.fstat(f.fileno())) != row['identity']:
            raise ValueError('opened identity changed')
        data = f.read(limit + 1)
        if identity(os.fstat(f.fileno())) != row['identity'] or len(data) != row['size']:
            raise ValueError('read changed')
    return data


def metadata(text):
    """Shallow frontmatter signals only, never epistemic/authorship inference."""
    normalized = text.replace('\r\n', '\n')
    match = re.match(r'\A---\n(.*?)\n---(?:\n|$)', normalized, re.S)
    fields = {}
    if match:
        fields = dict(re.findall(r'^([A-Za-z_][A-Za-z0-9_-]{0,63}):\s*([^\n]*)', match[1], re.M))
    kind = fields.get('type', '').strip().strip('\"\'').casefold()
    role = 'unspecified'
    if kind in {'reference', 'source', 'original-reference', 'original_reference'}:
        role = 'original_reference'
    elif kind in {'author-note', 'author_note', 'authornote', 'author-notes'}:
        role = 'author_note'
    return {'frontmatter_present': bool(match), 'frontmatter_keys': sorted(fields),
            'role_hint': role, 'role_basis': 'explicit_type_only',
            'reference_field_present': bool(set(fields) & {'source', 'url', 'reference', 'references', 'doi'}),
            'parser': 'shallow_top_level_keys_not_full_yaml'}


def local_links(text, source, paths):
    """Local targets only; no aliases, quotes, URL values, or note body retained."""
    targets = [('wiki', t.split('|', 1)[0]) for t in re.findall(r'\[\[([^\]\n]+)\]\]', text)]
    targets += [('markdown', t) for t in re.findall(r'(?<!!)\[[^\]\n]*\]\(([^\s)]+)(?:\s+[^)]*)?\)', text)]
    links = []
    external = 0
    for kind, raw in targets:
        target = unquote(raw.strip('<>')).split('#', 1)[0].split('?', 1)[0].replace('\\', '/')
        if not target:
            continue
        if ':' in target or target.startswith('//'):
            external += 1
            continue
        if len(target) > 1024 or any(ord(c) < 32 for c in target):
            continue
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
        rooted = posixpath.normpath(target.lstrip('/'))
        options = {relative, rooted}
        if kind == 'wiki':
            options |= {p + '.md' for p in list(options) if not p.lower().endswith('.md')}
        candidates = sorted(p for p in paths if p in options)
        if not candidates and kind == 'wiki' and '/' not in target:
            candidates = sorted(p for p in paths if posixpath.basename(p) in {target, target + '.md'})
        links.append({'source': source, 'target': target, 'kind': kind, 'candidates': candidates,
                      'status': 'resolved' if len(candidates) == 1 else 'ambiguous' if candidates else 'unresolved'})
    return links, external


def inventory(root, output, max_bytes=8 * 1024 * 1024):
    root, output = Path(root).absolute(), Path(output).absolute()
    if is_link(root.lstat()) or not root.is_dir():
        raise ValueError('source must be real directory')
    root, output = root.resolve(), output.resolve()
    if root == output or root in output.parents or output.exists():
        raise ValueError('output must be new and outside source')
    if max_bytes < 1:
        raise ValueError('invalid byte limit')
    rows = scan(root)
    paths = {r['path'] for r in rows}
    links = []
    for r in rows:
        if r['status'] != 'candidate':
            continue
        if r['size'] > max_bytes:
            r['status'] = 'oversize'
            continue
        try:
            data = safe_bytes(root, r, max_bytes)
            text = data.decode('utf-8-sig', errors='strict')
            if '\x00' in text:
                r['status'] = 'binary_text'
            elif SECRET.search(text):
                r['status'] = 'quarantine_secret'
            else:
                r.update(status='eligible', sha256=hashlib.sha256(data).hexdigest(), encoding='utf-8-sig' if data.startswith(b'\xef\xbb\xbf') else 'utf-8', metadata=metadata(text))
                note_links, external_count = local_links(text, r['path'], paths)
                links.extend(note_links)
                r['metadata'].update(local_link_count=len(note_links), external_link_count=external_count)
        except UnicodeDecodeError:
            r['status'] = 'encoding_error'
        except (OSError, ValueError) as e:
            r.update(status='read_error_or_changed', error_type=type(e).__name__)
    after = scan(root)
    before_map = {r['path']: r.get('identity') for r in rows}
    after_map = {r['path']: r.get('identity') for r in after}
    changed = sorted(k for k in before_map.keys() | after_map.keys() if before_map.get(k) != after_map.get(k))
    hash_changed = []
    hashes = defaultdict(list)
    for r in rows:
        if r['status'] == 'eligible':
            hashes[r['sha256']].append(r['path'])
            try:
                if hashlib.sha256(safe_bytes(root, r, max_bytes)).hexdigest() != r['sha256']:
                    hash_changed.append(r['path'])
            except (OSError, ValueError):
                hash_changed.append(r['path'])
    final_map = {r['path']: r.get('identity') for r in scan(root)}
    changed = sorted(set(changed) | {k for k in before_map.keys() | final_map.keys() if before_map.get(k) != final_map.get(k)})
    duplicates = [{'sha256': h, 'paths': paths} for h, paths in sorted(hashes.items()) if len(paths) > 1]
    counts, sizes, extensions = Counter(), Counter(), {}
    for r in rows:
        counts[r['status']] += 1
        if r.get('kind') == 'file':
            sizes[r['status']] += r['size']
            ext = extensions.setdefault(r['extension'] or '<none>', {'files': 0, 'bytes': 0})
            ext['files'] += 1
            ext['bytes'] += r['size']
    result = {'schema_version': 1, 'source_root': str(root), 'created_utc': datetime.now(timezone.utc).isoformat(), 'manifest_records': len(rows), 'observed_file_entries': sum(r.get('kind') == 'file' for r in rows), 'observed_file_bytes': sum(sizes.values()), 'status_counts': dict(sorted(counts.items())), 'status_file_bytes': dict(sorted(sizes.items())), 'extensions': dict(sorted(extensions.items())), 'duplicate_groups': len(duplicates), 'duplicate_files': sum(len(d['paths']) for d in duplicates), 'verification': {'eligible_hashes_unchanged': not hash_changed, 'metadata_unchanged': not changed, 'metadata_changed_paths': changed, 'hash_changed_paths': hash_changed}, 'import_ready': not changed and not hash_changed and not any(r['status'] in {'scan_error', 'stat_error', 'read_error_or_changed'} for r in rows)}
    protocol = {'schema_version': 1, 'permissions': {'local_inventory': True, 'local_private_finance_admin_indexing': True, 'network_upload': False, 'ingestion_this_run': False, 'source_writes': False, 'model_downloads': False, 'future_prune': 'separate explicit file-level review required'}, 'eligible_extensions': sorted(SUPPORTED), 'max_bytes': max_bytes, 'excluded_directory_names': sorted(EXCLUDED), 'archive_extensions': sorted(ARCHIVES), 'sensitive_name_pattern': SENSITIVE.pattern, 'secret_pattern': SECRET.pattern, 'secret_detector_limit': 'heuristic; not a complete DLP guarantee', 'scope': 'reachable regular files except explicit opaque exclusions; not all knowledge migrated', 'omissions': 'excluded directory descendants unenumerated and unknown; each boundary recorded', 'importer_contract': 'require import_ready; consume eligible only; recheck paths, reparse/hardlinks, secrets and exact sha256; never follow manifest links', 'unsupported_policy': 'PDF Office images and other non-MD/TXT pending extraction; preserve originals', 'verification_scope': 'observed metadata rescanned; eligible bytes SHA256 twice; excluded and unsupported bytes NOT read or hash-certified'}
    protocol['worker_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    protocol['metadata_limits'] = 'Shallow frontmatter keys and explicit type hints only; no epistemic distinction. Wiki/inline Markdown links are heuristic; code blocks, reference-style links, complex YAML and URL targets are not fully interpreted.'
    result['link_status_counts'] = dict(Counter(link['status'] for link in links))
    result['role_hint_counts'] = dict(Counter(r['metadata']['role_hint'] for r in rows if r['status'] == 'eligible'))
    output.mkdir(parents=True, exist_ok=False)
    (output / 'links.jsonl').write_text(''.join(json.dumps(link, ensure_ascii=True) + '\n' for link in links), encoding='utf-8')
    for name, value in [('summary.json', result), ('protocol.json', protocol), ('duplicates.json', duplicates)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    (output / 'manifest.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=True) + '\n' for r in rows), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--output')
    parser.add_argument('--max-bytes', type=int, default=8 * 1024 * 1024)
    args = parser.parse_args()
    output = Path(args.output) if args.output else Path(__file__).resolve().parents[1] / 'artifacts/vault-inventory' / uuid.uuid4().hex
    result = inventory(args.root, output, args.max_bytes)
    print(json.dumps({'output': str(output), **{k: result[k] for k in ['manifest_records', 'observed_file_entries', 'observed_file_bytes', 'status_counts', 'status_file_bytes', 'duplicate_groups', 'duplicate_files', 'import_ready']}, 'verification': {k: v for k, v in result['verification'].items() if not k.endswith('_paths')}}, indent=2))


if __name__ == '__main__':
    main()
