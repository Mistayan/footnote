mod app;
mod audit;
mod daemon;
mod encoder;
#[cfg(feature = "llama")]
mod llama;
mod extract;
mod install;
mod lexical;
mod mcp;
mod memory;
mod metrics;
mod records;
mod semantic;
mod state;
fn main() {
    app::run();
}
