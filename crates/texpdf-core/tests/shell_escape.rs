use std::fs;

use texpdf_core::{compile, CompileRequest, TexPdfError};

#[test]
fn shell_escape_cannot_create_a_sentinel_file() {
    let workspace = tempfile::tempdir().expect("temporary workspace");
    let input = workspace.path().join("shell-escape.tex");
    let output = workspace.path().join("shell-escape.pdf");
    let sentinel = workspace.path().join("texpdf-shell-escape-sentinel");
    fs::write(
        &input,
        format!(
            r#"\documentclass{{article}}
\begin{{document}}
\immediate\write18{{printf compromised > '{}'}}
Shell escape must not execute.
\end{{document}}
"#,
            sentinel.display()
        ),
    )
    .expect("write shell-escape fixture");

    match compile(&CompileRequest::new(&input, &output)) {
        Ok(_) => {}
        Err(TexPdfError::Engine { .. }) => {}
        Err(error) => panic!("unexpected shell-escape result: {error:#}"),
    }
    assert!(
        !sentinel.exists(),
        "shell escape executed despite the restrictive engine configuration"
    );
}
