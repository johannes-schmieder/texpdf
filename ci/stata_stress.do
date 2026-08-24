version 18.0
clear all
set more off

local iterations : environment TEXPDF_STRESS_ITERATIONS
if `"`iterations'"' == "" local iterations "1000"
local repetitions = real(`"`iterations'"')
if missing(`repetitions') | `repetitions' < 1 | `repetitions' > 10000 {
    display as error "TEXPDF_STRESS_ITERATIONS must be between 1 and 10000"
    exit 198
}

local repo `"`c(pwd)'"'
adopath ++ `"`repo'/stata"'
which texpdf
texpdf, version
assert `"`r(engine)'"' == "tectonic"

local runid : environment GITHUB_RUN_ID
if `"`runid'"' == "" local runid "local"
local root = c(tmpdir) + "/texpdf-stress-" + `"`runid'"'
capture mkdir `"`root'"'
local source = `"`root'"' + "/stress.tex"
local output = `"`root'"' + "/stress.pdf"
local bad = `"`root'"' + "/bad.tex"
local badoutput = `"`root'"' + "/bad.pdf"

tempname handle
file open `handle' using `"`source'"', write text replace
file write `handle' "\documentclass{article}" _n
file write `handle' "\begin{document}" _n
file write `handle' "Standalone in-process stress test. $\alpha+\beta$." _n
file write `handle' "\end{document}" _n
file close `handle'

file open `handle' using `"`bad'"', write text replace
file write `handle' "\documentclass{article}\begin{document}\undefinedcontrolsequence\end{document}" _n
file close `handle'

forvalues iteration = 1/`repetitions' {
    texpdf using `"`source'"', saving(`"`output'"') replace
    confirm file `"`output'"'
    assert `"`r(engine)'"' == "tectonic"

    if mod(`iteration', 10) == 0 {
        capture noisily texpdf using `"`bad'"', saving(`"`badoutput'"') replace
        assert _rc == 459
        capture confirm file `"`badoutput'"'
        assert _rc != 0
        texpdf, version
        assert `"`r(engine)'"' == "tectonic"
    }
}

capture erase `"`source'"'
capture erase `"`output'"'
capture erase `"`bad'"'
capture erase `"`badoutput'"'
capture rmdir `"`root'"'

display as result "TEXPDF STRESS PASS"
