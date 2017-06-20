$IF NOT SET aggr          $SET aggr           50states

* Load indexing sets from trade-balanced data file:

SET f(*)    "Factors",
    t(*)    "Accounts",
    i(*)    "Institutions",
    g(*)    "Goods and sectors",
    r(*)    "Aggregate regions",
    j(*)    "Aggregated SAM accounts";
$GDXIN '%aggr%_dtrdbal.gdx'
$load f t i j g r

SET h(i)    "Households",
  pub(i)    "Public entities",
  corp(i)   "Corporate entities";
$load h pub corp

SET labtype(*) "Labor risk classification";
$load labtype

SET plant(*)   "impact crops to be weighted by area planted";
$load plant

set age(*)    "single years of age used in the population model";
$load age
parameter ageYears(age) "value of single years of age";
$load ageYears

set ir(*)                   "Impact data regions",
    mapir(r,ir)             "mapping of impact regions to CGE model regions",
    ANSI(*)                 "State codes in the ANSI dataset",
    map_ansi(ir,ansi)       "Mapping from ANSI regions to impact regions (states)";
$load ir mapir ansi map_ansi

SET cr "Census Regions";
$load cr

set NODAMAGE(r)  "Regions with impacts held to zero";
$load NODAMAGE

ALIAS (s,g,ss,gg) , (h,hh) , (i,ii) , (r,rr) , (f,ff);

SET mkt /dmkt,ftrd,dtrd/,
  trd(mkt)/ftrd,dtrd/;

set crops /OSD, GRN, COT/;


* Load parameters from trade-balanced data file:

PARAMETER
  OutputTot0(r,s)           "Reference output (domestic and exports) of good s (2011 US$M)",
  IndExpTot0(r,s)           "Reference output to the domestic market (2011 US$M)",
  OutputExp0(r,s,trd)       "Reference output to export markets (2011 US$M)",
  IndDemDom0(r,g,s)         "Reference industrial intermediate demand - domestic (2011 US$M)",
  IndDemImp0(r,g,trd,s)     "Reference industrial intermediate demand - imported (2011 US$M)",
  FacDemDom0(r,f,s)         "Reference industrial factor demand - domestic (2011 US$M)",
  IndIntExp0(r,s,trd)       "Reference industrial and institutional exports (2011 US$M)",
  IndExpTot0(r,s)           "Reference total exports by industry (2011 US$M)",
  ImpGdsTot0(r,g,trd)       "Reference total imports by good and market (2011 US$M)",
  HhdDemTot0(r,h)           "Reference demand by household type - total (2011 US$M)",
  HhdDemDom0(r,g,h)         "Reference demand by household type - domestic (2011 US$M)",
  HhdDemImp0(r,g,trd,h)     "Reference demand by household type - imported (2011 US$M)",
  InvDemTot0(r)             "Reference investment demand - total (2011 US$M)",
  InvDemDom0(r,g)           "Reference investment demand by good - domestic (2011 US$M)",
  InvDemImp0(r,g,trd)       "Reference investment demand by good - imported (2011 US$M)",
  PubDemTot0(r,pub)         "Reference public sector demand - total (2011 US$M)",
  PubDemDom0(r,g,pub)       "Reference public sector demand by good - domestic (2011 US$M)",
  PubDemImp0(r,g,trd,pub)   "Reference public sector demand by good - imported (2011 US$M)",
  IntFacSup0(r,f,i,t)       "Reference institutional factor supply (2011 US$M)",
  IntGdsSup0(r,g,i)         "Reference institutional goods supply (make and export) (2011 US$M)",
  CorpProft0(r,i)           "Reference corporate profits by institution (2011 US$M)",
  Transfers0(r,i,t)         "Reference transfers by source institution (2011 US$M)",
  DomOutTot0(r,s)           "Reference domestic industrial and institutional output (2011 US$M)",
  trnsfer(r,i,t,ii)         "Reference inter-institutional transfers (2011 US$M)",
  cropshares(r,crops)       "Shares of real total crop production value held by each crop in 2012 by region",
  areaPlanted_IR(ir,plant)  "Base-year area planted by crop type by impact region (2012)",
  impctCropAgShr(r)         "Shares of total real agricultural production from impacted crops in 2012 by region",
  laborAtRisk(ir,labtype)   "Value of labor by impact region and labor risk category",
  grainCaloricOutput_IR(ir)  "Base-year caloric output of grain crops by impacted region",
  censusPop(r,cr)           "Population in each IMPLAN region living within each census region in 2010";

* Read benchmark data:

$load OutputTot0 IndExpTot0 OutputExp0 IndDemDom0 IndDemImp0 FacDemDom0 IndIntExp0 ImpGdsTot0 HhdDemTot0 
$load HhdDemDom0 HhdDemImp0 InvDemTot0 InvDemDom0 InvDemImp0 PubDemTot0 PubDemDom0 PubDemImp0 IntFacSup0
$load IntGdsSup0 CorpProft0 Transfers0 DomOutTot0 cropshares impctCropAgShr trnsfer laborAtRisk areaPlanted_IR
$load censusPop grainCaloricOutput_IR

PARAMETER RegPopByAge(r,age)      "Base-year population by single year of age by region (2010, persons)",
          RegPopByAge_IR(ir,age)  "Base-year population by single year of age by impact region (2010, persons)";
$load RegPopByAge RegPopByAge_IR

* ==================================================================================================

PARAMETER
        IndDemTot0(r,g,s)     "Total intermediate demand",
        FacEndInt0(r,i,f)     "Factor endowment by institution",
        ArmAggGds0(r,s)       "Armington supply including imports",
        DomTrdGds0(g)         "Intra-national trade",
        InvDemCom0(r,g)       "Investment demand by commodity",
        InvDemHhd0(r,h)       "Investment demand by household",
        incadj(r,h)           "Base year net transfer";

$load  IndDemTot0 FacEndInt0 ArmAggGds0 DomTrdGds0 InvDemCom0 InvDemHhd0 incadj

* =================================================================================================
SET       coastReg(*)                       "Regions affected by coastal damages";
$load coastReg
PARAMETER CoastCapShr(coastReg)   "Share of total CGE regional capital in each coastal impact region",
          CoastOutShr(coastReg)   "Share of total CGE regional output in each coastal impact region",
          physExposure(coastReg) "RMS Physical exposure by coastal region",
          busIExposure(coastReg) "RMS Business interruption exposure by coastal region";
$load CoastCapShr CoastOutShr physExposure busIExposure
set mapcoast(r,coastReg) "Mapping set for regional aggregation";
$load mapcoast

* ==================================================================================================

PARAMETER
  DemTotReg0(r)             "Reference total consumer demand by region (2011 US$M)",
  DemGdsReg0(r,g)           "Reference consumer goods demand by region (2011 US$M)",
  PubDemSec0(r,s,pub)       "Reference public sector demand by sector (2011 US$M)",
  BalOfPymt0(r)             "Reference balance of foreign payments deficit by region (2011 US$M)";

DemTotReg0(r)       = sum(h,HhdDemTot0(r,h));
DemGdsReg0(r,g)     = sum(h, HhdDemDom0(r,g,h) + sum(trd, HhdDemImp0(r,g,trd,h)));
IndDemTot0(r,g,s)   = IndDemDom0(r,g,s) + sum(trd, IndDemImp0(r,g,trd,s));
ArmAggGds0(r,s)     = sum(trd,ImpGdsTot0(r,s,trd)) + DomOutTot0(r,s);
PubDemSec0(r,s,pub) = PubDemDom0(r,s,pub) + sum(trd,PubDemImp0(r,s,trd,pub));
BalOfPymt0(r)       = sum(s,ImpGdsTot0(r,s,"ftrd")) - sum(s,IndIntExp0(r,s,"ftrd")) - sum(pub,PubDemTot0(r,pub));
