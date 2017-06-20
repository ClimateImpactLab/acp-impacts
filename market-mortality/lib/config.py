import numpy as np, pandas as pd

#	Note on Time Ranges:
#	Defined here as slice bounds - thus, (1,45) represents ages 1 to 44, inclusive, 
# as slices are mathematically interpreted [lbound,ubound). These are converted 
#	into ranges of single ages using ConfigData.ages[slice(*age_range)].
#	This would convert the range definition (1,5) to the statement ConfigData.ages[1:5:1],
#	leading to the set of ages [1,2,3,4].


class ConfigData(object):
	
	#	All ages used in projecting 
	max_age = 86
	ages = range(max_age)

	#	Mortality cohorts used in impact functions
	mort_cohort_names = ['0-0','1-44','45-64','65-inf']
	mort_cohort_tuples = [(None,1),(1,45),(45,65),(65,None)]
	get_mort_cohort_name = {(None,1):'0-0',(1,45):'1-44',(45,65):'45-64',(65,None):'65-inf'}
	get_mort_cohort_tuple = {v:k for k,v in get_mort_cohort_name.items()}

	#	Scenario data
	rcps	=	['rcp26','rcp45','rcp60','rcp85']
	tps		=	['2020','2040','2080']

	#	Discount rates used in calculating mortality cost: 0% and 3%
	discount_rates = np.array([0,3],dtype='float64')/100

	#	Deflation data
	DEFLATOR_2012_TO_2011 = 0.982324529

	STATE_ABBREV_TO_ANSI = {
					'AL':  1, 'AK':  2, 'AZ':  4, 'AR':  5, 'CA':  6, 'CO':  8, 'CT':  9, 'DC': 11, 'DE': 10, 'FL': 12, 'GA': 13, 'HI': 15, 'ID': 16, 'IL': 17,
					'IN': 18, 'IA': 19, 'KS': 20, 'KY': 21, 'LA': 22, 'ME': 23, 'MD': 24, 'MA': 25, 'MI': 26, 'MN': 27, 'MS': 28, 'MO': 29, 'MT': 30, 'NE': 31,
					'NV': 32, 'NH': 33, 'NJ': 34, 'NM': 35, 'NY': 36, 'NC': 37, 'ND': 38, 'OH': 39, 'OK': 40, 'OR': 41, 'PA': 42, 'RI': 44, 'SC': 45, 'SD': 46,
					'TN': 47, 'TX': 48, 'UT': 49, 'VT': 50, 'VA': 51, 'WA': 53, 'WV': 54, 'WI': 55, 'WY': 56}

	STATE_ANSI_TO_ABBREV = {v:k for k,v in STATE_ABBREV_TO_ANSI.items()}


	@classmethod 
	def get_age_range_from_cohort(cls,cohort):
		return cls.ages[slice(*cohort)]

	@classmethod
	def get_mort_cohort_by_age(cls,age):
		if age < 0:
			raise ValueError('Ages must be positive integers, floats, or another data type that satisfies the comparison operation >= 0')
		for cohort in cls.mort_cohort_tuples:
			if age in cls.get_age_range_from_cohort(cohort):
				return cohort
		return None


