version 18.0
set more off
set varabbrev off

args output_dir
if `"`output_dir'"' == "" {
    display as error "help-example output directory is required"
    exit 198
}

capture mkdir `"`output_dir'"'
local original_pwd `"`c(pwd)'"'
cd `"`output_dir'"'

sysuse auto, clear
local original_observations = _N
texpdf_run manual using texpdf.sthlp, preserve
assert _N == `original_observations'
confirm file "./texpdf_examples/manual/table.tex"
confirm file "./texpdf_examples/manual/price-mpg.pdf"
confirm file "./texpdf_examples/manual/report.tex"
confirm file "./texpdf_examples/manual/report.pdf"

* A second click must replace the same inspectable outputs cleanly.
texpdf_run manual using texpdf.sthlp, preserve
assert _N == `original_observations'
confirm file "./texpdf_examples/manual/report.pdf"

capture noisily texpdf_run not-an-example using texpdf.sthlp, preserve
assert _rc == 111
assert _N == `original_observations'

local latexlog_dir : environment LATEXLOG_DIR
if `"`latexlog_dir'"' == "" {
    capture noisily texpdf_run latexlog using texpdf.sthlp, preserve
    assert _rc == 499
    assert _N == `original_observations'
    display as text "TEXPDF OPTIONAL LATEXLOG EXAMPLE SKIPPED"
}
else {
    adopath ++ `"`latexlog_dir'"'
    which latexlog
    texpdf_run latexlog using texpdf.sthlp, preserve
    assert _N == `original_observations'
    confirm file "./texpdf_examples/latexlog/report.tex"
    confirm file "./texpdf_examples/latexlog/figures/wage-experience.pdf"
    confirm file "./texpdf_examples/latexlog/report.pdf"
    adopath - `"`latexlog_dir'"'
    display as result "TEXPDF OPTIONAL LATEXLOG EXAMPLE PASS"
}

local viewer_log : environment TEXPDF_VIEW_LOG
if `"`viewer_log'"' != "" {
    confirm file `"`viewer_log'"'
    tempname viewer_handle
    file open `viewer_handle' using `"`viewer_log'"', read text
    local manual_launches = 0
    local latexlog_launches = 0
    file read `viewer_handle' viewer_line
    while r(eof) == 0 {
        if strpos(`"`viewer_line'"', "/texpdf_examples/manual/report.pdf") {
            local ++manual_launches
        }
        if strpos(`"`viewer_line'"', "/texpdf_examples/latexlog/report.pdf") {
            local ++latexlog_launches
        }
        file read `viewer_handle' viewer_line
    }
    file close `viewer_handle'
    assert `manual_launches' == 2
    if `"`latexlog_dir'"' != "" assert `latexlog_launches' == 1
}

cd `"`original_pwd'"'
display as result "TEXPDF HELP EXAMPLES PASS"
