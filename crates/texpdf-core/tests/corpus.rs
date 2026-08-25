use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};

use serde::Deserialize;
use texpdf_core::{compile, CompileRequest, Diagnostic, DiagnosticKind};

#[derive(Debug, Deserialize)]
struct CorpusManifest {
    schema_version: u32,
    permitted_engine_diagnostics: Vec<PermittedDiagnostic>,
    fixtures: Vec<CorpusFixture>,
}

#[derive(Debug, Deserialize)]
struct CorpusFixture {
    id: String,
    entrypoint: String,
    assets: Vec<String>,
    permitted_diagnostics: Vec<PermittedDiagnostic>,
}

#[derive(Debug, Deserialize)]
struct PermittedDiagnostic {
    kind: String,
    contains: String,
}

fn kind_name(kind: DiagnosticKind) -> &'static str {
    match kind {
        DiagnosticKind::Note => "note",
        DiagnosticKind::Warning => "warning",
        DiagnosticKind::Error => "error",
        DiagnosticKind::Log => "log",
    }
}

fn is_permitted(diagnostic: &Diagnostic, permitted: &[PermittedDiagnostic]) -> bool {
    permitted.iter().any(|item| {
        item.kind == kind_name(diagnostic.kind) && diagnostic.message.contains(&item.contains)
    })
}

fn load_manifest() -> (PathBuf, CorpusManifest) {
    let repository = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let corpus_root = repository.join("tests/fixtures/real-world");
    let manifest_path = corpus_root.join("manifest.json");
    let manifest: CorpusManifest =
        serde_json::from_slice(&fs::read(&manifest_path).expect("read real-world corpus manifest"))
            .expect("parse real-world corpus manifest");
    assert_eq!(manifest.schema_version, 1, "unsupported corpus schema");
    assert!(!manifest.fixtures.is_empty(), "corpus is empty");
    (corpus_root, manifest)
}

fn compile_fixture(
    corpus_root: &Path,
    manifest: &CorpusManifest,
    fixture: &CorpusFixture,
    output_root: &Path,
) {
    let canonical_corpus = fs::canonicalize(corpus_root).expect("resolve corpus root");
    let input = corpus_root.join(&fixture.entrypoint);
    assert!(input.is_file(), "{} entrypoint is absent", fixture.id);
    let resolved_input = fs::canonicalize(&input).expect("resolve corpus entrypoint");
    assert!(
        resolved_input.starts_with(&canonical_corpus),
        "{} entrypoint escapes the corpus",
        fixture.id
    );

    for asset in &fixture.assets {
        let path = corpus_root.join(asset);
        assert!(path.is_file(), "{} asset is absent: {}", fixture.id, asset);
        let resolved = fs::canonicalize(&path).expect("resolve corpus asset");
        assert!(
            resolved.starts_with(&canonical_corpus),
            "{} asset escapes the corpus: {}",
            fixture.id,
            asset
        );
    }

    let output = output_root.join(format!("{}.pdf", fixture.id));
    let mut request = CompileRequest::new(&input, &output);
    request.replace = true;
    let result = compile(&request)
        .unwrap_or_else(|error| panic!("{} failed to compile: {error:#}", fixture.id));
    let bytes = fs::read(&result.output).expect("read corpus PDF");
    assert!(
        bytes.starts_with(b"%PDF-"),
        "{} output is not PDF",
        fixture.id
    );
    assert!(
        bytes.len() > 5_000,
        "{} output is unexpectedly small: {} bytes",
        fixture.id,
        bytes.len()
    );

    let unexpected: Vec<String> = result
        .diagnostics
        .iter()
        .filter(|diagnostic| {
            !is_permitted(diagnostic, &manifest.permitted_engine_diagnostics)
                && !is_permitted(diagnostic, &fixture.permitted_diagnostics)
        })
        .map(|diagnostic| format!("{}: {}", kind_name(diagnostic.kind), diagnostic.message))
        .collect();
    assert!(
        unexpected.is_empty(),
        "{} emitted unpermitted diagnostics:\n{}",
        fixture.id,
        unexpected.join("\n")
    );
}

#[test]
fn corpus_child() {
    let Some(identifier) = env::var_os("TEXPDF_CORPUS_CHILD_FIXTURE") else {
        return;
    };
    let output_root = PathBuf::from(
        env::var_os("TEXPDF_CORPUS_CHILD_OUTPUT_ROOT").expect("child output root is required"),
    );
    let (corpus_root, manifest) = load_manifest();
    let identifier = identifier.to_string_lossy();
    let fixture = manifest
        .fixtures
        .iter()
        .find(|fixture| fixture.id == identifier)
        .unwrap_or_else(|| panic!("unknown corpus fixture: {identifier}"));
    compile_fixture(&corpus_root, &manifest, fixture, &output_root);
}

#[test]
fn embedded_bundle_compiles_real_world_corpus() {
    let (_, manifest) = load_manifest();

    let retained_root = env::var_os("TEXPDF_CORPUS_OUTPUT").map(PathBuf::from);
    let temporary = retained_root
        .is_none()
        .then(|| tempfile::tempdir().expect("create corpus output directory"));
    let output_root = retained_root
        .as_deref()
        .unwrap_or_else(|| temporary.as_ref().expect("temporary output").path());
    fs::create_dir_all(output_root).expect("create retained corpus output directory");
    for fixture in &manifest.fixtures {
        let status = Command::new(env::current_exe().expect("resolve corpus test executable"))
            .args(["--exact", "corpus_child", "--nocapture"])
            .env("TEXPDF_CORPUS_CHILD_FIXTURE", &fixture.id)
            .env("TEXPDF_CORPUS_CHILD_OUTPUT_ROOT", output_root)
            .status()
            .unwrap_or_else(|error| panic!("cannot launch {} child: {error}", fixture.id));
        assert!(
            status.success(),
            "{} child compilation failed with {status}",
            fixture.id,
        );
    }
}
