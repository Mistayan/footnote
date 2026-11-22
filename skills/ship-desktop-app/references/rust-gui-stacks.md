# Rust GUI stacks by use case

Ecosystem and licences move: re-check before locking a stack (last checked 2026-11-21).

| Stack | Model & renderer | Pick when | Avoid / watch-outs |
|---|---|---|---|
| **Tauri 2** | Retained DOM in OS WebView (WebView2 / WebKit) + Rust IPC | Rich data UIs (tables, charts, forms, rich text), existing HTML/CSS/React design system, fast visual polish | WebView process-tree RAM overhead; not for 120 FPS custom canvases or minimal tray utilities |
| **egui** | Immediate-mode (redraws from state each frame, wgpu / glow) | Internal dev tools, debuggers, profilers, parameter sweepers, embedded overlays; fastest zero-to-UI | Hard to match consumer/OS-native polish; complex text layout, IME and accessibility lag retained kits |
| **Iced** | Retained Elm MVU (`State → Message → Update → View`, wgpu / tiny-skia) | Pure-Rust cross-platform desktop apps needing predictable state, low RAM, no WebView, strong Linux polish | Thinner charting and complex-table ecosystem than web; pre-1.0 breaking releases |
| **GPUI** | Retained + GPU-accelerated custom engine (Zed's UI layer) | Ultra-dense, high-frame-rate custom surfaces (editors, terminals, large log/diff viewers, live feeds) | Rapid API churn, smaller off-the-shelf widget kit, heavy custom styling effort |
| **Slint** | Declarative `.slint` DSL compiled to native Rust (Skia / FemtoVG / software) | Ultra-lightweight native apps, tray companions, embedded UIs, native backdrop blur without WebView2 | Check licence first (GPLv3 / Royalty-free / Commercial); complex charts need custom canvas work |
| **Dioxus** | React-like RSX + reactive signals (WebView default; Blitz native in progress) | Rust teams wanting React ergonomics and shared web/desktop/mobile components | WebView desktop inherits WebView2 trade-offs; native renderer still maturing |
| **gtk-rs** | Retained native GTK4 bindings | Linux-first / GNOME-native desktop apps needing full OS accessibility and platform conventions | Heavy non-native packaging and theming friction on Windows and macOS |

## Selection rules
- Pick the **rendering model** first, not the brand: WebView hybrid when web widgets/CSS dominate; immediate-mode for internal engineering tools; retained native when zero-WebView footprint, native latency, or custom GPU rendering is a hard requirement.
- Prototype one representative screen with real data volume (HiDPI scaling, keyboard nav, text selection, accessibility, settled process-tree RAM) before committing to a pre-1.0 pure-Rust toolkit.
- Keep business logic, storage, and state in a GUI-free core crate so the UI layer stays replaceable.
- Never assume "pure Rust" beats WebView on shipping speed: if the app needs financial charts, complex filterable tables, or rich prose, Tauri 2 + a Rust core crate usually ships weeks faster.
