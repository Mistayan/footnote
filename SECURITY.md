# Security policy

Footnote is a local tool that serves your own documents to your own agents. It opens outbound network connections only in commands you run yourself (`footnote models install`, `footnote crawl <url>`, `footnote docs add`, `footnote docs refresh`, `footnote docs install <url>`) and in `footnote find`'s fetch on miss, which reads up to 3 pages of an already cached docs site when no cached passage matches well and never sends your query (`FOOTNOTE_NO_LIVE_FETCH=1` turns it off; see the README's security model), and its MCP tools cannot write to your documents; the only write tools add or retire agent memories in a separate memory database and, only when you turn on `memory.skill_rewrite`, change a copy of a skill in the state folder (see [Agent skill edits](#agent-skill-edits)). Agent memories are written by the agent you already use, into a local file; no other model receives your conversation. Once a week, that agent's CLI also reviews your project memories (see [Memory cleaning](#memory-cleaning)).
The model that describes what it defends against is in the README under [Security model](README.md#security-model).

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private reporting:
**Security → Report a vulnerability** on this repository.

Include what you did, what you expected, what happened, and the version (`footnote --version`) and operating system.

## In scope

- Anything that lets retrieved text act as an instruction to the server or to the agent beyond being labelled data.
- Any way for an MCP client to write to the corpus, read outside the indexed roots, or bypass the audit log.
- Weaknesses in the daemon's local socket authentication, the audit log's hash chain or MAC, or the private state folder. (Known limit, not a vulnerability: a hash chain cannot show that its newest entries were cut off; keep the last verified hash elsewhere.)
- A way to make the embedding encoder load a model that does not match its pinned manifest.
- Resource exhaustion through a query, a document or a helper response that the documented bounds should have stopped.
- Any way for `footnote_skill_edit` to write outside the agent skill layer, change a curated skill, or make a change to a skill's scripts served without the user's approval.
- In the official Docker setup (`Dockerfile`, `compose.yaml`): any path-traversal bypass in `FOOTNOTE_PATH_MAP`, privilege escalation out of the non-root container (`UID 10001`, `--network none`, `--read-only`, read-only workspace mounts), or a mounted repository (its files or its `.git/config`) that makes Footnote start a program inside the container.

## Agent skill edits

With `memory.skill_rewrite` on (off by default), agents get `footnote_skill_edit`. Skills are instructions that every later agent follows, and some carry scripts that agents run. An agent that read hostile text could try to turn one injected instruction into a standing one, or into code. The defences:
- **Only copies are written.** Edits go to the agent skill layer in the state folder (`skills/agent/`). The curated skill is never written. Paths must stay inside the skill folder, and a skill holds at most 200 files and 2 MB.
- **Every revision is kept.** `footnote skills revisions` shows each one, with who made it and why. `restore` and `drop` undo any of them.
- **Script changes wait for the user.** A change that touches anything but Markdown is stored as pending and is not served until `footnote skills approve`. Only one can wait at a time. Session start and `footnote memory-review` say that it is waiting. The approval is refused if the skill changed in the meantime.
- **The review shows the code.** `footnote skills diff` and the launcher's Skills screen show a pending change line by line against the version it would replace, and the launcher can open its folder. The launcher's page names only the skill: the folder path comes from the engine, so a page cannot make the window open an arbitrary path.
- **Footnote never runs a skill's scripts.** It does not run them to check a change either. The agent runs them in its own shell, under its own permission prompts.
- **Rewrites wait too.** A Markdown change that changes more than 6 lines of `SKILL.md`, or more than a quarter of a skill over 24 lines, is held as pending like a script change (#470). The edit request names the script that failed and asks for a change to its step only.
- **What remains:** a small Markdown change goes live without review, so an injected instruction of a few lines can still reach later sessions through prose. It is limited to the skill's own folder, visible in the revision history, and reversible. Treat `skill_rewrite` like any setting that lets agents write instructions for other agents.

## Memory cleaning

Every `memory.clean_days` (7 by default; 0 turns it off), the next session start runs `footnote memory-clean` in the background. It sends up to 400 project memories, each cut to 300 characters, to Claude Code (Haiku) through its own CLI and sign-in when selected. With Codex selected, all cleaning stays local. Footnote stores no API key, and the run uses the user's own subscription. Conversations and global memories are never sent. Memory text may carry injected instructions, so:
- **The agent runs without tools**, in an empty folder, with Footnote's own hook off: Claude Code receives `--tools ""` and `--strict-mcp-config`. When Codex is selected, Footnote runs only its local deterministic rules because Codex exec has no tool-free mode.
- **The model only names ids.** Ids outside the memories it was sent are ignored, and global memories are never sent, so it cannot retire one.
- **A run is capped.** A run that would retire more than 15% of the live memories retires nothing and leaves a warning in `footnote status`.
- **Every retirement can be undone.** `footnote memory-restore <id>` brings a memory back, and the run's report lists each id with its reason.

## Container security boundary (`Dockerfile`, `compose.yaml`)

When running Footnote inside Docker (for example on Windows hosts where Application Control blocks local unsigned builds), the container preserves the same local-only, read-only threat model:

- Runs as dedicated non-root user `footnote` (`10001:10001`) with `ENTRYPOINT ["footnote"]`, `cap_drop: [ALL]`, `no-new-privileges`, and `--read-only` rootfs (writable `/tmp` tmpfs only, `noexec`).
- Uses `--network none` for offline CLI, MCP, and daemon workloads. Only the explicit network commands (`models install`, `docs add`, `crawl`) use a bridged network, never `--network host`. The Compose `footnote-net` service that runs them mounts no workspace, so the one container that can reach the network sees no repository.
- Stores secrets, databases, and daemon sockets inside a named Docker volume at `/state` (`0700`), never on a host bind-mount.
- Mounts user repositories read-only (`:ro`). Host-to-container path translation (`FOOTNOTE_PATH_MAP`) is operator-configured via environment variable only, matches full path-segment boundaries, and fails closed on `..` traversal segments before `known_project()` and `no_links()` run. Agent session files are not mounted into the container.
- Git trusts mounted repositories for ownership (`safe.directory`) only at `/workspace` and `/workspaces`, never `*`. Every git query Footnote runs turns `core.fsmonitor` off on the command line. `git status` is skipped for a repository that defines its own filter driver. So a repository's `.git/config` cannot start a program next to the state volume.
- The Compose daemon is bounded (`pids_limit`, `mem_limit`, rotated logs), so one runaway agent cannot exhaust the host.
- Base images are pinned by `@sha256` digest. The ONNX Runtime archive that `ort-sys` downloads at build time is checked against the hashes pinned in that crate, which `Cargo.lock` pins in turn. Dependabot proposes refreshed digests every week, so the runtime image picks up Debian security fixes.

### One person per container

Docker support is for one person: their agents, sessions and MCP hosts using one memory, as on a host. **Anyone who can use the Docker engine can read, change and delete every memory in the state volume** (through `docker exec`, `docker cp`, or another container on the volume), so a stack shared between people is not supported.

- **Backups** (`footnote backup`) hold every memory in clear text. Store them with the same access rules as the volume.

## Out of scope

- An attacker who already has write access to your user account, the database file or the state folder: they can change anything Footnote can read.
- Quality of retrieval results (use a normal issue, with the benchmark protocol in `bench/`).
- Vulnerabilities in third-party models or libraries, unless Footnote's use of them is the cause.
