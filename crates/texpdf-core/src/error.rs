use std::path::PathBuf;

use thiserror::Error;

use crate::Diagnostic;

/// Failures that can be reported safely across the Stata ABI boundary.
#[derive(Debug, Error)]
pub enum TexPdfError {
    /// The requested source does not exist.
    #[error("input file does not exist: {0}")]
    InputMissing(PathBuf),

    /// The requested source is not a regular file.
    #[error("input path is not a regular file: {0}")]
    InputNotFile(PathBuf),

    /// The final output resolves to the primary source path.
    #[error("output PDF must not be the input TeX file: {0}")]
    OutputIsInput(PathBuf),

    /// The output exists and replacement was not authorized.
    #[error("output file already exists; specify replace: {0}")]
    OutputExists(PathBuf),

    /// A path cannot be represented as UTF-8 for the engine interface.
    #[error("path is not valid UTF-8: {0}")]
    NonUtf8Path(PathBuf),

    /// A filesystem operation failed.
    #[error("{context}: {source}")]
    Io {
        /// Human-readable operation context.
        context: String,
        /// Underlying I/O error.
        #[source]
        source: std::io::Error,
    },

    /// The embedded bundle could not be opened or described.
    #[error("embedded bundle error: {0}")]
    Bundle(String),

    /// Tectonic rejected the document or failed internally.
    #[error("{message}")]
    Engine {
        /// Concise primary message.
        message: String,
        /// Structured bounded diagnostics available to the caller.
        diagnostics: Vec<Diagnostic>,
    },

    /// The single-threaded engine lock was poisoned.
    #[error("internal engine synchronization failure")]
    EngineLock,
}

impl TexPdfError {
    pub(crate) fn io(context: impl Into<String>, source: std::io::Error) -> Self {
        Self::Io {
            context: context.into(),
            source,
        }
    }

    /// Diagnostics attached to an engine failure, if any.
    pub fn diagnostics(&self) -> &[Diagnostic] {
        match self {
            Self::Engine { diagnostics, .. } => diagnostics,
            _ => &[],
        }
    }
}
