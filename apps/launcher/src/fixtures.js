// Invented sample data, shaped like the engine's real JSON, for browser screenshots only (`?mock=1`). Never shown in the app.
const models = {
  folder: "C:/Users/sample/AppData/Local/footnote/models",
  memory_uses_from_elsewhere: [],
  models: [
    { name: "bekko-a8m", installed: true, bytes: 164462521, license: "MIT", role: "default pair, multilingual half", used_by_memory: true },
    { name: "gte-small", installed: true, bytes: 34726087, license: "MIT", role: "default pair, English half", used_by_memory: true },
    { name: "e5-small", installed: false, download_bytes: 135390915, license: "MIT", role: "earlier model, tests and comparison", used_by_memory: false },
    { name: "jina-v5-nano", installed: false, download_bytes: 232883776, license: "CC-BY-NC-4.0 (no commercial use)", role: "French or mixed corpora, opt-in (llama build)", used_by_memory: false },
  ],
};

const status = {
  version: "0.1.0-alpha.3",
  models,
  products: {
    code: { built: true, enabled: true, graphs: 2, rust_indexer: true },
    library: { built: true, enabled: true },
    memory: {
      built: true, enabled: true, memories: 318, saved_last_7_days: 41, recalls_last_7_days: 276, daemon_running: true,
      agents: [
        { agent: "claude-code", hooks: true, mcp_server: true },
        { agent: "codex", hooks: true, mcp_server: true },
        { agent: "deepseek-harness", hooks: false, mcp_server: true },
        { agent: "gemini-cli", hooks: false, mcp_server: false },
      ],
    },
  },
};

const today = new Date();
const iso = (back) => {
  const d = new Date(today);
  d.setDate(today.getDate() - back);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const projects = {
  projects: [
    { name: "atlas-api", path: "D:/work/atlas-api", exists: true, first_seen: iso(20), last_seen: iso(0), memories: 96, code_graph: true, git: { uncommitted: 0, unpushed: 0 } },
    { name: "harbor-web", path: "D:/work/harbor-web", exists: true, first_seen: iso(12), last_seen: iso(1), memories: 31, code_graph: false, git: { uncommitted: 12, unpushed: 3 }, ask: { kind: "commit", asked_at: 1763800000 } },
    { name: "ledger-sync", path: "D:/work/ledger-sync", exists: true, first_seen: iso(9), last_seen: iso(3), memories: 18, code_graph: true, git: { uncommitted: 4, unpushed: 5 } },
    { name: "old-prototype", path: "D:/archive/old-prototype", exists: false, first_seen: iso(30), last_seen: iso(14), memories: 4, code_graph: false, git: null },
  ],
};

const activity = {
  activity_log: true,
  note: "dates in UTC; saves by the date the agent observed; prompt text is never recorded",
  days: [6, 5, 4, 3, 2, 1, 0].map((back, i) => ({
    date: iso(back),
    saved: [0, 3, 7, 0, 12, 9, 10][i],
    prompts_given_memories: [0, 22, 41, 0, 63, 70, 80][i],
    sessions: [0, 2, 4, 0, 6, 5, 7][i],
  })),
  recent: [
    { t: Date.parse(`${iso(0)}T09:12:00Z`), event: "recall", project: "atlas-api", memories: [
      { id: 17, kind: "fact", scope: "atlas-api", observed_at: "2026-11-12", text: "The API keeps cursor pagination; offset pagination was dropped after the slow-count incident." },
      { id: 42, kind: "preference", scope: "global", observed_at: "2026-11-10", text: "Prefers small pull requests, one per piece of work, with tests run locally before review." }] },
    { t: Date.parse(`${iso(0)}T08:40:00Z`), event: "pack", project: "harbor-web", memories: [
      { id: 88, kind: "fact", scope: "harbor-web", observed_at: "2026-11-09", text: "harbor-web deploys from the release branch only; main is for review builds." },
      { id: 9, gone: true }] },
  ],
  most_used: [
    { id: 42, times: 31, memory: { kind: "preference", scope: "global", text: "Prefers small pull requests, one per piece of work, with tests run locally before merging." } },
    { id: 17, times: 24, memory: { kind: "decision", scope: "atlas-api", text: "The API keeps cursor pagination; offset pagination was dropped after the slow-page incident in October." } },
    { id: 88, times: 19, memory: { kind: "fact", scope: "harbor-web", text: "harbor-web deploys from the release branch only; main is for review builds." } },
  ],
};

// The impact radius of `save_order` in the fictional atlas-api project.
const codeImpact = {
  symbol: "save_order", depth: 3, origin: "compiler",
  found: [{ kind: "function", path: "crates/store/src/orders.rs" }],
  callers: [
    { level: 1, name: "create_order", kind: "function", path: "crates/http/src/orders.rs", line: 40, call_line: 52, origin: "compiler" },
    { level: 1, name: "retry_failed", kind: "function", path: "crates/jobs/src/retry.rs", line: 12, call_line: 30, origin: "resolved" },
    { level: 2, name: "routes", kind: "function", path: "crates/http/src/lib.rs", line: 8, call_line: 21, origin: "compiler" },
    { level: 3, name: "main", kind: "function", path: "src/main.rs", line: 3, call_line: 9, origin: "compiler" },
  ],
  tests: [{ level: 2, name: "creates_an_order", kind: "function", path: "tests/orders.rs", line: 5, call_line: 11, origin: "compiler" }],
  counts: { callers: 4, tests: 1, files: 5, compiler_links: 4, resolved_links: 1 },
  files: ["crates/http/src/lib.rs", "crates/http/src/orders.rs", "crates/jobs/src/retry.rs", "src/main.rs", "tests/orders.rs"],
  blocks: ["crates/http", "crates/jobs", "src", "tests"],
  memories: [{ id: 63, text: "Migrations ran twice under two replicas; an advisory lock now guards them." }],
};

const codeMap = {
  root: "D:/work/atlas-api", origin: "compiler", depth: 2,
  blocks: [
    { name: "src", files: 14, symbols: 212, entry: true, memories: { count: 2, recent: [
      { id: 51, kind: "fix", observed_at: "2026-11-14", text: "Requests hung on shutdown because the job queue was dropped first; the server now drains it before exit." },
      { id: 48, kind: "fact", observed_at: "2026-11-09", text: "Every route returns problem+json errors; the old plain-text errors were removed in v2." }] } },
    { name: "crates/http", files: 6, symbols: 96, entry: false, memories: { count: 1, recent: [
      { id: 17, kind: "fact", observed_at: "2026-11-12", text: "The API keeps cursor pagination; offset pagination was dropped after the slow-count incident." }] } },
    { name: "crates/store", files: 5, symbols: 74, entry: false, memories: { count: 3, recent: [
      { id: 63, kind: "fix", observed_at: "2026-11-15", text: "Migrations ran twice under two replicas; an advisory lock now guards them." },
      { id: 60, kind: "fact", observed_at: "2026-11-13", text: "Orders are soft-deleted; reports must filter deleted_at." }] } },
    { name: "crates/jobs", files: 4, symbols: 58, entry: false },
    { name: "crates/common", files: 4, symbols: 41, entry: false },
    { name: "tests", files: 11, symbols: 63, entry: true },
  ],
  links: [
    { from: "src", to: "crates/http", references: 64 },
    { from: "crates/http", to: "crates/store", references: 48 },
    { from: "crates/store", to: "crates/common", references: 22 },
    { from: "src", to: "crates/jobs", references: 18 },
    { from: "crates/jobs", to: "crates/store", references: 15 },
    { from: "crates/http", to: "crates/common", references: 12 },
    { from: "tests", to: "crates/http", references: 30 },
  ],
  outside: [
    { package: "serde_json", version: "1.0.140", references: 310, class: null, used_by: ["src", "crates/http", "crates/store"] },
    { package: "axum", version: "0.8.4", references: 120, class: "server", used_by: ["src", "crates/http"] },
    { package: "sqlx", version: "0.8.6", references: 96, class: "database", used_by: ["crates/store"] },
    { package: "redis", version: "0.32.4", references: 31, class: "database", used_by: ["crates/jobs"] },
    { package: "reqwest", version: "0.12.22", references: 27, class: "network", used_by: ["crates/jobs"] },
    { package: "async-openai", version: "0.29.0", references: 14, class: "model", used_by: ["crates/jobs"] },
    { package: "walkdir", version: "2.5.0", references: 6, class: "system", used_by: ["src"] },
    { package: "anyhow", version: "1.0.98", references: 88, class: null, used_by: ["src", "crates/common"] },
  ],
};

const code = {
  root: "D:/work/atlas-api", origin: "compiler", stale: [],
  symbols: [{
    name: "fetch_page", kind: "function", path: "crates/store/src/pages.rs", lines: [41, 88], references: 3,
    signature: "pub async fn fetch_page(db: &Pool, cursor: Option<Cursor>, limit: u32) -> Result<Page>",
    callers: [
      { name: "list_orders", kind: "function", path: "src/routes/orders.rs", lines: [57] },
      { name: "list_invoices", kind: "function", path: "src/routes/invoices.rs", lines: [33] },
      { name: "export_all", kind: "function", path: "src/jobs/export.rs", lines: [120] },
    ],
    callees: [
      { name: "decode_cursor", kind: "function", path: "crates/common/src/cursor.rs", lines: [52] },
      { name: "Page", kind: "type", path: "crates/store/src/pages.rs", lines: [80] },
    ],
  }],
};

const day = (back, requests, output, read, price) => ({
  date: iso(back), requests, output, cache_read: read, input: requests * 40, cache_write_5m: 0,
  cache_write_1h: requests * 900, api_price_usd: price, unpriced_requests: 0,
});
const usageDays = [day(6, 410, 380000, 61e6, 21.4), day(5, 980, 910000, 140e6, 52.9), day(4, 0, 0, 0, 0),
  day(3, 640, 600000, 95e6, 33.1), day(2, 1210, 1150000, 188e6, 71.6), day(1, 870, 790000, 133e6, 49.2),
  day(0, 520, 470000, 79e6, 28.8)];
const sum = (k) => usageDays.reduce((s, d) => s + d[k], 0);
// Bucket costs as `footnote usage` sends them (#248), split from the fixture's price in fixed shares.
for (const d of usageDays) Object.assign(d, { cost_cache_read: d.api_price_usd * 0.6, cost_cache_write: d.api_price_usd * 0.25, cost_input: d.api_price_usd * 0.01, cost_output: d.api_price_usd * 0.14 });
const usage = {
  days: 7, prices: "2026-11-16", note: "",
  totals: Object.fromEntries(["requests", "output", "cache_read", "input", "cache_write_5m", "cache_write_1h", "api_price_usd",
    "unpriced_requests", "cost_cache_read", "cost_cache_write", "cost_input", "cost_output"].map((k) => [k, sum(k)])),
  limits: { current: [
    { agent: "codex", window: "5h", used_percent: 42, resets_at: 0, resets_in_minutes: 138 },
    { agent: "codex", window: "weekly", used_percent: 93, resets_at: 0, resets_in_minutes: 4100 }] },
  by_day: usageDays.filter((d) => d.requests > 0),
  by_model: [
    { model: "claude-opus-5-5", requests: 2600, api_price_usd: 171.2 },
    { model: "claude-sonnet-5-5", requests: 1450, api_price_usd: 63.4 },
    { model: "gpt-6.1-terra", requests: 580, api_price_usd: 22.4 },
  ],
  by_agent: [{ agent: "claude-code", requests: 4050 }, { agent: "codex", requests: 580 }],
  unpriced_models: [],
  measured_savings: {
    source: "Footnote Lean (usage/lean.jsonl)",
    total_saved_bytes: 3_516_000,
    total_saved_tokens_estimate: 879_000,
    shell: { commands: 640, before_bytes: 2_998_000, after_bytes: 1_322_000, saved_bytes: 1_676_000, saved_tokens_estimate: 419_000, saved_share: 0.559, handles_stored: 512, handles_retrieved: 11, miss_rate: 0.021, by_family: [], by_day: [] },
    footnote: { calls: 412, saved_bytes: 1_840_000, saved_tokens_estimate: 460_000 },
  },
};

// `footnote options`, only the entries the window reads. Gain and cost are the engine catalogue's text for this option.
const rewrite = {
  key: "memory.skill_rewrite", default: false, value: false, locked: false, reason: null, source: "default", range: null,
  gain: "Agents may change the skills you reuse to fit your projects: they get `footnote_skill_edit`, and after a skill's script fails they are asked once whether the skill itself was wrong. Worth it when the same skills come back session after session",
  cost: "Each change request costs one more agent turn, about as much as sending a third of the session's context once as fresh input (see `bench/experiments/SKILL-EDIT-COST-2026-11-21.md`). Later sessions read a changed skill again, and a change that does worse is rolled back. Changes to a skill's scripts wait for your review",
};
const options = (o = {}) => ({ options: [{ key: "memory.enabled", value: true }, { ...rewrite, ...o }] });
const history = "C:\\Users\\maya\\AppData\\Local\\footnote\\skills\\agent\\.history";
const review = (skills_pending) => ({ pending: skills_pending.length ? [
  { id: 88, kind: "preference", scope: "global", observed_at: "2026-11-21", text: "Prefers one pull request per issue, merged only after CI passes." }] : [], duplicates: [], old_sessions: [], unused: [], counts: {}, skills_pending });
const pending = [
  { name: "css-transitions", scope: "global", revision: 3, changed: ["scripts/check.mjs"], at: "2026-11-21T16:42:10Z", by: "agent",
    reason: "The check flagged transitions on prefers-reduced-motion users as missing; it now reads the media query before failing.",
    files: `${history}\\global\\css-transitions\\3\\files` },
  { name: "release-checklist", scope: "atlas-api", revision: 2, changed: ["scripts/verify.sh", "SKILL.md"], at: "2026-11-20T09:15:00Z", by: "agent",
    reason: "This repo publishes from the release branch, not main; the verify step checked out the wrong branch and failed every time.",
    files: `${history}\\project-atlas-api\\release-checklist\\2\\files` },
  { name: "postgres-zero-downtime-migrations", scope: "harbor-web", revision: 5, changed: ["scripts/lint_migrations.py"], at: "2026-11-18T13:02:44Z", by: "agent",
    reason: "Added a guard for the advisory lock the deploy uses, so the lint no longer reports the lock statement as an unsafe migration.",
    files: `${history}\\project-harbor-web\\postgres-zero-downtime-migrations\\5\\files` },
];
// `footnote skills diff <name>`: the line diff the review shows (#472), with each side's line number.
const line = (op, text, old, nw) => ({ op, text, old: op === "+" ? null : old, new: op === "-" ? null : nw });
// A folded run with its lines, as the engine sends it (runs over 500 lines come without them).
const fold = (fromOld, fromNew, texts) => ({ op: "…", text: `${texts.length} unchanged line${texts.length === 1 ? "" : "s"}`,
  lines: texts.map((t, k) => line(" ", t, fromOld + k, fromNew + k)) });
const diff = {
  name: "css-transitions", scope: "global", revision: 3, base_revision: 2, folder: pending[0].files,
  files: [{ file: "scripts/check.mjs", status: "changed", lines: [
    fold(1, 1, ["// Fails when a CSS transition has no reduced-motion fallback.", "import { readFileSync } from \"node:fs\";", "import { parse } from \"./css.mjs\";", "", "const file = process.argv[2];", "if (!file) {", "  console.error(\"usage: check.mjs <file.css>\");", "  process.exit(2);", "}", "const sheet = parse(readFileSync(file, \"utf8\"));", "let failed = 0;", "const fail = (rule, why) => {", "  failed += 1;", "  console.log(`${rule.selectorText}: ${why}`);", "};", "const hasReducedMotion = (rule) =>", "  sheet.reducedMotion.has(rule.selectorText);", ""]),
    line(" ", "for (const rule of sheet.cssRules) {", 19, 19),
    line(" ", "  if (!rule.style?.transition) continue;", 20, 20),
    line("-", "  if (!hasReducedMotion(rule)) fail(rule, \"no reduced-motion fallback\");", 21),
    line("+", "  const guarded = rule.parentRule?.media?.mediaText.includes(\"prefers-reduced-motion\")", null, 21),
    line("+", "    || hasReducedMotion(rule);", null, 22),
    line("+", "  if (!guarded) fail(rule, \"no reduced-motion fallback\");", null, 23),
    line(" ", "}", 22, 24),
    { op: "…", text: "612 unchanged lines (open the folder to read them)" }, // over 500: counted only
  ] }],
};
// Two files: a script and a prose step.
const diff2 = {
  name: "release-checklist", scope: "atlas-api", revision: 2, base_revision: 1, folder: pending[1].files,
  files: [
    { file: "scripts/verify.sh", status: "changed", lines: [
      line(" ", "set -euo pipefail", 1, 1),
      line("-", "git checkout main", 2),
      line("+", "git checkout \"${RELEASE_BRANCH:-release}\"", null, 2),
      line(" ", "cargo test --locked", 3, 3),
      fold(4, 4, ["cargo clippy --locked -- -D warnings", "", "branch=$(git rev-parse --abbrev-ref HEAD)", "echo \"verified $branch\"", "", "if [ -n \"${CI:-}\" ]; then", "  echo \"::notice::release verified\"", "fi", "", "git checkout -", "", "exit 0"]),
    ] },
    { file: "SKILL.md", status: "changed", lines: [
      fold(1, 1, ["---", "name: release-checklist", "description: Steps to cut and verify a release of this repo.", "---", "# Release checklist", "", "1. Update CHANGELOG.md.", "2. Bump the version in Cargo.toml.", ""]),
      line(" ", "## Verify", 10, 10),
      line("-", "Run `scripts/verify.sh` from main.", 11),
      line("+", "Run `scripts/verify.sh`; it checks out the release branch (`RELEASE_BRANCH`, default `release`).", null, 11),
    ] },
  ],
};

export const fixtures = {
  ok: { status, projects, activity, "models list": models, "code-map": codeMap, "code-impact": codeImpact, code, usage, "config set": {},
    options: options(), "agent-ask": { queued: true }, "install --memory": { installed: true },
    "update --check": { installed: "0.1.0-alpha.3", latest: "0.1.0-alpha.4", newer: true, installer: "Footnote-Setup-0.1.0-alpha.4-x64.exe",
      published_at: new Date(Date.now() - 51 * 60000).toISOString(),
      notes: "## Release Notes\n\nSecond alpha. The headline is a Windows installer that brings the desktop launcher, in the tray. Expect rough edges and\nbreaking changes between versions.\n\n### New\n\n- **Windows installer** (`Footnote-Setup-0.1.0-alpha.3-x64.exe`, #125): the engine and the desktop launcher in one step, for\n  your user, with no administrator rights.\n  - **Always added:** a Start menu shortcut.\n  - **On by default:** Footnote starts in the tray (notification area) when you sign in, and goes on PATH. Both can be\n    unchecked.\n  - **Off by default:** a desktop shortcut, and connecting the coding agents found now (`footnote install`).\n  - It carries the Visual C++ runtime the engine needs, so it runs on a fresh Windows.\n  - **Upgrades:** safe while your agents use Footnote. The old binary is set aside, and their MCP servers keep running.\n  - **Uninstall:** takes Footnote out of your agents first, and keeps your data.\n- **Launcher:**\n  - It starts in the tray without opening a window, and runs once: opening it again shows the window that is already open.\n  - A new **Skills** screen: the skill-rewrite switch with its cost, and your review of pending skill changes (#461).\n- **Agent skill layer, opt-in** (#453, #455, #458, #459, #460):\n  - Agents can propose edits to the skills they use, through `footnote_skill_edit`. Each edit passes check gates, and you\n    review it.\n  - An edit that does worse in trials is rolled back.\n  - Skills that are never read stop being suggested.\n  - Off until you turn on `memory.skill_rewrite`.\n- **Curated skills:** 23 agent skills rewritten, each with a check script (#439).\n- **Library:** search hits carry the crawled page's URL (#438). A refresh re-indexes a page whose words were only reordered\n  (#431).\n- **Memory:** a project's handoffs retire once delivered (#436).\n- **Code:** a Rust project in a subfolder (a Tauri app's `src-tauri`, `backend/`) now gets its compiler indexer (#428).\n\n### Before you install\n\n- **Nothing is code-signed.** Windows SmartScreen asks once: **More info**, then **Run anyway**. Check the file against its\n  `.sha256` first.\n- **Windows 11 hides new tray icons.** It puts them behind the `^` arrow next to the clock. To keep Footnote visible:\n  Settings > Personalization > Taskbar > Other system tray icons > Footnote.\n- **Linux needs glibc 2.38 or newer** (Ubuntu 24.04, Debian 13, Fedora 39 or later). The launcher is Windows-only for now.\n- Encrypted memory (`--features encryption`) is experimental and not in these binaries.\n\n### Install\n\n- **Windows, with the launcher:** download `Footnote-Setup-0.1.0-alpha.3-x64.exe` below and run it.\n- **Windows, command line only:**\n  `powershell -ExecutionPolicy Bypass -c \"irm https://github.com/bobcat88/footnote/releases/download/v0.1.0-alpha.3/footnote-installer.ps1 | iex\"`\n- **Linux x64:**\n  `curl --proto '=https' --tlsv1.2 -LsSf https://github.com/bobcat88/footnote/releases/download/v0.1.0-alpha.3/footnote-installer.sh | sh`\n\nThen follow [HOW-TO.md](https:/" },
    "update --download": { installer: "C:/Users/sample/AppData/Local/footnote/updates/Footnote-Setup-0.1.0-alpha.4-x64.exe", version: "0.1.0-alpha.4" }, "memory-review": review(pending), "skills approve": {}, "skills reject": {}, "memory-restore": {}, forget: {},
    corpora: { corpora: [
      { path: "D:/docs/atlas.db", exists: true },
      { path: "C:/Users/sample/AppData/Local/footnote/docs/rust-perf-book/latest.db", exists: true },
      { path: "C:/Users/sample/AppData/Local/footnote/docs/jiff-guide/1.0.db", exists: true },
      { path: "E:/old/handbook.db", exists: false }] },
    "memory-list": { total: 6, scopes: [{ scope: "atlas-api", memories: 3 }, { scope: "global", memories: 2 }, { scope: "harbor-web", memories: 1 },
      ...["ledger-sync", "old-prototype", "design-notes", "site", "infra", "mobile-app", "data-pipeline", "billing", "docs-portal",
        "2026-11-21-research-scratch"].map((scope) => ({ scope, memories: 1 }))], memories: [
      { id: 17, kind: "fact", scope: "atlas-api", observed_at: "2026-11-12", text: "The API keeps cursor pagination; offset pagination was dropped after the slow-count incident. Pages hold 50 items; the cursor is opaque and signed.", tags: [] },
      { id: 42, kind: "preference", scope: "global", observed_at: "2026-11-10", text: "Prefers small pull requests with tests run locally before review.", tags: ["review"] },
      { id: 51, kind: "fix", scope: "atlas-api", observed_at: "2026-11-15", text: "Migrations ran twice under two replicas; an advisory lock now guards them. Run them from the release job only.", tags: ["db"], origin: "claude-code" },
      { id: 63, kind: "session", scope: "harbor-web", observed_at: "2026-11-18", text: "Session: moved the checkout form to server actions, kept the old route behind a flag until Friday.", tags: [] },
      { id: 70, kind: "preference", scope: "global", observed_at: "2026-11-19", text: "Wants dates written as 22 Nov 2026 in every user-facing text, never 11/22.", tags: [] },
      { id: 74, kind: "fact", scope: "atlas-api", observed_at: "2026-11-21", text: "The staging database is reset every Monday at 06:00 UTC.", tags: ["ops"] }] },
    "docs list": { docs: [
      { site: "react.dev", version: "19", state: "ready", pages: 412, bytes: 38_400_000, modified_unix: 1763337600 },
      { site: "docs.pydantic.dev", version: "2.12", state: "embedding 140/388", pages: 388, bytes: 21_000_000, modified_unix: 1763683200 }] }, "skills diff release-checklist": diff2, "skills diff": diff,
    "find --": { query: "pagination", products: [
      { product: "memory", state: "ok", results: [
        { id: 17, title: "The API keeps cursor pagination; offset pagination was dropped after the slow-count incident.", detail: "fact · atlas-api · 2026-11-12" },
        { id: 42, title: "Prefers small pull requests, one per piece of work, with tests run locally before review.", detail: "preference · global · 2026-11-10" }] },
      { product: "library", state: "ok", corpora: 1, problems: [], results: [
        { id: 311, title: "Pagination", detail: "docs/api/guide.md:84", snippet: "Pass the cursor from the previous page; pages hold 50 items by default.", source: "D:/docs/atlas.db" }] },
      { product: "code", state: "not_a_symbol", results: [] }] } },
  // A download in progress: the install never answers and `jobs` reports its bytes.
  installing: {
    status, projects, activity, "models list": models,
    jobs: { jobs: [{ kind: "models.install", label: "jina-v5-nano model.gguf", state: "running", unit: "bytes", done: 97_000_000, total: 232_883_776 }], total: 1, hidden: 0 },
  },
  // One product switched off and one left out of the build: the switch's two other states.
  off: {
    status: { ...status, products: { ...status.products, code: { built: false }, library: { built: true, enabled: false } } },
    projects, activity, "config set": {},
    // A company policy forces skill rewriting off: the switch shows the policy's reason instead.
    options: options({ locked: true, source: "policy", reason: "agents may not write instructions for other agents on managed laptops" }),
    "memory-review": review([]),
    "find --": { query: "zebra", products: [
      { product: "memory", state: "nothing_found", results: [] },
      { product: "library", state: "off", results: [] },
      { product: "code", state: "not_built", results: [] }] },
  },
  empty: {
    status: {
      ...status,
      products: {
        code: { built: true, graphs: 0, rust_indexer: false },
        library: { built: true },
        memory: { built: true, enabled: true, memories: 0, saved_last_7_days: 0, recalls_last_7_days: 0, agents: [] },
      },
      models: { ...models, models: models.models.map((m) => ({ ...m, installed: false, bytes: undefined })) },
    },
    projects: { projects: [] },
    activity: { activity_log: false, days: [], most_used: [] },
    usage: { ...usage, totals: Object.fromEntries(Object.keys(usage.totals).map((k) => [k, 0])), by_day: [], by_model: [], by_agent: [],
      measured_savings: { source: "Footnote Lean (usage/lean.jsonl)", total_saved_bytes: 0, total_saved_tokens_estimate: 0, shell: { commands: 0, before_bytes: 0, after_bytes: 0, saved_bytes: 0, saved_tokens_estimate: 0, saved_share: 0, handles_stored: 0, handles_retrieved: 0, miss_rate: 0, by_family: [], by_day: [] }, footnote: { calls: 0, saved_bytes: 0, saved_tokens_estimate: 0 } } },
    "models list": { ...models, models: models.models.map((m) => ({ ...m, installed: false, bytes: undefined })) },
    options: options({ value: true, source: "user" }), "memory-review": review([]), "config set": {},
  },
};
