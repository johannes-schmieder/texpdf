{smcl}
{* *! version 0.1.0 24aug2026}{...}
{title:Title}

{phang}
{bf:texpdf} {hline 2} compile a LaTeX document to PDF with a standalone embedded Tectonic engine

{title:Syntax}

{p 8 16 2}
{cmd:texpdf using} {it:filename.tex}
[{cmd:,} {opt saving(filename.pdf)} {opt replace}]

{p 8 16 2}
{cmd:texpdf, version}

{title:Description}

{pstd}
{cmd:texpdf} compiles one complete LaTeX document. The released package contains
Tectonic and its supported TeX resources inside one native Stata plugin. No
system TeX installation or network connection is used at runtime.

{pstd}
Relative inputs, figures, and bibliography files are resolved from the primary
source directory. If {opt saving()} is omitted, a final {cmd:.tex} suffix is
replaced by {cmd:.pdf}; otherwise {cmd:.pdf} is appended.

{title:Options}

{phang}{opt saving(filename.pdf)} specifies the output PDF.

{phang}{opt replace} permits replacement of an existing output PDF.

{phang}{opt version} reports embedded engine and bundle metadata.

{title:Stored results}

{synoptset 24 tabbed}{...}
{synopt:{cmd:r(pdf)}}absolute output PDF path after compilation{p_end}
{synopt:{cmd:r(engine)}}{cmd:tectonic}{p_end}
{synopt:{cmd:r(engine_version)}}embedded Tectonic version{p_end}
{synopt:{cmd:r(bundle_version)}}embedded resource-bundle version{p_end}
{synopt:{cmd:r(bundle_digest)}}Tectonic bundle content digest{p_end}
{synopt:{cmd:r(bundle_zip_sha256)}}SHA-256 of the embedded ZIP{p_end}
{synopt:{cmd:r(warnings)}}number of warning diagnostics{p_end}

{title:Remarks}

{pstd}
Version 1 is a compiler only. Shell escape and arbitrary external helper
programs are disabled. BibTeX with {cmd:natbib} is supported by the intended v1
bundle; Biber/{cmd:biblatex}, Beamer, TikZ/PGF, and PSTricks are outside the
initial compatibility tier. The private RC provides English-language
hyphenation only; broad language and hyphenation collections are unsupported.

{title:Author}

{pstd}Johannes Schmieder
