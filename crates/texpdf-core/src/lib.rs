//! Standalone, offline LaTeX-to-PDF compilation for `texpdf`.
//!
//! The public API deliberately exposes no Tectonic types. The Stata bridge and
//! future non-Stata callers use the same request/result/error contract.

mod bundle;
mod compile;
mod diagnostics;
mod error;
mod memory;

use std::path::PathBuf;

pub use bundle::{bundle_info, BundleInfo};
pub use diagnostics::{Diagnostic, DiagnosticKind};
pub use error::TexPdfError;

/// The Tectonic crate version pinned by this release.
pub const TECTONIC_VERSION: &str = "0.17.0";

/// A request to compile one complete LaTeX document.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CompileRequest {
    /// Primary `.tex` input path.
    pub input: PathBuf,
    /// Final PDF path.
    pub output: PathBuf,
    /// Whether an existing output may be replaced.
    pub replace: bool,
    /// Whether the TeX log should be retained next to the output PDF.
    pub keep_log: bool,
}

impl CompileRequest {
    /// Construct a request with safe defaults: no overwrite and no retained log.
    pub fn new(input: impl Into<PathBuf>, output: impl Into<PathBuf>) -> Self {
        Self {
            input: input.into(),
            output: output.into(),
            replace: false,
            keep_log: false,
        }
    }
}

/// Metadata returned after a successful compile.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CompileResult {
    /// Final PDF path.
    pub output: PathBuf,
    /// Nonfatal diagnostics captured during processing.
    pub diagnostics: Vec<Diagnostic>,
    /// Pinned Tectonic version.
    pub engine_version: String,
    /// Human-readable embedded bundle version.
    pub bundle_version: String,
    /// Tectonic content digest stored in the bundle.
    pub bundle_digest: String,
    /// SHA-256 of the embedded deterministic ZIP.
    pub bundle_zip_sha256: String,
}

impl CompileResult {
    /// Number of warning diagnostics emitted by the engine.
    pub fn warning_count(&self) -> usize {
        self.diagnostics
            .iter()
            .filter(|item| item.kind == DiagnosticKind::Warning)
            .count()
    }
}

/// Compile one complete LaTeX document with the embedded offline bundle.
///
/// The pressure-relief guard is created before entering the engine so that it
/// runs after all per-compilation Rust and native wrapper objects have been
/// dropped, including on recoverable errors.
pub fn compile(request: &CompileRequest) -> Result<CompileResult, TexPdfError> {
    let _memory_pressure_relief = memory::MemoryPressureReliefGuard::new();
    compile::compile(request)
}
