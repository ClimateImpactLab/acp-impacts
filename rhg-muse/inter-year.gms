

$IF NOT SET TP $ABORT "TP must be set in delta run"
$EVAL NEXT_TP (%TP% + 1)

* =========================================================

! Solve model for this time period

$include muse_core.GEN
solve muse_core using MCP;
 


! Set value of report parameters
! -------------------------------------------------------------------------------------------------

product("%TP%",r,s)       = (pyYX.l(r,s)*py.l(r,s)) + (pnYX.l(r,s)*pn.l(s)) 
                      + (pfxYX.l(r,s)*pfx.L) + (pyY.l(r,s)*py.l(r,s))
                      + (pnY.l(r,s)*pn.l(s)) + (pfxY.l(r,s)*pfx.L);

rproduct("%TP%",r,s)      = pyYX.l(r,s) + pnYX.l(r,s) + pfxYX.l(r,s) + 
                        pyY.l(r,s)  + pnY.l(r,s)  + pfxY.l(r,s);


grp("%TP%",r)             = I_R.l(r) * sum(s,PA.L(r,s)*thetaRSAV(r,s))
                      + raConsum.l(r) * PC.l(r)
                      + raGov.l(r) * PGOV.l(r)
                      + sum(s,(yPN.l(r,s)+yxPN.l(r,s)-aPN.l(r,s))*PN.l(s))
                      + sum(s,(yPFX.l(r,s)+yxPFX.l(r,s)-aPFX.l(r,s))*PFX.l);

gdp("%TP%")               = sum(r,grp("%TP%",r)); 

                      ! savings  + consumption  + government + exports - imports
rgrp("%TP%",r)            = I_R.l(r) + raConsum.l(r)+raGov.l(r)+ sum(s,(yPN.l(r,s)+yxPN.l(r,s)-aPN.l(r,s))) 
                         + sum(s,(yPFX.l(r,s)+yxPFX.l(r,s)-aPFX.l(r,s)));
         
rgdp("%TP%")              = sum(r,rgrp("%TP%",r));

cons("%TP%",r,g)          = raGdCns.l(r,g);
rcons("%TP%",r,g)         = raGdCns.l(r,g)*PA.l(r,g);

use("%TP%",r,g)           = sum(s,paY.l(r,s,g)+paYX.l(r,s,g));
ruse("%TP%",r,g)          = sum(s,paY.l(r,s,g)+paYX.l(r,s,g))*PA.l(r,g);

cap("%TP%", r)            = sum(s,(KX_Use.L(r,s)*RKX.L(r,s) + KN_Use.L(r,s)*RK.L(r)));
rcap("%TP%", r)           = sum(s,(KX_Use.L(r,s) + KN_Use.L(r,s)));

p_a("%TP%",r,s)           = pa.l(r,s);



! Capital damages 
! -------------------------------------------------------------------------------------------------
dam_cap_val(r,s) = 0;

if((shock_capital_flag and damage_run_flag), ! test flag - damage 20% of capital in 2020
  if((year("%TP%")=2020),
    dam_cap_val(r,s) = (1-depr)*(KX_Use.L(r,s)+KN_Use.L(r,s))*(0.8);
    dam_cap_val(r,s)$NODAMAGE(r) = 0;
  );
);

if((damage_capital_flag and damage_run_flag),
  if((year("%TP%")>2010),
    dam_cap_val(r,s) = (1-depr)*(KX_Use.L(r,s)+KN_Use.L(r,s))*(shrInundDamage(r,"%NEXT_TP%")+shrDirectDamage(r,"%NEXT_TP%"));
    dam_cap_val(r,s)$NODAMAGE(r) = 0;
  );
);

! Labor endowment grows using population growth rate
! -------------------------------------------------------------------------------------------------

if((shock_mort_flag and (year("%TP%")=2020) and damage_run_flag), ! test flag - reduce 20% of labor supply in 2020
  labor(r)  = labor(r) * popGrowth("%NEXT_TP%")*0.8;
);

if((shock_mort_flag and (not year("%TP%")=2020) and damage_run_flag),
  labor(r)  = labor(r) * popGrowth("%NEXT_TP%");
);

if((damage_mort_flag and damage_run_flag),
  labor(r)  = labor(r) * updatedPopGrowth("%NEXT_TP%",r);
);

if(((not damage_mort_flag) and (not shock_mort_flag) and damage_run_flag),
  labor(r)  = labor(r) * popGrowth("%NEXT_TP%");
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


! baseline labor productivity
! -------------------------------------------------------------------------------------------------
gammaL(r,s) = gammaL(r,s) * baseLabProd;


! Heat-related labor productivity change
! -------------------------------------------------------------------------------------------------
labHeatImpct(r,s) =1.0;

if((shock_labprod_flag and damage_run_flag), ! test flag - reduce labor productivity by 20% in 2020
  if((year("%TP%")=2020),  
    labHeatImpct(r,s)$lowlaborRisk(s) = 0.8;
    labHeatImpct(r,s)$highlaborRisk(s) = 0.8;
    labHeatImpct(r,s)$NODAMAGE(r) = 1;
  );
);

if((damage_labprod_flag and damage_run_flag),
  if((year("%TP%")>2010),  
    labHeatImpct(r,s)$lowlaborRisk(s) = labProdChange("%NEXT_TP%",r,"lowR");
    labHeatImpct(r,s)$highlaborRisk(s) = labProdChange("%NEXT_TP%",r,"highR");
    labHeatImpct(r,s)$NODAMAGE(r) = 1;
  );
);


! Output productivity change (from coastal business interruption and agriculture impacts)
! -------------------------------------------------------------------------------------------------
outdam(r,s) =1.0;

if((shock_outprod_flag and damage_run_flag), ! test flag - BI impact = 10% across the board, 30% for AG with productivity damage
  if((year("%TP%")=2020),
    outdam(r,s) = (0.9);
    outdam(r,"AGR") = (0.7);
    outdam(r,s)$NODAMAGE(r) = 1.00;
  );
);

if((damage_outprod_flag and damage_run_flag),
  if((year("%TP%")>2010),
    outdam(r,s) = (1-shrBusInterrupt(r,"%NEXT_TP%"));
    outdam(r,"AGR") = (1-shrBusInterrupt(r,"%NEXT_TP%"))
        * (1.00 - (sum(crops, cropshares(r,crops)*(1-yieldFactor("%NEXT_TP%",r,crops))))*impctCropAgShr(r));
    outdam(r,s)$NODAMAGE(r) = 1.00;
  );
);


! Change in energy demand from changes in heating and cooling requirements (modeled in NEMS)
! -------------------------------------------------------------------------------------------------

if((shock_energy_flag and damage_run_flag), ! test flag - Increase in energy demand = 20% (residential & commercial)
  if((year("%TP%")=2020),

    encdam(r,"ENR","indoorServ") = 0.2;
    enrdam(r,"ENR")              = 0.2;
    encdam(r,g,s)$NODAMAGE(r) = 1;
    enrdam(r,s)$NODAMAGE(r) = 1;
  );
);

if((damage_energy_flag and damage_run_flag),
  if((year("%TP%")>2010),

  	!		Apply COMMERCIAL energy damages impacts to the indoor services energy demand
    encdam(r,"ENR","indoorServ") = comEnerExpChange("%NEXT_TP%",r);

    !		Apply RESIDENTIAL energy demand impacts to the household energy demand
    enrdam(r,"ENR")              = resEnerExpChange("%NEXT_TP%",r);

    !		Turn off energy damages for non-contiguous US regions
    encdam(r,g,s)$NODAMAGE(r) = 1;
    enrdam(r,s)$NODAMAGE(r) = 1;
  );
);
