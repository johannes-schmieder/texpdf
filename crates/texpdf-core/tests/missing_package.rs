use std::fs;

use texpdf_core::{compile, CompileRequest, TexPdfError};

#[test]
fn unsupported_package_fails_without_creating_output() {
    let workspace = tempfile::tempdir().expect("temporary workspace");
    let input = workspace.path().join("missing-package.tex");
    let output = workspace.path().join("missing-package.pdf");
    fs::write(
        &input,
        r#"\documentclass{article}
\usepackage{texpdf-package-that-does-not-exist}
\begin{document}
This document must not compile.
\end{document}
"#,
    )
    .expect("write source");

    let error = compile(&CompileRequest::new(&input, &output))
        .expect_err("an unsupported package must fail explicitly");
    assert!(matches!(error, TexPdfError::Engine { .. }));
    assert!(!output.exists());
    assert!(
        error.diagnostics().iter().any(|diagnostic| diagnostic
            .message
            .contains("texpdf-package-that-does-not-exist")),
        "the missing package name should appear in bounded diagnostics"
    );
}
