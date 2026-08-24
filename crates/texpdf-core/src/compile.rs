use std::{
    env, fs,
    path::{Path, PathBuf},
    sync::{Mutex, OnceLock},
};

use tectonic::driver::{OutputFormat, ProcessingSessionBuilder};

use crate::{
    bundle::{bundle_info, open_bundle},
    diagnostics::DiagnosticCollector,
    CompileRequest, CompileResult, TexPdfError, TECTONIC_VERSION,
};

static ENGINE_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

/// Compile one complete LaTeX document with the embedded offline bundle.
pub fn compile(request: &CompileRequest) -> Result<CompileResult, TexPdfError> {
    let engine_lock = ENGINE_LOCK.get_or_init(|| Mutex::new(()));
    let _guard = engine_lock.lock().map_err(|_| TexPdfError::EngineLock)?;
    compile_locked(request)
}

fn compile_locked(request: &CompileRequest) -> Result<CompileResult, TexPdfError> {
    if !request.input.exists() {
        return Err(TexPdfError::InputMissing(request.input.clone()));
    }
    if !request.input.is_file() {
        return Err(TexPdfError::InputNotFile(request.input.clone()));
    }

    let input = fs::canonicalize(&request.input)
        .map_err(|error| TexPdfError::io("cannot resolve input path", error))?;
    let output = resolve_output_path(&request.output)?;

    if output.exists() {
        let existing_output = fs::canonicalize(&output)
            .map_err(|error| TexPdfError::io("cannot resolve existing output path", error))?;
        if existing_output == input {
            return Err(TexPdfError::OutputIsInput(output));
        }
        if !request.replace {
            return Err(TexPdfError::OutputExists(output));
        }
    }

    let input_dir = input
        .parent()
        .ok_or_else(|| TexPdfError::Bundle("input has no parent directory".to_owned()))?;
    let input_name = input
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| TexPdfError::NonUtf8Path(input.clone()))?;
    let output_parent = output
        .parent()
        .ok_or_else(|| TexPdfError::Bundle("output has no parent directory".to_owned()))?;

    let info = bundle_info()?.clone();
    let format_cache = format_cache_path(&info.tectonic_bundle_digest);
    fs::create_dir_all(&format_cache)
        .map_err(|error| TexPdfError::io("cannot create format cache", error))?;
    let staging = tempfile::Builder::new()
        .prefix(".texpdf-")
        .tempdir_in(output_parent)
        .map_err(|error| TexPdfError::io("cannot create output staging directory", error))?;

    let mut status = DiagnosticCollector::default();
    let mut builder = ProcessingSessionBuilder::default();
    builder
        .primary_input_path(&input)
        .tex_input_name(input_name)
        .filesystem_root(input_dir)
        .output_dir(staging.path())
        .format_name("latex")
        .format_cache_path(&format_cache)
        .output_format(OutputFormat::Pdf)
        .keep_intermediates(false)
        .keep_logs(request.keep_log)
        .print_stdout(false)
        .shell_escape_disabled()
        .build_date_from_env(false)
        .bundle(open_bundle()?);

    let mut session = builder
        .create(&mut status)
        .map_err(|error| TexPdfError::Engine {
            message: format!("cannot initialize Tectonic: {error:#}"),
            diagnostics: status.snapshot(),
        })?;
    session
        .run(&mut status)
        .map_err(|error| TexPdfError::Engine {
            message: format!("LaTeX compilation failed: {error:#}"),
            diagnostics: status.snapshot(),
        })?;

    let generated_pdf = staging
        .path()
        .join(Path::new(input_name).with_extension("pdf"));
    if !generated_pdf.is_file() {
        return Err(TexPdfError::Engine {
            message: "Tectonic reported success but produced no PDF".to_owned(),
            diagnostics: status.snapshot(),
        });
    }

    if output.exists() {
        fs::remove_file(&output)
            .map_err(|error| TexPdfError::io("cannot replace existing output", error))?;
    }
    fs::rename(&generated_pdf, &output)
        .map_err(|error| TexPdfError::io("cannot install compiled PDF", error))?;

    if request.keep_log {
        let generated_log = staging
            .path()
            .join(Path::new(input_name).with_extension("log"));
        if generated_log.is_file() {
            let output_log = output.with_extension("log");
            if output_log.exists() && request.replace {
                fs::remove_file(&output_log)
                    .map_err(|error| TexPdfError::io("cannot replace existing log", error))?;
            }
            fs::rename(generated_log, output_log)
                .map_err(|error| TexPdfError::io("cannot install TeX log", error))?;
        }
    }

    Ok(CompileResult {
        output,
        diagnostics: status.into_items(),
        engine_version: TECTONIC_VERSION.to_owned(),
        bundle_version: info.bundle_version,
        bundle_digest: info.tectonic_bundle_digest,
        bundle_zip_sha256: info.zip_sha256,
    })
}

fn absolute_path(path: &Path) -> Result<PathBuf, TexPdfError> {
    if path.is_absolute() {
        return Ok(path.to_owned());
    }
    env::current_dir()
        .map(|directory| directory.join(path))
        .map_err(|error| TexPdfError::io("cannot resolve current directory", error))
}

fn resolve_output_path(path: &Path) -> Result<PathBuf, TexPdfError> {
    let absolute = absolute_path(path)?;
    let parent = absolute
        .parent()
        .ok_or_else(|| TexPdfError::Bundle("output has no parent directory".to_owned()))?;
    if !parent.is_dir() {
        return Err(TexPdfError::io(
            format!("output directory does not exist: {}", parent.display()),
            std::io::Error::new(std::io::ErrorKind::NotFound, "directory not found"),
        ));
    }
    if absolute.file_name().is_none() {
        return Err(TexPdfError::Bundle(
            "output has no file name".to_owned(),
        ));
    }
    Ok(absolute)
}

fn format_cache_path(bundle_digest: &str) -> PathBuf {
    if let Some(path) = env::var_os("TEXPDF_FORMAT_CACHE") {
        return PathBuf::from(path).join(bundle_digest);
    }
    env::temp_dir()
        .join("texpdf-format-cache")
        .join(bundle_digest)
}

#[cfg(test)]
mod tests {
    use super::*;

    const MINIMAL: &str = r#"\documentclass{article}
\begin{document}
Hello from texpdf. $\hat\beta=(X'X)^{-1}X'y$.
\end{document}
"#;

    #[test]
    fn resolves_existing_output_directory_without_canonicalizing_it() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let spelling = format!("{}//result.pdf", workspace.path().display());
        let resolved = resolve_output_path(Path::new(&spelling)).expect("resolve output");
        assert_eq!(resolved.file_name().and_then(|name| name.to_str()), Some("result.pdf"));
    }

    #[test]
    fn compiles_minimal_document_and_enforces_replace() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let input = workspace.path().join("minimal.tex");
        let output = workspace.path().join("minimal.pdf");
        fs::write(&input, MINIMAL).expect("write source");

        let request = CompileRequest::new(&input, &output);
        let result = compile(&request).expect("compile minimal document");
        let bytes = fs::read(&result.output).expect("read PDF");
        assert!(bytes.starts_with(b"%PDF-"));
        assert_eq!(result.engine_version, TECTONIC_VERSION);

        let error = compile(&request).expect_err("overwrite must be rejected");
        assert!(matches!(error, TexPdfError::OutputExists(_)));

        let mut replacement = request;
        replacement.replace = true;
        compile(&replacement).expect("replace output");
    }

    #[test]
    fn rejects_output_that_is_the_input_even_with_replace() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let input = workspace.path().join("source.tex");
        fs::write(&input, MINIMAL).expect("write source");
        let mut request = CompileRequest::new(&input, &input);
        request.replace = true;

        let error = compile(&request).expect_err("source overwrite must be rejected");
        assert!(matches!(error, TexPdfError::OutputIsInput(_)));
        assert_eq!(fs::read_to_string(input).expect("source survives"), MINIMAL);
    }

    #[test]
    fn reports_bad_latex_without_panicking() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let input = workspace.path().join("bad.tex");
        let output = workspace.path().join("bad.pdf");
        fs::write(
            &input,
            "\\documentclass{article}\\begin{document}\\undefinedcontrolsequence\\end{document}",
        )
        .expect("write source");
        let error = compile(&CompileRequest::new(input, output)).expect_err("bad TeX");
        assert!(matches!(error, TexPdfError::Engine { .. }));
        assert!(!error.diagnostics().is_empty());
    }
}
