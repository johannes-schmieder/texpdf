//! Isolated Tectonic compiler embedded in the `texpdf` Stata plugin.

use std::{
    env,
    ffi::{OsStr, OsString},
    panic::{catch_unwind, AssertUnwindSafe},
    path::{Path, PathBuf},
    process,
};

use texpdf_core::{
    bundle_info, compile, CompileRequest, Diagnostic as CoreDiagnostic,
    DiagnosticKind as CoreDiagnosticKind, TexPdfError, TECTONIC_VERSION,
};
use texpdf_protocol::{
    write_result_file, Diagnostic, DiagnosticKind, ResultRecord, RC_INPUT_MISSING, RC_INTERNAL,
    RC_IO, RC_OUTPUT_EXISTS, RC_SYNTAX, RC_TEX_FAILURE, RESULT_SCHEMA_VERSION,
};

#[derive(Debug)]
struct HelperFailure {
    rc: i32,
    message: String,
    diagnostics: Vec<Diagnostic>,
}

impl HelperFailure {
    fn new(rc: i32, message: impl Into<String>) -> Self {
        Self {
            rc,
            message: message.into(),
            diagnostics: Vec::new(),
        }
    }
}

fn expected_result_path(arguments: &[OsString]) -> Option<PathBuf> {
    match arguments.first().and_then(|value| value.to_str()) {
        Some("version") if arguments.len() >= 2 => Some(PathBuf::from(&arguments[1])),
        Some("compile") if arguments.len() >= 4 => Some(PathBuf::from(&arguments[3])),
        _ => None,
    }
}

fn operation_name(arguments: &[OsString]) -> String {
    arguments
        .first()
        .and_then(|value| value.to_str())
        .unwrap_or("invalid")
        .to_owned()
}

fn common_fields() -> Vec<(String, String)> {
    let mut fields = vec![
        ("execution_model".to_owned(), "embedded_helper".to_owned()),
        (
            "helper_protocol".to_owned(),
            RESULT_SCHEMA_VERSION.to_string(),
        ),
    ];
    if let Some(digest) = env::var_os("TEXPDF_HELPER_DIGEST") {
        fields.push((
            "helper_sha256".to_owned(),
            digest.to_string_lossy().into_owned(),
        ));
    }
    fields
}

fn success_record(
    operation: &str,
    mut fields: Vec<(String, String)>,
    diagnostics: &[Diagnostic],
) -> ResultRecord {
    fields.extend(common_fields());
    ResultRecord::success(operation, fields, diagnostics)
}

fn failure_record(operation: &str, failure: HelperFailure) -> ResultRecord {
    let mut fields = common_fields();
    fields.insert(0, ("operation".to_owned(), operation.to_owned()));
    ResultRecord::failure_with_fields(failure.rc, failure.message, fields, &failure.diagnostics)
}

fn dispatch(arguments: &[OsString]) -> Result<ResultRecord, HelperFailure> {
    match arguments.first().and_then(|value| value.to_str()) {
        Some("version") => version_command(arguments),
        Some("compile") => compile_command(arguments),
        Some(other) => Err(HelperFailure::new(
            RC_SYNTAX,
            format!("unknown texpdf helper operation: {other}"),
        )),
        None => Err(HelperFailure::new(
            RC_SYNTAX,
            "missing texpdf helper operation",
        )),
    }
}

fn version_command(arguments: &[OsString]) -> Result<ResultRecord, HelperFailure> {
    if arguments.len() != 2 {
        return Err(HelperFailure::new(
            RC_SYNTAX,
            "version operation expects one result-file argument",
        ));
    }
    let info = bundle_info().map_err(map_core_error)?;
    Ok(success_record(
        "version",
        vec![
            ("engine".to_owned(), "tectonic".to_owned()),
            ("engine_version".to_owned(), TECTONIC_VERSION.to_owned()),
            ("bundle_version".to_owned(), info.bundle_version.clone()),
            (
                "bundle_digest".to_owned(),
                info.tectonic_bundle_digest.clone(),
            ),
            ("bundle_zip_sha256".to_owned(), info.zip_sha256.clone()),
            ("warnings".to_owned(), "0".to_owned()),
        ],
        &[],
    ))
}

fn compile_command(arguments: &[OsString]) -> Result<ResultRecord, HelperFailure> {
    if arguments.len() != 6 {
        return Err(HelperFailure::new(
            RC_SYNTAX,
            "compile operation expects input, output, result file, replace flag, and log flag",
        ));
    }
    let replace = parse_flag(&arguments[4], "replace")?;
    let keep_log = parse_flag(&arguments[5], "keep-log")?;
    let mut request = CompileRequest::new(
        PathBuf::from(arguments[1].clone()),
        PathBuf::from(arguments[2].clone()),
    );
    request.replace = replace;
    request.keep_log = keep_log;

    let result = compile(&request).map_err(map_core_error)?;
    let diagnostics = convert_diagnostics(&result.diagnostics);
    let warning_count = result.warning_count();
    Ok(success_record(
        "compile",
        vec![
            (
                "pdf".to_owned(),
                result.output.to_string_lossy().into_owned(),
            ),
            ("engine".to_owned(), "tectonic".to_owned()),
            ("engine_version".to_owned(), result.engine_version),
            ("bundle_version".to_owned(), result.bundle_version),
            ("bundle_digest".to_owned(), result.bundle_digest),
            ("bundle_zip_sha256".to_owned(), result.bundle_zip_sha256),
            ("warnings".to_owned(), warning_count.to_string()),
        ],
        &diagnostics,
    ))
}

fn parse_flag(value: &OsStr, name: &str) -> Result<bool, HelperFailure> {
    match value.to_str() {
        Some("0") => Ok(false),
        Some("1") => Ok(true),
        _ => Err(HelperFailure::new(
            RC_SYNTAX,
            format!("{name} flag must be 0 or 1"),
        )),
    }
}

fn convert_diagnostics(diagnostics: &[CoreDiagnostic]) -> Vec<Diagnostic> {
    diagnostics
        .iter()
        .map(|diagnostic| Diagnostic {
            kind: match diagnostic.kind {
                CoreDiagnosticKind::Note => DiagnosticKind::Note,
                CoreDiagnosticKind::Warning => DiagnosticKind::Warning,
                CoreDiagnosticKind::Error => DiagnosticKind::Error,
                CoreDiagnosticKind::Log => DiagnosticKind::Log,
            },
            message: diagnostic.message.clone(),
        })
        .collect()
}

fn map_core_error(error: TexPdfError) -> HelperFailure {
    let rc = match &error {
        TexPdfError::InputMissing(_) | TexPdfError::InputNotFile(_) => RC_INPUT_MISSING,
        TexPdfError::OutputExists(_) => RC_OUTPUT_EXISTS,
        TexPdfError::OutputIsInput(_) | TexPdfError::NonUtf8Path(_) => RC_SYNTAX,
        TexPdfError::Io { .. } => RC_IO,
        TexPdfError::Engine { .. } => RC_TEX_FAILURE,
        TexPdfError::Bundle(_) | TexPdfError::EngineLock => RC_INTERNAL,
    };
    HelperFailure {
        rc,
        message: error.to_string(),
        diagnostics: convert_diagnostics(error.diagnostics()),
    }
}

fn write_record(path: &Path, record: &ResultRecord) -> Result<(), String> {
    write_result_file(path, record)
        .map_err(|error| format!("cannot write helper result {}: {error}", path.display()))
}

fn run() -> Result<(), String> {
    let arguments = env::args_os().skip(1).collect::<Vec<_>>();
    let result_path = expected_result_path(&arguments).ok_or_else(|| {
        "helper invocation does not identify a valid result-file argument".to_owned()
    })?;
    let operation = operation_name(&arguments);
    let record = match catch_unwind(AssertUnwindSafe(|| dispatch(&arguments))) {
        Ok(Ok(record)) => record,
        Ok(Err(failure)) => failure_record(&operation, failure),
        Err(_) => failure_record(
            &operation,
            HelperFailure::new(
                RC_INTERNAL,
                "the isolated Tectonic helper panicked; the unwind was contained",
            ),
        ),
    };
    write_record(&result_path, &record)
}

fn main() {
    if let Err(error) = run() {
        eprintln!("TEXPDF_HELPER_ERROR {error}");
        process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn result_path_is_selected_by_operation() {
        assert_eq!(
            expected_result_path(&[OsString::from("version"), OsString::from("result.txt"),]),
            Some(PathBuf::from("result.txt"))
        );
        assert_eq!(
            expected_result_path(&[
                OsString::from("compile"),
                OsString::from("in.tex"),
                OsString::from("out.pdf"),
                OsString::from("result.txt"),
                OsString::from("0"),
                OsString::from("0"),
            ]),
            Some(PathBuf::from("result.txt"))
        );
    }

    #[test]
    fn bad_boolean_flag_is_rejected() {
        let error = parse_flag(OsStr::new("yes"), "replace").expect_err("bad flag");
        assert_eq!(error.rc, RC_SYNTAX);
    }

    #[test]
    fn version_record_uses_embedded_bundle_metadata() {
        let record = version_command(&[OsString::from("version"), OsString::from("result.txt")])
            .expect("version record");
        assert_eq!(record.rc, 0);
        assert!(record
            .fields
            .iter()
            .any(|(key, value)| key == "engine" && value == "tectonic"));
    }
}
