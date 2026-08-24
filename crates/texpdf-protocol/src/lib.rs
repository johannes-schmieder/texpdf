//! Versioned file protocol between the Stata plugin and embedded helper.

use std::{
    collections::BTreeMap,
    fs,
    io::{self, Write},
    path::Path,
};

/// Current on-disk result schema.
pub const RESULT_SCHEMA_VERSION: u32 = 1;

/// Stata syntax error.
pub const RC_SYNTAX: i32 = 198;
/// Missing or invalid input file.
pub const RC_INPUT_MISSING: i32 = 601;
/// Existing output without replacement authorization.
pub const RC_OUTPUT_EXISTS: i32 = 602;
/// Filesystem or process I/O failure.
pub const RC_IO: i32 = 603;
/// Recoverable TeX/typesetting failure.
pub const RC_TEX_FAILURE: i32 = 459;
/// Internal bridge/helper failure.
pub const RC_INTERNAL: i32 = 710;
/// Embedded helper exceeded its execution deadline.
pub const RC_TIMEOUT: i32 = 711;

const MAX_RESULT_DIAGNOSTICS: usize = 20;

/// Severity of a bounded helper diagnostic.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DiagnosticKind {
    /// Informational note.
    Note,
    /// Nonfatal warning.
    Warning,
    /// Error-level diagnostic.
    Error,
    /// Bounded engine log excerpt.
    Log,
}

impl DiagnosticKind {
    /// Stable protocol spelling.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Note => "note",
            Self::Warning => "warning",
            Self::Error => "error",
            Self::Log => "log",
        }
    }
}

/// One protocol diagnostic.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Diagnostic {
    /// Severity.
    pub kind: DiagnosticKind,
    /// Single-record UTF-8 message.
    pub message: String,
}

/// Result status written by the helper.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ResultStatus {
    /// Operation completed successfully.
    Success,
    /// Operation failed with a Stata return code.
    Failure,
}

impl ResultStatus {
    const fn as_str(self) -> &'static str {
        match self {
            Self::Success => "success",
            Self::Failure => "failure",
        }
    }
}

/// Complete result record before serialization.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ResultRecord {
    /// Success or failure.
    pub status: ResultStatus,
    /// Stata return code; zero on success.
    pub rc: i32,
    /// Additional ordered key/value fields.
    pub fields: Vec<(String, String)>,
}

impl ResultRecord {
    /// Build a successful record.
    pub fn success(
        operation: impl Into<String>,
        mut fields: Vec<(String, String)>,
        diagnostics: &[Diagnostic],
    ) -> Self {
        fields.insert(0, ("operation".to_owned(), operation.into()));
        append_diagnostics(&mut fields, diagnostics);
        Self {
            status: ResultStatus::Success,
            rc: 0,
            fields,
        }
    }

    /// Build a failure record without additional metadata.
    pub fn failure(rc: i32, message: impl Into<String>, diagnostics: &[Diagnostic]) -> Self {
        Self::failure_with_fields(rc, message, Vec::new(), diagnostics)
    }

    /// Build a failure record with additional metadata.
    pub fn failure_with_fields(
        rc: i32,
        message: impl Into<String>,
        mut fields: Vec<(String, String)>,
        diagnostics: &[Diagnostic],
    ) -> Self {
        fields.insert(0, ("message".to_owned(), message.into()));
        append_diagnostics(&mut fields, diagnostics);
        Self {
            status: ResultStatus::Failure,
            rc,
            fields,
        }
    }
}

/// Minimal validated view used by the parent plugin.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ParsedResult {
    /// Protocol status.
    pub status: ResultStatus,
    /// Stata return code.
    pub rc: i32,
    /// Parsed fields, including protocol keys.
    pub fields: BTreeMap<String, String>,
}

fn append_diagnostics(fields: &mut Vec<(String, String)>, diagnostics: &[Diagnostic]) {
    let retained: Vec<_> = diagnostics
        .iter()
        .filter(|item| item.kind != DiagnosticKind::Note)
        .take(MAX_RESULT_DIAGNOSTICS)
        .collect();
    fields.push(("diagnostic_count".to_owned(), retained.len().to_string()));
    for (index, diagnostic) in retained.into_iter().enumerate() {
        let number = index + 1;
        fields.push((
            format!("diagnostic_{number}_kind"),
            diagnostic.kind.as_str().to_owned(),
        ));
        fields.push((
            format!("diagnostic_{number}_message"),
            diagnostic.message.clone(),
        ));
    }
}

/// Write a result atomically.
pub fn write_result_file(path: &Path, record: &ResultRecord) -> io::Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent)?;
    if path.exists() {
        fs::remove_file(path)?;
    }
    let mut temporary = tempfile::NamedTempFile::new_in(parent)?;
    writeln!(temporary, "schema_version={RESULT_SCHEMA_VERSION}")?;
    writeln!(temporary, "status={}", record.status.as_str())?;
    writeln!(temporary, "rc={}", record.rc)?;
    for (key, value) in &record.fields {
        validate_key(key)?;
        writeln!(temporary, "{key}={}", sanitize_value(value))?;
    }
    temporary.flush()?;
    temporary.as_file().sync_all()?;
    temporary.persist(path).map_err(|error| error.error)?;
    Ok(())
}

/// Parse and validate a result file.
pub fn read_result_file(path: &Path) -> io::Result<ParsedResult> {
    let text = fs::read_to_string(path)?;
    let mut fields = BTreeMap::new();
    for (line_number, line) in text.lines().enumerate() {
        let (key, value) = line.split_once('=').ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                format!("malformed result line {}", line_number + 1),
            )
        })?;
        validate_key(key)?;
        if fields.insert(key.to_owned(), value.to_owned()).is_some() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!("duplicate result key {key:?}"),
            ));
        }
    }
    let expected_schema = RESULT_SCHEMA_VERSION.to_string();
    if fields.get("schema_version").map(String::as_str) != Some(expected_schema.as_str()) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unsupported result schema",
        ));
    }
    let status = match fields.get("status").map(String::as_str) {
        Some("success") => ResultStatus::Success,
        Some("failure") => ResultStatus::Failure,
        _ => {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "invalid result status",
            ));
        }
    };
    let rc = fields
        .get("rc")
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidData, "missing result rc"))?
        .parse::<i32>()
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    if (status == ResultStatus::Success && rc != 0) || (status == ResultStatus::Failure && rc == 0)
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "inconsistent result status and rc",
        ));
    }
    Ok(ParsedResult { status, rc, fields })
}

fn validate_key(key: &str) -> io::Result<()> {
    if key.is_empty()
        || !key
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'_')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("invalid result key {key:?}"),
        ));
    }
    Ok(())
}

fn sanitize_value(value: &str) -> String {
    value.replace('\0', "\\0").replace(['\r', '\n'], " | ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn successful_record_round_trips() {
        let directory = tempfile::tempdir().expect("tempdir");
        let path = directory.path().join("result.txt");
        let record = ResultRecord::success(
            "version",
            vec![("engine".to_owned(), "tectonic".to_owned())],
            &[],
        );
        write_result_file(&path, &record).expect("write result");
        let parsed = read_result_file(&path).expect("read result");
        assert_eq!(parsed.status, ResultStatus::Success);
        assert_eq!(parsed.rc, 0);
        assert_eq!(
            parsed.fields.get("engine").map(String::as_str),
            Some("tectonic")
        );
    }

    #[test]
    fn failure_diagnostics_are_bounded_and_sanitized() {
        let diagnostics = (0..30)
            .map(|number| Diagnostic {
                kind: DiagnosticKind::Error,
                message: format!("line {number}\ncontinued"),
            })
            .collect::<Vec<_>>();
        let record = ResultRecord::failure(459, "failed\ncleanly", &diagnostics);
        assert_eq!(record.fields[0].1, "failed\ncleanly");
        let directory = tempfile::tempdir().expect("tempdir");
        let path = directory.path().join("result.txt");
        write_result_file(&path, &record).expect("write result");
        let text = fs::read_to_string(path).expect("read text");
        assert!(text.contains("message=failed | cleanly"));
        assert!(text.contains("diagnostic_count=20"));
        assert!(!text.contains("diagnostic_21_message"));
    }

    #[test]
    fn malformed_result_is_rejected() {
        let directory = tempfile::tempdir().expect("tempdir");
        let path = directory.path().join("bad.txt");
        fs::write(&path, "schema_version=1\nstatus=success\nrc=1\n")
            .expect("write malformed result");
        assert_eq!(
            read_result_file(&path).expect_err("must reject").kind(),
            io::ErrorKind::InvalidData
        );
    }
}
