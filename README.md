This repository contains scripts and libraries used in the generation
of results for the American Climate Prospectus.  The directories are
as follows:

 - `adaptation`: Adapting curve framework for estimating adaptation
   through changing response curves.

 - `census`: The data used to describe county populations, and a
   module for accessing them.

 - `climate`: The CO2 concentration data.

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

 - `rhg-muse`: Computable general equilibrium model used in estimating
   macroeconomic effects.