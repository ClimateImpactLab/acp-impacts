## Load the variation data
tbl <- read.csv("../bars/data/uncstds.csv")

tbl$name <- paste(tbl$sector, tbl$outcome, sep='-')
tbl$varsum <- tbl$model_SD^2 + tbl$weather_SD^2 + tbl$stat_SD^2

library(ggplot2)

## Create a big table of all the data
gtbl <- data.frame(sector=c(), outcome=c(), scenario=c(), year=c(), ymin=c(), ymax=c(), variable=c(), yint=c())
for (scenario in unique(tbl$scenario)) {
    for (name in unique(tbl$name)) {
        sector <- tbl$sector[tbl$name == name][1]
        outcome <- tbl$outcome[tbl$name == name][1]
        ## Baseline values in 2010
        gtbl <- rbind(gtbl, data.frame(sector=sector, outcome=outcome, scenario=scenario, year=rep(2010, 3), group="variance",
                                       ymin=c(0, 0, 0),
                                       ymax=c(0, 0, 0),
                                       variable=c("model_SD", "weather_SD", "stat_SD"), yint=0))

        ## Uncertainty values in the future
        for (year in c(2020, 2040, 2080)) {
            stbl <- tbl[tbl$name == name & tbl$year == year & tbl$scenario == scenario,]
            gtbl <- rbind(gtbl, data.frame(sector=sector, outcome=outcome, scenario=scenario, year=rep(year, 3), group="fraction",
                                           ymin=c(0, stbl$model_SD^2 / stbl$varsum, (stbl$model_SD^2 + stbl$weather_SD^2) / stbl$varsum),
                                           ymax=c(stbl$model_SD^2 / stbl$varsum, (stbl$model_SD^2 + stbl$weather_SD^2) / stbl$varsum,
                                                  1),
                                           variable=c("model_SD", "weather_SD", "stat_SD"), yint=stbl$all_SD^2 / stbl$varsum))
            gtbl <- rbind(gtbl, data.frame(sector=sector, outcome=outcome, scenario=scenario, year=rep(year, 3), group="variance",
                                           ymin=c(0, stbl$model_SD^2, stbl$model_SD^2 + stbl$weather_SD^2),
                                           ymax=c(stbl$model_SD^2, stbl$model_SD^2 + stbl$weather_SD^2, stbl$varsum),
                                           variable=c("model_SD", "weather_SD", "stat_SD"), yint=stbl$all_SD^2))
    }
  }
}

## Titles for all of the results
gtbl$title <- NA
gtbl$title[gtbl$sector == 'labor' & gtbl$outcome == 'lowproductivity'] <- "Low-risk labor productivity"
gtbl$title[gtbl$sector == 'labor' & gtbl$outcome == 'highproductivity'] <- "High-risk labor productivity"
gtbl$title[gtbl$sector == 'health' & gtbl$outcome == 'mortage0to0'] <- "Mortality, ages <1"
gtbl$title[gtbl$sector == 'health' & gtbl$outcome == 'mortage1to44'] <- "Mortality, ages 1-44"
gtbl$title[gtbl$sector == 'health' & gtbl$outcome == 'mortage45to64'] <- "Mortality, ages 45-64"
gtbl$title[gtbl$sector == 'health' & gtbl$outcome == 'mortage65toinf'] <- "Mortality, ages >64"
gtbl$title[gtbl$sector == 'health' & gtbl$outcome == 'mortality'] <- "Mortality, all ages"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'cotton'] <- "Cotton yields"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'cottonnoco2'] <- "Cotton yields, without CO2 fertilization"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'maize'] <- "Maize yields"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'maizenoco2'] <- "Maize yields, without CO2 fertilization"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'oilcrop'] <- "Soybean yields"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'oilcropnoco2'] <- "Soybean yields, without CO2 fertilization"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'wheat'] <- "Wheat yields"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'wheatnoco2'] <- "Wheat yields, without CO2 fertilization"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'grains'] <- "Combined grains (by calorie)"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'grainsnoco2'] <- "Combined grains (by calorie), without CO2 fertilization"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'total'] <- "Combined yields (by area)"
gtbl$title[gtbl$sector == 'yields' & gtbl$outcome == 'totalnoco2'] <- "Combined yields (by area), without CO2 fertilization"
gtbl$title[gtbl$sector == 'crime' & gtbl$outcome == 'property'] <- "Property crime"
gtbl$title[gtbl$sector == 'crime' & gtbl$outcome == 'violent'] <- "Violent crime"


library(scales)
library(grid)

## Create a plot for each sector and outcome
for (do.sector in unique(gtbl$sector)) {
    for (do.outcome in unique(gtbl$outcome[gtbl$sector == do.sector])) {
        ## Create the ggplot object
        ggplot(subset(gtbl, sector == do.sector & outcome == do.outcome & scenario == "rcp85" & variable != "all_SD" & group == 'fraction'),
           aes(x=year+10, ymin=ymin, ymax=ymax, fill=variable)) +
            geom_ribbon() +
            geom_line(aes(y=yint), col="#bedcc3", cex=2) +
            geom_hline(yintercept=1)+
            ylab("Attributed Variance") + xlab("Year") +
            theme_bw() +
            theme(legend.position="top") + ggtitle(paste("Variance Decomposition:", gtbl$title[gtbl$sector == do.sector & gtbl$outcome == do.outcome][1])) +
                     scale_fill_manual(name="Source of Variance: ",
                                       breaks=c("model_SD", "weather_SD", "stat_SD"),
                                       labels=c("climate", "weather", "dose-response"),
                                       values=c("#aad8e4", "#c50035", "#ff7d2d")) +
                                           scale_x_continuous(expand=c(0, 0)) + scale_y_continuous(expand=c(0, 0))

        # Save it
        ggsave(paste0("overtime/", do.sector, '-', do.outcome, ".pdf"))
    }
}
