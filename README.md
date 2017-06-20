This repository contains scripts and libraries used in the generation
of results for the American Climate Prospectus.  The directories are
as follows:

 - `adaptation`: Adapting curve framework for estimating adaptation
   through changing response curves.

 - `census`: The data used to describe county populations, and a
   module for accessing them.

 - `climate`: The CO2 concentration data.

 - `coastal-impacts`: Module for producing coastal damage estimates from RMS
   simulation results.

 - `controller`: The top-level controller for generating all results.
   This is extract from the DMAS system, and cannot currently be run
   without it.

 - `crime`: Post-processed form of the Ranson replication dataset and
   a module for accessing it as a baseline.

 - `crops`: Data and modules for harvested areas, production, and crop
   calendars.

 - `extract`: Scripts for translating projection data into composite
   results.

 - `iam`: The top-level framework for generating projection results.

 - `agriculture`: Logic for describing agricultural response functions.

 - `market-mortality`: Module for computing market mortality impacts.

 - `analysis`: Scripts to analyze the results and produce plots.

To generate results, you will also need to install
https://github.com/ClimateImpactLab/open-estimate.

To extract information from the results, use the tools at
https://github.com/jrising/prospectus-tools/tree/master/acra/extract.
