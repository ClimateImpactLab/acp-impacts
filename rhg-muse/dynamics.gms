

parameter product   "Model output regional and sectoral output",
          rproduct  "Model output regional and sectoral output - real",
          grp       "Model output gross regional product",
          gdp       "Model output GDP",
          rgrp      "Model output gross regional product",
          rgdp      "Model output GDP",
          cons      "Model output agent consumption",
          rcons     "Model output real agent consumption",
          use       "Model output sector use",
          ruse      "Model output real sector use",
          cap       "Model output capital stock",
          rcap      "Model output real capital stock",
          capr      "Model output regional capital stock",
          rcapr     "Model output regional real capital stock",
          p_a       "Armington good price",
          lab       "Model labor supply";



* test damage year functionality with put
file yearfile/"listings/yearfile.log"/;


* =========================================================

* Loop over all time periods
loop(tp,

  ! Solve model for this time period

$include muse_core.GEN
  solve muse_core using MCP;
   


  put yearfile;
  put '~~~~~~~~~~~~~~~~~~' /;
  put 'TIME PERIOD: ', tp.tl /;
  put 'DAMAGE YEAR: %DAMAGE_YEAR%' /;
  put 'EQUALITY: ', (year(tp) = year("%DAMAGE_YEAR%")) /;
  put 'LABOR: ', sum(r, labor(r)) /;
  ! putclose;


  ! Set value of report parameters
  ! -------------------------------------------------------------------------------------------------
  
  product(tp,r,s)       = (pyYX.l(r,s)*py.l(r,s)) + (pnYX.l(r,s)*pn.l(s)) 
                        + (pfxYX.l(r,s)*pfx.L) + (pyY.l(r,s)*py.l(r,s))
                        + (pnY.l(r,s)*pn.l(s)) + (pfxY.l(r,s)*pfx.L);

  rproduct(tp,r,s)      = pyYX.l(r,s) + pnYX.l(r,s) + pfxYX.l(r,s) + 
                          pyY.l(r,s)  + pnY.l(r,s)  + pfxY.l(r,s);


  grp(tp,r)             = I_R.l(r) * sum(s,PA.L(r,s)*thetaRSAV(r,s))
                        + raConsum.l(r) * PC.l(r)
                        + raGov.l(r) * PGOV.l(r)
                        + sum(s,(yPN.l(r,s)+yxPN.l(r,s)-aPN.l(r,s))*PN.l(s))
                        + sum(s,(yPFX.l(r,s)+yxPFX.l(r,s)-aPFX.l(r,s))*PFX.l);

  gdp(tp)               = sum(r,grp(tp,r)); 
  
                        ! savings  + consumption  + government + exports - imports
  rgrp(tp,r)            = I_R.l(r) + raConsum.l(r)+raGov.l(r)+ sum(s,(yPN.l(r,s)+yxPN.l(r,s)-aPN.l(r,s))) 
                           + sum(s,(yPFX.l(r,s)+yxPFX.l(r,s)-aPFX.l(r,s)));
           
  rgdp(tp)              = sum(r,rgrp(tp,r));

  cons(tp,r,g)          = raGdCns.l(r,g);
  rcons(tp,r,g)         = raGdCns.l(r,g)*PA.l(r,g);

  use(tp,r,g)           = sum(s,paY.l(r,s,g)+paYX.l(r,s,g));
  ruse(tp,r,g)          = sum(s,paY.l(r,s,g)+paYX.l(r,s,g))*PA.l(r,g);

  capr(tp, r)           = sum(s,(KX_Use.L(r,s)*RKX.L(r,s) + KN_Use.L(r,s)*RK.L(r)));
  rcapr(tp, r)          = sum(s,(KX_Use.L(r,s) + KN_Use.L(r,s)));

  cap(tp)               = sum(r,capr(tp,r));
  rcap(tp)              = sum(r,rcapr(tp,r));

  p_a(tp,r,s)           = pa.l(r,s);

  lab(tp)               = sum(r, labor(r));


  ! Capital damages 
  ! no damage = 0, damage > 0
  ! -------------------------------------------------------------------------------------------------
  dam_cap_val(r,s) = 0;

  if (((year("%DAMAGE_YEAR%")=0) or (year("%DAMAGE_YEAR%")=year(tp)+1)),
    if((shock_capital_flag and damage_run_flag), ! test flag - damage 20% of capital in 2020
      if((year(tp)=2020),
        dam_cap_val(r,s)$(not NODAMAGE(r)) = (1-depr)*(KX_Use.L(r,s)+KN_Use.L(r,s))*(0.8);
      );
    
    elseif (damage_capital_flag and damage_run_flag),
      if((year(tp)>2010),
        dam_cap_val(r,s)$(not NODAMAGE(r)) = (1-depr)*(KX_Use.L(r,s)+KN_Use.L(r,s))*(shrInundDamage(r,tp+1)+shrDirectDamage(r,tp+1));
      );
    );
  );

  ! Labor endowment grows using population growth rate
  ! Modified growth rates determined in initialYearDefs - no growth = 1, no damage = popGrowth, damage < popGrowth
  ! -------------------------------------------------------------------------------------------------

  if(((shock_mort_flag and (year(tp)=2020) and damage_run_flag)), ! test flag - reduce 20% of labor supply in 2020
    labor(r)  = labor(r) * popGrowth(tp+1)*0.8;

  elseif ((damage_mort_flag and damage_run_flag) and ((year("%DAMAGE_YEAR%")=0) or (year("%DAMAGE_YEAR%")=year(tp)+1))),
    labor(r)  = labor(r) * updatedPopGrowth(tp+1,r);

  else
    labor(r)  = labor(r) * popGrowth(tp+1);
  );
    

  ! Update the reference quantities of labor and capital used in extant production
  ! -------------------------------------------------------------------------------------------------
  lx_refUse(r,s)$lx_refUse(r,s) = (lx_refUse(r,s)*YX.L(r,s) + gammaL(r,s)*labHeatImpct(r,s)*LN_Use.L(r,s))/(YX.L(r,s)+Y.L(r,s));
  kx_refUse(r,s)$kx_refUse(r,s) = (kx_refUse(r,s)*YX.L(r,s) + KN_Use.L(r,s))/(YX.L(r,s)+Y.L(r,s));


  ! Update the share of extant capital going to each region and sector
  ! -------------------------------------------------------------------------------------------------  
  kx(r,s) = (1-depr)*(KX_Use.L(r,s) + KN_Use.L(r,s)) - dam_cap_val(r,s);
  kxt = sum((r,s),kx(r,s));

  ! Update the extant capital stock endowment by region
  ! Storms reduce regional capital returns endowments by share of regional ownership
  ! -------------------------------------------------------------------------------------------------
  kexch(r) = (1-depr)*(kexch(r) + THETAS.L(r)*sum((rr,s), KN_Use.L(rr,s)))
     - kexch(r)/sum(rr,kexch(rr)) * sum((rr,s),dam_cap_val(rr,s));


  ! baseline labor productivity growth
  ! -------------------------------------------------------------------------------------------------
  gammaL(r,s) = gammaL(r,s) * baseLabProd;


  ! Heat-related labor productivity change
  ! no damage = 1, damage < 1
  ! -------------------------------------------------------------------------------------------------
  labHeatImpct(r,s) =1.0;

  if (((year("%DAMAGE_YEAR%")=0) or (year("%DAMAGE_YEAR%")=year(tp)+1)),
    if((shock_labprod_flag and damage_run_flag), ! test flag - reduce labor productivity by 20% in 2020
      if((year(tp)=2020),  
        labHeatImpct(r,s)$(lowlaborRisk(s) and (not NODAMAGE(r))) = 0.8;
        labHeatImpct(r,s)$(highlaborRisk(s) and (not NODAMAGE(r))) = 0.8;
      );

    elseif (damage_labprod_flag and damage_run_flag),
      if((year(tp)>2010),  
        labHeatImpct(r,s)$(lowlaborRisk(s) and (not NODAMAGE(r))) = labProdChange(tp+1,r,"lowR");
        labHeatImpct(r,s)$(highlaborRisk(s) and (not NODAMAGE(r))) = labProdChange(tp+1,r,"highR");
      );
    );
  );


  ! Output productivity factor (from coastal business interruption and agriculture impacts
  ! no damage = 1, damage < 1
  ! -------------------------------------------------------------------------------------------------
  outdam(r,s) =1.0;

  if (((year("%DAMAGE_YEAR%")=0) or (year("%DAMAGE_YEAR%")=year(tp)+1)),
    if((shock_outprod_flag and damage_run_flag), ! test flag - BI impact = 10% across the board, 30% for AG with productivity damage
      if((year(tp)=2020),
        outdam(r,s)$(not NODAMAGE(r)) = (0.9);
        outdam(r,"AGR")$(not NODAMAGE(r)) = (0.7);
      );

    elseif (damage_outprod_flag and damage_run_flag),
      if((year(tp)>2010),
        outdam(r,s)$(not NODAMAGE(r)) = (1-shrBusInterrupt(r,tp+1));
        outdam(r,"AGR")$(not NODAMAGE(r)) = (1-shrBusInterrupt(r,tp+1))
            * (1.00 - (sum(crops, cropshares(r,crops)*(1-yieldFactor(tp+1,r,crops))))*impctCropAgShr(r));
      );
    );
  );


  ! Change in energy demand from changes in heating and cooling requirements (modeled in NEMS)
  ! No damage = 0, damage > 0
  ! -------------------------------------------------------------------------------------------------

  encdam(r,g,s) = 0;
  enrdam(r,s) = 0;

  if (((year("%DAMAGE_YEAR%")=0) or (year("%DAMAGE_YEAR%")=year(tp)+1)),
    if((shock_energy_flag and damage_run_flag), ! test flag - Increase in energy demand = 20% (residential & commercial)
      if((year(tp)=2020),

        encdam(r,"ENR","indoorServ")$(not NODAMAGE(r)) = 0.2;
        enrdam(r,"ENR")$(not NODAMAGE(r))              = 0.2;
      );

    elseif (damage_energy_flag and damage_run_flag),
      if((year(tp)>2010),

        !   Apply COMMERCIAL energy damages impacts to the indoor services energy demand
        encdam(r,"ENR","indoorServ")$(not NODAMAGE(r)) = comEnerExpChange(tp+1,r);

        !   Apply RESIDENTIAL energy demand impacts to the household energy demand
        enrdam(r,"ENR")$(not NODAMAGE(r))              = resEnerExpChange(tp+1,r);

      );
    );
  );
  
);


putclose;

$SET DAMAGE_SUFFIX 
$SET YEAR_SUFFIX 
$IF "%SINGLE_DAMAGE%"=="FALSE" $SET DAMAGE_SUFFIX _ALL
$IFE (%DAMAGE_YEAR%>0) $SET YEAR_SUFFIX _y%DAMAGE_YEAR%
execute_unload 'results%slash%%runID%%DAMAGE_SUFFIX%%YEAR_SUFFIX%.gdx' product,grp,gdp,rproduct,
  rgrp,rgdp,cons,rcons,use,ruse,p_a,nodamage,cap,rcap,capr,rcapr, shrInundDamage, shrBusInterrupt, 
  shrDirectDamage,lab;