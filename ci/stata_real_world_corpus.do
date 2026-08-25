version 18.0
set more off
set varabbrev off

local repo `"`c(pwd)'"'
local output_dir : environment TEXPDF_CORPUS_OUTPUT
if `"`output_dir'"' == "" {
    local output_dir `"`c(tmpdir)'/texpdf-real-world-corpus"'
}
capture mkdir `"`output_dir'"'

* CORPUS_FIXTURE latexlog-current latexlog-current/report.tex
* CORPUS_FIXTURE latexlog-legacy latexlog-legacy/report.tex
* CORPUS_FIXTURE economics-manuscript manuscript/main.tex

local fixture_ids "latexlog-current latexlog-legacy economics-manuscript"
local fixture_paths "latexlog-current/report.tex latexlog-legacy/report.tex manuscript/main.tex"
local fixture_warnings "0 0 0"
local fixture_count : word count `fixture_ids'

forvalues index = 1/`fixture_count' {
    local fixture_id : word `index' of `fixture_ids'
    local fixture_path : word `index' of `fixture_paths'
    local expected_warnings : word `index' of `fixture_warnings'
    local source `"`repo'/tests/fixtures/real-world/`fixture_path'"'
    local output `"`output_dir'/`fixture_id'.pdf"'
    capture erase `"`output'"'
    texpdf using `"`source'"', saving(`"`output'"') replace
    confirm file `"`output'"'
    assert r(warnings) == `expected_warnings'
    assert strlen(`"`r(bundle_version)'"') > 0
    assert strlen(`"`r(bundle_digest)'"') == 64
    assert strlen(`"`r(bundle_zip_sha256)'"') == 64
}

display as result "TEXPDF REALISTIC CORPUS PASS"
