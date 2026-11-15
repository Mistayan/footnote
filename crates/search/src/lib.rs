//! Footnote's search engine: storage, keyword index (Tantivy), embeddings and fusion, records (ADR 0001).
pub mod encoder;
pub mod lexical;
#[cfg(feature = "llama")]
pub mod llama;
pub mod records;
pub mod semantic;
pub mod store;

use footnote_core::{metrics, state};
