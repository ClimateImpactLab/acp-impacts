## Load th Ranson et al. replication dataset
library(foreign)
xx = read.dta("CCRsetup1a_CountyMonthDataset.dta")

## Merge values into violent and property crime
violent <- xx$murder + xx$rape + xx$assaultaggr + xx$assaultsimple
property <- xx$robbery + xx$burglary + xx$larceny + xx$vehicletheft

## Construct a unified dataset with crimes with average between 2000 and 2005
result <- data.frame(county=c(), violent=c(), property=c())
for (county in unique(xx$county)) {
  print(county)
  result <- rbind(result, data.frame(county, violent=mean(violent[xx$county == county & xx$year >= 2000 & xx$year <= 2005]), property=mean(property[xx$county == county & xx$year >= 2000 & xx$year <= 2005])))
}

## Projection code uses these baselines
write.csv(result, file="baseline.csv", row.names=F)

# Determine the average rate per person (for all other regions)
avgrate.violent <- mean(violent[xx$year >= 2000 & xx$year <= 2005] / xx$pop[xx$year >= 2000 & xx$year <= 2005])
# 0.0007995658
avgrate.property <- mean(property[xx$year >= 2000 & xx$year <= 2005] / xx$pop[xx$year >= 2000 & xx$year <= 2005])
# 0.00187557

# I use 2010 populations, so I want to scale down accordingly
# Want to calculate C = R * avgpop
# I'll calculate C = R' * 2010pop, so R' = R * avgpop / 2010pop
adjrate.violent <- avgrate.violent * mean(c(282.2, 285, 287.6, 290.1, 292.8, 295.5)) / 309.3
# 0.000746744
adjrate.property <- avgrate.property * mean(c(282.2, 285, 287.6, 290.1, 292.8, 295.5)) / 309.3
# 0.001751664

# Just get the 2000-2005 population
frm <- data.frame(fips=xx$county, pop=rep(NA, nrow(xx)))
for (ii in 1:nrow(xx))
  frm$pop[ii] <- mean(xx$pop[xx$year >= 2000 & xx$year <= 2005 & xx$county == frm$fips[ii]])

write.csv(frm, "pop2000-2005.csv")
