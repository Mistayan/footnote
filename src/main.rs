mod app;
mod daemon;
#[cfg(feature = "memory")]
mod hook;
mod install;
mod mcp;

// Moved to library crates (ADR 0001); imported here so `crate::<module>` paths keep working.
use footnote_core::{audit, metrics, state};
#[cfg(feature = "memory")]
use footnote_memory as memory;
#[cfg(feature = "library")]
use footnote_search::lexical;
use footnote_search::{records, semantic};

fn main() {
    app::run();
}
