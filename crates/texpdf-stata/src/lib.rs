//! Stata SPI 3.0 bridge for `texpdf`.
//!
//! Only `pginit` and `stata_call` cross the native ABI. Substantial result data
//! are returned through a bounded line-oriented result file, which keeps the
//! bridge independent of Stata callback-table details.

use std::{
    ffi::{c_char, c_int, c_void, CStr},
    fs,
    io::Write,
    panic::{catch_unwind, AssertUnwindSafe},
    path::{Path, PathBuf},
    slice,
};

use texpdf_core::{
    bundle_info, compile, CompileRequest, Diagnostic, DiagnosticKind, TexPdfError,
    TECTONIC_VERSION,
};

const SPI_VERSION_3_0: c_int = 3;
const RC_SYNTAX: i32 = 198;
const RC_INPUT_MISSING: i32 = 601;
const RC_OUTPUT_EXISTS: i32 = 602;
const RC_IO: i32 = 603;
const RC_TEX_FAILURE: i32 = 459;
const RC_INTERNAL: i32 = 710;
const RESULT_SCHEMA_VERSION: u32 = 1;
const MAX_RESULT_DIAGNOSTICS: usize = 20;

/// Initialize the plugin under Stata's SPI 3.0 protocol.
///
/// `stplugin.c` returns `SF_MAKELONG(3, 0)` for SPI 3.0, which is the integer
/// value three. This bridge does not use Stata's callback table, so the pointer
/// remains opaque.
#[unsafe(no_mangle)]
pub extern "C" fn pginit(_stata: *mut c_void) -> c_int {
    SPI_VERSION_3_0
}

/// Execute one bridge request from Stata.
///
/// # Safety
///
/// Stata must provide `argc` valid, NUL-terminated C strings through `argv` for
/// the duration of this call, as required by the SPI 3.0 plugin ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn stata_call(argc: c_int, argv: *mut *mut c_char) -> c_int {
    let args = match unsafe { collect_arguments(argc, argv) } {
        Ok(values) => values,
        Err(_) => return RC_SYNTAX,
    };
    let result_path = expected_result_path(&args).map(Path::to_owned);
    let record = match catch_unwind(AssertUnwindSafe(|| dispatch(&args))) {
        Ok(Ok(record)) => record,
        Ok(Err(failure)) => ResultRecord::failure(failure),
        Err(_) => ResultRecord::failure(BridgeFailure::new(
            RC_INTERNAL,
            "the native texpdf engine panicked; the unwind was contained at the ABI boundary",
        )),
    };

    let Some(path) = result_path else {
        return if record.status == ResultStatus::Success {
            0
        } else {
            RC_SYNTAX
        };
    };

    if write_result_file(&path, &record).is_err() {
        return RC_INTERNAL;
    }

    // Returning a nonzero code would make Stata abort before the ado layer can
    // read the structured result. Ordinary compile failures therefore return
    // through the result record; nonzero values are reserved for bridge-level
    // failures such as an invalid invocation or unwritable result path.
    0
}

unsafe fn collect_arguments(
    argc: c_int,
    argv: *mut *mut c_char,
) -> Result<Vec<String>, BridgeFailure> {
    if argc < 0 || (argc > 0 && argv.is_null()) {
        return Err(BridgeFailure::new(
            RC_SYNTAX,
            "invalid plugin argument vector",
        ));
    }
    let raw = if argc == 0 {
        &[][..]
    } else {
        unsafe { slice::from_raw_parts(argv, argc as usize) }
    };
    let mut values = Vec::with_capacity(raw.len());
    for (index, pointer) in raw.iter().enumerate() {
        let argument_number = index + 1;
        if pointer.is_null() {
            return Err(BridgeFailure::new(
                RC_SYNTAX,
                format!("plugin argument {argument_number} is null"),
            ));
        }
        let value = unsafe { CStr::from_ptr(*pointer) }
            .to_str()
            .map_err(|_| {
                BridgeFailure::new(
                    RC_SYNTAX,
                    format!("plugin argument {argument_number} is not valid UTF-8"),
                )
            })?
            .to_owned();
        values.push(value);
    }
    Ok(values)
}

fn expected_result_path(args: &[String]) -> Option<&Path> {
    match args.first().map(String::as_str) {
        Some("version") if args.len() >= 2 => Some(Path::new(&args[1])),
        Some("compile") if args.len() >= 4 => Some(Path::new(&args[3])),
        _ => None,
    }
}

fn dispatch(args: &[String]) -> Result<ResultRecord, BridgeFailure> {
    match args.first().map(String::as_str) {
        Some("version") => version_command(args),
        Some("compile") => compile_command(args),
        Some(other) => Err(BridgeFailure::new(
            RC_SYNTAX,
            format!("unknown texpdf plugin operation: {other}"),
        )),
        None => Err(BridgeFailure::new(
            RC_SYNTAX,
            "missing texpdf plugin operation",
        )),
    }
}

fn version_command(args: &[String]) -> Result<ResultRecord, BridgeFailure> {
    if args.len() != 2 {
        return Err(BridgeFailure::new(
            RC_SYNTAX,
            "version operation expects one result-file argument",
        ));
    }
    let info = bundle_info().map_err(map_core_error)?;
    Ok(ResultRecord::version(
        TECTONIC_VERSION,
        &info.bundle_version,
        &info.tectonic_bundle_digest,
        &info.zip_sha256,
    ))
}

fn compile_command(args: &[String]) -> Result<ResultRecord, BridgeFailure> {
    if args.len() != 6 {
        return Err(BridgeFailure::new(
            RC_SYNTAX,
            "compile operation expects input, output, result file, replace flag, and log flag",
        ));
    }
    let replace = parse_flag(&args[4], "replace")?;
    let keep_log = parse_flag(&args[5], "keep-log")?;
    let mut request = CompileRequest::new(PathBuf::from(&args[1]), PathBuf::from(&args[2]));
    request.replace = replace;
    request.keep_log = keep_log;
    let result = compile(&request).map_err(map_core_error)?;
    Ok(ResultRecord::compiled(
        &result.output,
        &result.engine_version,
        &result.bundle_version,
        &result.bundle_digest,
        &result.bundle_zip_sha256,
        result.warning_count(),
        &result.diagnostics,
    ))
}

fn parse_flag(value: &str, name: &str) -> Result<bool, BridgeFailure> {
    match value {
        "0" => Ok(false),
        "1" => Ok(true),
        _ => Err(BridgeFailure::new(
            RC_SYNTAX,
            format!("{name} flag must be 0 or 1"),
        )),
    }
}

fn map_core_error(error: TexPdfError) -> BridgeFailure {
    let rc = match &error {
        TexPdfError::InputMissing(_) | TexPdfError::InputNotFile(_) => RC_INPUT_MISSING,
        TexPdfError::OutputExists(_) => RC_OUTPUT_EXISTS,
        TexPdfError::OutputIsInput(_) | TexPdfError::NonUtf8Path(_) => RC_SYNTAX,
        TexPdfError::Io { .. } => RC_IO,
        TexPdfError::Engine { .. } => RC_TEX_FAILURE,
        TexPdfError::Bundle(_) | TexPdfError::EngineLock => RC_INTERNAL,
    };
    BridgeFailure {
        rc,
        message: error.to_string(),
        diagnostics: error.diagnostics().to_vec(),
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ResultStatus {
    Success,
    Failure,
}

#[derive(Debug)]
struct ResultRecord {
    status: ResultStatus,
    rc: i32,
    fields: Vec<(String, String)>,
}

impl ResultRecord {
    fn version(engine: &str, bundle_version: &str, bundle_digest: &str, zip_sha: &str) -> Self {
        Self {
            status: ResultStatus::Success,
            rc: 0,
            fields: vec![
                ("operation".into(), "version".into()),
                ("engine".into(), "tectonic".into()),
                ("engine_version".into(), engine.into()),
                ("bundle_version".into(), bundle_version.into()),
                ("bundle_digest".into(), bundle_digest.into()),
                ("bundle_zip_sha256".into(), zip_sha.into()),
                ("warnings".into(), "0".into()),
                ("diagnostic_count".into(), "0".into()),
            ],
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn compiled(
        output: &Path,
        engine_version: &str,
        bundle_version: &str,
        bundle_digest: &str,
        zip_sha: &str,
        warning_count: usize,
        diagnostics: &[Diagnostic],
    ) -> Self {
        let mut fields = vec![
            ("operation".into(), "compile".into()),
            ("pdf".into(), output.to_string_lossy().into_owned()),
            ("engine".into(), "tectonic".into()),
            ("engine_version".into(), engine_version.into()),
            ("bundle_version".into(), bundle_version.into()),
            ("bundle_digest".into(), bundle_digest.into()),
            ("bundle_zip_sha256".into(), zip_sha.into()),
            ("warnings".into(), warning_count.to_string()),
        ];
        append_diagnostics(&mut fields, diagnostics);
        Self {
            status: ResultStatus::Success,
            rc: 0,
            fields,
        }
    }

    fn failure(failure: BridgeFailure) -> Self {
        let mut fields = vec![("message".into(), failure.message)];
        append_diagnostics(&mut fields, &failure.diagnostics);
        Self {
            status: ResultStatus::Failure,
            rc: failure.rc,
            fields,
        }
    }
}

fn append_diagnostics(fields: &mut Vec<(String, String)>, diagnostics: &[Diagnostic]) {
    let retained: Vec<_> = diagnostics
        .iter()
        .filter(|item| item.kind != DiagnosticKind::Note)
        .take(MAX_RESULT_DIAGNOSTICS)
        .collect();
    fields.push(("diagnostic_count".into(), retained.len().to_string()));
    for (index, diagnostic) in retained.into_iter().enumerate() {
        let number = index + 1;
        fields.push((
            format!("diagnostic_{number}_kind"),
            diagnostic_kind_name(diagnostic.kind).into(),
        ));
        fields.push((
            format!("diagnostic_{number}_message"),
            diagnostic.message.clone(),
        ));
    }
}

fn diagnostic_kind_name(kind: DiagnosticKind) -> &'static str {
    match kind {
        DiagnosticKind::Note => "note",
        DiagnosticKind::Warning => "warning",
        DiagnosticKind::Error => "error",
        DiagnosticKind::Log => "log",
    }
}

#[derive(Debug)]
struct BridgeFailure {
    rc: i32,
    message: String,
    diagnostics: Vec<Diagnostic>,
}

impl BridgeFailure {
    fn new(rc: i32, message: impl Into<String>) -> Self {
        Self {
            rc,
            message: message.into(),
            diagnostics: Vec::new(),
        }
    }
}

fn write_result_file(path: &Path, record: &ResultRecord) -> std::io::Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent)?;
    if path.exists() {
        fs::remove_file(path)?;
    }
    let mut temporary = tempfile::NamedTempFile::new_in(parent)?;
    writeln!(temporary, "schema_version={RESULT_SCHEMA_VERSION}")?;
    writeln!(
        temporary,
        "status={}",
        match record.status {
            ResultStatus::Success => "success",
            ResultStatus::Failure => "failure",
        }
    )?;
    writeln!(temporary, "rc={}", record.rc)?;
    for (key, value) in &record.fields {
        writeln!(temporary, "{key}={}", sanitize_value(value))?;
    }
    temporary.flush()?;
    temporary.persist(path).map_err(|error| error.error)?;
    Ok(())
}

fn sanitize_value(value: &str) -> String {
    value.replace('\0', "\\0").replace(['\r', '\n'], " | ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_record_is_machine_readable() {
        let workspace = tempfile::tempdir().expect("tempdir");
        let result_path = workspace.path().join("version.result");
        let args = vec![
            "version".to_owned(),
            result_path.to_string_lossy().into_owned(),
        ];
        let record = dispatch(&args).expect("version record");
        write_result_file(&result_path, &record).expect("write record");
        let text = fs::read_to_string(result_path).expect("read record");
        assert!(text.contains("status=success\n"));
        assert!(text.contains("engine=tectonic\n"));
        assert!(text.contains("bundle_digest="));
    }

    #[test]
    fn rejects_bad_flags() {
        let args = vec![
            "compile".to_owned(),
            "input.tex".to_owned(),
            "output.pdf".to_owned(),
            "result.txt".to_owned(),
            "yes".to_owned(),
            "0".to_owned(),
        ];
        let error = dispatch(&args).expect_err("bad flag");
        assert_eq!(error.rc, RC_SYNTAX);
    }

    #[test]
    fn sanitizes_multiline_values() {
        assert_eq!(sanitize_value("a\nb\r\nc"), "a | b |  | c");
    }
}
