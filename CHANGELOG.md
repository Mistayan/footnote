# Changelog

Notable changes to Footnote, newest first. Versions follow semantic versioning, with the bump rule in
[docs/VERSIONING.md](docs/VERSIONING.md). From 16 November 2026 the entries start from
Conventional Commits with git-cliff (`cliff.toml`) and are edited for readers; earlier entries were written by hand. A version's
section is also its GitHub release notes.

## 0.6.0 - 2026-11-23

Footnote Lean now rewrites about half of what agents run, up from a third, and fixes a Windows bug that broke the `npx`
and `npm` commands it rewrote. Footnote also runs in Docker as one person's long-lived daemon, and the MCP memory tools
work on the memory database the hooks use.

### New

- **Docker daemon for one person's agents** (#426, by Mistayan): a hardened image (non-root user, pinned base images, an
  allowlist `.dockerignore`) and a Compose daemon that keeps the models loaded and serves both the MCP server and the
  memory hooks through `docker exec`. `scripts/docker-agents.ps1` and `.sh` register both with Claude Code, Codex, Gemini
  CLI and Antigravity, add no double hooks, and `--remove` takes out only the Docker entries. `FOOTNOTE_PATH_MAP` turns
  Windows host paths into container paths and refuses `..`. Git queries no longer run a repository's `core.fsmonitor`
  program or filter driver, which a mounted repository could use to run code. Hook latency through Docker Desktop:
  210 ms median. See `DOCKER.md`.
- **MCP memory tools on the memory database** (#440, by Mistayan): `footnote_recall`'s `project` is now the memory scope
  (that project's memories plus the global ones), so a project-scoped recall finds memories. `footnote_wake_up` returns
  the session-start memory pack, `footnote_remember` embeds with the models `footnote models use` configured, and MCP
  recalls count in the activity log (ids only, never the query). Before the first memory, the read tools answer empty
  instead of "database not found".

- **Compound lines with groups** (#582): a line with a subshell, script block, `$(…)` or input redirect is no longer
  skipped as a whole. Only the part holding it is left alone, and the parts around it are still rewritten: after
  `if ($LASTEXITCODE -eq 0) { cargo test }`, a `git push` line is wrapped. Bash keywords that start a part (`then`, `do`,
  `else`, `time`) are skipped when finding the program.
- **Stderr redirects** (#582): a part that sends stderr elsewhere (`2>/dev/null`, `2>$null`, `2>err.txt`) runs as
  `footnote run --raw-stderr`, a new flag that keeps the program's stderr out of the filtered output so the redirect still
  applies.
- **More commands** (#582): git fetch, pull, push, checkout, switch, add, commit, worktree, stash, ls-files and other
  subcommands; `npm ci/install`, `npx` and `npm run` builds, tests and deploys, `uv sync/lock`, `gh`, `cargo fmt/install`,
  `make`, `docker build/logs`, `kubectl get/logs`, `find`, and `ls` in bash. Commands that wait on the user or keep
  running are left alone: `git commit` without a message, `git rebase -i`, `git add -p`, dev servers and followed logs.
- **Shorter `ls -l` and git output** (#583): `ls -l` keeps each entry's name, size and kind (`dir/`, `tool*`,
  `link -> target`) and drops the permission, owner, group and date columns, 72-76% smaller on real listings; dates stay
  for `-t` and `--time-style`. git push, pull, fetch and clone drop progress lines, `remote:` banners and hints, and the
  one-per-file Windows line-ending warnings become one line.

Coverage of sampled agent commands: Claude Code 49.8% (0.5.0: 35.2%), Antigravity 56.5% (35.8%).

### Fixed

- **Windows: `npx`, `npm` and `find` under `footnote run`** (#582): `footnote run` could not start `.cmd` shims, so
  rewritten `npm test` and `npx vitest` commands failed with "program not found", and `find` started
  `C:\Windows\System32\find.exe`. Programs are now found on `PATH` the way the shell finds them.
- **In-app update with an older launcher** (#585): the update check compared only the engine's version, so after an
  engine-only update (`footnote update --from`, a release zip) the launcher's update button said "up to date" while the
  launcher itself stayed behind. The check now counts the older of the engine and the launcher beside it, so the
  installer, which replaces both, is offered.

## 0.5.0 - 2026-11-23

Footnote now reaches Claude Code profiles kept with `CLAUDE_CONFIG_DIR`, which had no hooks or MCP server at all, and
Footnote Lean covers more of what agents run.

### New

- **`tail` pipes and global options** (#580): a command piped into `tail -N` or `Select-Object -Last N` is now compacted
  too. It runs as `footnote run --no-footer`, a new flag that leaves out the closing `[footnote: …]` note so `tail` still
  returns the program's last lines; the pipe and its exit code are unchanged. `git -C <dir> status` and
  `cargo +nightly test` are recognised. Coverage of sampled agent commands: Claude Code 35.8% (0.4.0: 32.0%), Antigravity
  33.8% (31.8%).

### Fixed

- **Claude Code profiles beside the default** (#579): with `CLAUDE_CONFIG_DIR=<dir>`, Claude Code reads
  `<dir>/settings.json` and `<dir>/.claude.json`, which `footnote install` never wrote. Install, uninstall and status now
  cover the variable's folder and any other `~/.claude*` folder holding both `projects/` and `.claude.json`. Run
  `footnote install` again to set them up.
- **git status:** the closing hint (`no changes added to commit …`) was listed as an untracked file (#580).

## 0.4.0 - 2026-11-23

Footnote Lean compacts far more of what agents actually run: compound commands such as `cd x && cargo test | head -40` and
`Set-Location x; git status && git diff` are now rewritten part by part, which lifts coverage from about 1-3% to about 32% of
Claude Code's and Antigravity's shell commands. Models get their own screen, GGUF import and a choice of how long they stay
in memory.

### Breaking

- **`footnote_code` takes `op` and `target`** (#561). The nine mode fields (`name`, `outline`, `unresolved`, `map`, `impact`,
  `stack`, `frame`, …) are replaced by `op` (`symbol` by default, `impact`, `outline`, `unresolved`, `map`, `stack`, `frame`)
  and `target`. A call with the old fields now fails with an error naming the new ones. Agents pick up the new schema when
  they restart their MCP session.

### New

- **Lean rewrites compound commands** (#574). Each part of a line that runs a filtered program gets `footnote run -- ` in
  front, and every other byte is kept, so `&&`, `||`, `;`, `cd`, `$env:` and exit codes behave as before. A part is left
  alone when its output goes to a file, its stderr is discarded, or it pipes into anything but `head` or
  `Select-Object -First`. Claude Code's PowerShell tool now reaches the hook too; run `footnote install --lean` again to
  widen its matcher.
- **Smaller MCP tool list** (#561): `tools/list` drops from 4,963 to 3,749 bytes. Unknown arguments are now refused instead
  of ignored, and `op: map` with a `target` keeps one block, as `code-map --block` does.
- **Models** (#555, #557, #558):
  - Choose how long models stay in RAM (`memory.idle_seconds`, "Keep in memory" on the Models screen); the daemon unloads
    them when idle, even with sessions open.
  - `footnote models import <file.gguf>` adds a GGUF embedding model from a file.
  - The Models screen shows ranked cards, with "Load a GGUF model…".
- **MCP results are compact** (#511): one line per hit with the untrusted-data label once, several ids in one
  `footnote_get`, and lexical results when hybrid recall is unavailable.
- **Skills** (#470, #471, #551): agent edits are kept to the step that failed, Codex sessions count toward skill outcomes,
  and a new skill guides the choice of a Rust GUI stack.

### Fixed

- **GGUF models a build cannot load are refused** (#559): `footnote models use` stops with a clear message on a build
  without llama.cpp, and `footnote update --from` warns when the new binary lacks it.
- **The background service exits once an update replaces its binary** (#552), so the next hook call runs the new build.
- **`footnote status` and the session-start hook say when recall is keyword only** (#553).
- Audit fixes across indexing, recall, `footnote run`, Codex support and dependencies (#544).

## 0.3.0 - 2026-11-22

Projects you can act on from the launcher: commit and push in one click, add or ignore a project, and open its folder at
once. The Code screen gets a zoomable architecture map. Coming from 0.2.0, the launcher offers this update itself.

### New

- **Commit and push now** (#531): the commit pictogram runs the agent you last used in that project, unattended, to make
  logical commits and push them (`footnote agent-commit <project>`). It never force-pushes, rewrites history or edits files,
  and it names anything it left out (generated, unintended or secret files). The pictogram spins while it runs, and a note
  reports what was committed, pushed and left. Claude Code runs with git commands only; Codex runs in its workspace sandbox.
  With neither installed, it falls back to the request queued for the next turn.
- **Projects** (#526):
  - `footnote projects add <folder>`, `ignore <name>` and `unignore <name>`. An ignored project is no longer recorded; its
    memories stay.
  - On the Projects screen: an Ignore button on each card with Undo, a list that restores ignored projects, and **Add
    project**, which opens the launcher's own folder browser. Folders that no longer exist are hidden.
  - Opening a project's folder takes 0.05 s instead of 5 to 6 s.
- **Code › Architecture, zoomable** (#529): the project's blocks laid out left to right, each card with its manifest
  description or module doc. Selecting a block lights what a change would affect and what it relies on. Double-click opens
  a block's files (`footnote code-map --block <path>`); drag pans, the wheel zooms, Esc goes back up. The Symbol tab can show
  both sides, only the callers, or only what it relies on.
- **Launcher:** the scroll rail is sparser, magnifies under the pointer, and scrolls the popover menus too (#524).

### Fixed

- **The mini window shows again** (#528). In 0.2.0 the tray and the Mini button hid the main window and showed nothing. It
  now has rounded corners and no white edge on Windows 11.
- **Large repositories read as fully committed.** With more than about 4 KB of `git status`, the hook waited 5 s and saw no
  changes; it now reads git's output while git runs (#526).
- Long memory text on the Code screen wraps inside its card.
- The release notes lead with the Windows installer (#522).
- The Docker image compiles again: the build copies the session rules the binary embeds (#536, from @Mistayan).

## 0.2.0 - 2026-11-22

The first release with a plain version number (#507): from here every version is `X.Y.Z`, and the commits since the last
release decide which number moves (`docs/VERSIONING.md`). The headline is a reworked launcher that updates itself. Coming
from 0.1.0-alpha.3, install this one with `Footnote-Setup-0.2.0-x64.exe`; later releases arrive in the app.

### New

- **Launcher, reworked** (#503):
  - **Look:** five palettes (Afterglow, Graphite, Midnight, Ember, Daylight) from the Options gear; glass sidebar, top bar,
    menus and tooltips; squircle corners; popover menus, sliding tabs, a spring switch, and a tick rail instead of the
    scrollbar.
  - **Projects:** one card per project. The folder opens in Explorer, and pictograms show memories, the code graph and work
    to commit.
  - **Send to the agent:** the red commit pictogram asks the agent working in that project to commit and push
    (`footnote agent-ask`). Its next turn there takes the request once; a click withdraws it while it waits.
  - **Agent repair:** each agent is green, amber or red by whether its Memory hooks and MCP server are connected; a wrench
    reconnects them (`footnote install --memory`).
  - **Models, Memory, Activity:** a header with the active model; memory rows that open in place; only the days something
    happened, each opening its recalls.
  - **Updates in the app:** the launcher checks GitHub's latest release at start and every six hours. A newer one shows what's
    new; one click downloads it and checks its SHA-256, the next installs it with no window and reopens Footnote. Agents get
    a note to restart, since their running MCP server is the old binary until they do (`footnote update --check`,
    `--download`).
  - **Mini window:** the tray's quick look is now a small widget with one number per card (memory, today's usage, work to
    commit, agents, Library and Code) and its own minimize, open and close buttons.
  - Earlier in this release: a frameless shell with Memory, Library and Usage screens (#478), rate limits, the cost split, the
    review queue and the docs cache (#343), skill changes reviewed as a diff (#476), measured savings in Tokens by type, the
    daily chart read per provider on hover, and indexing projects from the Projects screen.
- **Memory:**
  - Recall looks at what the prompt names first: memories anchored to the files and symbols in it come before the semantic
    matches, and each recall, miss or skip is logged without its text (#241).
  - Injected memory is byte-identical from run to run, so the agent's prompt cache keeps it (#242).
  - Recall packs short pointers instead of whole memories past the first few, with two floors that keep weak matches out
    (#356).
  - `footnote memory-clean` retires stale project memories: exact duplicates and old session notes by rule, then the project
    memories a model judges stale through your own Claude Code or Codex. Session start runs it every 7 days
    (`memory.clean_days`, 0 turns it off); every retirement can be restored, and global memories are never sent (#437).
- **Lean:**
  - A whole-file read of a large indexed file is answered with its outline, so the agent reads only the part it needs
    (`install --lean` now also covers Claude Code's Read) (#240).
  - Opt-in Lean B rules at session start, with a check that durable prose stays readable (`memory.lean_rules`,
    `memory.lean_prose`, both off by default) (#239).
- **Code:** the code map names the symbols each link uses, classifies more outside packages (#475), and leaves dot folders
  and `.footnoteignore` paths off the map.
- **Library:** a docs refresh skips pages it found empty for 30 days, then tries them once more (#474).

### Fixed

- The code map no longer collapses to a thin strip when the graph has a cycle.
- TypeScript member names keep their trailing digits (`base64`, `retry2`) (#473).
- The release build downloads the tagged engine for the installer (#467).

## 0.1.0-alpha.3 - 2026-11-22

Second alpha. The headline is a Windows installer that brings the desktop launcher, in the tray. Expect rough edges and
breaking changes between versions.

### New

- **Windows installer** (`Footnote-Setup-0.1.0-alpha.3-x64.exe`, #125): the engine and the desktop launcher in one step, for
  your user, with no administrator rights.
  - **Always added:** a Start menu shortcut.
  - **On by default:** Footnote starts in the tray (notification area) when you sign in, and goes on PATH. Both can be
    unchecked.
  - **Off by default:** a desktop shortcut, and connecting the coding agents found now (`footnote install`).
  - It carries the Visual C++ runtime the engine needs, so it runs on a fresh Windows.
  - **Upgrades:** safe while your agents use Footnote. The old binary is set aside, and their MCP servers keep running.
  - **Uninstall:** takes Footnote out of your agents first, and keeps your data.
- **Launcher:**
  - It starts in the tray without opening a window, and runs once: opening it again shows the window that is already open.
  - A new **Skills** screen: the skill-rewrite switch with its cost, and your review of pending skill changes (#461).
- **Agent skill layer, opt-in** (#453, #455, #458, #459, #460):
  - Agents can propose edits to the skills they use, through `footnote_skill_edit`. Each edit passes check gates, and you
    review it.
  - An edit that does worse in trials is rolled back.
  - Skills that are never read stop being suggested.
  - Off until you turn on `memory.skill_rewrite`.
- **Curated skills:** 23 agent skills rewritten, each with a check script (#439).
- **Library:** search hits carry the crawled page's URL (#438). A refresh re-indexes a page whose words were only reordered
  (#431).
- **Memory:** a project's handoffs retire once delivered (#436).
- **Code:** a Rust project in a subfolder (a Tauri app's `src-tauri`, `backend/`) now gets its compiler indexer (#428).

### Before you install

- **Nothing is code-signed.** Windows SmartScreen asks once: **More info**, then **Run anyway**. Check the file against its
  `.sha256` first.
- **Windows 11 hides new tray icons.** It puts them behind the `^` arrow next to the clock. To keep Footnote visible:
  Settings > Personalization > Taskbar > Other system tray icons > Footnote.
- **Linux needs glibc 2.38 or newer** (Ubuntu 24.04, Debian 13, Fedora 39 or later). The launcher is Windows-only for now.
- Encrypted memory (`--features encryption`) is experimental and not in these binaries.

### Install

- **Windows, with the launcher:** download `Footnote-Setup-0.1.0-alpha.3-x64.exe` below and run it.
- **Windows, command line only:**
  `powershell -ExecutionPolicy Bypass -c "irm https://github.com/bobcat88/footnote/releases/download/v0.1.0-alpha.3/footnote-installer.ps1 | iex"`
- **Linux x64:**
  `curl --proto '=https' --tlsv1.2 -LsSf https://github.com/bobcat88/footnote/releases/download/v0.1.0-alpha.3/footnote-installer.sh | sh`

Then follow [HOW-TO.md](https://github.com/bobcat88/footnote/blob/main/HOW-TO.md) to connect your agents.

## 0.1.0-alpha.2 - 2026-11-21

### Added

- **library:** Documentation crawler, system TLS roots, overnight benchmarks
- **search:** Structure-aware chunks, heading path, extraction fix (#19)
- **search:** Lean search output, one passage per page for docs (#20)
- **models:** Installable French model (Jina v5 nano), llama in releases (#22)
- **memory:** Recall by meaning on each prompt, on by default (#23)
- **alias:** French identifier rules with check digits, alias-scan (#25)
- **search:** Hybrid by default when the corpus models are installed (#27)
- **memory:** Tags and scope as pre-filters before ranking (#28)
- **memory:** Tag engine, tested and left off (any@3 0.91 to 0.87) (#29)
- **alias:** Name model and keyed pseudonyms inside the binary (#31)
- **models:** Install Alias's detector, every file pinned (#32)
- **code:** Stage 1, a code graph from rust-analyzer's SCIP index (#33)
- **code:** Footnote_code MCP tool for agents (#44)
- **projects:** Every project an agent opens, listed with its state (#45)
- **status:** Footnote Code in the product overview (#46)
- **code:** Include Code in the free default build (#53)
- **code:** Architecture map from the compiler index (#54)
- **launcher:** Tauri window with the Overview screen (#55)
- **usage:** Token counts and list prices from agent session files (#56)
- **launcher:** Code screens, architecture map and symbol view (#59)
- **launcher:** Projects, Models, Activity and Usage screens (#60)
- **launcher:** Mini mode, the lens window (#61)
- **memory:** Opt-in encrypted personal store (experimental) (#65)
- Per-product switches for Library and Code (#68)
- **usage:** Measured savings from RTK, kept apart from cost (#70)
- **launcher:** Product switches on the Overview cards (#72)
- Footnote find, one search across the switched-on products (#73)
- **launcher:** Search screen over Memory, Library and Code (#74)
- **launcher:** Install a model from the Models screen (#78)
- **launcher:** Live in the tray; closing a window hides it (#79)
- **search:** Reuse vectors by text across files and versions (#80)
- **memory:** Memory-review lists candidates; memory-restore undoes (#81)
- **library:** Footnote corpora lists, adds and removes corpora (#143)
- **memory:** Activity shows which memories reached which prompt (#161)
- **usage:** Measure Footnote's own lean search results (#165)
- **usage:** Count DeepSeek Harness tokens; name what is not measured (#168)
- **encryption:** Memory runs on an encrypted personal store (#177)
- **encryption:** Keep decrypted memory out of Windows crash reports (#178)
- **code:** TypeScript/JavaScript and Python projects through SCIP (#180)

### Fixed

- **library:** Crawler saves each page once (.md, HTML and trailing-slash forms)
- **search:** Plain Windows paths in results, backlog up to date (#30)
- **models:** State every default model's licence (#43)
- **daemon:** Keep an agent's tools when the shared daemon stops (#67)
- **find:** Keep test corpora out of the user's corpus list (#75)
- Keep test runs out of the real state folder; cap footnote jobs (#77)
- Write each log line in one append so parallel writers never mix (#166)
- **audit:** A starting server waits for an append instead of refusing (#169)
- **code:** Run scip-python on Windows without editing its package (#181)

### Performance

- **search:** One lock per model; keyword search outside its lock (#171)

### Documentation

- **library:** Documentation storage and crawler study; pre-registered crawl bench
- **research:** Alias desk study, remote access, launcher catalogue (#21)
- **federation:** Rights from company SSO, inside the agent session (#34)
- **roadmap:** Free and commercial editions, one engine (#35)
- **roadmap:** Free edition, private data and five linked devices (#36)
- Today's claims checked against their sources (#37)
- **roadmap:** Footnote One and Footnote Enterprise, the split (#38)
- **roadmap:** Editions review, encryption rule, licence options (#39)
- **roadmap:** Footnote One stays Apache-2.0 (#40)
- **p1:** Launcher lists Enterprise modules, muted, no nagging (#41)
- **p1:** One quiet support link in the launcher (#42)
- **backlog:** How T3 Code gets usage, cost and limits (#47)
- **design:** Lock the launcher, D1 full window with D2 mini mode (#48)
- **backlog:** Spend and savings module, design rules (#49)
- **code:** Architecture map, how open projects build it (#50)
- **roadmap:** Overnight plan for 17 November (#51)
- **roadmap:** Add five overnight goals at launch (#52)
- **bench:** Memory encryption build check, blocked on Perl (#57)
- Overnight catch-up and morning report (#62)
- **roadmap:** Fix the install folder path in the morning report (#63)
- **roadmap:** Restore the backslash path in the morning report (#64)
- **roadmap:** Plan the encrypted personal corpus (#76)
- Epics, user stories and the definition of done (#82)
- **roadmap:** Migrate issue tracking to GitHub Issues (#164)
- **encryption:** Derived-data audit of the personal store (#174)

### Tests and benchmarks

- **docs:** Fresh 40-question confirmation set and protocol, written before running; crawler keeps same-host redirect scope only
- **docs:** Confirmation verdict (worse), sealed held-out set 3 and optimisation protocol; crawler cites the HTML page for Markdown copies
- **bench:** Alias evaluation set v1 and rules, before any detector (#24)
- **bench:** Alias rules plus OpenAI Privacy Filter pass on held-out (#26)
- **bench:** Reranker abstention gate fails on dev (goal 9) (#69)
- **bench:** Bge-reranker candidate stopped before scoring (#71)
- Keep usage tests out of the user's real agent sessions (#170)
- **bench:** Shared daemon +54 to +58 % throughput, same rankings (#175)
- **hook:** Hook.log never quotes prompt or memory text (#176)

## 0.1.0-alpha.1 - 2026-11-15

Private pre-release (GitHub Releases, Windows and Linux x64, built with dist).

### Added
- `footnote status`: what is installed, on, registered and running, and what memory did this week (the launcher's overview).
- `footnote options` and `footnote config get/set`: the options catalogue, memory on/off, and a company policy file
  (`%ProgramData%\footnote\policy.json`, `/etc/footnote/policy.json`) that settings cannot override.
- `footnote uninstall --memory`.
- Model manager: `footnote models list/install/use/remove/recommend`, with hardware detection (GPU vendor, VRAM, CPU, RAM);
  downloaded models stay out of any git repository.
- Memory scope is the repository's remote name (folder name as fallback); `footnote memory-rescope`.
- Live progress of long steps (`footnote jobs`, `<state>/jobs/<id>.json`), `footnote memory-list`, `footnote activity --days`.
- Release workflow (dist): GitHub Releases for Windows and Linux x64.

### Changed
- The repository is a Cargo workspace (ADR 0001): `footnote-core`, `footnote-search`, `footnote-library` and `footnote-memory`
  under `crates/`, the `footnote` executable at the root. Library and Memory are features of the executable, on by default.
- The memory hook runs in Rust (`footnote hook`); the Python hook is gone. Per-prompt recall about 24 ms in-process.
- Embeddings are computed in-process with ONNX Runtime; no Python on the search or memory path.
- Product site and QLoop passes moved under `design/`.

### Added
- Opt-in resident daemon for recall by meaning on each prompt (`"resident": true`, off by default until its relevance cutoff passes).
- Memory visibility: agents say when a memory shapes an answer and give a one-line receipt after each save.
- Opt-in metrics build (`--features metrics`) and `footnote metrics`.
- CI on Windows and Linux: format, clippy for every product combination, tests.

### Fixed
- Audit chain fork when two MCP sessions wrote at once.
- Long accented prompts failed memory recall (512-byte query limit).
