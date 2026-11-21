# Skill edit request cost (#456), 2026-11-21

Question: what does one Footnote skill edit request (`memory.skill_rewrite`, #446) cost an agent, measured on real sessions?

Result: the request caused 3 more model calls in both sessions: 120,808 cache-read, 2,134 cache-write and 844 output tokens at a 40k-token context, and 444,268 cache-read, 2,217 cache-write and 970 output tokens at a 148k-token context; about 3 times the context in cache reads, plus 2k written and 1k out.

## Setup

- **Agent:** Claude Code 2.1.330, headless (`claude -p`), model Sonnet 5.5, on the maintainer's Windows 11 machine, 21 Nov 2026.
- **Isolation:** each session ran with `--setting-sources project` and `--strict-mcp-config`, its own `FOOTNOTE_STATE_DIR` and its own project folder. The only hooks were the test's (`SessionStart`, `UserPromptSubmit` and `Stop` calling `footnote hook`), and the only MCP server was `footnote-memory`.
- **Footnote:** a debug build of the #448 branch tip, the whole skill stack. Settings: `skills: true`, `skill_rewrite: true`, `every_turns: 1000`, handoffs off. With those settings, the skill edit request is the only Stop request.
- **Allowed tools:** `Read`, `Edit`, `Write`, `Bash(node:*)`, `footnote_skill_edit`.
- **Project:** a git folder holding `menu.css` (a `.dropdown` with no transition) and a `CLAUDE.md` saying "When Footnote suggests a skill that fits the task, follow it, including any check it asks you to run."
- **Prompt:** "Add a fade transition to the dropdown in menu.css when it opens."
- **Skill:** one curated skill, `css-fade`, indexed as theme `demo`. It is wrong on purpose: its text asks for the `transition` shorthand, but its check script demands a `transition-duration` declaration.

  ```md
  1. On the closed element set `opacity: 0` and `transition: opacity 160ms ease` (the shorthand).
  2. On the open state (for example `.dropdown.open`) set `opacity: 1`.
  3. Check the file: `node <skill>/scripts/check.mjs <css file>`. It must print OK.
  ```

  ```js
  if (!/transition-duration\s*:/.test(css)) { console.error('FAIL: no transition-duration declaration'); process.exit(1); }
  ```
- **Context sizes:** the small session had no added context. The large one appended 290 KB of this repository's docs to the system prompt (`--append-system-prompt-file`). That kept the user prompt short, so the hook's 500-character suggestion query stayed the task.

## Method

`bench/skill-edit-cost/split.mjs` reads the session file. It counts each API call once, by message id, and splits the calls at the line carrying the Stop hook's request ("Footnote: you read the skill …"). Calls before it are the task; calls from it on are what the request caused. The token counts are the API's own `usage` fields.

## Results

| Session | Context at the request | Part | Calls | Cache read | Cache write | Input | Output |
|---|---|---|---|---|---|---|---|
| small | 41,610 | task | 4 | 143,367 | 9,942 | 8 | 1,798 |
| small | 41,610 | **request** | **3** | **120,808** | **2,134** | 8 | **844** |
| large | 149,509 | task | 4 | 465,132 | 119,666 | 8 | 1,706 |
| large | 149,509 | **request** | **3** | **444,268** | **2,217** | 8 | **970** |

Whole-session cost reported by Claude Code (`total_cost_usd`, list prices, task and request together): $0.101 for small, $0.605 for large.

**What the agent did:**
- Both sessions read the suggested skill and ran its check. The first runs failed; the agent then made the check pass by adding `transition-duration`.
- Stop asked once. In both sessions the agent judged the skill wrong, not its own code, and changed `SKILL.md` through `footnote_skill_edit`, as a global, prose-only change that goes live. It left the script alone.
- The large session also added an unrelated step about `pointer-events` to the skill. The trial (#447) exists to catch edits like that.

## Reading

- **The request costs one more round of the agent loop.** Here that was 3 calls, each re-reading the whole context from the prompt cache. Cache reads therefore grow with context size: 2.9 times the context in the small session, 3.0 times in the large one.
- **Cache writes and output stay small:** about 2k and 1k tokens.
- **In fresh-input terms.** A cache read is commonly priced at a tenth of a fresh input token. On that basis, the request costs about as much as sending 30% of the context once as fresh input, plus about 1k output tokens.
- **The request is rare.** It fires at most once per session, and only after a suggested skill was read and its script failed.

## Limits

- **Small sample.** One session per size, one model, one deliberately broken skill. The number of calls depends on what the agent does (read the skill again, write one file or several), so 3 is an observation, not a constant.
- **Excluded:** later sessions re-reading the changed skill, trials and rollbacks are not in these numbers.
- **Observed while setting up.** A longer prompt ("In menu.css, add a fade transition to the dropdown when it opens (.dropdown.open). If a skill is suggested for this, follow it, including its check. Keep the change small.") got **no** suggestion. Its extra topic words put the skill under the 40% coverage rule of LEAN-05, so the instruction moved into `CLAUDE.md`.
- **Two runs were discarded:**
  - The first small session ($0.059) used that longer prompt, so nothing was suggested.
  - A first large session ($0.87, 480 KB of padding, about 216k tokens) stopped at the account's usage limit before the task started.
- **Total spent:** about $1.63 for the experiment.
