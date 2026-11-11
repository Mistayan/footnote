"""Project-local official Rust components; no rustup/global environment changes."""
import hashlib
import json
import shutil
import tarfile
import urllib.request
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'artifacts/toolchain'
ROOT.mkdir(parents=True, exist_ok=True)
raw = urllib.request.urlopen('https://static.rust-lang.org/dist/channel-rust-stable.toml', timeout=90).read()
manifest = tomllib.loads(raw.decode())
(ROOT / 'channel-rust-stable.toml').write_bytes(raw)
receipts = []
for name in ['rustc', 'cargo', 'rust-std', 'rustfmt-preview', 'clippy-preview']:
    item = manifest['pkg'][name]['target']['x86_64-pc-windows-msvc']
    url, expected = item['xz_url'], item['xz_hash']
    archive = ROOT / url.rsplit('/', 1)[1]
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        urllib.request.urlretrieve(url, archive)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        top = members[0].name.split('/')[0]
        components = tf.extractfile(top + '/components').read().decode().splitlines()
        for member in members:
            parts = Path(member.name).parts
            if len(parts) < 3 or parts[1] not in components or member.isdir():
                continue
            if not member.isfile() or '..' in parts:
                raise ValueError('unsafe toolchain archive entry')
            relative = Path(*parts[2:])
            if relative.name == 'manifest.in':
                continue
            dest = ROOT / 'installed' / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(member) as src, dest.open('wb') as out:
                shutil.copyfileobj(src, out)
    receipts.append({'component': name, 'url': url, 'sha256': expected})
    print(name, 'verified and installed', flush=True)
(ROOT / 'receipt.json').write_text(json.dumps(receipts, indent=2))
