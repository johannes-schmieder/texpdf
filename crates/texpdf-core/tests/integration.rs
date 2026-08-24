use std::fs;

use texpdf_core::{compile, CompileRequest, TexPdfError};

const ARTICLE: &str = r#"\documentclass{article}
\begin{document}
Hello from texpdf. $\widehat\beta=(X'X)^{-1}X'y$.
\end{document}
"#;

#[test]
fn relative_include_spaces_and_unicode_paths_compile() {
    let workspace = tempfile::tempdir().expect("temporary workspace");
    let root = workspace.path().join("project space é");
    let sections = root.join("sections");
    fs::create_dir_all(&sections).expect("create source tree");

    let input = root.join("main file é.tex");
    let output = root.join("compiled result é.pdf");
    fs::write(
        &input,
        r#"\documentclass{article}
\begin{document}
\input{sections/content.tex}
\end{document}
"#,
    )
    .expect("write main source");
    fs::write(
        sections.join("content.tex"),
        "Relative input from a Unicode path.",
    )
    .expect("write included source");

    let result = compile(&CompileRequest::new(&input, &output))
        .expect("compile source with relative include");
    assert!(fs::read(result.output).expect("read PDF").starts_with(b"%PDF-"));
}

#[test]
fn failed_replacement_preserves_existing_pdf() {
    let workspace = tempfile::tempdir().expect("temporary workspace");
    let input = workspace.path().join("document.tex");
    let output = workspace.path().join("document.pdf");
    fs::write(&input, ARTICLE).expect("write valid source");

    compile(&CompileRequest::new(&input, &output)).expect("initial compile");
    let original = fs::read(&output).expect("read original PDF");

    fs::write(
        &input,
        "\\documentclass{article}\\begin{document}\\undefinedcommand\\end{document}",
    )
    .expect("write invalid replacement source");
    let mut replacement = CompileRequest::new(&input, &output);
    replacement.replace = true;
    let error = compile(&replacement).expect_err("replacement compile must fail");
    assert!(matches!(error, TexPdfError::Engine { .. }));
    assert_eq!(fs::read(&output).expect("read preserved PDF"), original);
}

#[test]
fn repeated_compiles_in_one_process_succeed() {
    let workspace = tempfile::tempdir().expect("temporary workspace");
    let input = workspace.path().join("repeat.tex");
    let output = workspace.path().join("repeat.pdf");
    fs::write(&input, ARTICLE).expect("write source");

    for iteration in 0..10 {
        let mut request = CompileRequest::new(&input, &output);
        request.replace = iteration > 0;
        let result = compile(&request).expect("repeated compile");
        assert!(fs::read(result.output).expect("read PDF").starts_with(b"%PDF-"));
    }
}
