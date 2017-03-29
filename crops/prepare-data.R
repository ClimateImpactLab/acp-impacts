## Read in the dataset from Wolfram
library(foreign)
xx = read.dta("NASS_1950_2005_from_wolfram.dta")

## Extract the following columns
columns <- c("cornGrain_yieldPlanted", "soybeans_yieldPlanted", "cottonUpland_yieldPlanted", "wheatAll_yieldPlanted")

## Extract average yields by county
outputs <- c("maize-yield.csv", "soy-yield.csv", "cotton-yield.csv", "wheat-yield.csv")
# Convert all to MT
scaling <- c(56 * 0.453592 / 1000, 60 * 0.453592 / 1000, 1, 60 * 0.453592 / 1000) # from http://extension.missouri.edu/publications/DisplayPub.aspx?P=G4020

for (ii in 1:4) {
  print(columns[ii])
  yy <- data.frame(fips=c(), yield=c())
  for (fips in unique(xx$fips)) {
    print(fips)
    yy <- rbind(yy, data.frame(fips=c(fips), yield=c(mean(xx[xx$fips == fips & xx$year >= 2000 & xx$year <= 2005, columns[ii]], na.rm=T) * scaling[ii])))
  }

  write.csv(yy, file=paste("../iam/cropdata", outputs[ii], sep="/"), row.names=F)
}

# Same as above, but with a multiplication between column1 and column2
columns1 <- c("cornGrain_acres", "soybeans_acres", "cottonUpland_acres", "wheatAll_acres")
columns2 <- c("cornGrain_yieldPlanted", "soybeans_yieldPlanted", "cottonUpland_yieldPlanted", "wheatAll_yieldPlanted")
outputs <- c("maize-prod2.csv", "soy-prod2.csv", "cotton-prod2.csv", "wheat-prod2.csv")
# Convert all to MT
scaling <- c(56 * 0.453592 / 1000, 60 * 0.453592 / 1000, 1, 60 * 0.453592 / 1000) # from http://extension.missouri.edu/publications/DisplayPub.aspx?P=G4020

for (ii in 1:4) {
  print(columns1[ii])
  yy <- data.frame(fips=c(), yield=c())
  for (fips in unique(xx$fips)) {
    print(fips)
    yy <- rbind(yy, data.frame(fips=c(fips), yield=c(mean(xx[xx$fips == fips & xx$year >= 2000 & xx$year <= 2005, columns1[ii]] * xx[xx$fips == fips & xx$year >= 2000 & xx$year <= 2005, columns2[ii]], na.rm=T) * scaling[ii])))
  }

  write.csv(yy, file=paste("../iam/cropdata", outputs[ii], sep="/"), row.names=F)
}
