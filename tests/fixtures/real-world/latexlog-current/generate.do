version 18.0
clear all
set more off
set varabbrev off
set seed 24082026

args output_dir
if `"`output_dir'"' == "" {
    display as error "output directory is required"
    exit 198
}

local latexlog_dir : environment LATEXLOG_DIR
if `"`latexlog_dir'"' == "" {
    display as error "LATEXLOG_DIR is required"
    exit 198
}
adopath ++ `"`latexlog_dir'"'
which latexlog

capture mkdir `"`output_dir'"'
capture mkdir `"`output_dir'/figures"'
local report `"`output_dir'/report.tex"'

set obs 72
generate index = _n
generate treatment = mod(_n, 2)
generate region = 1 + mod(_n, 3)
label define region_label 1 "North" 2 "Central" 3 "South"
label values region region_label
generate exposure = 0.15 * index + 1.5 * treatment + rnormal(0, 0.35)
generate outcome = 2.0 + 0.55 * treatment + 0.08 * exposure + rnormal(0, 0.25)
label variable outcome "Synthetic outcome"
label variable exposure "Synthetic exposure"
label define treatment_label 0 "Comparison" 1 "Program"
label values treatment treatment_label

latexlog `report': open, ///
    geometry(lmargin=2.4cm,rmargin=2.4cm,tmargin=2.1cm,bmargin=2.1cm) ///
    predocopen(\newcommand{\estimand}{\widehat{\theta}}) ///
    postdocopen(\noindent)
latexlog `report': title "Synthetic latexlog Compatibility Report"
latexlog `report': writeln "This report is generated from deterministic synthetic Stata data."
latexlog `report': section "Model"
latexlog `report': writeln "The custom command produces $\estimand$ and the displayed equation is"
latexlog `report': writeln "\[\estimand=(X^{\prime}X)^{-1}X^{\prime}y,\qquad \mathrm{E}[u\mid X]=0.\]"

latexlog `report': section "Figures"
latexlog `report': writeln "The color figures use navy observations and orange fitted or comparison elements."
twoway (scatter outcome index, msize(vsmall) mcolor(navy)) ///
    (lfit outcome index, lcolor(orange) lwidth(medthick)), ///
    title("Outcome over the synthetic index") legend(off) scheme(s2color)
latexlog `report': addfig, filename(figures/outcome-by-index.pdf) float ///
    title(Synthetic Outcome and Linear Fit) ///
    notes(Deterministic synthetic observations., center) width(.72)

graph bar (mean) outcome, over(treatment) asyvars ///
    bar(1, color(navy)) bar(2, color(orange)) ///
    title("Mean outcome by assignment") scheme(s2color)
latexlog `report': writeln "The next PNG figure is included inline."
latexlog `report': addfig, filename(figures/outcome-by-treatment.png) width(.48)

latexlog `report': subsection "Subfigures"
latexlog `report': subfigure, open title(Synthetic outcomes and exposures)
twoway scatter outcome exposure, msize(vsmall) mcolor(navy) ///
    title("Outcome") legend(off) scheme(s2color)
latexlog `report': subfigure, addfig filename(figures/panel-outcome.pdf) ///
    caption("Outcome and exposure") width(.45)
twoway scatter exposure index, msize(vsmall) mcolor(orange) ///
    title("Exposure") legend(off) scheme(s2color)
latexlog `report': subfigure, addfig filename(figures/panel-exposure.pdf) ///
    caption("Exposure over index") width(.45)
latexlog `report': subfigure, close ///
    notes(All panels use the same deterministic synthetic sample.)

latexlog `report': section "Tables"
table treatment region, statistic(mean outcome) statistic(sd outcome) nototals
latexlog `report': collect export, ///
    title(Synthetic Outcome by Assignment and Region) ///
    booktabs novert threeparttable ///
    notes(Means and standard deviations from synthetic data.)

table region treatment, statistic(mean exposure) nototals
latexlog `report': collect export, ///
    title(Synthetic Exposure in a Landscape Tabularx Table) ///
    booktabs novert landscape threeparttable ///
    tabularx(2 3, width(1.18\textwidth)) ///
    notes(Selected columns use the tabularx X column type.)

latexlog `report': section "Conclusion"
latexlog `report': writeln "Figures, tables, notes, custom commands, and mathematics resolved successfully."
latexlog `report': close

display as result "TEXPDF LATEXLOG GENERATOR PASS"
