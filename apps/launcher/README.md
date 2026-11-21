# Footnote One launcher

The desktop window over the `footnote` engine (Tauri 2 + React). It holds no data of its own: each screen runs engine commands
(`status`, `projects`, `activity`, `models list`, `code`, `code-map`, `options`, `memory-review`) as a child process, through
one Tauri command with an allowlist (`src-tauri/src/main.rs`). The allowlist permits only a few reversible writes:
- a product's on/off switch;
- the skill-rewriting switch (`memory.skill_rewrite`), whose cost the Skills screen shows before it is turned on;
- `skills approve` or `skills reject` for an agent's pending skill change. Nothing in the window or the engine runs that change.

Design: [DESIGN.md](../../DESIGN.md) section 11.

## Build and run (Windows; Linux and macOS untested)

Needs Node 20+, Rust 1.92+, WebView2 (shipped with Windows 11), and the `footnote` engine: `FOOTNOTE_BIN`, beside the app,
`%LOCALAPPDATA%\Programs\footnote\footnote.exe`, or on PATH.

```sh
npm ci --ignore-scripts        # 25 packages, none needs an install script (checked 16 Nov 2026); .npmrc enforces it
npx tauri dev                  # window with live reload
npx tauri build --no-bundle    # src-tauri/target/release/footnote-launcher.exe; the installer packs it (../../installer)
```

`src-tauri` is its own Cargo workspace, so Tauri stays out of the engine's build and CI.

`footnote-launcher.exe --tray` starts in the tray without opening a window (the installer's Windows startup entry uses it).
Only one launcher runs at a time: starting it again opens the running one's window.

## Screenshots without the app

`npx vite build && npx vite preview`, then open `/#/overview?mock=1&state=ok|empty|missing|loading`: invented sample data
(`src/fixtures.js`) for the QLoop UI gates. Outside the app and without `mock=1`, the page shows "engine not found".
