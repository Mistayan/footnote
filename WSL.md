# Footnote natively in WSL 2

For one person on Windows whose machine blocks local builds (Smart App Control or a WDAC policy: `os error 4551`), WSL 2
is the other way to run Footnote besides [Docker](DOCKER.md): Footnote is built and runs as a Linux program inside WSL,
and the repositories it reads can live on WSL's own disk (ext4) instead of the Windows one.

## What it changes, measured

Windows 11, WSL 2 Ubuntu, 23 November 2026, quiet machine (Windows CPU 3 to 5 %). From PowerShell, 30 runs each (10 for
`git status`), alternating, warm-ups left out. WSL runs a binary built from `main` (0.6.1); Docker runs the `footnote:local`
image (0.3.0) in a throwaway container started as `compose.yaml` does (read-only bind mount of the repository).

| From Windows, p50 (p95) | `docker exec` | `wsl.exe`, repository on `/mnt/c` | `wsl.exe`, repository on ext4 |
|---|---:|---:|---:|
| `footnote --version` | 72 ms (76) | 68 ms (80) | 68 ms (80) |
| memory hook, `UserPromptSubmit` | 73 ms (82) | 67 ms (77) | 69 ms (76) |
| `git status` of this repository, as the `Stop` hook runs it | 1,755 ms (2,040) | 2,265 ms (2,933) | 97 ms (113) |

- Starting Footnote costs about the same through `wsl.exe` as through `docker exec`: per prompt, WSL is not faster.
- Where the repository lives is what differs. A Windows folder read from Linux is slow either way (Docker's bind mount or
  WSL's `/mnt/c`); a copy on WSL's ext4 is read twenty times faster. That is what `footnote-wsl-codebase` below is for, and
  it matters to everything that reads the repository: the `Stop` hook's `git status` (4-second budget), `footnote grep`,
  `footnote code-index`.
- Inside WSL, without the `wsl.exe` start, the same hook takes 7.5 ms with the repository on ext4 and 27 ms on `/mnt/c`.

The scripts used are in the pull request that added this guide.

## Install

Inside WSL (Ubuntu 24.04 or Debian 13 or later: the ONNX Runtime Footnote links needs glibc 2.38), with Rust installed
there, from a checkout of this repository:

```bash
bash scripts/wsl-install.sh --install-models
```

It builds `footnote` with its target folder on ext4 (`~/.cache/footnote-target`), installs it in `~/.local/bin`, and adds:

- `~/.local/bin/footnote-wsl-env`: starts Footnote with a Linux-only `PATH` (WSL appends the Windows folders, and every
  program lookup then crosses to Windows) and with `FOOTNOTE_PATH_MAP` from `~/.local/state/footnote/wsl-path-map.env`.
- `~/.local/bin/footnote-wsl-codebase`: copies repositories onto ext4 (next section).
- a systemd user service, `footnote-memory.service`, that keeps the memory daemon's models loaded, when systemd runs in
  this distribution (`[boot] systemd=true` in `/etc/wsl.conf`). Without it, the first hook starts the daemon.

Options: `--skip-build` (use the installed binary), `--from-db <file>` (start from a copy of an existing `memory.db`, only
when the state folder has none), `--from-models <dir>` (copy downloaded models), `--import-repo <path>`,
`--sync-win-configs` and `--dry-run` (passed to `wsl-agents.sh`), `--state-dir`, `--target-dir`.

## Repositories on ext4

```bash
footnote-wsl-codebase import /mnt/c/Users/<user>/repos/project   # or C:\Users\<user>\repos\project
footnote-wsl-codebase import-all /mnt/c/Users/<user>/repos        # every git repository directly inside
footnote-wsl-codebase list
footnote-wsl-codebase sync --all                                  # fetch from the Windows checkout, fast-forward
```

`import` clones the repository into `~/workspaces/<name>`, keeps its `origin` URL (so memories keep the same project
name) and adds a remote `windows` pointing at the Windows checkout. It records the Windows path and the `/mnt/c` path as
`FOOTNOTE_PATH_MAP` entries pointing at the clone, so a hook that receives `C:\...` from an agent reads the ext4 copy, then
runs `footnote projects add` and `footnote code-index`. It refuses a target folder that exists and is not a clone.
`--with-untracked` also copies uncommitted files (rsync, build folders left out); `--no-index` skips the code index.

The clone is a second working copy: commit in one, then `git fetch windows` (or `sync`) in the other.

## Agents

**Inside WSL** (Claude Code, Codex and Antigravity started in a WSL shell, in `~/workspaces/<repo>`):

```bash
bash scripts/wsl-agents.sh --dry-run
bash scripts/wsl-agents.sh
```

It runs `footnote install --memory --lean` with the WSL binary, links `claude`, `codex` and `agy` into `~/.local/bin` when
they are only installed elsewhere, and installs a `footnote` shim for Cygwin and Git Bash that runs the WSL binary (it never
replaces a `footnote` that is not this shim). `--sync-win-configs` copies agent settings (`.claude/settings.json`,
`.codex/config.toml`, `.codex/hooks.json`, `.gemini/config/*.json`) from the Windows home where WSL has none. Credentials are
never copied: sign in to each agent inside WSL. Copied settings keep their other Windows-specific entries; check them.
`--remove` runs `footnote uninstall --memory --lean`.

**Antigravity on Windows** using the WSL install:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wsl-agents.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wsl-agents.ps1
```

It writes the `footnote-memory` MCP server and hooks into `~/.gemini/config`, as `wsl.exe -d <distro> -- <wrapper> ...`.
An existing entry is kept unless `-Force`; `-Remove` deletes only an entry that starts Footnote through `wsl.exe`.

## Limits

- One person, as with Docker: anyone who can run commands in this WSL distribution can read every memory.
- Footnote in WSL and Footnote on Windows or in Docker keep separate state folders. Use one of them, or move the memories
  with a backup (`--from-db`).
- Checked on one machine only: Windows 11 with Ubuntu 26.04 in WSL 2.
