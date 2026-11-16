"""Download pinned third-party A3 conversions; verify before placing in lab cache."""
from hashlib import sha256
from pathlib import Path
import shutil

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    ("seamon67/Octen-Embedding-4B-GGUF", "80cd80f8c5db1f1a77b053aab6d332b04db0a55a", "Octen-Embed-4B-Q8_0.gguf", "7bc93bb1a5a1f28ee89668e04d034a30c7cf1358195f1f1b2a8a8ace68bd2632"),
    ("seamon67/F2LLM-v2-1.7B-GGUF", "4c7707d0606d07f57efc730062f6fedf81ad26de", "F2LLM-V2-1.7B-Q8_0.gguf", "0aea1de64aed99b266680be0f3ddfc58c7e624b35971620f8b15b427da559a75"),
    ("calculatortamer/harrier-oss-v1-0.6b-Q8_0-GGUF", "1e84dd3b4df5c8f9129b8b740a04d05c8cf95e95", "harrier-oss-v1-0.6b-q8_0.gguf", "3948d3b594931ba5c62479c09a2a0ad41c8008640d6280a79b346f0f18ef72e6"),
)


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    destination = ROOT / "artifacts" / "gguf"
    destination.mkdir(parents=True, exist_ok=True)
    for repo, revision, filename, expected in FILES:
        target = destination / filename
        if target.exists():
            if digest(target) != expected:
                raise RuntimeError(f"Existing file differs; preserved: {target}")
        else:
            print(f"Downloading {repo} at {revision}", flush=True)
            source = Path(hf_hub_download(repo_id=repo, revision=revision, filename=filename, token=False))
            if digest(source) != expected:
                raise RuntimeError(f"Downloaded file failed SHA-256: {source}")
            temporary = destination / (filename + ".a3-part")
            if temporary.exists():
                raise RuntimeError(f"Temporary file already exists; preserved: {temporary}")
            shutil.copyfile(source, temporary)
            if digest(temporary) != expected:
                raise RuntimeError(f"Copied file failed SHA-256: {temporary}")
            temporary.rename(target)
        print(f"Verified {filename}: {expected}", flush=True)


if __name__ == "__main__":
    main()
