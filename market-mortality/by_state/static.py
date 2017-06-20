import numpy as np, pandas as pd
import lib.data, lib.config, lib.national


class StaticData(object):

    #    ***** IMPORTANT *****

    # This class is a member of the by_state version of this module. As such, all
    # data are organized at a state level or higher. The outputs of this module
    # are consistent with the results presented in ACP 1.2. Note that these results
    # are not consistent with the results presented in the county clusters in the 
    # ACP Midwest and California reports. The discrepancy is due primarily to  
    # differences in impact aggregation but importantly also to differences in the
    # base data used. Specifically, cohort population data in this module uses
    # state-by-age population data, whereas county-by-cohort population data, which
    # is inconsistent with the state-by-age population data, is used in the 
    # by_county version of this module. Additionally, FTE and GDP data in this 
    # version are BEA estimates, whereas by_county uses IMPLAN data to distribute
    # the BEA estimates at the county level.

    national_data = lib.national.NationalData
    source_data = lib.data.SourceData
    config_data = lib.config.ConfigData

    # This class gathers the configuration data from data.py (in this module) and 
    # combines it to form all of the impact-independent parameters used in the
    # calculation of lost labor income mortality damages. Compare the state-level
    # data calculated on this sheet to values found on the 'Config' tab of the
    # excel version of this module.

    # Additional configuration parameters (simple data such as region definitions,
    # age ranges, and deflators) are included in config.py


    #########################################
    #        Public Instance Methods        #
    #########################################

    def __init__(self,deflator=None):

        if deflator is None:
            deflator = self.config_data.DEFLATOR_2012_TO_2011
        
        self.deflator = deflator
        
        self.set_national_config_data()
        self.set_state_config_data()
        self.deflate_config_data()

    def set_national_config_data(self):
        
        self.labor_participation = self.national_data._get_and_validate_labor_participation()

        #    Retrieve, validate, and set mortality_share_by_cohort
        mortality_share_by_cohort = self.national_data._get_mortality()
        self.source_data.validate_mortality_share_by_cohort(mortality_share_by_cohort)
        self.mortality_share_by_cohort = mortality_share_by_cohort
        
        #    Retrieve, validate, and set lost_participation_years
        lost_participation_years = self.national_data.get_lost_participation_years(self.labor_participation,self.mortality_share_by_cohort)
        self.source_data.validate_lost_labor_participation(lost_participation_years)
        self.lost_participation_years = lost_participation_years

    def set_state_config_data(self):

        #    Retrieve cohort and total state populations and validate against one another
        total_population = self.source_data.statePop
        cohort_population = self.source_data.cohort_population
        self.source_data.validate_population_data(total_population,cohort_population)
        self.total_population = total_population
        self.cohort_population = cohort_population

        self.value_per_fte = self._get_value_per_fte()

        #    Retrieve, validate, and set discounted_labor_lost and cohort_mortality_value, once for each discount rate
        self.discounted_labor_lost = {}
        self.cohort_mortality_value = {}

        for discount_rate in self.config_data.discount_rates:
            discounted_labor_lost, cohort_mortality_value = self._get_discounted_mort_value(discount_rate)
            self.source_data.validate_cohort_mortality_value(cohort_mortality_value,discount_rate)

            self.discounted_labor_lost[discount_rate] = discounted_labor_lost
            self.cohort_mortality_value[discount_rate] = cohort_mortality_value

    def deflate_config_data(self):
        self.value_per_fte = self.deflator * self.value_per_fte

        for discount_rate in self.config_data.discount_rates:
            self.cohort_mortality_value[discount_rate] = self.deflator * self.cohort_mortality_value[discount_rate]



    #########################################
    #       Private Instance Methods        #
    #########################################

    def _get_value_per_fte(self):
        return self.source_data.state_value_added['GDP'] * np.float64( 1e6 ) / self.source_data.state_fte_employment['employment']

    def _get_discounted_mort_value(self,discount_rate):

        #    Shift lost_participation_years by 1 year to take NPV assuming deaths occur at end of year
        shifted_lost_participation = self.lost_participation_years.copy()
        shifted_lost_participation.index = shifted_lost_participation.index + 1
        shifted_lost_participation = shifted_lost_participation.reindex(range(self.config_data.max_age+1),fill_value=0)

        #    Take the NPV of the time series of expected labor-force participation years lost given a death for each cohort
        discounted_labor_lost = pd.DataFrame([(cohort[0],np.npv(discount_rate,cohort[1])) for cohort in shifted_lost_participation.iteritems()])

        #    Clean up DataFrame
        discounted_labor_lost = discounted_labor_lost.set_index(0)
        discounted_labor_lost.indexname = ['cohort']

        #    Take the outer product to get the discounted value by state and cohort
        cohort_mortality_value = np.outer(self.value_per_fte, discounted_labor_lost)

        #    Convert back to DataFrame and clean up data
        cohort_mortality_value = pd.DataFrame(cohort_mortality_value, index=self.value_per_fte.index, columns=discounted_labor_lost.index)

        return discounted_labor_lost, cohort_mortality_value
