
# Market mortality valuation module

Created by [Michael Delgado][] of the [Rhodium Group][]

[Michael Delgado]: http://rhg.com/people/michael-delgado
[Rhodium Group]: http://rhg.com/



## Running a scenario ##

Run the module from control.py.

* Use the StateRun class to use state-level data (consistent with the ACP)
* Use the CountyRun class to use county-level data (consistent with the Midwest, California reports)

## Run Options ##

### StateRun Options ###

The core class StateRun provides no mechanisms for modifying defaults.

#### Other options ####

* **readdir** - Mortality impact data directory
* **deflator** - Deflator (currently 2012 to 2011: `0.982324529`) may be changed in the `DEFLATOR_2012_TO_2011` parameter in lib/config.py
* **discrate** - Set of discount rates used in mortality cost projections - may be changed in the `discount_rates` parameter in lib/config.py
* **valuedir** - Output directory for absolute costs/benefits - may be changed in by_state/writer.py
* **percapdir** - Output directory for per capita costs/benefits - may be changed in by\_state/writer.py
* **CSV\_HEADER** - Header placed at the top of output CSV files - may be changed in by\_state/writer.py

### CountyRun Options ###

#### ClassMethod CountyRun.run_scenario() options ####

* **readdir** - Mortality impact data directory
* **agglev** - Aggregation scheme for moving from counties to super-county groups. Options are 'county','state','nca','midwest','california'
* **deflator** - Override the default deflator (currently 2012 to 2011: 0.982324529)
* **test\_data** - Testing flag - True allows extrapolating state-level data to county level data in place of IMPLAN values

#### Modifying the aggregation scheme ####

The aggregation tools are available in `regions.regdef`. To add an aggregation
scheme, provide an aggregation map (see 'midwestMap'), create a function to
convert counties to regions, vectorize it using RegionDefinitions.vectorize,
then provide this as an option in RegionDefinitions.county_aggregator