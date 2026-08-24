version 18.0
clear all
set more off
set varabbrev off

* This profile is the release-gate probe for post-compile allocator pressure
* relief and long-lived in-process stability.
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

tempfile source output bad badoutput
tempname handle
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

forvalues iteration = 1/`repetitions' {
    texpdf using `"`source'"', saving(`"`output'"') replace
    confirm file `"`output'"'
    assert `"`r(engine)'"' == "tectonic"

    if mod(`iteration', 25) == 0 {
        capture noisily texpdf using `"`bad'"', saving(`"`badoutput'"') replace
        assert _rc == 459
        capture confirm file `"`badoutput'"'
        assert _rc != 0
        texpdf, version
        assert `"`r(engine)'"' == "tectonic"
    }

    if `"`progress'"' != "" & mod(`iteration', 5) == 0 {
        tempname progress_handle
        file open `progress_handle' using `"`progress'"', write text replace
        file write `progress_handle' "`iteration'" _n
        file close `progress_handle'
    }

    if mod(`iteration', 100) == 0 {
        display as text "TEXPDF_STRESS_PROGRESS iteration=`iteration'"
    }
}

if `"`progress'"' != "" {
    tempname progress_handle
    file open `progress_handle' using `"`progress'"', write text replace
    file write `progress_handle' "`repetitions'" _n
    file close `progress_handle'
}

display as result "TEXPDF STRESS 1000 PASS"
