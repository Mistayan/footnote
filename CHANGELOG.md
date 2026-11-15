# Changelog

Notable changes to Footnote, newest first. Versions follow semantic versioning; the first tagged release will be 0.1.0.

## Unreleased

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
