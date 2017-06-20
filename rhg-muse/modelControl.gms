$title US Climate Risk Assessment Model Control File

$oneolcom
$eolcom !

$IF NOT dexist listings     $CALL 'mkdir listings'
$IF NOT dexist results      $CALL 'mkdir results'

$IF NOT SET threadID        $abort 'threadID not found'
$IF NOT SET HURR_ACTIV_SCEN $abort 'hurricane id not found'
$IF NOT SET runID           $abort 'runID not found'

*   Damage flags for testing & sensitivity studies
*-------------------------------------------------------------------------------------------------
*   Run type and damage file settings
$IF NOT SET DELTA_RUN           $SET DELTA_RUN          FALSE
$IF NOT SET DAMAGE_OFF          $SET DAMAGE_OFF         FALSE
$IF NOT SET SINGLE_DAMAGE       $SET SINGLE_DAMAGE      FALSE
$IF NOT SET SDAMAGE_TYPE        $SET SDAMAGE_TYPE       NONE
$IF NOT SET isuffix             $SET isuffix            state
$IF NOT SET DAMAGE_YEAR         $SET DAMAGE_YEAR        0

* The following flags force a run of each sector. They do not need to be true
* for that sector to run, but if they are true, the sector will be read. Used in
*   local combo runs.
$IF NOT SET RUN_COASTAL         $SET RUN_COASTAL        FALSE
$IF NOT SET RUN_ENERGY          $SET RUN_ENERGY         FALSE
$IF NOT SET RUN_LABOR           $SET RUN_LABOR          FALSE
$IF NOT SET RUN_MORTALITY       $SET RUN_MORTALITY      FALSE
$IF NOT SET RUN_AG              $SET RUN_AG             FALSE


* These flags turn on or off the final stage of damage handling. Damages will be read based on the
* control parameters above, but these control their use in the CGE model.
parameter
  damage_run_flag              "flag to indicate whether damages are enabled for delta run",

  damage_capital_flag          "flag to use coastal capital damages in solution",
  damage_labprod_flag          "flag to use labor productivity damages in solution",
  damage_outprod_flag          "flag to use output productivity damages in solution",
  damage_energy_flag           "flag to use energy expenditure damages in solution",
  damage_mort_flag             "flag to use mortality damages in solution",

  shock_capital_flag           "flag to test single-year coastal capital damages in solution",
  shock_labprod_flag           "flag to test single-year labor productivity damages in solution",
  shock_outprod_flag           "flag to test single-year output productivity damages in solution",
  shock_energy_flag            "flag to test single-year energy expenditure damages in solution",
  shock_mort_flag              "flag to test single-year mortality damages in solution";
           
damage_run_flag     = yes;

damage_capital_flag = yes;
damage_labprod_flag = yes;
damage_outprod_flag = yes;
damage_energy_flag  = yes;
damage_mort_flag    = yes;

shock_capital_flag  = no ;
shock_labprod_flag  = no ;
shock_outprod_flag  = no ;
shock_energy_flag   = no ;
shock_mort_flag     = no ;

* Consumer elasticity of substitution for energy/nonenergy goods
$IF NOT SET CEELAS $SET CEELAS 1
*-------------------------------------------------------------------------------------------------





* Set backup command line parameter defaults. Defaults should be set in root/runsetup.py
*-------------------------------------------------------------------------------------------------
$IF NOT SET aggr $SET aggr NCA

* Change for UNIX platforms:
$setglobal slash \

*-------------------------------------------------------------------------------------------------


* Include formatted and balanced IMPLAN SAM data
$batinclude regionaldata

* Include additional parameter definitions used in the calculation of the base year equilibrium
$batinclude initialYearDefs

$goto end

* Read MPSGE model file
$batinclude muse_core.mpsge


$IFTHEN.delta "%DELTA_RUN%" == "FALSE"

*   Include dynamics file, which runs multi-year simulation, updates calibrating parameters, applies damages, and tabulates results
$batinclude dynamics.gms

$ELSE.delta

$batinclude "inter-pre.gms"

$ENDIF.delta

$label end