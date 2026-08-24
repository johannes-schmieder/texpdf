//! Verified extraction and execution of the helper embedded in the plugin.

use std::{
    env,
    fs::{self, File, OpenOptions},
    io::{self, Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Mutex, OnceLock},
    thread,
    time::{Duration, Instant},
};

use sha2::{Digest, Sha256};
use texpdf_protocol::{
    read_result_file, ParsedResult, ResultStatus, RESULT_SCHEMA_VERSION, RC_INTERNAL, RC_IO,
    RC_SYNTAX, RC_TIMEOUT,
};

static HELPER_BYTES: &[u8] = include_bytes!(concat!(env!("OUT_DIR"), "/texpdf-helper.bin"));
static HELPER_DIGEST: OnceLock<String> = OnceLock::new();
static EXTRACTION_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

const DEFAULT_TIMEOUT_SECONDS: u64 = 300;
const MAX_TIMEOUT_SECONDS: u64 = 3600;

/// Failure that the Stata ABI layer can serialize safely.
#[derive(Debug)]
pub(crate) struct HelperBridgeError {
    pub(crate) rc: i32,
    pub(crate) message: String,
}

impl HelperBridgeError {
    fn new(rc: i32, message: impl Into<String>) -> Self {
        Self {
            rc,
            message: message.into(),
        }
    }

    fn io(context: &str, error: io::Error) -> Self {
        Self::new(RC_IO, format!("{context}: {error}"))
    }
}

/// Execute one helper operation and validate the result it wrote.
pub(crate) fn run(arguments: &[String], result_path: &Path) -> Result<ParsedResult, HelperBridgeError> {
    if cfg!(texpdf_helper_stub) {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "this plugin was built without a real embedded helper executable",
        ));
    }
    let operation = arguments
        .first()
        .ok_or_else(|| HelperBridgeError::new(RC_SYNTAX, "missing helper operation"))?;
    if result_path.exists() {
        fs::remove_file(result_path)
            .map_err(|error| HelperBridgeError::io("cannot clear prior result file", error))?;
    }

    let helper = ensure_embedded_helper()?;
    let digest = helper_digest();
    let timeout = helper_timeout()?;
    let mut child = Command::new(&helper)
        .args(arguments)
        .env("TEXPDF_HELPER_DIGEST", digest)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| HelperBridgeError::io("cannot launch embedded helper", error))?;

    let deadline = Instant::now() + timeout;
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(20)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(HelperBridgeError::new(
                    RC_TIMEOUT,
                    format!(
                        "isolated Tectonic helper exceeded the {}-second timeout",
                        timeout.as_secs()
                    ),
                ));
            }
            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(HelperBridgeError::io(
                    "cannot query embedded helper status",
                    error,
                ));
            }
        }
    };
    if !status.success() {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            format!(
                "isolated Tectonic helper terminated without a valid result ({status})"
            ),
        ));
    }

    let parsed = read_result_file(result_path).map_err(|error| {
        HelperBridgeError::new(
            RC_INTERNAL,
            format!("isolated helper produced an invalid result record: {error}"),
        )
    })?;
    validate_result(&parsed, operation, digest)?;
    Ok(parsed)
}

fn validate_result(
    result: &ParsedResult,
    operation: &str,
    digest: &str,
) -> Result<(), HelperBridgeError> {
    let fields = &result.fields;
    if fields.get("operation").map(String::as_str) != Some(operation) {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "isolated helper result identifies the wrong operation",
        ));
    }
    if fields.get("execution_model").map(String::as_str) != Some("embedded_helper") {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "isolated helper result has the wrong execution model",
        ));
    }
    let protocol = RESULT_SCHEMA_VERSION.to_string();
    if fields.get("helper_protocol").map(String::as_str) != Some(protocol.as_str()) {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "isolated helper result has the wrong protocol version",
        ));
    }
    if fields.get("helper_sha256").map(String::as_str) != Some(digest) {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "isolated helper result does not match the embedded helper digest",
        ));
    }
    if result.status == ResultStatus::Success && result.rc != 0 {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "isolated helper success record has a nonzero return code",
        ));
    }
    Ok(())
}

fn helper_timeout() -> Result<Duration, HelperBridgeError> {
    let seconds = match env::var("TEXPDF_HELPER_TIMEOUT_SECONDS") {
        Ok(value) => value.parse::<u64>().map_err(|_| {
            HelperBridgeError::new(
                RC_SYNTAX,
                "TEXPDF_HELPER_TIMEOUT_SECONDS must be an integer",
            )
        })?,
        Err(env::VarError::NotPresent) => DEFAULT_TIMEOUT_SECONDS,
        Err(env::VarError::NotUnicode(_)) => {
            return Err(HelperBridgeError::new(
                RC_SYNTAX,
                "TEXPDF_HELPER_TIMEOUT_SECONDS is not valid Unicode",
            ));
        }
    };
    if !(1..=MAX_TIMEOUT_SECONDS).contains(&seconds) {
        return Err(HelperBridgeError::new(
            RC_SYNTAX,
            format!(
                "TEXPDF_HELPER_TIMEOUT_SECONDS must be between 1 and {MAX_TIMEOUT_SECONDS}"
            ),
        ));
    }
    Ok(Duration::from_secs(seconds))
}

fn helper_digest() -> &'static str {
    HELPER_DIGEST.get_or_init(|| sha256_bytes(HELPER_BYTES))
}

fn ensure_embedded_helper() -> Result<PathBuf, HelperBridgeError> {
    let root = helper_cache_root()?;
    ensure_helper_from_bytes(HELPER_BYTES, helper_digest(), &root)
}

fn ensure_helper_from_bytes(
    bytes: &[u8],
    digest: &str,
    root: &Path,
) -> Result<PathBuf, HelperBridgeError> {
    let lock = EXTRACTION_LOCK.get_or_init(|| Mutex::new(()));
    let _guard = lock.lock().map_err(|_| {
        HelperBridgeError::new(RC_INTERNAL, "embedded helper extraction lock was poisoned")
    })?;

    let directory = root.join(digest);
    create_private_directory(&directory)?;
    let target = directory.join(helper_filename());
    if helper_file_is_valid(&target, digest)? {
        make_executable(&target)?;
        return Ok(target);
    }
    if target.exists() {
        fs::remove_file(&target)
            .map_err(|error| HelperBridgeError::io("cannot replace invalid helper cache", error))?;
    }

    let temporary = directory.join(format!(
        ".{}-{}.tmp",
        helper_filename(),
        std::process::id()
    ));
    if temporary.exists() {
        fs::remove_file(&temporary).map_err(|error| {
            HelperBridgeError::io("cannot remove stale helper extraction", error)
        })?;
    }
    let mut stream = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temporary)
        .map_err(|error| HelperBridgeError::io("cannot create helper extraction", error))?;
    stream
        .write_all(bytes)
        .map_err(|error| HelperBridgeError::io("cannot write helper extraction", error))?;
    stream
        .sync_all()
        .map_err(|error| HelperBridgeError::io("cannot sync helper extraction", error))?;
    drop(stream);
    make_executable(&temporary)?;
    fs::rename(&temporary, &target)
        .map_err(|error| HelperBridgeError::io("cannot install helper extraction", error))?;
    if !helper_file_is_valid(&target, digest)? {
        let _ = fs::remove_file(&target);
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "extracted helper failed its SHA-256 verification",
        ));
    }
    make_executable(&target)?;
    Ok(target)
}

fn helper_file_is_valid(path: &Path, digest: &str) -> Result<bool, HelperBridgeError> {
    let metadata = match fs::symlink_metadata(path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(false),
        Err(error) => {
            return Err(HelperBridgeError::io(
                "cannot inspect helper cache entry",
                error,
            ));
        }
    };
    if !metadata.file_type().is_file() {
        return Ok(false);
    }
    sha256_file(path)
        .map(|actual| actual == digest)
        .map_err(|error| HelperBridgeError::io("cannot hash helper cache entry", error))
}

fn create_private_directory(path: &Path) -> Result<(), HelperBridgeError> {
    fs::create_dir_all(path)
        .map_err(|error| HelperBridgeError::io("cannot create helper cache", error))?;
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| HelperBridgeError::io("cannot inspect helper cache", error))?;
    if !metadata.file_type().is_dir() {
        return Err(HelperBridgeError::new(
            RC_INTERNAL,
            "helper cache path is not a directory",
        ));
    }
    set_private_directory_permissions(path)
}

fn helper_cache_root() -> Result<PathBuf, HelperBridgeError> {
    if let Some(path) = env::var_os("TEXPDF_HELPER_CACHE_DIR") {
        return Ok(PathBuf::from(path));
    }

    #[cfg(target_os = "macos")]
    if let Some(home) = env::var_os("HOME") {
        return Ok(PathBuf::from(home)
            .join("Library")
            .join("Caches")
            .join("texpdf")
            .join("helpers"));
    }

    #[cfg(target_os = "windows")]
    if let Some(local) = env::var_os("LOCALAPPDATA") {
        return Ok(PathBuf::from(local)
            .join("texpdf")
            .join("Cache")
            .join("helpers"));
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        if let Some(cache) = env::var_os("XDG_CACHE_HOME") {
            return Ok(PathBuf::from(cache).join("texpdf").join("helpers"));
        }
        if let Some(home) = env::var_os("HOME") {
            return Ok(PathBuf::from(home)
                .join(".cache")
                .join("texpdf")
                .join("helpers"));
        }
    }

    Ok(env::temp_dir().join("texpdf-helper-cache"))
}

#[cfg(windows)]
fn helper_filename() -> &'static str {
    "texpdf-helper.exe"
}

#[cfg(not(windows))]
fn helper_filename() -> &'static str {
    "texpdf-helper"
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn sha256_file(path: &Path) -> io::Result<String> {
    let mut stream = File::open(path)?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 1024 * 1024];
    loop {
        let count = stream.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(format!("{digest:x}"))
}

#[cfg(unix)]
fn make_executable(path: &Path) -> Result<(), HelperBridgeError> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
        .map_err(|error| HelperBridgeError::io("cannot secure helper executable", error))
}

#[cfg(not(unix))]
fn make_executable(_path: &Path) -> Result<(), HelperBridgeError> {
    Ok(())
}

#[cfg(unix)]
fn set_private_directory_permissions(path: &Path) -> Result<(), HelperBridgeError> {
    use std::os::unix::fs::PermissionsExt;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
        .map_err(|error| HelperBridgeError::io("cannot secure helper cache", error))
}

#[cfg(not(unix))]
fn set_private_directory_permissions(_path: &Path) -> Result<(), HelperBridgeError> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extraction_repairs_a_corrupt_cached_helper() {
        let directory = tempfile::tempdir().expect("tempdir");
        let bytes = b"embedded helper fixture";
        let digest = sha256_bytes(bytes);
        let path = ensure_helper_from_bytes(bytes, &digest, directory.path())
            .expect("extract helper");
        fs::write(&path, b"corrupt").expect("corrupt helper");
        let repaired = ensure_helper_from_bytes(bytes, &digest, directory.path())
            .expect("repair helper");
        assert_eq!(fs::read(repaired).expect("read helper"), bytes);
    }

    #[test]
    fn result_validation_requires_the_embedded_digest() {
        let directory = tempfile::tempdir().expect("tempdir");
        let path = directory.path().join("result.txt");
        let record = texpdf_protocol::ResultRecord::success(
            "version",
            vec![
                ("execution_model".to_owned(), "embedded_helper".to_owned()),
                (
                    "helper_protocol".to_owned(),
                    RESULT_SCHEMA_VERSION.to_string(),
                ),
                ("helper_sha256".to_owned(), "wrong".to_owned()),
            ],
            &[],
        );
        texpdf_protocol::write_result_file(&path, &record).expect("write result");
        let parsed = read_result_file(&path).expect("read result");
        assert_eq!(
            validate_result(&parsed, "version", "expected")
                .expect_err("must reject")
                .rc,
            RC_INTERNAL
        );
    }

    #[cfg(unix)]
    #[test]
    fn extracted_helper_is_owner_only_executable() {
        use std::os::unix::fs::PermissionsExt;
        let directory = tempfile::tempdir().expect("tempdir");
        let bytes = b"helper permissions fixture";
        let digest = sha256_bytes(bytes);
        let path = ensure_helper_from_bytes(bytes, &digest, directory.path())
            .expect("extract helper");
        assert_eq!(
            fs::metadata(path).expect("metadata").permissions().mode() & 0o777,
            0o700
        );
    }
}
