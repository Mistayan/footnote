"""The version rule (docs/VERSIONING.md): the next version from the commits since the last release tag, and one version in
every manifest.

    python scripts/next-version.py              the next version, and the commits that decide it
    python scripts/next-version.py --set X.Y.Z  write X.Y.Z into every manifest and lock file (no suffix)
    python scripts/next-version.py --check      every manifest carries the workspace version (CI)

Breaking (`type!:` or a `BREAKING CHANGE:` line) bumps MINOR before 1.0 and MAJOR from 1.0; `feat` bumps MINOR; any other
type bumps PATCH. A version is X.Y.Z and nothing else.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRATES = {"footnote", "footnote-code", "footnote-core", "footnote-library", "footnote-memory", "footnote-search",
          "footnote-launcher"}
SUBJECT = re.compile(r"^(?P<type>[a-z]+)(\([^)]*\))?(?P<bang>!)?: ")
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?$")


def kind(subject: str, body: str) -> str:
    """`breaking`, `feature` or `patch` for one commit."""
    m = SUBJECT.match(subject)
    if (m and m["bang"]) or re.search(r"^BREAKING[ -]CHANGE: ", body, re.M):
        return "breaking"
    return "feature" if m and m["type"] == "feat" else "patch"


def bump(version: str, kinds: list[str]) -> str | None:
    """The next release version after `version` (a suffix is dropped first), or None with nothing to release."""
    m = VERSION.match(version.lstrip("v"))
    if not m:
        raise ValueError(f"not a version: {version}")
    major, minor, patch = map(int, m.groups())
    if not kinds:
        return None
    if "breaking" in kinds:
        return f"{major + 1}.0.0" if major >= 1 else f"{major}.{minor + 1}.0"
    if "feature" in kinds:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def manifests() -> dict[str, str]:
    """Each manifest's version, by path."""
    found = {}
    cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    found["Cargo.toml"] = re.search(r'\[workspace\.package\]\s*\nversion = "([^"]+)"', cargo)[1]
    launcher = (ROOT / "apps/launcher/src-tauri/Cargo.toml").read_text(encoding="utf-8")
    found["apps/launcher/src-tauri/Cargo.toml"] = re.search(r'^version = "([^"]+)"', launcher, re.M)[1]
    for path in ("apps/launcher/src-tauri/tauri.conf.json", "apps/launcher/package.json"):
        found[path] = json.loads((ROOT / path).read_text(encoding="utf-8"))["version"]
    lock = json.loads((ROOT / "apps/launcher/package-lock.json").read_text(encoding="utf-8"))
    found["apps/launcher/package-lock.json"] = lock["version"]
    for path in ("Cargo.lock", "apps/launcher/src-tauri/Cargo.lock"):
        text = (ROOT / path).read_text(encoding="utf-8")
        for name, version in re.findall(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"', text):
            if name in CRATES:
                found[f"{path} ({name})"] = version
    return found


def set_version(new: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        sys.exit(f"{new}: a version is X.Y.Z, with no suffix (docs/VERSIONING.md)")

    def edit(path: str, change) -> None:
        p = ROOT / path
        text = p.read_text(encoding="utf-8")
        p.write_text(change(text), encoding="utf-8", newline="")

    edit("Cargo.toml", lambda t: re.sub(r'(\[workspace\.package\]\s*\nversion = ")[^"]+', rf"\g<1>{new}", t, count=1))
    edit("apps/launcher/src-tauri/Cargo.toml", lambda t: re.sub(r'(?m)^(version = ")[^"]+', rf"\g<1>{new}", t, count=1))
    for path in ("apps/launcher/src-tauri/tauri.conf.json", "apps/launcher/package.json"):
        edit(path, lambda t: re.sub(r'(?m)^(  "version": ")[^"]+', rf"\g<1>{new}", t, count=1))
    # package-lock.json: the root and its `packages[""]` entry, the first two "version" keys.
    edit("apps/launcher/package-lock.json", lambda t: re.sub(r'("version": ")[^"]+', rf"\g<1>{new}", t, count=2))
    for path in ("Cargo.lock", "apps/launcher/src-tauri/Cargo.lock"):
        names = "|".join(re.escape(n) for n in CRATES)
        edit(path, lambda t: re.sub(rf'(\[\[package\]\]\r?\nname = "(?:{names})"\r?\nversion = ")[^"]+', rf"\g<1>{new}", t))


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--set"] and len(args) == 2:
        set_version(args[1])
        print(f"version {args[1]} written; run `cargo check` once to confirm the lock files agree")
        return 0
    if args == ["--check"]:
        found = manifests()
        want = found["Cargo.toml"]
        off = {k: v for k, v in found.items() if v != want}
        for path, v in off.items():
            print(f"{path}: {v}, but the workspace is {want}")
        if not off:
            print(f"every manifest carries {want}")
        return 1 if off else 0
    if args:
        print(__doc__)
        return 2
    tag = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*").strip()
    log = git("log", "--no-merges", "--format=%h%x1f%s%x1f%b%x1e", f"{tag}..HEAD")
    commits = [c.strip("\n").split("\x1f") for c in log.split("\x1e") if c.strip()]
    kinds = [kind(s, b) for _, s, b in commits]
    nxt = bump(tag, kinds)
    if not nxt:
        print(f"nothing since {tag}")
        return 0
    print(f"{tag} -> {nxt}  ({kinds.count('breaking')} breaking, {kinds.count('feature')} feat, "
          f"{kinds.count('patch')} other)")
    for (sha, subject, _), k in zip(commits, kinds):
        if k != "patch":
            print(f"  {k:8}  {sha}  {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
