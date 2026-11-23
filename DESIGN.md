# DESIGN
Last reviewed: 2026-11-14 · Direction locked in Design Studio on 2026-11-14 · **Status: WIP**

> **Work in progress.** The direction, palette, type and shape below are locked choices. The logo and product marks, the glass treatment and the motion are a decent first pass that will need deeper work: treat them as provisional, not final artwork.

Footnote is transparent for your team: set it up, and what comes into focus is your team's data and knowledge. The page shows that literally: data flowing in the background, liquid glass that brings part of it into focus, and the product answering with its sources.

## 1. Tokens source
Hand-written, then tuned and locked on 2026-11-14 (base direction D2 "Afterglow"). Contrast values measured at the lock.

## 2. References
| # | Product or source | URL | Date viewed | Evidence type | Borrowed | Rejected and why |
|---|---|---|---|---|---|---|
| 1 | Raycast | https://www.raycast.com | 2026-11-14 | live page | dark ground, short centred headline, the product shown as a command palette | the shader sculpture standing in for the product |
| 2 | LangChain | https://www.langchain.com | 2026-11-14 | live page | a field of flowing dots as the background (data in motion) | blue accent, logo wall |
| 3 | Mode | https://mode.com | 2026-11-14 | live page | large rounded blocks that interlock around content | stock photography, lime and forest palette |
| 4 | Fabric | https://www.fabric.vc/portfolio | 2026-11-14 | live page | card grid with category tags and card motion | orange line-field header |
| 5 | Zed | https://zed.dev | 2026-11-14 | live page | the real product filling the hero | (direction D1, not chosen) |
| 6 | Warp | https://www.warp.dev | 2026-11-14 | live page | captioned live figure with a legend | (not used) |
| 7 | mem0 | https://mem0.ai | 2026-11-14 | live page | category baseline to differ from | centred SaaS hero, purple, code block as the product |
Structure, layout and motion patterns only: no brand names, logos, copy, imagery or proprietary fonts are copied. Blocked access: none.

## 3. Color roles
Dark-first. A light theme is not designed yet (WIP); until it is, the page commits to dark and sets every color explicitly.

| Role | Dark | Contrast |
|---|---|---|
| background | #09120B | - |
| surface (blocks, cards) | #121C15 | - |
| line (hairlines, borders) | #29332C | - |
| text | #EAF0EB | 16.47:1 on background, 15.1:1 on surface |
| muted text | #A2AFA5 | 8.35:1 on background |
| accent (teal) | #2B9185 | 4.98:1 on background (UI) |
| button text on accent | #101114 | 4.94:1 |
| glow (data dots, marks in lenses) | #5FD3C3 | decorative and marks only |
| mint block (statements, results) | #D7EFE8 with ink #0B1A12, muted #3D5A4D | pale contrast blocks, added 2026-11-14 |
| success / warning (freshness: current, stale) | #7FD39A / #F2B84B | from D2, to re-measure |

Rule: the accent marks actions, Footnote's own results in charts, and sources. No violet, no blue-to-purple gradient.

## 4. Typography
- Families: **Plus Jakarta Sans** 600 (display, maintainer choice) and **Hanken Grotesk** (body); JetBrains Mono for paths, hashes, commands and numbers in tables. Self-hosted in the final build (local-first: no font request leaves the page).
- Scale (ratio 1.335, density 1.05):

| Name | Size | Use |
|---|---|---|
| small | 12 px | captions, meta rows (11 px floor for functional text) |
| body | 16 to 18 px | prose, 60 to 70 characters per line |
| card title | 21 px | product card titles (body size × 1.335) |
| h3 | 29 px | block titles |
| h2 | 38 px | section titles |
| h1 | 68 px | hero statement |

- Tabular numerals wherever numbers are compared.

## 5. Space and shape
- Spacing steps (from the lock): 4, 8, 13, 17, 25, 34, 50, 67 px.
- Radius: 21 px for blocks and cards on the site. The launcher draws every corner as a squircle and never full round (22 Nov
  2026, section 11); full round stays only for the logo lens, the mini-mode lenses and status dots.
- Elevation: **slight liquid glass** on chosen elements only (the logo lens, the product palette, one or two hero panels): translucent fill, specular rim, refraction of the moving data behind. Everything else is flat surface + hairline. Never glass on every card.
- Icons: thin outline, 1.6 stroke on a 24-unit grid, round joins.

## 6. Layout and density
- Max content width 1120 to 1200 px; 16 px minimum side gutter; works at 390 px.
- Rounded blocks that interlock (reference 3) for the sections after the hero.
- Marketing density: one idea per screen.

## 7. Logo and product marks (WIP)
Concept A, "the lens numeral": the word **Footnote** is the family; a small glass lens takes the place of the footnote number and carries the product's mark. Everyone reads Footnote as the family and the mark as the product.

| Product | Mark in the lens | Status |
|---|---|---|
| Footnote (umbrella) | the numeral 1 | provisional |
| Footnote Library | database cylinder: L1 plain, or L2 with lines of text | open, not chosen |
| Footnote Memory | wireframe brain: M1 plain, or M2 with connected nodes | open, not chosen |
| Footnote Code | `{x}` (maintainer choice) | chosen, drawing provisional |

Work-in-progress logo sketches live outside the git repository. Still to do: final SVG geometry, a still version for places without motion, an app icon (concept B, the focus tile, is the candidate), and a pass by someone with real logo skills.

## 8. Motion (WIP)
- Level: lively, with meaning. Durations 160 to 320 ms, ease-out, transform and opacity only. **320 ms is a hard cap** for every transition, entrance and hover; only ambient loops (the data stream, the orbit) run longer. Stagger delays may add up past it, each step may not.
- Background: a slow field of dots flowing in bands (data stream), paused under reduced motion.
- The lens drifts slightly over the data, as if reading it.
- Product heroes each tell their own story around the lens (`site/src/scenes.js`), never a repeat of the home "1": Library is a magnifier over a page of docs that cites the line under it (file:line, current or changed since); Memory is a web of memories that grows from the conversation and lights a few at each session start; Code is a call graph with pulses through the function in focus, walking to the next one, with one unresolved caller left dashed and unnamed; Lean takes yellow noise and green failure lines in mixed, sinks the yellow to the bottom of the lens and drops it, and sends only the green into a structured prompt card headed by a real benchmark case.
- Cards rise and reveal on entry and hover (reference 4); content is visible at rest and never waits at opacity 0.
- Never: numbers counting up, parallax on text, motion that implies a result the tool did not measure.

## 9. Copy rules
- Every number carries its dataset and split; every claim links to a receipt.
- Footnote Code is shown as "soon" until it ships.
- Banned words: "supercharge", "unlock", "seamless", "next-generation", "revolutionize"; no fake testimonials, logo walls or invented customer counts.

## 11. Launcher (app), locked 16 November 2026
Design pass selected D1's structure for the full window and D2's lenses for the mini mode, with the family's colours and fonts on both.

- **Full window (D1 "Console" structure):** sidebar 232 px (products, workspace, not installed, Footnote Enterprise group, quiet
  support link at the foot), top bar 44 px, content, activity column 320 px. Dense tables for projects and agents,
  three product cards with one big number each.
- **Mini mode (reworked 22 Nov 2026; was D2 "Lens"):** the tray's quick look, opened by a left click on the tray icon. One
  widget that fills its 380 x 248 window: no shadow (Tauri draws a frameless window's shadow as a light 1 px line), and
  Windows 11 rounds the corners with no border (no bezel). A transparent window, tried first, never showed on Windows
  (#525). A title row with the lens mark and
  three controls: minimize, open the full window (in place of maximize), close to the tray. Below, a slider of single-KPI
  cards (Memory, today's tokens and list cost, projects with work to commit, agents connected, Library and Code), each with
  one big number, one line, and a link that opens the matching screen in the full window. Arrow keys, the bar-shaped page
  marks or the side chevrons move between cards; the last card shown is remembered. It follows the palette chosen in the
  full window. Anything to act on happens in the full window.
- **Tokens:** the site's palette (section 3), Plus Jakarta Sans for titles and big numbers, Hanken Grotesk 14 px for UI text,
  JetBrains Mono for paths, ids and timings. App radius 16 px for cards and 10 px for controls, drawn as squircles (see the glass
  rework below; the site's 21 px stays for marketing blocks). Functional text never below 11 px. Afterglow (dark) is the default palette; four
  more are the viewer's choice since 22 Nov 2026 (see the glass rework below).
- **Motion:** full window subtle (160 ms, transform and opacity only); mini mode lively (the lenses and data flow); nothing moves
  under reduced motion.
- **Code views, by zoom level:** architecture map (blocks with import counts and outside services as dashed nodes: the inputs and
  outputs), then a block's files, then one symbol's callers and callees. Never the whole graph at once; the full "hairball" only
  as ambient decoration in mini mode.
- **Architecture map, blueprint layout (17 Nov 2026):** chosen as a blend of four layout directions:
  three columns (`Flows | map | detail`). The map sits on a 24 px blueprint grid, with the code in a solid zone and "Calls out" in a
  dashed zone grouped by kind (databases, model runtimes, network and APIs, files and system). `server` and `mcp` packages are
  listed as "Calls in". Blocks carry yellow (`--warn`) memory pills from anchored memories. A flow starts at an entry block and
  follows the heaviest references; the lit path animates with dots, but not under reduced motion. The detail panel shows the
  selected flow or block: its memories first, then its steps or links. All colours, type and radii are this section's tokens.
  The Layers tab reads the same map top to bottom: entry, features, base, outside, each with its links down.
- **Architecture map by zoom level (22 Nov 2026, #360, replaces the blueprint map above):** the mockup approved in chat, built on
  this section's tokens. Level 1 is the project's linked blocks (tests, benchmarks and examples are listed, not drawn), "Calls in"
  for `server`/`mcp` packages and "Calls out" by kind; level 2 is one block's files (`code-map --block`). ELK lays each level out
  left to right with orthogonal routes. Cards carry the block's manifest `description` or the file's leading module doc, as
  written. Selecting a card lights what a change affects in `--warn` and what it relies on in `--acc`, with moving dots on the
  lit routes (not under reduced motion); the side panel lists both with reference counts and top symbol names. Double-click or
  "Open its files" goes down, Esc or the breadcrumb goes up; drag pans, the wheel zooms, Fit shows the whole level. The Symbol
  tab adds a side toggle: both sides, "Affected if it changes" (callers by level from `code-impact`), "It relies on".
- **Launcher-only colour roles:** besides section 3, the window uses `--side` #0D1810 (sidebar ground), `--raise` #182A20
  (selected rows, raised fills, callouts), `--line2` #34413A (control borders) and `--dim` #8A978D (tertiary labels; 5.7:1 on
  the surface). `--acc` in the window is the glow teal #5FD3C3, used for focus and primary-button borders.
- **Skills screen (21 Nov 2026, #457; reworked 22 Nov 2026, #472):** a workspace screen in one 760 px reading column, left
  aligned like every other screen (the activity column belongs to Overview only). Two blocks, 24 px apart.
  - One card holds the `memory.skill_rewrite` switch, with the engine catalogue's gain and cost text. That text is read from `footnote options`, never copied into the app, and its backtick spans render as code.
  - The title row reads "Agents may change skills" (Hanken 14 px, 600: a card title, one step below the Jakarta 15 px section heading "Changes waiting for you"), then "On" or "Off" beside a 40 × 24 px switch whose off edge is `--mute` (≥ 3:1). Diff lines wrap inside their panel, keeping the line-number gutter.
  - Turning the switch on opens an inline confirmation inside the card. It has a `--warn` border, one line on what turning it on costs, and puts focus on "Turn on". Escape or Cancel closes it and returns focus to the switch. Turning it off is immediate.
  - A company policy replaces the switch with a borderless `--raise` status pill with a lock glyph naming the locked value ("Off, set by your company"), and its reason sits under the title in a callout with a `--warn`-tinted border. The empty list then says that no change can arrive.
  - Below the card, under the title "Changes waiting for you" with their count, is the list of agents' pending skill changes. Each item has the name, scope, revision, the date it was proposed, the reason and changed files, then "Show the changes" (the line diff from `footnote skills diff`, with old and new line numbers, removed lines on a `--warn` tint, added on an `--ok` tint, unchanged runs folded into a row that unfolds them in place and moves focus to the first revealed line, or opens the folder for a run over 500 lines; no font ligatures in diffs), "Open folder" (the engine names the folder; the window only names the skill), and Approve / Reject on the right. Approve is a `--acc`-bordered button.
  - All prose is 14 px on a 20 px line, capped at 60ch (at most about 75 characters of Hanken Grotesk); the cost text is at full `--text` strength, and its measurement report opens on the project's site. Spacing is on the 4 px grid. The loading state draws the card and one change as skeletons of the same size.

- **Glass rework (22 Nov 2026, maintainer request; no QLoop pass yet):** Apple-derived chrome on the D1 structure. The
  tokens live in `apps/launcher/src/styles.css`, the components in `src/ui.jsx`, the materials in `src/glass.css`; each control
  follows a design-bank recipe (`design-bank/protos/css.html`, `protos/hover.html`).
  - **Palettes:** Afterglow (family, default), Graphite, Midnight, Ember and Daylight (the only light one), picked from the
    Appearance menu in the top bar and kept in the window's local storage. Every colour in the window reads a token; chart
    series use `--c1` to `--c4`, destructive actions `--bad`.
  - **Materials:** `.lglass` (blur 22 px, saturate 1.5) for the sidebar, top bar, heroes, menus and tooltips; `.surface` (the
    same tint without blur) for list rows, so a page of 50 rows never stacks 50 blurred layers. Under
    `prefers-reduced-transparency` both are solid `--panel`. Faint pools of `--acc` and `--acc2` sit behind the glass.
  - **Shape: squircles, never full round.** Every corner in the window is an Apple-style squircle (`corner-shape: squircle`;
    the radius grows about 1.6x to keep the same visual size: about 11 px for chips and icon tiles, 15 px for buttons,
    fields, tabs and the switch, 18 px for tab groups, stats and nav items, 22 px for menus, 27 px for cards). Pills, tabs,
    the switch track and knob, chips, badges, the scroll rail and the approve/reject buttons are all squircles; thin meters
    use 3 px. Full round is kept only for the logo lens, the mini-mode lenses and status dots. Without `corner-shape`
    support the same elements fall back to plain radii, still never full round. Lit border: a 240 px halo follows the
    pointer across neighbouring `.lit` cards; off for touch and reduced motion.
  - **Controls:** popover menus replace native selects (entry and exit with `@starting-style`, arrow keys, Escape); tabs carry a
    sliding pill anchored to the selected tab; the on/off switch is 44 x 26 with a `linear()` spring; tooltips are anchored
    manual popovers in the top layer and replace `title`; delete is a small trash whose lid lifts on hover, and a first click
    arms it (danger fill, one shake) for a second click to confirm. Approve and reject (pending memories, skill changes) are a
    green check and a red cross in 30 px squircles: hover fills them and redraws the mark, the one clicked pulses until the
    engine answers, and each names its effect in a tooltip.
  - **Options (sidebar foot):** a gear opens the palette (five squircle swatches; both windows follow the choice), the
    version and help. The installed version shows in full beside the brand (`0.1.0-alpha.3`, as shipped). The palette
    button left the top bar.
  - **Updates (T3 Code's flow), beside the gear:** a sync mark checks the latest GitHub release at start and every six
    hours (one request to GitHub's releases API; nothing is sent). When a newer release exists it becomes a download mark
    with a green badge, and hovering shows "what's new" from the release notes (top-level bullets, issue numbers dropped).
    A click downloads the Windows installer and checks it against the release's `.sha256`, drawing a squircle progress
    ring; then the mark becomes "restart to update". That click runs the installer with no window (`/VERYSILENT`), closes
    Footnote, and reopens it when the installer is done. Nothing is killed: the installer stops the launcher and sets
    aside a `footnote.exe` an agent still runs, and those agents pick up the new binary in their next session.
  - **Agents:** each agent chip is green (Memory hooks and MCP server connected), amber (one missing, shown dashed) or red
    (both missing). A non-green chip has a wrench that runs `footnote install --memory` (it reconnects every agent found and
    rewrites only Footnote's own entries) and asks for a restart of the agent.
  - **Commit pictogram:** a click commits and pushes now, in the background (`footnote agent-commit`): the agent last used in
    that project (recorded by the hook; Claude Code or Codex, else whichever is installed) runs unattended with the engine's
    fixed request. Claude Code may run git commands only; Codex runs in its workspace sandbox with network for the push. The
    pictogram spins while it runs, then a note that stays until dismissed says what was committed and pushed and what was
    left. With neither command line installed, the request waits instead (`footnote agent-ask`), meant for the project's
    last session (the one that started a turn there last): the pictogram turns into an accent send mark whose tip names
    that agent and session and says an idle agent cannot be reached, so it waits for the next prompt there; a click
    withdraws it. Once a session takes it, an accent double check (or the green check, once all is committed) says which
    agent session took it, when, and at which hook (#501).
  - **Scrolling (T3 Code's rail):** no native scrollbar in the main area or in menus. A sparse tick rail on the right edge,
    about four ticks per screen of content (8 to 36; three per screen in a menu, 6 to 20). The screen in view is brighter,
    and one long white tick marks where you are. On hover the rail spreads and the ticks near the pointer grow like a
    magnifier, the one under it in `--acc`; widths and spacing move on the spring curve. Clicking or dragging scrolls.
  - **Pages:** a hero opens Projects, Models, Library and Activity with the one number or state the page is about. Projects
    are one card each: name (24 characters, full name in the tooltip), last seen, a drive squircle plus the last folder (opens
    the folder; the shell checks the engine's project list first), then pictograms for memories, code graph (or a build
    button) and uncommitted changes (red; a click commits and pushes in the background). Unpushed counts are
    dropped. At the bottom right, an eye-off button ignores the project: it leaves the list and new sessions there are not
    recorded (memories stay); the note that confirms it has Undo, and "N ignored projects" under the grid restores any.
    Opening a folder checks it against the quick project list (names and folders, no git), so it opens at once. Models: the hero names the active model(s); each licence chip opens what the licence allows and links its text.
    Memory rows show only id, kind pictogram, first sentence, scope and date; the text opens below with
    `interpolate-size`. Activity shows only days with activity; a day (bar or list) opens its recalls in a fixed-width table.
    The Overview's 320 px activity column renders the week as a 7-day × 24-hour bubble grid (#635): one dot per hour sized by
    share of the week's saves and recalls, coloured by blending `--c1` (saves) and `--c2` (recalls) in OKLab, with a ring on the
    week's busiest hour, composited `--spring` hover/focus scaling and tooltip glide, and week totals at the foot.

## 10. Decision log
| Date | Decision | Reason | Rejected alternative |
|---|---|---|---|
| 2026-11-23 | Overview activity column becomes a 7-day × 24-hour bubble grid (`--c1` saves blended with `--c2` recalls in OKLab, ring on the week's busiest hour, explanation in the info tooltip) (#635) | The day table repeated the Activity screen and could not show when memory worked during the day; maintainer picked direction 4 (the organic bubble grid) and asked to keep text off the face | 12+12 two-row bar grid, stacked hour bars, radial week clock, and text lines naming the busiest hour |
| 2026-11-23 | A waiting commit request names the session it is meant for, and its receipt (who took it, when, at which hook) shows on the same pictogram, in its tip and label (#501) | The maintainer expected the click to reach the last agent directly; no supported agent can be messaged while idle, so the window must say who will take it and when it did | A new status line or badge on the card (a new visual element for a rare state); typing into the agent's terminal (a non-goal) |
| 2026-11-22 | Mini window becomes a squircle KPI widget with a card slider and its own minimize / open full / close controls; Options menu (palette, updates from GitHub releases, help) at the sidebar foot; agent chips repair themselves; the commit pictogram sends the request to the agent | Maintainer review of the real window: the mini's lenses and frame read as a bezel, the version label did not match the shipped release, and copying a request to the clipboard was a useless step | Keep the D2 lenses; a check only when Options opens (replaced the same day by T3 Code's flow: check at start and every six hours, download, restart to update); per-agent installs (the engine connects every agent found in one step) |
| 2026-11-22 | Launcher shape: squircles everywhere, never full round (pills, tabs, switch, chips, rail, buttons); approve and reject as a green check and a red cross | Maintainer review: the app never used full round, and Apple's squircle is the reference; text Approve/Reject buttons read heavier than the decision needs | Capsule pills and round icon buttons (the first pass of the rework); text buttons |
| 2026-11-22 | Launcher glass rework: five palettes, glass chrome and heroes, squircle cards, lit borders, tick scroll rail, popover selects, sliding tabs, spring switch, anchored tooltips, armed trash; Projects as cards; Activity only on active days | Maintainer review of the launcher (22 Nov): native controls looked dated, tables were dense and noisy, zero rows and unpushed counts said nothing | Keep dark-only Afterglow with native selects and scrollbars; glass on every row (cost: many blurred layers) |
| 2026-11-21 | Product heroes get their own canvas scene (magnifier, memory web, call graph) behind an unblurred lens | Each product page should feel alive like the home page but show what that product does | The home swarm settling into each product mark (read as the same animation with a different logo) |
| 2026-11-21 | Home: four product cards (Lean added) in a 2 × 2 staggered grid, each with a static example snippet of its own output instead of the big glyph lens; 21 px card-title size; 320 ms motion cap | Cards looked identical; Lean shipped in v0.1.0-alpha.2; critics flagged ad-hoc title sizes and 0.5 to 1 s transitions | Lean inside the engine section; glyph lens on every card |
| 2026-11-16 | Launcher: D1 structure (full window) + D2 lenses (mini mode), family palette and fonts | D2 is clean aesthetically but sparse in data; D1 surfaces all operational telemetry; shared palette unifies both modes | D3 Ledger (light paper, serif), D4 Palette (command box first) |
| 2026-11-14 | Base direction D2 "Afterglow", tuned: green-black ground, teal accent, Jakarta + Hanken, radius 21, lively motion | Selected in design review; D1, D3 and D4 looked too similar to each other | D1 Workbench, D3 Living memory, D4 Paper |
| 2026-11-14 | Slight liquid glass over a data-flow background | Visual metaphor: Footnote is transparent and brings data into focus | Flat dark cards only; glass everywhere |
| 2026-11-14 | Logo concept A (lens numeral), mark becomes the product | The family stays legible (Footnote) and each product is one glyph | B focus tile as the main logo (kept as the app-icon candidate), C mark system |
| 2026-11-14 | Footnote stays the umbrella name: Library, Memory, Code | Maintainer decision after naming brainstorm | Cairn, Gloss |
| 2026-11-14 | Page v2: stream into a glass lens (hero), interlocking mint blocks, staggered product cards, orbit beside a bleeding glass panel | Stronger visual hierarchy than v1 using flow and card rhythm | v1 centred hero with flat cards |
| 2026-11-14 | Design status WIP | Acceptable initial pass; deeper polish deferred | Treating the first pass as final |
| 2026-11-12 | (superseded 2026-11-14) Paper and ink palette with one proof red, Newsreader, radii 0 and 2 px, no glass | Was the first draft; replaced by the studio lock | |
| 2026-11-12 | (kept) Benchmarks as a table first, a chart second | Numbers must be readable and copyable | Chart-only hero |
| 2026-11-12 | (kept) Self-host fonts | A local-first, no-telemetry product must not call font CDNs | Google Fonts at runtime |
