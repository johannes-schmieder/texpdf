//! Panic-safe SPI 3.0 bridge for `texpdf`.
//!
//! The bridge never links Tectonic. It validates Stata's argument vector,
//! materializes the exact helper embedded at build time, launches that helper
//! without a shell, and leaves the helper's bounded result record for the ado
//! layer to consume.

mod embedded_helper;

use std::{
    ffi::{c_char, c_int, c_void, CStr},
    panic::{catch_unwind, AssertUnwindSafe},
    path::Path,
    slice,
};

use embedded_helper::HelperBridgeError;
use texpdf_protocol::{write_result_file, ResultRecord, RC_INTERNAL, RC_SYNTAX};

const SPI_VERSION_3_0: c_int = 3;

/// Initialize the plugin under Stata's SPI 3.0 protocol.
#[unsafe(no_mangle)]
pub extern "C" fn pginit(_stata: *mut c_void) -> c_int {
    SPI_VERSION_3_0
}

/// Execute one bridge request from Stata.
///
/// # Safety
///
/// Stata must provide `argc` valid, NUL-terminated C strings through `argv`
/// for the duration of this call, as required by the SPI 3.0 plugin ABI.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn stata_call(argc: c_int, argv: *mut *mut c_char) -> c_int {
    let args = match unsafe { collect_arguments(argc, argv) } {
        Ok(values) => values,
        Err(error) => return error.rc,
    };
    let Some(result_path) = expected_result_path(&args).map(Path::to_owned) else {
        return RC_SYNTAX;
    };

    let outcome = catch_unwind(AssertUnwindSafe(|| dispatch(&args, &result_path)));
    let failure = match outcome {
        Ok(Ok(())) => return 0,
        Ok(Err(error)) => error,
        Err(_) => HelperBridgeError::new(
            RC_INTERNAL,
            "the texpdf bridge panicked; the unwind was contained at the ABI boundary",
        ),
    };
    let record = ResultRecord::failure(failure.rc, failure.message, &[]);
    if write_result_file(&result_path, &record).is_err() {
        return RC_INTERNAL;
    }

    // Ordinary helper failures are transported through the result file so the
    // ado layer can print the specific diagnostic before exiting with its rc.
    0
}

unsafe fn collect_arguments(
    argc: c_int,
    argv: *mut *mut c_char,
) -> Result<Vec<String>, HelperBridgeError> {
    if argc < 0 || (argc > 0 && argv.is_null()) {
        return Err(HelperBridgeError::new(
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
        if pointer.is_null() {
            return Err(HelperBridgeError::new(
                RC_SYNTAX,
                format!("plugin argument {} is null", index + 1),
            ));
        }
        let value = unsafe { CStr::from_ptr(*pointer) }
            .to_str()
            .map_err(|_| {
                HelperBridgeError::new(
                    RC_SYNTAX,
                    format!("plugin argument {} is not valid UTF-8", index + 1),
                )
            })?
            .to_owned();
        values.push(value);
    }
    Ok(values)
}

fn expected_result_path(args: &[String]) -> Option<&Path> {
    match args.first().map(String::as_str) {
        Some("version") if args.len() == 2 => Some(Path::new(&args[1])),
        Some("compile") if args.len() == 6 => Some(Path::new(&args[3])),
        _ => None,
    }
}

fn dispatch(args: &[String], result_path: &Path) -> Result<(), HelperBridgeError> {
    match args.first().map(String::as_str) {
        Some("version") if args.len() == 2 => {}
        Some("compile") if args.len() == 6 => {
            parse_flag(&args[4], "replace")?;
            parse_flag(&args[5], "keep-log")?;
        }
        Some(other) => {
            return Err(HelperBridgeError::new(
                RC_SYNTAX,
                format!("invalid texpdf plugin operation or argument count: {other}"),
            ));
        }
        None => {
            return Err(HelperBridgeError::new(
                RC_SYNTAX,
                "missing texpdf plugin operation",
            ));
        }
    }
    embedded_helper::run(args, result_path).map(|_| ())
}

fn parse_flag(value: &str, name: &str) -> Result<bool, HelperBridgeError> {
    match value {
        "0" => Ok(false),
        "1" => Ok(true),
        _ => Err(HelperBridgeError::new(
            RC_SYNTAX,
            format!("{name} flag must be 0 or 1"),
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn selects_only_well_formed_result_paths() {
        let version = vec!["version".to_owned(), "result.txt".to_owned()];
        assert_eq!(
            expected_result_path(&version),
            Some(Path::new("result.txt"))
        );
        let short_compile = vec!["compile".to_owned(), "input.tex".to_owned()];
        assert_eq!(expected_result_path(&short_compile), None);
    }

    #[test]
    fn rejects_bad_flags_before_launch() {
        assert_eq!(
            parse_flag("yes", "replace").expect_err("bad flag").rc,
            RC_SYNTAX
        );
    }

    #[test]
    fn embedded_metadata_is_available_at_compile_time() {
        assert!(!env!("TEXPDF_EMBEDDED_HELPER_SHA256").is_empty());
        assert_ne!(env!("TEXPDF_EMBEDDED_HELPER_SIZE"), "0");
    }

    #[test]
    fn pathbuf_import_remains_platform_neutral() {
        let path = PathBuf::from("result.txt");
        assert_eq!(path, Path::new("result.txt"));
    }
}
