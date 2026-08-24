version 18.0
clear all
set more off
set varabbrev off

display as result "TEXPDF_STATA_SMOKE_BEGIN"
display as text "stata_version=" c(stata_version)
display as text "stata_edition=" c(edition_real)
display as text "stata_os=" c(os)
display as text "stata_machine_type=" c(machine_type)
assert c(stata_version) >= 18

mata:
assert(sum((1, 2, 3)) == 6)
end

local repo `"`c(pwd)'"'
adopath ++ `"`repo'/stata"'
which texpdf

texpdf, version
assert `"`r(engine)'"' == "tectonic"
assert `"`r(engine_version)'"' == "0.17.0"
assert strlen(`"`r(bundle_digest)'"') == 64
assert strlen(`"`r(bundle_zip_sha256)'"') == 64
assert r(warnings) == 0

capture noisily texpdf
local syntax_rc = _rc
assert `syntax_rc' == 198

tempfile missing
capture noisily texpdf using `"`missing'"'
local missing_rc = _rc
assert `missing_rc' == 601

tempfile source output
tempname handle
file open `handle' using `"`source'"', write text replace
file write `handle' "not compiled in the quick stub-bundle profile" _n
file close `handle'
file open `handle' using `"`output'"', write text replace
file write `handle' "existing output" _n
file close `handle'
capture noisily texpdf using `"`source'"', saving(`"`output'"')
local overwrite_rc = _rc
assert `overwrite_rc' == 602

local command_marker = "TEXPDF STATA COMMAND SMOKE " + "PASS"
display as result `"`command_marker'"'

capture confirm file `"`repo'/ci/FULL_ENGINE"'
local full_engine = (_rc == 0)
if `full_engine' {
    tempfile compiled
    local compiled_pdf `"`compiled'.pdf"'
    texpdf using `"`repo'/tests/fixtures/academic.tex"', saving(`"`compiled_pdf'"') replace
    confirm file `"`compiled_pdf'"'
    assert `"`r(engine)'"' == "tectonic"
    assert `"`r(engine_version)'"' == "0.17.0"
    assert strlen(`"`r(bundle_digest)'"') == 64
    assert strlen(`"`r(bundle_zip_sha256)'"') == 64
    assert r(warnings) >= 0

    tempfile bad badpdf
    local bad_pdf `"`badpdf'.pdf"'
    file open `handle' using `"`bad'"', write text replace
    file write `handle' "\documentclass{article}\begin{document}\undefinedcontrolsequence\end{document}" _n
    file close `handle'
    capture noisily texpdf using `"`bad'"', saving(`"`bad_pdf'"') replace
    local bad_rc = _rc
    assert `bad_rc' == 459
    capture confirm file `"`bad_pdf'"'
    local bad_output_rc = _rc
    assert `bad_output_rc' != 0

    * A recoverable TeX error must not damage the in-process plugin.
    texpdf, version
    assert `"`r(engine)'"' == "tectonic"
    forvalues iteration = 1/3 {
        texpdf using `"`repo'/tests/fixtures/academic.tex"', saving(`"`compiled_pdf'"') replace
        confirm file `"`compiled_pdf'"'
    }

    local full_marker = "TEXPDF FULL ENGINE STATA " + "PASS"
    display as result `"`full_marker'"'
}

local suite_marker = "TEXPDF STATA MATA SMOKE " + "PASS"
display as result `"`suite_marker'"'
