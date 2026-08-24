//! Repeated in-process compiler probe used to isolate Tectonic memory growth.

use std::{
    env,
    fs::{self, File},
    io::Write,
    path::{Path, PathBuf},
    process,
};

use texpdf_core::{compile, CompileRequest};

const SOURCE: &str = r#"\documentclass{article}
\usepackage{amsmath}
\begin{document}
Repeated compile $\widehat\beta=(X'X)^{-1}X'y$.
\end{document}
"#;

fn parse_iterations() -> Result<usize, String> {
    let value = env::args().nth(1).unwrap_or_else(|| "1000".to_owned());
    let iterations = value
        .parse::<usize>()
        .map_err(|error| format!("invalid iteration count {value:?}: {error}"))?;
    if !(1..=10_000).contains(&iterations) {
        return Err("iteration count must be between 1 and 10000".to_owned());
    }
    Ok(iterations)
}

fn workspace() -> Result<PathBuf, String> {
    let root = env::var_os("TEXPDF_MEMORY_PROBE_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            env::temp_dir().join(format!("texpdf-rust-memory-probe-{}", process::id()))
        });
    if root.exists() {
        fs::remove_dir_all(&root)
            .map_err(|error| format!("cannot remove prior workspace {root:?}: {error}"))?;
    }
    fs::create_dir_all(&root)
        .map_err(|error| format!("cannot create workspace {root:?}: {error}"))?;
    Ok(root)
}

fn write_progress(path: &Path, iteration: usize) -> Result<(), String> {
    let temporary = path.with_extension("tmp");
    let mut stream = File::create(&temporary)
        .map_err(|error| format!("cannot create progress file {temporary:?}: {error}"))?;
    writeln!(stream, "{iteration}")
        .map_err(|error| format!("cannot write progress file {temporary:?}: {error}"))?;
    stream
        .sync_all()
        .map_err(|error| format!("cannot sync progress file {temporary:?}: {error}"))?;
    fs::rename(&temporary, path)
        .map_err(|error| format!("cannot install progress file {path:?}: {error}"))?;
    Ok(())
}

fn run() -> Result<(), String> {
    let iterations = parse_iterations()?;
    let root = workspace()?;
    let input = root.join("probe.tex");
    let output = root.join("probe.pdf");
    fs::write(&input, SOURCE)
        .map_err(|error| format!("cannot write probe source {input:?}: {error}"))?;
    let progress = env::var_os("TEXPDF_MEMORY_PROBE_PROGRESS").map(PathBuf::from);

    for iteration in 1..=iterations {
        let mut request = CompileRequest::new(&input, &output);
        request.replace = iteration > 1;
        let result = compile(&request)
            .map_err(|error| format!("compile {iteration}/{iterations} failed: {error}"))?;
        let metadata = fs::metadata(&result.output)
            .map_err(|error| format!("cannot inspect output {:?}: {error}", result.output))?;
        if metadata.len() < 5 {
            return Err(format!(
                "compile {iteration} produced an implausibly small PDF"
            ));
        }
        if iteration % 5 == 0 || iteration == iterations {
            if let Some(path) = &progress {
                write_progress(path, iteration)?;
            }
        }
        if iteration % 100 == 0 || iteration == iterations {
            println!("TEXPDF_RUST_MEMORY_PROGRESS iteration={iteration}");
        }
    }

    println!(
        "TEXPDF_RUST_MEMORY_PASS iterations={iterations} workspace={}",
        root.display()
    );
    fs::remove_dir_all(&root)
        .map_err(|error| format!("cannot clean workspace {root:?}: {error}"))?;
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("TEXPDF_RUST_MEMORY_ERROR {error}");
        process::exit(2);
    }
}
