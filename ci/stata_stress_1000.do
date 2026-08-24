version 18.0
clear all
set more off
set varabbrev off

* Release gate for long-lived Stata-parent stability with one isolated helper
* process per compile request.
local iterations : environment TEXPDF_STRESS_ITERATIONS
if `"`iterations'"' == "" local iterations "1000"
local repetitions = real(`"`iterations'"')
assert `repetitions' >= 1
assert `repetitions' <= 10000

local progress : environment TEXPDF_STRESS_PROGRESS
local repo `"`c(pwd)'"'
adopath ++ `"`repo'/stata"'
which texpdf
texpdf, version
assert `"`r(engine)'"' == "tectonic"

tempfile source output bad badoutput corrupt corruptsource missing missingoutput
tempname handle
local protected `"`badoutput'.pdf"'
local corruptpng `"`corrupt'.png"'
file open `handle' using `"`source'"', write text replace
file write `handle' "\documentclass{article}" _n
file write `handle' "\usepackage{amsmath}" _n
file write `handle' "\begin{document}" _n
file write `handle' "Repeated compile $\widehat\beta=(X'X)^{-1}X'y$." _n
file write `handle' "\end{document}" _n
file close `handle'

file open `handle' using `"`bad'"', write text replace
file write `handle' "\documentclass{article}\begin{document}\undefinedcontrolsequence\end{document}" _n
file close `handle'

file open `handle' using `"`protected'"', write text replace
file write `handle' "preserve-existing-output" _n
file close `handle'

file open `handle' using `"`corruptpng'"', write text replace
file write `handle' "not-a-valid-png" _n
file close `handle'
file open `handle' using `"`corruptsource'"', write text replace
file write `handle' "\documentclass{article}\usepackage{graphicx}\begin{document}" _n
file write `handle' "\includegraphics{`corruptpng'}\end{document}" _n
file close `handle'

file open `handle' using `"`missing'"', write text replace
file write `handle' "\documentclass{article}\usepackage{texpdf_missing_stress_package}\begin{document}x\end{document}" _n
file close `handle'

local failures = 0
capture noisily texpdf using `"`corruptsource'"', saving(`"`missingoutput'"') replace
assert _rc == 459
local failures = `failures' + 1
capture noisily texpdf using `"`missing'"', saving(`"`missingoutput'"') replace
assert _rc == 459
local failures = `failures' + 1

forvalues iteration = 1/`repetitions' {
    if mod(`iteration', 25) == 0 {
        capture noisily texpdf using `"`bad'"', saving(`"`protected'"') replace
        assert _rc == 459
        local failures = `failures' + 1
        confirm file `"`protected'"'
        tempname check_handle
        file open `check_handle' using `"`protected'"', read text
        file read `check_handle' preserved
        file close `check_handle'
        assert `"`preserved'"' == "preserve-existing-output"
        texpdf, version
        assert `"`r(engine)'"' == "tectonic"
    }

    * A successful compile immediately after each injected error proves recovery.
    texpdf using `"`source'"', saving(`"`output'"') replace
    confirm file `"`output'"'
    assert `"`r(engine)'"' == "tectonic"

    if `"`progress'"' != "" & mod(`iteration', 5) == 0 {
        tempname progress_handle
        file open `progress_handle' using `"`progress'"', write text replace
        file write `progress_handle' "`iteration' `failures'" _n
        file close `progress_handle'
    }

    if mod(`iteration', 100) == 0 {
        display as text "TEXPDF_STRESS_PROGRESS iteration=`iteration'"
    }
}

if `"`progress'"' != "" {
    tempname progress_handle
    file open `progress_handle' using `"`progress'"', write text replace
    file write `progress_handle' "`repetitions' `failures'" _n
    file close `progress_handle'
}

display as result "TEXPDF STRESS 1000 PASS"
display as result "TEXPDF_STRESS_SUCCESSFUL=`repetitions'"
display as result "TEXPDF_STRESS_FAILURES=`failures'"
