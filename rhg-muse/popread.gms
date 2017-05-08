$ONTEXT
  Population data reading and processing control file
  
  FILE:         popread.gms
  LANGUAGE:     GAMS
  CALLED BY:    modelControl.gms
  
  PURPOSE:      This file imports the UN population projection, 


$OFFTEXT

parameter usPopulation(*) "US Population read from USPOP.dat, data from UN Projections 2010-2100";

$GDXIN usPop.gdx
$load usPopulation

*	popGrowth is defined as pop(tp+1)/pop(tp) so that the growth rate may be multiplied by the current population
*	at the end of each loop of the recursive dynamic. 
parameter popGrowth(tp)		US Population growth from current year to next year;

loop(tp$(not (ord(tp) eq card(tp))),
	popGrowth(tp) = usPopulation(tp+1)/usPopulation(tp);
);




