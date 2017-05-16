// 	PLOTTING STACKED BAR PLOT FOR UNCERTAINTY ANALYSIS

//cd ~/Dropbox/ACRA/science_submission/figures/uncertainty/
cd "~/Dropbox/Rhodium/ACP Team/Papers/science_submission/figures/uncertainty/"

capture mkdir figures
capture mkdir figures/gph
capture mkdir figures/pdf

clear

insheet using "./data/uncstds.csv"

sort sector outcome scenario year

loc var_list "model weather stat all"

loc mortality_rate_all = (0.0483802996264*36913469.5+0.00626023170248*71574854.8+0.000950382305292*171974655.4+0.00696366664835*3994760.4)/(36913469.5+71574854.8+171974655.4+3994760.4)

foreach i of loc var_list {

//	replace `i'_sd = `i'_sd*100000 if sector == "health" // convert to units of death per 100000

	replace `i'_sd = `i'_sd/0.00696366664835*100 if outcome == "mortage0to0" // convert to units of percentage points of baseline
	replace `i'_sd = `i'_sd/0.000950382305292*100 if outcome == "mortage1to44" // convert to units of percentage points of baseline
	replace `i'_sd = `i'_sd/0.00626023170248*100 if outcome == "mortage45to64" // convert to units of percentage points of baseline
	replace `i'_sd = `i'_sd/0.0483802996264*100 if outcome == "mortage65toinf" // convert to units of percentage points of baseline
	replace `i'_sd = `i'_sd/`mortality_rate_all'*100 if outcome == "mortality" // convert to units of percentage points of baseline

	replace `i'_sd = `i'_sd*100 if sector ~= "health"	// convert to percentage points
}

foreach i of loc var_list {
	gen `i'_var = `i'_sd^2
}

// checking that sum of variances equals total variance
gen sum_all_var = model_var + weather_var + stat_var
plot all_var sum_all_var
reg all_var sum_all_var

// compute covariance contribution as residual variance
gen cov_var = all_var - sum_all_var


replace outcome = "0-1" if outcome == "mortage0to0"
replace outcome = "1-44" if outcome == "mortage1to44"
replace outcome = "45-64" if outcome == "mortage45to64"
replace outcome = ">64" if outcome == "mortage65toinf"
replace outcome = "total" if outcome == "newmort"

replace outcome = "high risk" if outcome == "highproductivity"
replace outcome = "low risk" if outcome == "lowproductivity"

gen co2 = "w/ CO2"
replace co2 = "no CO2" if outcome == "oilcropnoco2" | outcome == "grainsnoco2" | outcome == "cottonnoco2"
replace co2 = "" if sector ~= "yields"

gen crop = subinstr(outcome,"noco2","",1)
replace crop = "" if sector ~= "yields"


// bar plot

loc rcp_list "26 45 60 85"
loc year_list "2020 2040 2080"

loc rcp_list "85"
loc year_list "2080"

foreach rcp of loc rcp_list{
foreach y of loc year_list{


// yields
graph hbar model_var weather_var stat_var cov_var if sector == "yields" & year == `y' & scenario == "rcp`rcp'", over(crop) over(co2) stack bar(1, color(ltblue)) bar(2, color(cranberry)) bar(3, color(orange)) bar(4, color(olive_teal))  ytit("Variance (% baseline^2)") tit("Agriculture") note("RCP`rcp' `y'") saving(./figures/gph/uncertainty_yields_RCP`rcp'_`y'.gph, replace) legend(off) //legend(lab(1 "model") lab(2 "weather") lab(3 "statistical") lab(4 "covariance") col(4))

// crime
graph hbar model_var weather_var stat_var cov_var if sector == "crime" & year == `y' & scenario == "rcp`rcp'", over(outcome) stack bar(1, color(ltblue)) bar(2, color(cranberry)) bar(3, color(orange)) bar(4, color(olive_teal))  ytit("Variance (% baseline^2)") tit("Crime") note("RCP`rcp' `y'") saving(./figures/gph/uncertainty_crime_RCP`rcp'_`y'.gph, replace) legend(off) //legend(lab(1 "model") lab(2 "weather") lab(3 "statistical") lab(4 "covariance") col(4))


// mortality
graph hbar model_var weather_var stat_var cov_var if sector == "health" & year == `y' & scenario == "rcp`rcp'", over(outcome) stack bar(1, color(ltblue)) bar(2, color(cranberry)) bar(3, color(orange)) bar(4, color(olive_teal)) ytit("Variance (% baseline^2)") tit("Mortality") note("RCP`rcp' `y'")  saving(./figures/gph/uncertainty_health_RCP`rcp'_`y'.gph, replace) legend(off) //legend(lab(1 "model") lab(2 "weather") lab(3 "statistical") lab(4 "covariance") col(4))

// labor
graph hbar model_var weather_var stat_var cov_var if sector == "labor" & year == `y' & scenario == "rcp`rcp'", over(outcome) stack bar(1, color(ltblue)) bar(2, color(cranberry)) bar(3, color(orange)) bar(4, color(olive_teal)) legend(lab(1 "model") lab(2 "weather") lab(3 "statistical") lab(4 "interaction") col(4)) ytit("Variance (% baseline^2)") tit("Labor") note("RCP`rcp' `y'") saving(./figures/gph/uncertainty_labor_RCP`rcp'_`y'.gph, replace)


}
}

graph combine ///
figures/gph/uncertainty_yields_RCP85_2080.gph ///
figures/gph/uncertainty_health_RCP85_2080.gph ///
figures/gph/uncertainty_crime_RCP85_2080.gph ///
figures/gph/uncertainty_labor_RCP85_2080.gph ///
, cols(1) xsize(5) ysize(15)

graph export "figures/pdf/uncertainty_all_RCP85_2080.pdf", replace















