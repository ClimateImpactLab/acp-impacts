

* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* FINAL SAM ADJUSTMENTS AND ACCOUNTING VARIABLES
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=


* Define additional sets used in the dynamic model
*-------------------------------------------------------------------------------------------------

$if not set t_start     $set t_start    2011
$if not set t_end       $set t_end      2100

set tp          Time periods in model   /%t_start%*%t_end%/,
    tfirst(tp)  First period,
    tlast(tp)   Last period;

parameter year(*) Numerical value of year;
year(tp) = tp.val;
year("0") = 0;

tfirst(tp)  = yes$(ord(tp) eq 1);
tlast(tp)   = yes$(ord(tp) eq card(tp));

set fL(f)       Labor factor input          /empl/,
    fK(f)       Capital factor input        /prop,othp/,
    fT(f)       Business tax factor input   /btax/;

alias (r,rr), (g,gg), (tp,ttp);
*------------------------------------------------------------------------------------------------


* Read exogenous population projection
*------------------------------------------------------------------------------------------------
parameter usPopulation(*) "US Population read from USPOP.dat, data from UN Projections 2010-2100";

$GDXIN usPop.gdx
$load usPopulation

* popGrowth is defined as pop(tp+1)/pop(tp) so that the growth rate may be multiplied by the current population
* at the end of each loop of the recursive dynamic. 
parameter popGrowth(tp)   US Population growth from current year to next year;

loop(tp,
  if((year(tp)>2011),
      popGrowth(tp) = usPopulation(tp)/usPopulation(tp-1);
    );
);

*-------------------------------------------------------------------------------------------------


* Set calibration data
*-------------------------------------------------------------------------------------------------

scalar  r0              Benchmark interest rate             /0.199/
        depr            Depreciation rate                   /0.052/
        baseLabProd     Base labor productivity growth rate /1.01/;

* Consumer elasticity of substitution for energy/nonenergy goods
$IF NOT SET CEELAS $SET CEELAS 1

parameter
  out_elas(r,s)     "Armington good elasticity of transformation",
  arm_elas(r,s)     "Armington good elasticity of substitution";
  
* Armington and transformation elasticity between domestically traded and foreign traded good
* is set to twice the values below. 
out_elas(r,s) = 2.0;
arm_elas(r,s) = 2.0;
out_elas(r,"AGR")$NODAMAGE(r) = 0.0;
arm_elas(r,"AGR")$NODAMAGE(r) = 0.0;


scalar c_e_elas "Consumer energy-nonenergy elasticity of substitution" /%CEELAS%/;

*-------------------------------------------------------------------------------------------------


* Labor and Capital value-added accounting parameters
*-------------------------------------------------------------------------------------------------
parameter LabDemDom0(r,s)   "Reference industrial labor demand - domestic (2011 US$M)",
          CapDemDom0(r,s)   "Reference industrial capital demand - domestic (2011 US$M)",
          OthBusTax0(r,s)   "Reference business taxes (2011 US$M)",
          tax_split(r,s)    "Tax split between labor and capital";

LabDemDom0(r,s) = sum(fL,FacDemDom0(r,fL,s));
CapDemDom0(r,s) = sum(fK,FacDemDom0(r,fK,s));
OthBusTax0(r,s) = FacDemDom0(r,"btax",s);

* We do not have explicit taxation. All income goes to a representative agent which 
* which allocates income between household consumption, government consumption and savings. \
* So the output tax is split proportionally between labor and capital income. 

tax_split(r,s) = 0;   ! Initialize to 0 to catch cases where valueAdded(r,s) = 0;
tax_split(r,s)$(LabDemDom0(r,s)+CapDemDom0(r,s)) = (LabDemDom0(r,s))/(LabDemDom0(r,s)+CapDemDom0(r,s));

LabDemDom0(r,s) = LabDemDom0(r,s) + tax_split(r,s)*OthBusTax0(r,s);
CapDemDom0(r,s) = CapDemDom0(r,s) + (1-tax_split(r,s))*OthBusTax0(r,s);


parameter labor(r)        "Annual labor earnings endowment (2011 US$M)",
          gammaL(r,s)     "Annual labor productivity change";

*   Initialize reference labor endowments to equal labor demand by region and sector
labor(r)        = sum(s,LabDemDom0(r,s));
gammaL(r,s)     = 1.0;

parameter capUse(r,s)     "Annual reference capital use (2011 US$M)",
          labUse(r,s)     "Annual reference labor use (2011 US$M)",
          gdsUSe(r,g,s)   "Annual reference intermediate goods use (2011 US$M)";

labUse(r,s)   = LabDemDom0(r,s);
capUse(r,s)   = CapDemDom0(r,s);
gdsUse(r,g,s) = IndDemTot0(r,g,s);

* The value of labor use will be multiplied by the labor productivity growth, therefore, the real quantity of labor
* demanded will experience an inverse change. In 2011, this is inconsequential because gammaL is 1.
labUse(r,s)   = labUse(r,s) / gammaL(r,s); 


* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* The following fixes the small discrepancy in government expenditures which arises
* due to the current build. REMOVE it if the problem gets fixed in the new build 

parameter totingovtexpen Total initial govt expenditures,
          totscgovtexpen Total scaled govt expenditures,
          scalgovtexpen  Scaling factor for govt expenditure;

totingovtexpen = (sum((r,pub),PubDemTot0(r,pub)));
totscgovtexpen = sum((r,s),ImpGdsTot0(r,s,"ftrd")) - sum((r,s),IndIntExp0(r,s,"ftrd"));
totscgovtexpen = totscgovtexpen + sum((r,s),LabDemDom0(r,s))+sum((r,s),CapDemDom0(r,s))
                 - (sum(r,DemTotReg0(r))+sum((r,s),InvDemCom0(r,s)));

scalgovtexpen =   totscgovtexpen/totingovtexpen;

PubDemTot0(r,pub) = PubDemTot0(r,pub)*scalgovtexpen;


* Nominal trade balance is constant at 2011 levels

parameter TradeImbal0(r)      "Benchmark foreign trade deficit";
    
* Trade Imbalance = (GDP) - (C + I + G) = (NX)
TradeImbal0(r)  = (DemTotReg0(r) + sum(s,InvDemCom0(r,s)) + sum(pub,PubDemTot0(r,pub)))
                  - (sum(s,LabDemDom0(r,s) + CapDemDom0(r,s)));

InvDemCom0(r,s)$(DomOutTot0(r,s) = 0) =0;

*-------------------------------------------------------------------------------------------------





* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=



* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* Annually updating calibrating parameters
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=


parameter
  kn(r)             "Capital (new) - used to calibrate annual reference new vintage capital (2011 US$M)",
  kx(r,s)           "Capital (extant) - annual reference extant capital stock use by region and sector (2011 US$M)",
  kexch(r)          "Capital (exchange) - annual reference extant capital stock earnings (not use) by region (2011 US$M)",
  kx_refUse(r,s)    "Annual reference capital use in extant production (2011 US$M)",
  lx_refUse(r,s)    "Annual reference labor use in extant production (2011 US$M)",
  thetaRSAV(r,s)    "Share of investment goods by sector in each region (-)",
  mpsave(r)         "Marginal propensity to save by region, based on 2011 savings rate (-)",
  kxt               "Total extant capital used to distribute extant capital by region and sector in prod:K";



* Current investment in each region is assumed to equal savings.
* Simplifying assumption for the model to equilibrate in the base year. It takes two years for the model
* to reach steady growth so the growth in the first of couple years bounces around. After that
* it is smooth.

mpsave(r) = (sum(s,InvDemCom0(r,s)))/(DemTotReg0(r)+sum(s,InvDemCom0(r,s))+sum((s,pub),PubDemSec0(r,s,pub)));

* Distribute current capital stock between new vintage and extant
* r0 is the reference rate of return (rkref in Tom's model)

kn(r) = sum(s,InvDemCom0(r,s))*r0;
kexch(r) = (sum(s,CapDemDom0(r,s))) - kn(r);

* Distribute the extant capital by region and sector in Prod:K
kx(r,s) = (CapDemDom0(r,s)/sum(g,CapDemDom0(r,g)))*kexch(r);
kxt   = sum((r,s),kx(r,s));

* Initialize the capital and labor shares to the base data for extant production block
kx_refUse(r,s) =capUse(r,s);
lx_refUse(r,s) = labUse(r,s);

* Calculate the distribution of investment goods by region - remains same throughout the model
thetaRSAV(r,s) = InvDemCom0(r,s)/sum(g,InvDemCom0(r,g));

* Annual impact parameters - updated each year at the end of the dynamic equations

parameter
  labHeatImpct(r,s) "Change in labor productivity as a function of heat (indexed to 2011, low indicates low productivity)",
  outdam(r,s)       "Impact multiplier on output productivity (indexed to 2011, low indicates low productivity)",
  enrdam(r,s)       "Increase in energy expenditures - residential (fractional, positive indicates increase in energy expenditures)",
  encdam(r,g,s)     "Increase in energy expenditures - commercial (fractional, positive indicates increase in energy expenditures)",
  dam_cap_val(r,s)  "Capital damages in capital earnings equivalent (2011 US$M)";


* initialize the damages
labHeatImpct(r,s) = 1;
outdam(r,s)       = 1;
enrdam(r,s)       = 0;
encdam(r,g,s)     = 0;
dam_cap_val(r,s)  = 0;



* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* DOMAIN-LIMITING SETS FOR THE MPSGE CORE
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=


* The following parameters limit the domain of the major production and consumption blocks in the MPSGE static core
* to those regions and sectors in which the baseline activity level is nonzero.

set
      s_DomR(*,r)         "Set domain for all sectors indexed over r",
      s_DomRS(*,r,s)      "Set domain for all sectors indexed over r and s",
      c_DomR(*,r)         "Set domain for all commodities indexed over r",
      c_DomS(*,s)         "Set domain for all commodities indexed over s",
      c_DomRS(*,r,s)      "Set domain for all commodities indexed over r and s";

* Initialize domains as restrictive for most sectors/commodities. For some, positive values over all set values
* are required. For these, initialize to yes:

s_DomR("c",r)       = yes;
s_DomRS("y",r,s)    = no;
s_DomRS("yx",r,s)   = no;
s_DomRS("a",r,s)    = no;
s_DomR("inv",r)     = yes;
s_DomR("gov",r)     = yes;
s_DomR("kn",r)      = yes;
c_DomR("pc",r)      = yes;
c_DomRS("pa",r,s)   = no;
c_DomS("pn",s)      = no;
c_DomR("pgov",r)    = yes;
c_DomR("pl",r)      = yes;
c_DomRS("py",r,s)   = no;
c_DomR("pinv",r)    = yes;
c_DomR("rk",r)      = yes;
c_DomRS("rkx",r,s)  = no;
c_DomR("trB",r)     = yes;

* For optional sectors/commodities, allow domains where initial production is nonzero

s_DomRS("y",r,s)$(   DomOutTot0(r,s) > 0) = yes;
s_DomRS("yx",r,s)$(  DomOutTot0(r,s) > 0) = yes;
s_DomRS("a",r,s)$(   ArmAggGds0(r,s) > 0) = yes;
c_DomRS("pa",r,s)$(  ArmAggGds0(r,s) > 0) = yes;
c_DomRS("py",r,s)$(  DomOutTot0(r,s) > 0) = yes;
c_DomRS("rkx",r,s)$( CapDemDom0(r,s) > 0) = yes;
c_DomS("pn",s)$(sum(r,IndIntExp0(r,s,"ftrd")) > 0) = yes;




* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* READ IN IMPACT DATA FROM SEAGLAS DIRECT EFFECT MODELING
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=


$ONTEXT
  /*
   Determine impact indexing scheme

  Some impacts are delivered by region name (SWE, CA, etc.) and others by ANSI code (1001, 56, etc.)
  Depending on the aggregation level, ANSI 2-digit state codes or ANSI [4,5] digit county codes should
  be used, and read as integer values (without the leading zero). Set the impacts that will be read as
  ANSI codes vs. region names here.
  */
$OFFTEXT

$SET  ENERGY_REG  ir
$SET  AG_REG      ANSI
$SET  LABOR_REG   ANSI
$SET  MORT_REG    ANSI
$SET  COAST_REG   ANSI




* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* ENERGY IMPACT PROCESSING
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

$ONTEXT
  /*
  HDDS and CDDs are population-weighted averages across regions. We assume that the above relationships between energy and
  HDD/CDD holds for all counties within these regions, and that the impacts to each CGE region are based on a population-weighted 
  linear combination of the above values based on the county composition of each CGE region.
  */
$OFFTEXT

parameter totalpop(ir) "impact region total population";
totalpop(ir) = sum(age,RegPopByAge_IR(ir,age));

parameter expChange_raw(*,*,*)  "raw (state or ANSI code) change in energy expenditures";
parameter expChange(*,*,*)      "impact-region (states - DC separated) change in energy expenditures";

parameter resEnerExpChange(tp,r) "Change in residential energy expenditures in region r, value in 2011 = 0 (fraction)",
          comEnerExpChange(tp,r) "Change in commercial energy expenditures in region r, value in 2011 = 0 (fraction)";

$SET HCDD_READ FALSE

$IFTHEN.DAM_OFF "%DAMAGE_OFF%" == "FALSE"
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "FALSE"
$SET HCDD_READ TRUE
$ENDIF.SNGL_DAM
$ENDIF.DAM_OFF
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "TRUE"
$IFTHEN.SDAM_TYP "%SDAMAGE_TYPE%" == "ENERGY"
$SET HCDD_READ TRUE
$ENDIF.SDAM_TYP
$ENDIF.SNGL_DAM
$IFTHEN.FORCE_ENERGY "%RUN_ENERGY%" == "TRUE"
$SET HCDD_READ TRUE
$ENDIF.FORCE_ENERGY

$IFTHEN.READ_HCDD "%HCDD_READ%" == "TRUE"
$GDXIN impacts%slash%%threadID%_energy.gdx
$load expChange_raw=expChange

$IFTHEN.ENERGYREG "%ENERGY_REG%" == "ANSI"
expChange("residential",tp,ir) = sum(ansi$map_ansi(ir,ansi),expChange_raw("residential",tp,ansi));
expChange("commercial",tp,ir) = sum(ansi$map_ansi(ir,ansi),expChange_raw("commercial",tp,ansi));
$ENDIF.ENERGYREG
$IFTHEN.ENERGYREG "%ENERGY_REG%" == "ir"
expChange("residential",tp,ir) = expChange_raw("residential",tp,ir);
expChange("commercial",tp,ir) = expChange_raw("commercial",tp,ir);
$ENDIF.ENERGYREG

resEnerExpChange(tp,r) = sum(ir$mapir(r,ir),(expChange("residential",tp,ir)-expChange("residential",'2011',ir))*totalpop(ir)) / sum(ir$mapir(r,ir),totalpop(ir));
comEnerExpChange(tp,r) = sum(ir$mapir(r,ir),(expChange("commercial",tp,ir)-expChange("commercial",'2011',ir))*totalpop(ir)) / sum(ir$mapir(r,ir),totalpop(ir));

$ELSE.READ_HCDD

resEnerExpChange(tp,r) = 0;
comEnerExpChange(tp,r) = 0;

$ENDIF.READ_HCDD


* Set impact in 2100 to 0 to control cross-climate-model differences and prevent model failure
resEnerExpChange('2100',r) = 0;
comEnerExpChange('2100',r) = 0;



* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* YIELD LOSS PROCESSING
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

$ONTEXT
  /*
  Agricultural output impacts are calculated for four crops - wheat, maize, soy, and cotton. Wheat and maize are combined - together
  and by region - on a calorie basis, whereas soy and cotton are aggregated by area planted. Finally, these impacts are averaged using
  weights representing each crop's share of regional agricultural output. This is achieved in two steps - first by combining using 
  value weighting, then by multiplying the share of agriculture represented by the combined grains, oilseeds, and cotton IMPLAN sectors.
  */
$OFFTEXT


parameter yieldFactor(tp,r,crops) "Change in agricultural output by crop";

set yDomain(r,crops);
yDomain(r,crops) = no;
yDomain(r,'COT')$sum(ir$mapir(r,ir),areaPlanted_IR(ir,'cotton')) = yes;
yDomain(r,'OSD')$sum(ir$mapir(r,ir),areaPlanted_IR(ir,'soy')) = yes;
yDomain(r,'GRN')$sum(ir$mapir(r,ir),grainCaloricOutput_IR(ir)) = yes;

parameter yields_cotton_raw(*,*);
parameter yields_oilcrop_raw(*,*);
parameter yields_grains_raw(*,*);

parameter yields_cotton(*,*);
parameter yields_oilcrop(*,*);
parameter yields_grains(*,*);

$SET AGIMPCT_READ FALSE

$IFTHEN.DAM_OFF "%DAMAGE_OFF%" == "FALSE"
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "FALSE"
$SET AGIMPCT_READ TRUE
$ENDIF.SNGL_DAM
$ENDIF.DAM_OFF
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "TRUE"
$IFTHEN.SDAM_TYP "%SDAMAGE_TYPE%" == "AG"
$SET AGIMPCT_READ TRUE
$ENDIF.SDAM_TYP
$ENDIF.SNGL_DAM
$IFTHEN.FORCE_AG "%RUN_AG%" == "TRUE"
$SET AGIMPCT_READ TRUE
$ENDIF.FORCE_AG

$IFTHEN.READ_AGIMPCT "%AGIMPCT_READ%" == "TRUE"

$GDXIN 'impacts%slash%%threadID%_yields_cotton_%isuffix%.gdx'
$load yields_cotton_raw=yields_cotton_%isuffix%
$GDXIN 'impacts%slash%%threadID%_yields_oilcrop_%isuffix%.gdx'
$load yields_oilcrop_raw=yields_oilcrop_%isuffix%
$GDXIN 'impacts%slash%%threadID%_yields_grains_%isuffix%.gdx'
$load yields_grains_raw=yields_grains_%isuffix%

$IFTHEN.AGREG "%AG_REG%" == "ANSI"
yields_cotton(ir,tp) = sum(ansi$map_ansi(ir,ansi),yields_cotton_raw(ansi,tp));
yields_oilcrop(ir,tp) = sum(ansi$map_ansi(ir,ansi),yields_oilcrop_raw(ansi,tp));
yields_grains(ir,tp) = sum(ansi$map_ansi(ir,ansi),yields_grains_raw(ansi,tp));
$ENDIF.AGREG
$IFTHEN.AGREG "%AG_REG%" == "ir"
yields_cotton(ir,tp) = yields_cotton_raw(ir,tp);
yields_oilcrop(ir,tp) = yields_oilcrop_raw(ir,tp);
yields_grains(ir,tp) = yields_grains_raw(ir,tp);
$ENDIF.AGREG

yieldFactor(tp,r,'COT')$yDomain(r,'COT') = 1 - sum(ir$mapir(r,ir),(1-yields_cotton(ir,tp))*areaPlanted_IR(ir,'cotton')) / sum(ir$mapir(r,ir),areaPlanted_IR(ir,'cotton'));
yieldFactor(tp,r,'OSD')$yDomain(r,'OSD') = 1 - sum(ir$mapir(r,ir),(1-yields_oilcrop(ir,tp))*areaPlanted_IR(ir,'soy')) / sum(ir$mapir(r,ir),areaPlanted_IR(ir,'soy'));
yieldFactor(tp,r,'GRN')$yDomain(r,'GRN') = 1 - sum(ir$mapir(r,ir),(1-yields_grains(ir,tp))*grainCaloricOutput_IR(ir)) / sum(ir$mapir(r,ir),grainCaloricOutput_IR(ir));

$ELSE.READ_AGIMPCT

yieldFactor(tp,r,crops) = 1;
yieldFactor(tp,r,crops) = 1;

$ENDIF.READ_AGIMPCT

* Set impact in 2100 to 1 to control cross-climate-model differences and prevent model failure
yieldFactor('2100',r,crops) = 1;



* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* LABOR IMPACT PROCESSING
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

$ONTEXT
  /*
  Labor productivity affects the productivity of labor use by sectors, which are classified into 'low-' and 'high-risk'
  according to the definitions lowlaborRisk and highlaborRisk
  */
$OFFTEXT

set
  lowlaborRisk(s)   "sectors with low decline in labor productivity,",
  highlaborRisk(s)  "sectors with high decline in labor productivity";

lowlaborRisk(s) = no;
lowlaborRisk("realEstate") = yes;
lowlaborRisk("indoorServ") = yes;

highlaborRisk(s) = yes;
highlaborRisk("realEstate") = no;
highlaborRisk("indoorServ") = no;

parameter labor_high_productivity_raw(*,*)  "Labor productivity for high-risk occupations, indexed to 2011";
parameter labor_low_productivity_raw(*,*)  "Labor productivity for low-risk occupations, indexed to 2011";
parameter labor_high_productivity(*,*)  "Labor productivity for high-risk occupations, indexed to 2011";
parameter labor_low_productivity(*,*)  "Labor productivity for low-risk occupations, indexed to 2011";

parameter labProdChange(tp,r,labtype)         "Heat-induced change in labor productivity by sector class, indexed to 2011";

$SET LPROD_READ FALSE

$IFTHEN.DAM_OFF "%DAMAGE_OFF%" == "FALSE"
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "FALSE"
$SET LPROD_READ TRUE
$ENDIF.SNGL_DAM
$ENDIF.DAM_OFF
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "TRUE"
$IFTHEN.SDAM_TYP "%SDAMAGE_TYPE%" == "LABOR"
$SET LPROD_READ TRUE
$ENDIF.SDAM_TYP
$ENDIF.SNGL_DAM
$IFTHEN.FORCE_LABOR "%RUN_LABOR%" == "TRUE"
$SET LPROD_READ TRUE
$ENDIF.FORCE_LABOR

$IFTHEN.READ_LPROD "%LPROD_READ%" == "TRUE"

$GDXIN 'impacts%slash%%threadID%_labor_high_productivity_%isuffix%.gdx'
$load labor_high_productivity_raw=labor_high_productivity_%isuffix%

$GDXIN 'impacts%slash%%threadID%_labor_low_productivity_%isuffix%.gdx'
$load labor_low_productivity_raw=labor_low_productivity_%isuffix%


$IFTHEN.LABREG "%AG_REG%" == "ANSI"
labor_low_productivity(ir,tp) = sum(ansi$map_ansi(ir,ansi),labor_low_productivity_raw(ansi,tp));
labor_high_productivity(ir,tp) = sum(ansi$map_ansi(ir,ansi),labor_high_productivity_raw(ansi,tp));
$ENDIF.LABREG
$IFTHEN.LABREG "%AG_REG%" == "ir"
labor_low_productivity(ir,tp) = labor_low_productivity_raw(ir,tp);
labor_high_productivity(ir,tp) = labor_high_productivity_raw(ir,tp);
$ENDIF.LABREG


labProdChange(tp,r,'lowR')   = 1- sum(ir$mapir(r,ir),(1-labor_low_productivity(ir,tp))*laborAtRisk(ir,'lowR'))/sum(ir$mapir(r,ir),laborAtRisk(ir,'lowR'));
labProdChange(tp,r,'highR')  = 1- sum(ir$mapir(r,ir),(1-labor_high_productivity(ir,tp))*laborAtRisk(ir,'highR'))/sum(ir$mapir(r,ir),laborAtRisk(ir,'highR'));

$ELSE.READ_LPROD

labProdChange(tp,r,labtype) = 1;

$ENDIF.READ_LPROD

* Set impact in 2100 to 1 to control cross-climate-model differences and prevent model failure
labProdChange('2100',r,labtype) = 1;



* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* SEA LEVEL IMPACT PROCESSING
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

$ONTEXT
  /*
  Coastal damages come in three forms: inundation, direct capital damages from storms, and business interruption from storms.
  Inundation damages read from #_coastal.gdx are cumulative, and are weakly increasing (drops in sea level are ignored due to
  the inability to characterize the value of receding sea levels and due to the inapplicability of the damage function to
  negative changes in sea level). Capital damages applied in the model are the marginal change in inundation plus the fraction
  of capital lost during a storm times the depreciated capital stock. Business interruption is the fraction of output lost to
  business interruption times the share of total regional output. Both direct damages and business interruption are then 
  further discounted by the share of capital already inundated - it is assumed that inundated capital cannot be damaged and
  inundated businesses do not suffer additional interruption, and that rebuilt capital and business is no longer exposed to 
  coastal storms.
  */
$OFFTEXT


set   coastDamTypes    "types of damage suffered during coastal storms and due to LSL rise" /
      inundation,direct,bi
      /;


parameter coastDamage(coastDamTypes,coastReg,tp)   "coastal damages of type coastDamTypes (1 USD)";

$SET SLEV_READ FALSE

$IFTHEN.DAM_OFF "%DAMAGE_OFF%" == "FALSE"
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "FALSE"
$SET SLEV_READ TRUE
$ENDIF.SNGL_DAM
$ENDIF.DAM_OFF
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "TRUE"
$IFTHEN.SDAM_TYP "%SDAMAGE_TYPE%" == "COASTAL"
$SET SLEV_READ TRUE
$ENDIF.SDAM_TYP
$ENDIF.SNGL_DAM

$IFTHEN.FORCE_COASTAL "%RUN_COASTAL%" == "TRUE"
$SET SLEV_READ TRUE
$ENDIF.FORCE_COASTAL

$IFTHEN.READ_SLEV "%SLEV_READ%" == "TRUE"

$GDXIN 'impacts%slash%%threadID%_coastal.gdx'
$load coastDamage=impact

$ELSE.READ_SLEV

coastDamage(coastDamTypes,coastReg,tp) = 0;

$ENDIF.READ_SLEV

* Set impact in 2100 to 1 to control cross-climate-model differences and prevent model failure
coastDamage(coastDamTypes,coastReg,'2100') = 0;

parameter margInunDam(coastReg,tp)          "Marginal inundation damages (1 USD)",
          maxInundationToDate(coastReg,tp)  "Maximum inundation damages in each state to date by year (1 USD)";

margInunDam(coastReg,tp) = 0;
maxInundationToDate(coastReg,tp) = 0;

loop(tp$(year(tp) > 2011),
* In the scripts that create the GDX files feeding into this simulation, coastDamage("inundation",coastReg,tp) is already
* a weakly increasing function of time, set to zero in 2011. That code can be viewed and downloaded at 
* https://mdelgado_RhG@bitbucket.org/mdelgado_RhG/slimpacts.git
  margInunDam(coastReg,tp) = coastDamage("inundation",coastReg,tp) - coastDamage("inundation",coastReg,tp-1);
  maxInundationToDate(coastReg,tp) = max(maxInundationToDate(coastReg,tp-1),coastDamage("inundation",coastReg,tp));
);

parameter shrExposureRemaining(coastReg,tp)     "Share of RMS property exposed not inundated to date";
shrExposureRemaining(coastReg,tp)$physExposure(coastReg) = (physExposure(coastReg) - maxInundationToDate(coastReg,tp))/physExposure(coastReg);

parameter shrInundDamage(r,tp)           "Share of direct exposure inundated in each year",
          shrDirectDamage(r,tp)          "Share of direct exposure damaged in each year",
          shrBusInterrupt(r,tp)          "Share of business interruption exposure damaged in each year";

* Inundation damages are the marginal inundation damages in each coastal region as a fraction of total capital
* exposure in that region times the previous period's share of capital not yet inundated, averaged across coastal
* regions in the CGE region weighted by the contribution of that coastal region to total CGE region capital
shrInundDamage(r,tp)$(year(tp) > 2011) = sum(coastReg$(mapcoast(r,coastReg) and physExposure(coastReg)),
    margInunDam(coastReg,tp)/physExposure(coastReg) * shrExposureRemaining(coastReg,tp-1) * CoastCapShr(coastReg));

* Direct capital damages from storms are the fraction of base capital damaged times the share of capital not yet
* inundated, averaged across coastal regions in the CGE region, weighted by the contribution of that coastal 
* region to the total CGE region's base capital
shrDirectDamage(r,tp) = sum(coastReg$(mapcoast(r,coastReg) and physExposure(coastReg)), 
    coastDamage("direct",coastReg,tp) /physExposure(coastReg) * shrExposureRemaining(coastReg,tp) * CoastCapShr(coastReg));


* Business interruption damages from storms are the fraction of business interruption exposure damaged, averaged
* across the coastal regions in the CGE region, weighted by the contribution of that coastal region to the total 
* CGE region's base output
shrBusInterrupt(r,tp) = sum(coastReg$(mapcoast(r,coastReg) and busIExposure(coastReg)), 
    coastDamage("bi",coastReg,tp)/busIExposure(coastReg) * CoastOutShr(coastReg));



* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
* MORTALITY IMPACT PROCESSING
* =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

$ONTEXT
  /*
  Mortality is tracked using a simple population model, which ages temperature-related deaths so that they affect the labor force as
  they grow. Though our baseline population model does not include demographic shifts, it was important to capture the very different
  effect that the mortality of infant, middle aged, and elderly members of the population have on the workforce. Mortality does not
  affect birth rates or migration, but make up a separate, stationary negative-population model (though in many cases this model is
  in fact tracking decreases in mortality, leading to an increase in population).
  */
$OFFTEXT



set ageCohorts /'0_0','1_44','45_64','65_inf'/;

parameter health_mortage_0_0_raw(*,*);
parameter health_mortage_1_44_raw(*,*);
parameter health_mortage_45_64_raw(*,*);
parameter health_mortage_65_inf_raw(*,*);

parameter health_mortage_0_0(*,*);
parameter health_mortage_1_44(*,*);
parameter health_mortage_45_64(*,*);
parameter health_mortage_65_inf(*,*);

parameter popimpact(tp,r,ageCohorts)  "Heat-related change in population per 100,000, relative to 2011";

$SET MORT_READ FALSE

$IFTHEN.DAM_OFF "%DAMAGE_OFF%" == "FALSE"
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "FALSE"
$SET MORT_READ TRUE
$ENDIF.SNGL_DAM
$ENDIF.DAM_OFF
$IFTHEN.SNGL_DAM "%SINGLE_DAMAGE%" == "TRUE"
$IFTHEN.SDAM_TYP "%SDAMAGE_TYPE%" == "MORTALITY"
$SET MORT_READ TRUE
$ENDIF.SDAM_TYP
$ENDIF.SNGL_DAM

$IFTHEN.FORCE_MORT "%RUN_MORTALITY%" == "TRUE"
$SET MORT_READ TRUE
$ENDIF.FORCE_MORT

$IFTHEN.READ_MORT "%MORT_READ%" == "TRUE"

$GDXIN 'impacts%slash%%threadID%_health_mortage_0_0_%isuffix%.gdx'
$load health_mortage_0_0_raw=health_mortage_0_0_%isuffix%

$GDXIN 'impacts%slash%%threadID%_health_mortage_1_44_%isuffix%.gdx'
$load health_mortage_1_44_raw=health_mortage_1_44_%isuffix%

$GDXIN 'impacts%slash%%threadID%_health_mortage_45_64_%isuffix%.gdx'
$load health_mortage_45_64_raw=health_mortage_45_64_%isuffix%

$GDXIN 'impacts%slash%%threadID%_health_mortage_65_inf_%isuffix%.gdx'
$load health_mortage_65_inf_raw=health_mortage_65_inf_%isuffix%


$IFTHEN.LABREG "%AG_REG%" == "ANSI"
health_mortage_0_0(ir,tp) = sum(ansi$map_ansi(ir,ansi),health_mortage_0_0_raw(ansi,tp));
health_mortage_1_44(ir,tp) = sum(ansi$map_ansi(ir,ansi),health_mortage_1_44_raw(ansi,tp));
health_mortage_45_64(ir,tp) = sum(ansi$map_ansi(ir,ansi),health_mortage_45_64_raw(ansi,tp));
health_mortage_65_inf(ir,tp) = sum(ansi$map_ansi(ir,ansi),health_mortage_65_inf_raw(ansi,tp));
$ENDIF.LABREG
$IFTHEN.LABREG "%AG_REG%" == "ir"
health_mortage_0_0(ir,tp) = health_mortage_0_0_raw(ir,tp);
health_mortage_1_44(ir,tp) = health_mortage_1_44_raw(ir,tp);
health_mortage_45_64(ir,tp) = health_mortage_45_64_raw(ir,tp);
health_mortage_65_inf(ir,tp) = health_mortage_65_inf_raw(ir,tp);
$ENDIF.LABREG


popimpact(tp,r,'0_0') = sum(ir$mapir(r,ir),health_mortage_0_0(ir,tp)*totalpop(ir)) / sum(ir$mapir(r,ir),totalpop(ir));
popimpact(tp,r,'1_44') = sum(ir$mapir(r,ir),health_mortage_1_44(ir,tp)*totalpop(ir)) / sum(ir$mapir(r,ir),totalpop(ir));
popimpact(tp,r,'45_64') = sum(ir$mapir(r,ir),health_mortage_45_64(ir,tp)*totalpop(ir)) / sum(ir$mapir(r,ir),totalpop(ir));
popimpact(tp,r,'65_inf') = sum(ir$mapir(r,ir),health_mortage_65_inf(ir,tp)*totalpop(ir)) / sum(ir$mapir(r,ir),totalpop(ir));

$ELSE.READ_MORT

popimpact(tp,r,ageCohorts) = 0;

$ENDIF.READ_MORT

* Set impact in 2100 to 0 to control cross-climate-model differences and prevent model failure
popimpact('2100',r,ageCohorts) = 0;


set  agelast(age)   Last age group,
     agefirst(age)  First age group;


agelast(age)   = yes$(ord(age) eq card(age));
agefirst(age)  = yes$(ord(age) eq 1);


set maternal(age) /a20*a45/;

set map_cohort_to_age(ageCohorts,age) /
  0_0.(a00),
  1_44.(a01*a44),
  45_64.(a45*a64),
  65_inf.(a65*a85)
/;



parameter basePopByAge (tp,r,age)     "Baseline population projection by region and single year of age (persons)"; 

basePopByAge(tp,r,age) = RegPopByAge(r,age); 


loop (tp, 
    
      if((not tfirst(tp)),
           basePopByAge(tp,r, age) = basePopByAge(tp-1,r, age) * popGrowth(tp);
        );
   );


parameter addlDeaths(tp,r,age)        "Additional mortality in period tp attributable to temperature change (may be negative) (persons)",
          updatedPop(tp,r,age)        "Population projection, which equals baseline projection - additional mortality from climate (persons)",
          totalMortality(tp,r,age)    "Running tally of additional deaths, including new mortality and the previous period's mortality aged by 1 year (persons)";

addlDeaths(tp,r,age) = 0; 
totalMortality(tp,r,age) = 0;
updatedPop(tp,r,age) = RegPopByAge(r,age);

loop(tp,
*    age total mortality by 1 year
  totalMortality(tp,r,age)$(ageYears(age)>0) = totalMortality(tp-1,r,age-1);
  totalMortality(tp,r,age)$(ageYears(age)=0) = 0;
*    additional deaths are current population (base projection - mortality) times change in heat-related mortality per person
  addlDeaths(tp,r,age) = (basePopByAge(tp,r,age) - totalMortality(tp,r,age)) * sum(ageCohorts$map_cohort_to_age(ageCohorts,age),popimpact(tp,r,ageCohorts));
*    total mortality is updated by new deaths
  totalMortality(tp,r,age) = totalMortality(tp,r,age) + addlDeaths(tp,r,age);
  totalMortality(tp,r,age)$nodamage(r) = 0;
*    total population (used in model) is updated by that period's total mortality
  updatedPop(tp,r,age) = basePopByAge(tp,r,age) - totalMortality(tp,r,age);
)

*    Note that in this formulation the population of 85+ year-olds will not be reliable.
*    However this has no impact on the results which treat mortality as an impact on labor supply.


*   The temperature-related % change in the labor force equals the temperature-related % change in the 15-64 year-old population
set workAge(age) /a15*a64/;

parameter updatedPopGrowth(tp,r);
updatedPopGrowth(tp,r) = 0;

*   Calculate mortality-adjusted population growth rate to apply to labor supply
updatedPopGrowth(tp,r)$(year(tp)>2011) = sum(age$workAge(age),updatedPop(tp,r,age))/sum(age$workAge(age),updatedPop(tp-1,r,age));

execute_unload 'results%slash%deaths_%runID%.gdx' basePopByAge, addlDeaths, totalMortality, updatedPop; 
