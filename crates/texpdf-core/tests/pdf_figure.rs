use std::fs;

use texpdf_core::{compile, CompileRequest};

#[test]
fn embedded_engine_includes_a_generated_pdf_figure() {
    let workspace = tempfile::tempdir().expect("temporary workspace");
    let asset_source = workspace.path().join("asset.tex");
    let asset_pdf = workspace.path().join("asset.pdf");
    fs::write(
        &asset_source,
        r#"\documentclass{article}
\pagestyle{empty}
\begin{document}
\rule{25mm}{15mm}
\end{document}
"#,
    )
    .expect("write PDF asset source");
    compile(&CompileRequest::new(&asset_source, &asset_pdf)).expect("compile PDF asset");

    let input = workspace.path().join("figure.tex");
    let output = workspace.path().join("figure.pdf");
    fs::write(
        &input,
        r#"\documentclass{article}
\usepackage{graphicx}
\begin{document}
\includegraphics[width=25mm]{asset.pdf}
\end{document}
"#,
    )
    .expect("write figure source");
    let result = compile(&CompileRequest::new(&input, &output)).expect("include PDF figure");
    assert!(fs::read(result.output)
        .expect("read generated PDF")
        .starts_with(b"%PDF-"));
}
