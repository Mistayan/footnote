# Footnote in Docker — Setup & Operations (Windows, Linux, macOS)

Docker support is for **one person**: your agents (Claude Code, Codex, Gemini CLI, Antigravity), their parallel sessions and MCP hosts use one memory database, as they do on a host. Run Footnote in a hardened Linux container when:

- **Windows blocks local builds**: Smart App Control or a managed WDAC / AppLocker policy stops `cargo build` at the first build script (`os error 4551`) and blocks an unsigned `footnote.exe`. Self-signing does not get past it, and turning Smart App Control off cannot be undone without reinstalling Windows: use the container instead of weakening the policy.
- **You want one warm daemon** for all your agents: it keeps the embedding models loaded, and the memory hooks reach it through `docker exec`.

See [SECURITY.md → One person per container](SECURITY.md#one-person-per-container) for the container trust boundary.

Like [HOW-TO.md](HOW-TO.md), this guide is written for humans and AI coding agents.

---

## 1. Build the Image

Requirements: Docker Desktop (Windows / macOS, WSL 2 backend on Windows) or Docker Engine (Linux). From the repository root:

```bash
docker build -t footnote:local .
```

The image (`Dockerfile`):

- builds on Debian 13 (trixie): the static ONNX Runtime that `ort-sys` downloads fails to link on bookworm (undefined `__isoc23_strtoll`);
- runs as the non-root user `footnote` (`10001:10001`), `ENTRYPOINT ["footnote"]`, with no `curl`/`wget`;
- pins both base images by `@sha256` digest (Dependabot refreshes them every week);
- keeps everything Footnote stores (memory DB `/state/memory.db`, indexes, models, keys, daemon socket) in `/state`, and reads code from `/workspace` or `/workspaces`.

Mount a **named Docker volume** on `/state`, never a Windows host folder, so `0700`/`0600` permissions, atomic `hard_link` secrets and Unix daemon sockets work (ext4 inside WSL 2).

---

## 2. One Command at a Time

Mount the project you work on at `/workspace`, read-only, and run offline with a read-only root filesystem and no capabilities:

```powershell
# Windows (Windows PowerShell 5.1 / pwsh)
$H = @('--network','none','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=64m','--cap-drop=ALL','--security-opt=no-new-privileges:true')
docker run --rm -i @H -v footnote-state:/state -v "${PWD}:/workspace:ro" footnote:local status
docker run --rm -i @H -v footnote-state:/state -v "${PWD}:/workspace:ro" footnote:local code-index .
# The only commands that need the network (bridged, never --network host):
docker run --rm -i --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop=ALL `
  --security-opt=no-new-privileges:true -v footnote-state:/state footnote:local models install bekko-a8m gte-small
```

```bash
# Linux / macOS (Git Bash: export MSYS_NO_PATHCONV=1 first)
H="--network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop=ALL --security-opt=no-new-privileges:true"
docker run --rm -i $H -v footnote-state:/state -v "${PWD}:/workspace:ro" footnote:local status
docker run --rm -i $H -v footnote-state:/state -v "${PWD}:/workspace:ro" footnote:local code-index .
# The only commands that need the network (bridged, never --network host):
docker run --rm -i --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop=ALL \
  --security-opt=no-new-privileges:true -v footnote-state:/state footnote:local models install bekko-a8m gte-small
```

MCP entry for an agent on the host, one container per session (use the absolute path of `docker` for GUI hosts):

```json
{
  "mcpServers": {
    "footnote-memory": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
               "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
               "-v", "footnote-state:/state", "footnote:local", "--db", "/state/memory.db", "mcp"]
    }
  }
}
```

Each such session starts a container and loads the models again, and there are no memory hooks. For daily use, keep one daemon running instead (Section 3). To reach a service on the host (for example Ollama on port 11434), drop `--network none`, add `--add-host=host.docker.internal:host-gateway` and use `http://host.docker.internal:11434`; Footnote's embeddings still run in-process and do not use Ollama yet.

---

## 3. The Compose Daemon: One for All Your Agents (`compose.yaml`)

`compose.yaml` keeps **one hardened daemon** running (`--db /state/memory.db serve --mcp --daemon`, without `--idle-seconds`) so embedding models stay loaded in RAM (`memory.idle_seconds` unloads models only on an on-demand host daemon). The database is always `/state/memory.db` for the daemon, MCP server, and memory hooks alike. Your agents reach it with `docker exec -i`: the MCP server for their tools, and the memory hook for the memory pack at session start, recall on each prompt, and the save request at stop.

**Security defaults:**
- Offline (`network_mode: none`), `read_only` rootfs with a `noexec` `/tmp` tmpfs, `cap_drop: [ALL]`, `no-new-privileges`, non-root user `10001`.
- Repositories mounted **read-only** under `/workspaces`: git trusts mounted repositories there only, and Footnote's git queries never run a repository's `core.fsmonitor` or filter drivers.
- Agent session files are not mounted into the container.
- The network profile (`footnote-net`) mounts no workspace. The daemon is bounded (`pids_limit`, `mem_limit`, rotated logs), and `FOOTNOTE_NO_LIVE_FETCH=1` turns off live fetch-on-miss and scheduled `memory-clean`.
- **One person per container.** Anyone who can use the Docker engine can read, change and delete every memory in the volume ([SECURITY.md](SECURITY.md#one-person-per-container)).

### 3.1 Start the Daemon

`FOOTNOTE_WORKSPACES`, the host folder that holds your repositories (mounted read-only at `/workspaces`), is **required** by every Compose command, including the `net` profile. Put it once in a `.env` file next to `compose.yaml` (git ignores it). `compose.yaml` derives `FOOTNOTE_PATH_MAP` from it unless you set that yourself.

Optional single-user settings in `.env` (listed at the top of `compose.yaml`): `FOOTNOTE_CONTAINER_NAME` (default `footnote`, to run a second container next to the usual one for a while, for example to try a newly built image before switching to it), `FOOTNOTE_IMAGE` (default `footnote:local`, to test another locally built tag), `FOOTNOTE_STATE_VOLUME` (default `footnote-state`, to attach an existing named volume with another name), `FOOTNOTE_PATH_MAP` (explicit mapping override), `FOOTNOTE_PIDS_LIMIT` (default `512`), `FOOTNOTE_MEM_LIMIT` (default `4g`).

```text
# .env (Windows example; Linux: /home/<user>/repos)
FOOTNOTE_WORKSPACES=C:\Users\<user>\repos
```

```bash
docker compose up -d
docker compose ps

# One-time model download, through the explicit-network profile:
docker compose --profile net run --rm footnote-net models install bekko-a8m gte-small
docker compose --profile net run --rm footnote-net models use bekko-a8m gte-small

# Make each repository known to footnote_code (and refresh it after changes):
docker exec footnote footnote code-index /workspaces/<repo>

# Full isolated smoke suite (temporary volume and containers, cleaned up on exit; Linux, macOS, Git Bash):
bash scripts/docker-smoke.sh footnote:local
```

If `footnote-state` (or `FOOTNOTE_STATE_VOLUME`) was already created by `docker run` in Section 2, Compose warns that it was not created by Docker Compose; that warning is harmless and the existing volume is mounted as-is.

### 3.2 Register Your Agents Automatically

Once the daemon runs, one command registers it with every agent found for your user: the `footnote-memory` MCP server and the memory hooks, with the absolute path of `docker`. It detects **Claude Code, Codex, Gemini CLI and Antigravity** (also Antigravity's T3 Code provider folders and `$GEMINI_HOME`), and writes the same hooks as `footnote install --memory` on a host:

```powershell
# Windows (Windows PowerShell 5.1 or pwsh)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\docker-agents.ps1 -DryRun   # what would change
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\docker-agents.ps1
```

```bash
# Linux / macOS (JSON files need python3)
bash scripts/docker-agents.sh --dry-run
bash scripts/docker-agents.sh
```

| Agent | Detected by | MCP server | Memory hooks (events, timeouts) |
|---|---|---|---|
| Claude Code | `claude` on `PATH`, or `~/.claude` (`$CLAUDE_CONFIG_DIR`) | `claude mcp add --scope user` (its own command; `~/.claude.json` is never edited by the script) | `~/.claude/settings.json`: SessionStart 15 s, UserPromptSubmit 10 s, Stop 5 s |
| Codex | `codex` on `PATH`, or `$CODEX_HOME` / `~/.codex` | `[mcp_servers.footnote-memory]` in `config.toml` | `hooks.json`: SessionStart 15 s, UserPromptSubmit 10 s, Stop 5 s |
| Gemini CLI | `gemini` on `PATH`, or `~/.gemini/settings.json` | `mcpServers` in `~/.gemini/settings.json` | same file, `matcher: "*"`: SessionStart 15 000 ms, BeforeAgent 10 000 ms, AfterAgent 5 000 ms |
| Antigravity | `~/.gemini/config` (`antigravity`, `antigravity-cli`), `~/.t3/userdata/providers/antigravity/<id>/config`, `$GEMINI_HOME/config` | `mcpServers` in `<config>/mcp_config.json` | `<config>/hooks.json`, entry `"footnote-memory"`: SessionStart 15, PreInvocation 10, Stop 5 |

- **Safe to run again:** an existing `footnote-memory` entry is kept, and a Footnote memory hook already there (this script's or the native `footnote hook`) is not doubled. `-Force` / `--force` replaces them.
- **Docker-only removal:** `-Remove` / `--remove` deletes an MCP or hook entry only when its command runs `docker` or `docker.exe` with `exec -i` (reading `claude mcp get` for Claude Code). Any native `footnote` entry is left alone and reported as such.
- **Sandbox testing (`--home` / `-HomeDir`):** points file edits at another folder and skips `claude mcp` so the real `~/.claude.json` can never be modified. `-Container` / `--container` defaults to `FOOTNOTE_CONTAINER_NAME` when set (otherwise `footnote`), so you can target a second container or test container.
- **No double hooks with a host install either:** `footnote install --memory` and `footnote uninstall --memory` on the host count these Docker hooks as Footnote's own (install replaces them with the native hook, uninstall removes them). To move back to a native install, run the script with `--remove` first, so the MCP entry moves too.
- Each edited file is backed up once (`<file>.footnote-backup`, keeping file permissions) and replaced atomically. A file that its agent rewrote meanwhile is left alone. A JSON file with comments is left for you to edit.
- When the container runs, the script checks it answers `tools/list` through the registered command. Restart each agent afterwards.

### 3.3 Register an Agent by Hand

Every agent gets the same two commands:

- **MCP server:** `docker exec -i footnote footnote --db /state/memory.db mcp`. It is not a one-shot container: the process lives as long as the agent's session and talks to the running daemon, whose models stay loaded (`docker run --rm -i … mcp`, Section 2, is the one-shot form).
- **Memory hook:** `docker exec -i footnote footnote hook`, on the events of the table above. It reads the agent's event on stdin; `FOOTNOTE_PATH_MAP` translates its `cwd`.

Use the **absolute path of `docker`** for GUI hosts, which do not inherit the shell `PATH` (Windows: `(Get-Command docker).Source -replace '\\', '/'`; Linux / macOS: `command -v docker`), quoted in a hook command when it has a space, and replace `footnote` (the container) with `FOOTNOTE_CONTAINER_NAME` if you renamed it.

| Agent | MCP server, registered once (user scope) |
|---|---|
| Claude Code | `claude mcp add footnote-memory --scope user -- docker exec -i footnote footnote --db /state/memory.db mcp` |
| Codex | `codex mcp add footnote-memory -- docker exec -i footnote footnote --db /state/memory.db mcp` |
| Gemini CLI | `mcpServers` entry below in `~/.gemini/settings.json` |
| Antigravity | `mcpServers` entry below in `~/.gemini/config/mcp_config.json` |
| Cursor, Windsurf, Cline and other `mcpServers` hosts | `mcpServers` entry below in the host's MCP settings file |

```json
{
  "mcpServers": {
    "footnote-memory": {
      "command": "/ABSOLUTE/PATH/TO/docker",
      "args": ["exec", "-i", "footnote", "footnote", "--db", "/state/memory.db", "mcp"]
    }
  }
}
```

Memory hooks for Claude Code (`~/.claude/settings.json`; Codex's `hooks.json` takes the same `hooks` object):

```json
{
  "hooks": {
    "SessionStart": [{"hooks": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 15}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 10}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 5}]}]
  }
}
```

Gemini CLI (`~/.gemini/settings.json`, alongside `mcpServers`; timeouts in ms):

```json
{
  "hooks": {
    "SessionStart": [{"matcher": "*", "hooks": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 15000}]}],
    "BeforeAgent": [{"matcher": "*", "hooks": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 10000}]}],
    "AfterAgent": [{"matcher": "*", "hooks": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 5000}]}]
  }
}
```

Antigravity (`~/.gemini/config/hooks.json`; flat arrays under `"footnote-memory"`, no outer `"hooks"` object):

```json
{
  "footnote-memory": {
    "SessionStart": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 15}],
    "PreInvocation": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 10}],
    "Stop": [{"type": "command", "command": "/ABSOLUTE/PATH/TO/docker exec -i footnote footnote hook", "timeout": 5}]
  }
}
```

Check a registration with `claude mcp get footnote-memory` (it connects and reports `✔ Connected`) or `codex mcp get footnote-memory`. Remove it with `claude mcp remove footnote-memory --scope user` or `codex mcp remove footnote-memory`.

### 3.4 Hook Latency (measured)

A hook runs on every prompt, so its round trip matters. Measured on Windows 11 + Docker Desktop (WSL 2 engine), the machine otherwise idle, with a warm daemon, two embedding models and a copy of a daily memory database. Each call is started the way an agent starts it (event on stdin, answer read from stdout) and is a new session whose prompt recalls three memories (575 bytes of context added; the SessionStart pack is 777 bytes). 20 calls per cell, two runs, medians (p90):

| | `docker.exe` started directly | Through Git Bash, `bash -c` (Claude Code on Windows) |
|---|---|---|
| `docker exec` alone (`footnote --version`) | 100 ms (105) | 130 ms (140) |
| `UserPromptSubmit` (recall, every prompt) | 180–190 ms (≤ 202) | **210 ms** (≤ 233) |
| `SessionStart` (memory pack) | 210–220 ms (≤ 227) | 240–255 ms (≤ 269) |
| `Stop` | 170 ms (≤ 189) | 205–210 ms (≤ 220) |

- About 100 ms is `docker exec` itself and 80 to 90 ms the hook (recall with the daemon's warm models). Claude Code on Windows starts a hook command through Git Bash, which adds about 30 ms: about 210 ms per prompt.
- A Stop that asks the agent to save its memories also checks `git status` for the changed-files hint: up to 3.4 s on this repository through the Docker Desktop mount (both git queries share a 4 s budget so Stop stays inside its 5 s timeout).
- Not measured on a Linux host.

### 3.5 Host-to-Container Path Mapping (`FOOTNOTE_PATH_MAP`)

An agent on a Windows host sends Windows paths (`footnote_code` `root` and hook `cwd`), such as `C:\Users\<user>\repos\my-app`. `FOOTNOTE_PATH_MAP` translates them with semicolon-separated `HOST_PREFIX=CONTAINER_PREFIX` pairs (`compose.yaml` derives it from `FOOTNOTE_WORKSPACES`):

```text
FOOTNOTE_PATH_MAP=C:\Users\<user>\repos=/workspaces
```

- Matches full path-segment boundaries only (`C:\work\app` never matches `C:\work\app2`); drive paths compare case-insensitively, `\` and `/` alike.
- Longest matching prefix wins; any `..` traversal segment in the relative tail fails closed.
- Mounting a parent folder (`FOOTNOTE_WORKSPACES` → `/workspaces:ro`) keeps each repository's code graph separate.

---

## 4. Backup, Upgrade and Migration

**Backup** (Windows `pwsh`; a consistent, SHA-256-verified SQLite copy in a host folder):

```powershell
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m `
  --cap-drop=ALL --security-opt=no-new-privileges:true `
  -v footnote-state:/state -v "${PWD}:/backups" `
  footnote:local --db /state/memory.db backup --output /backups/memory-backup.db
```

The backup holds every memory in clear text: keep it where only you can read it. On Linux, the target folder must be writable by UID `10001` (for example `sudo install -d -m 0700 -o 10001 -g 10001 ./backups`, then mount `./backups`).

**Upgrade:** pull the repository, then `docker compose build` and `docker compose up -d`. The state volume is kept. Recreating the container ends any open MCP session (`docker exec -i … mcp`), so reconnect or restart each running agent afterwards.

**Restore (lost volume or failed upgrade):** before upgrading, tag the working image (`docker tag footnote:local footnote:previous`) so you can return to it with `FOOTNOTE_IMAGE=footnote:previous`. An older image refuses a database migrated to a newer schema (`user_version`), so the pre-upgrade backup is the way back.

1. Stop the daemon:
   ```powershell
   docker compose stop
   ```
2. Replace `/state/memory.db` and clear its sidecars and derived index (PowerShell; Linux / macOS: replace `` ` `` with `\` and ensure the backup is readable by UID `10001`):
   ```powershell
   docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m `
     --cap-drop=ALL --security-opt=no-new-privileges:true `
     -v footnote-state:/state -v "${PWD}:/backups:ro" --entrypoint sh footnote:local `
     -c "rm -rf /state/memory.db /state/memory.db-journal /state/memory.db-wal /state/memory.db-shm /state/memory.db.tantivy && cp /backups/memory-backup.db /state/memory.db && chmod 0600 /state/memory.db"
   ```
3. Sibling files in `/state`:
   - `memory.db-journal` (and `-wal`, `-shm`) and `memory.db.tantivy`: **delete** (done in step 2) — a leftover rollback journal is replayed into the restored DB on open, and a stale lexical index hides changes (Footnote rebuilds it automatically).
   - `audit.jsonl` and `audit.key`: **keep both** on an in-place restore so `footnote audit verify --file /state/audit.jsonl` stays valid (never delete only one; a fresh volume creates a new pair).
   - `memory.json` and `/state/models`: **keep** on an in-place restore; on a new volume, re-run `models install` and `models use` (Section 3.1) before step 4 for hybrid recall.
4. Start the daemon (set `FOOTNOTE_IMAGE=footnote:previous` first when rolling back):
   ```powershell
   docker compose up -d
   ```
5. Check the restored memories and recall (then reconnect or restart open agents):
   ```powershell
   docker exec footnote footnote status
   docker exec footnote footnote --db /state/memory.db search "<word from a memory>"
   ```

**A volume written by an image that ran as root** (the first Dockerfile, #415) needs its owner changed once, or the non-root image fails with `attempt to write a readonly database`:

```bash
docker run --rm -u 0 -v footnote-state:/state --entrypoint chown footnote:local -R 10001:10001 /state
```

**A volume mounted somewhere else than `/state` before:** `memory.json` lists the models by absolute path. Run `docker exec footnote footnote models use bekko-a8m gte-small` once after the move, or new memories are saved without vectors.

---

## 5. Feature Compatibility Matrix

| Product / Command | Docker status | Notes |
|---|---|---|
| **Footnote Memory** (`mcp`, `serve --mcp`, `remember`, `forget`, `recall`, `memory-review`) | **Supported** | Named volume on `/state` (`/state/memory.db`); the Compose daemon runs without `--idle-seconds` so ONNX models stay loaded in RAM. |
| **Memory Hooks** (`footnote hook`) | **Supported** | Registered by `scripts/docker-agents.*` (Section 3.2) through `docker exec -i`, with `FOOTNOTE_PATH_MAP`. The handoff asked at the end of a long Claude Code session is not available in Docker, because the container does not read session files; ask your agent for a handoff yourself. Latency: Section 3.4. |
| **Agent skill edits** (`memory.skill_rewrite`, `footnote_skill_edit`) | **Partial (opt-in)** | `footnote_skill_edit` writes copies under `/state/skills/agent/`; script edits and prose edits past `max(6, 25%)` lines wait for `docker exec footnote footnote skills diff` / `approve`. Automatic skill outcome tracking and failure prompts (which read Claude Code or Codex session files) are off because session files are not mounted. |
| **Footnote Library** (`index`, `search`, `find`, `docs add/list/refresh/prune`, `models install/use`) | **Supported** (Markdown/text/web docs, ONNX) | Markdown indexing uses embedded `tools/extract.py` offline (PDF/OCR helpers are not bundled). Network only through the `net` profile (`models install`, `docs add`); live fetch-on-miss is off. Default image builds without `llama.cpp`, so GGUF models (`models import`) are refused by `models use`. |
| **Footnote Code** (`code-index`, `code`, `code-map`, `code-impact`, `grep`, `stack`, `frame`, `footnote_code`) | **Supported (tree-sitter)** | Mount repositories `:ro` under `/workspaces`. Compiler indexers (`--deep`: `rust-analyzer`, `scip-typescript`, `scip-python`) are not in the image. |
| **Usage / Gain** (`usage`, `gain --missed`) | **Not supported** (host sessions) | Reads the host's local session files, which are not mounted into the container (`usage` / `gain` still report Footnote's own MCP trimming in `/state/usage/lean.jsonl`). |
| **`footnote memory-clean`** | **Not supported for model review** | Model review calls the host's `claude` CLI over the network (not in the image); `--agent codex` runs local rules only. Scheduled background cleaning is paused when `FOOTNOTE_NO_LIVE_FETCH=1`. |
| **`footnote agent-commit`** | **Not supported** | Runs the host's `claude` or `codex` CLI with write and network access (`agent-ask` still queues a request for the next agent turn). |
| **Footnote Lean** (`run`, `hook lean`, `audit-prefix --probe-mcp`) | **Not supported from a Windows host** | `footnote run` executes inside the Linux container, without the host's toolchains. |
| **`footnote install` / `update` / `rollback`** | **Not applicable** | Register agents with `scripts/docker-agents.ps1` / `scripts/docker-agents.sh` (Section 3.2). Rebuild the image and run `docker compose up -d` to upgrade, keeping the state volume (binary-replacement daemon exit is inactive on the read-only rootfs). |
| **`footnote personal` (DPAPI encryption) / `apps/launcher`** | **Not supported** | Windows-native DPAPI / Tauri GUI only. |
| **`footnote models recommend`** | **Approximate** | Reads the WSL 2 / container VM RAM (`/proc/meminfo`) and cannot see Windows host GPUs. |

---

## 6. Several Projects in One Daemon: Measured Limits

Measured on Windows 11 + Docker Desktop with three repositories under one `FOOTNOTE_WORKSPACES` folder and three agent sessions at once: path translation, per-project code graphs, per-project memory scopes and concurrent sessions work (a cold `docker exec` MCP session answers `tools/list` in about 0.3 s). The limits:

- **One parent folder.** Repositories outside `FOOTNOTE_WORKSPACES` are not mounted; `footnote_code` refuses them. Keep every repository under one dedicated folder.
- **The whole folder is visible** to the container (read-only), including files that are not repositories: do not point it at a Desktop or a home folder.
- **No automatic code graph.** A repository is known to `footnote_code` once a hook session started there or once `code-index` ran on it; refresh with `code-index` after changes (seconds per repository, tree-sitter only).
- **Pass the project root.** `footnote_code` looks up the code graph of the folder it is given; a subfolder of an indexed repository has none of its own.
- **Scopes are labels.** A project `scope` sorts your memories; it does not hide one project's memories from an agent working on another.
- **Git state of Windows checkouts.** Git for Windows converts line endings (`core.autocrlf`); git in the container does not, so a CRLF file whose stat data changed shows as modified in the changed-files hint and in `footnote projects`. `footnote projects` runs `git status` across repositories in parallel over the Docker Desktop mount (so several projects take roughly as long as the slowest one; a repository whose git query exceeds 5 s or that defines its own filter driver shows `null`; `footnote projects --quick` skips git).
- **A hook `cwd` outside the mapped folder** is recorded as a project that does not exist (named after its full Windows path) in `footnote projects`.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `cargo build` fails with `os error 4551` on Windows | Smart App Control / WDAC blocks unsigned build scripts | Use this guide; do not weaken the policy |
| `required variable FOOTNOTE_WORKSPACES is missing a value` | Every Compose command needs the workspace folder, the `net` profile too | Set it in `.env` next to `compose.yaml` (Section 3.1) |
| `attempt to write a readonly database` | The volume was written by an image that ran as root | Change its owner once (Section 4) |
| `… is not a project Footnote knows` from `footnote_code` | No hook session and no `code-index` for that repository yet, or it is outside `FOOTNOTE_WORKSPACES` | `docker exec footnote footnote code-index /workspaces/<repo>` |
| `no code graph at …` from `footnote_code` | `root` is a subfolder of the indexed repository | Pass the repository root |
| The agent shows `footnote-memory` as failed, or a hook error on each prompt | The container is not running, or the GUI host cannot find `docker` | `docker compose up -d`; register the absolute path of `docker` (Section 3.3) |
| Files show as changed in the save hint or `footnote projects` while `git status` on the host is clean | CRLF checkout of a Windows repository, read by git in the container (Section 6) | Expected: only CRLF files whose stat data changed are affected |
| New memories are not found by hybrid recall | The volume moved and `memory.json` points at the old model paths | `docker exec footnote footnote models use bekko-a8m gte-small` (Section 4) |
