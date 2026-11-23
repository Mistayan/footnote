# Shared context plan

Issues #510 and #513. Measure thresholds under #509. Use the repeated-work benchmark in #520 after the replay passes.

## 1. Resolve project scope and repair old names

Use the same project resolver for hooks, project registration and MCP session binding. Repositories with an origin keep the existing lowercase repository name. A linked worktree without an origin uses the name of its primary checkout. A scratch directory maps to a project only when the project registry or an explicit mapping establishes the association. An unknown directory must not acquire another project's scope through a shared folder name.

Canonicalize new scope values before writing metadata or hashing the memory. Match case and surrounding whitespace. Reserve global and personal scope names so a project with either repository name cannot impersonate those scopes. Keep explicit CLI project renames usable.

Migrate existing names in a SQLite transaction. Keep chunk and source IDs, tags, anchors, supersession links and status. Verify the source path used for duplicate detection follows the canonical scope. Report collisions and preserve both records until their links and metadata can be reconciled. Check SQLite, FTS and Tantivy views on a disposable database. A heading change affects embedding signatures, so check lexical and hybrid recall after refreshing the affected derived data.

Enforce visibility before ranking and again on direct reads. The same policy must cover packs, anchor hits, recall, get by ID, paging, pointers and all-corpus aggregation. Treat caller-supplied project arguments as filters within an already established session scope. Reserve personal reads for an explicitly authorized personal session. Legacy records marked global need an owner review before any move into the personal scope. Test with synthetic records.

## 2. Bind hook and MCP events to the same session

Prefer a session or turn ID verified from the host. Before relying on process ancestry, measure the hook and MCP launcher chains for Codex, Claude Code and Antigravity. A PID is a discovery hint. Verify process start identity and bind it to the actual host session and canonical scope. Resolve it before proxying into the daemon, whose parent process is shared. Test concurrent sessions, a reused PID, a process serving several conversations, worktrees and cross-project requests.

Store a short-lived ledger under the private state directory. Key each entry by session, scope, turn, and database or corpus identity where relevant. Store IDs, accounting and outcomes only. Use a transaction to reserve space and claim an item before emitting it. A source can retry without spending the budget twice. If binding is ambiguous, keep scope isolation and record that the source could not share state. Do not claim cross-channel deduplication for that session.

## 3. Share one budget across context sources

Render candidates deterministically and debit the actual rendered response, including framing, before emitting it. Use a supported model tokenizer when available and a conservative, documented estimate otherwise. Count start packs, prompt and tool hooks, skills, Lean instructions and MCP memory responses in the same turn budget. Limits on old inputs remain interface contracts. The shared cap is the last check.

Use a stable tie-breaker so replaying the same ordered events gives the same output. Keep distinct states for a pointer and full text. A permitted record already shown in full returns only its ID and an already-shown marker. A pointer can be upgraded once if the record is still visible and the budget allows it. A private record produces neither a marker nor a pointer outside its scope.

Use the #509 baseline to estimate full-text use, the cost of a lookup and expected remaining calls. Push full text when the estimated avoided lookup cost exceeds the expected cost of rereading it. Test both sides of the decision and the empty-budget and overflow cases. Record the chosen values and confidence limits next to the replay. Keep session activity opt-outs and retention settings effective.

## 4. Move recall closer to the task

Keep session start to project context, the most recent valid handoff, known open work and rules explicitly marked as binding. Offer other preferences only when their topic matches. Start with the existing prompt signals and anchor lookup.

Register native hooks only where each host exposes the event. Before an edit or initial exploration, query file and symbol anchors plus relevant dependents. Before filing an issue, search existing issues and locked decisions. After a failed command, retrieve a matching fix using redacted error signals. Respect the existing Lean rewrite and tool-result contracts. Keep raw prompts, commands and transcripts out of persistent activity.

## Replay and release gates

- Establish a frozen baseline of per-source precision, misses, calls, fixed tokens and re-read tokens under #509. Existing MCP logs count recall IDs but lack hook session binding and get outcomes.
- Replay isolated fixtures for hook then get, get then hook, same ID in different databases, two concurrent sessions, a personal record sought by ID, and a worktree handoff read from its primary checkout.
- Replay the measured session locally with the relevant design decisions annotated. Publish only aggregate counts or sanitized fixtures. Check the start pack, three target decisions, replay determinism, budget ceiling and recurrence of already-shown items.
- Compare paired tasks under #520 once the replay and scope checks pass. Measure successful completion, exploratory calls and cache reads before drawing a cost conclusion.
