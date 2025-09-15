pub mod analyzer;
pub mod complexity_analyzer;
pub mod indexer;

// Re-export main types and functions
pub use complexity_analyzer::*;
pub use indexer::{create_index, parser::*, CodeIndex};
