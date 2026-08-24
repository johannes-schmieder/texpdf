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
assert _rc == 198

tempfile missing
capture noisily texpdf using `"`missing'"'
assert _rc == 601

tempfile source output
tempname handle
file open `handle' using `"`source'"', write text replace
file write `handle' "not compiled in the quick stub-bundle profile" _n
file close `handle'
file open `handle' using `"`output'"', write text replace
file write `handle' "existing output" _n
file close `handle'
capture noisily texpdf using `"`source'"', saving(`"`output'"')
assert _rc == 602

display as result "TEXPDF STATA COMMAND SMOKE PASS"
display as result "TEXPDF STATA MATA SMOKE PASS"
