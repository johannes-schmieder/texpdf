use std::{
    collections::BTreeSet,
    env,
    error::Error,
    fmt::Arguments,
    fs,
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
};

use tectonic::driver::{OutputFormat, ProcessingSessionBuilder};
use tectonic_bundles::{itar::ItarBundle, Bundle};
use tectonic_errors::{Error as TectonicError, Result as TectonicResult};
use tectonic_io_base::{digest::DigestData, InputHandle, IoProvider, OpenResult};
use tectonic_status_base::{MessageKind, StatusBackend};

const MAX_TEX_LOG_BYTES: usize = 256 * 1024;

#[derive(Default)]
struct ResolverStatus;

impl StatusBackend for ResolverStatus {
    fn report(&mut self, kind: MessageKind, args: Arguments<'_>, err: Option<&TectonicError>) {
        let label = match kind {
            MessageKind::Note => "NOTE",
            MessageKind::Warning => "WARNING",
            MessageKind::Error => "ERROR",
            _ => "MESSAGE",
        };
        eprintln!("TEXPDF_RESOLVER_{label} {args}");
        if let Some(error) = err {
            eprintln!("TEXPDF_RESOLVER_CAUSE {error:#}");
        }
    }

    fn dump_error_logs(&mut self, output: &[u8]) {
        let retained = if output.len() > MAX_TEX_LOG_BYTES {
            &output[output.len() - MAX_TEX_LOG_BYTES..]
        } else {
            output
        };
        eprintln!(
            "TEXPDF_RESOLVER_TEX_LOG_BEGIN bytes={} retained={}",
            output.len(),
            retained.len()
        );
        eprintln!("{}", String::from_utf8_lossy(retained));
        eprintln!("TEXPDF_RESOLVER_TEX_LOG_END");
    }
}

struct RecordingBundle {
    inner: Box<dyn Bundle>,
    requested: Arc<Mutex<BTreeSet<String>>>,
}

impl IoProvider for RecordingBundle {
    fn input_open_name(
        &mut self,
        name: &str,
        status: &mut dyn StatusBackend,
    ) -> OpenResult<InputHandle> {
        if let Ok(mut requested) = self.requested.lock() {
            requested.insert(name.to_owned());
        }
        self.inner.input_open_name(name, status)
    }
}

impl Bundle for RecordingBundle {
    fn get_digest(&mut self) -> TectonicResult<DigestData> {
        if let Ok(mut requested) = self.requested.lock() {
            requested.insert("SHA256SUM".to_owned());
        }
        self.inner.get_digest()
    }

    fn all_files(&self) -> Vec<String> {
        self.inner.all_files()
    }
}

fn compile_source(
    bundle_url: &str,
    source: &Path,
    requested: Arc<Mutex<BTreeSet<String>>>,
) -> Result<(), Box<dyn Error>> {
    let input = fs::canonicalize(source)?;
    let input_dir = input.parent().ok_or("source has no parent directory")?;
    let input_name = input
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or("source path is not valid UTF-8")?;
    let output = tempfile::tempdir()?;
    let format_cache = tempfile::tempdir()?;

    let network_bundle = ItarBundle::new(bundle_url.to_owned())?;
    let recording = RecordingBundle {
        inner: Box::new(network_bundle),
        requested,
    };
    let mut status = ResolverStatus;
    let mut builder = ProcessingSessionBuilder::default();
    builder
        .primary_input_path(&input)
        .tex_input_name(input_name)
        .filesystem_root(input_dir)
        .output_dir(output.path())
        .format_name("latex")
        .format_cache_path(format_cache.path())
        .output_format(OutputFormat::Pdf)
        .keep_intermediates(false)
        .keep_logs(false)
        .print_stdout(false)
        .shell_escape_disabled()
        .build_date_from_env(true)
        .bundle(Box::new(recording));

    eprintln!("TEXPDF_RESOLVER_COMPILE_BEGIN source={}", input.display());
    let mut session = builder.create(&mut status)?;
    session.run(&mut status)?;
    let pdf = output.path().join(Path::new(input_name).with_extension("pdf"));
    if !pdf.is_file() {
        return Err("Tectonic resolver produced no PDF".into());
    }
    eprintln!(
        "TEXPDF_RESOLVER_COMPILE_SUCCESS source={} pdf_bytes={}",
        input.display(),
        pdf.metadata()?.len()
    );
    Ok(())
}

fn write_trace(path: &Path, requested: &Arc<Mutex<BTreeSet<String>>>) -> Result<(), Box<dyn Error>> {
    let values = requested.lock().map_err(|_| "resource trace lock was poisoned")?;
    let mut text = String::new();
    for value in values.iter() {
        text.push_str(value);
        text.push('\n');
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let temporary = path.with_extension("tmp");
    fs::write(&temporary, text)?;
    fs::rename(temporary, path)?;
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut arguments = env::args_os().skip(1);
    let bundle_url = arguments
        .next()
        .ok_or("usage: texpdf-bundle-resolver BUNDLE_URL TRACE SOURCE [SOURCE ...]")?
        .into_string()
        .map_err(|_| "bundle URL is not valid UTF-8")?;
    let trace = PathBuf::from(
        arguments
            .next()
            .ok_or("usage: texpdf-bundle-resolver BUNDLE_URL TRACE SOURCE [SOURCE ...]")?,
    );
    let sources: Vec<PathBuf> = arguments.map(PathBuf::from).collect();
    if sources.is_empty() {
        return Err("at least one source fixture is required".into());
    }

    let requested = Arc::new(Mutex::new(BTreeSet::new()));
    let mut first_error: Option<Box<dyn Error>> = None;
    for source in &sources {
        if let Err(error) = compile_source(&bundle_url, source, Arc::clone(&requested)) {
            eprintln!(
                "TEXPDF_RESOLVER_COMPILE_FAILURE source={} error={error:#}",
                source.display()
            );
            first_error = Some(error);
            break;
        }
    }
    write_trace(&trace, &requested)?;
    let count = requested
        .lock()
        .map_err(|_| "resource trace lock was poisoned")?
        .len();
    println!("TEXPDF_BUNDLE_TRACE_READY path={} files={count}", trace.display());
    if let Some(error) = first_error {
        return Err(error);
    }
    Ok(())
}
