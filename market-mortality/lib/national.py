import numpy as np, pandas as pd
import data, config


class NationalData(object):

	config_data = config.ConfigData

	@staticmethod
	def _get_and_validate_labor_participation():
	
		labor_participation_tuples = []
		for rng in sorted(data.SourceData.LABOR_PARTICIPATION_DATA,key=lambda x: x[0]):
			labor_participation_tuples.extend([(a,data.SourceData.LABOR_PARTICIPATION_DATA[rng]) for a in config.ConfigData.get_age_range_from_cohort(rng)]) 

		#	Check data excel version
		data.SourceData.validate_labor_participation(labor_participation_tuples)

		#	Convert to pandas DataFrame
		return pd.DataFrame(labor_participation_tuples,columns=['age','rate']).set_index('age')


	@staticmethod
	def _get_mortality():
	#	Computes probability of death at each age given membership of each of the four impact data cohorts using US_MORTALITY_DATA, assuming a
	#	uniform distribution of mortality within each cohort.

		cohort_mortality_total = {}						#	Total mortality for each US_MORTALITY_DATA 5-year cohort
		cohort_mortality_share_tuples = []		#	List of tuples of age, [p(mortality|c) for c in cohorts], to be converted to a DataFrame


		#	CALCULATE TOTAL MORTALITY BY IMPACT COHORT (0-0, 1-44, 45-64, 65-inf)
		# ---------------------------------------------------------------------

		#	Loop through mortality cohort, cohort age range pairs, sorted by cohort list (in order of age)
		for cohort, rng in sorted(config.ConfigData.get_mort_cohort_tuple.items(), key = lambda x: config.ConfigData.mort_cohort_names.index(x[0])):

			#	Create a set that enumerates the ages within each cohort
			mort_set = set(config.ConfigData.get_age_range_from_cohort(rng))

			#	Calculate cohort mortality totals by adding all data.SourceData.US_MORTALITY_DATA for which the age range is within mort_set
			cohort_mortality_total[rng] = 0
			for us_data_cohort in sorted(data.SourceData.US_MORTALITY_DATA.keys(), key=lambda x: x[0]):	#	Sort by first year in each 5-year age cohort range
				if set(config.ConfigData.get_age_range_from_cohort(us_data_cohort)) <= mort_set:
					cohort_mortality_total[rng] += data.SourceData.US_MORTALITY_DATA[us_data_cohort]


		#	DIVIDE MORTALITY AT EACH SINGLE YEAR OF AGE BY TOTAL MORTALITY FOR IMPACT COHORT TO ARRIVE AT P(death at age|cohort)
		#	--------------------------------------------------------------------------------------------------------------------

		#	Calculate share of total cohort mortality occurring at each age
		for us_data_cohort in sorted(data.SourceData.US_MORTALITY_DATA.keys(), key=lambda x: x[0]):	#	Sort by first year in each 5-year age cohort range
			rng = config.ConfigData.get_mort_cohort_by_age(config.ConfigData.get_age_range_from_cohort(us_data_cohort)[0])
			cohort_ages = config.ConfigData.get_age_range_from_cohort(us_data_cohort)

			#	Probability of mortality at a specific age given a death within each cohort
			#	For example, p(death at 20 | death at 1-44) = p(death at 20-25) / (sum_(i=1-44) p(death at i)) / (5 years in range 20-25)
			mort_value = [np.float64(data.SourceData.US_MORTALITY_DATA[us_data_cohort])/cohort_mortality_total[rng]/len(cohort_ages) 
															if set(config.ConfigData.get_age_range_from_cohort(us_data_cohort)) <= set(config.ConfigData.get_age_range_from_cohort(rng)) else 0 
															for rng in config.ConfigData.mort_cohort_tuples]

			#	Build data frame structure out of tuples of age and probability of mortality in each cohort
			cohort_mortality_share_tuples.extend([tuple([a] + mort_value) for a in cohort_ages])


		#	CONVERT LIST cohort_mortality_share_tuples TO pandas.DataFrame
		# --------------------------------------------------------------

		#	Convert data to pandas.DataFrame, indexed by age and mort_cohort
		mortality_share_by_cohort = pd.DataFrame(cohort_mortality_share_tuples,columns=(['age'] + config.ConfigData.mort_cohort_names)).set_index('age')
		return mortality_share_by_cohort


	@classmethod
	def get_lost_participation_years(cls,labor_participation,mortality_share_by_cohort):

		#	Lost participation-years is the expected number of participation-years that would have been worked by a person at every year after death given a death in 
		#	each cohort, assuming they would live to 80, but accounting for actual labor-force participation rates at each year of agse
		lost_participation_years = []
		for years_since_death in labor_participation.index:
			
			#	Produce an 86x1 column vector identical to labor_participation but shifted by years_since_death
			lost_labor = labor_participation.reindex(range(years_since_death,years_since_death+cls.config_data.max_age),fill_value=0)
			lost_labor.index = range(cls.config_data.max_age)

			#	Matrix multiply mortality_share_by_cohort.T by lost_labor
			#	This results in a column vector of expected remaining working years given years_since_death
			expected_lost_labor = mortality_share_by_cohort.T.dot(lost_labor)

			#	Convert to row vector and remove vertical dimension (no actual summing involved)
			expected_lost_labor = expected_lost_labor.T.sum()

			lost_participation_years.append(tuple([years_since_death]+list(expected_lost_labor)))

		lost_participation_years = pd.DataFrame(lost_participation_years)
		lost_participation_years.columns = ['years_since_death'] + cls.config_data.mort_cohort_names
		lost_participation_years = lost_participation_years.set_index('years_since_death')
		return lost_participation_years