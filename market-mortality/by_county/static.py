import numpy as np, pandas as pd
import lib.data, lib.config, lib.national
from regions.regdefs import RegionDefinitions

class StaticData(object):

	#	***** IMPORTANT *****

	# This class is a member of the by_county version of this module. As such, all
	# data are organized at a county level or higher. The outputs of this module
	# are consistent with the results presented in the county clusters in the 
	# ACP Midwest and California reports. Note that these results are not consistent 
	# with the results presented in ACP 1.2. The discrepancy is due primarily to  
	# differences in impact aggregation but importantly also to differences in the
	# base data used. Specifically, cohort population data in this module uses
	# county-by-cohort population data, whereas state-by-age population data, which
	# is inconsistent with the state-by-age population data, is used in the 
	# by_state version of this module. Additionally, FTE and GDP data in this 
	# version use IMPLAN data to distribute BEA estimates at the county level, 
	# whereas by_state data are BEA estimates.

	national_data	=	lib.national.NationalData
	source_data	= lib.data.SourceData
	config_data	=	lib.config.ConfigData

	# This class gathers the configuration data from data.py (in this module) and 
	# combines it to form all of the impact-independent parameters used in the
	# calculation of lost labor income mortality damages.

	# Additional configuration parameters (simple data such as region definitions,
	# age ranges, and deflators) are included in config.py

	
	#########################################
	#        Public Instance Methods        #
	#########################################

	def __init__(self, agglev='state', deflator=None, test_data=False):

		if deflator is None:
			deflator = self.config_data.DEFLATOR_2012_TO_2011

		self.agglev			=	agglev		#	Target level of aggregation: county, state, california, midwest
		self.deflator		= deflator	# Deflator used to move 2012 values to 2011 $US

		self.test_data	=	test_data

		self.set_national_config_data()
		self.set_regional_config_data()
		self.deflate_config_data()

	def set_national_config_data(self):

		self.labor_participation = self.national_data._get_and_validate_labor_participation()


		#	Retrieve, validate, and set mortality_share_by_cohort
		mortality_share_by_cohort = self.national_data._get_mortality()
		self.source_data.validate_mortality_share_by_cohort(mortality_share_by_cohort)
		self.mortality_share_by_cohort = mortality_share_by_cohort


		#	Retrieve, validate, and set lost_participation_years
		lost_participation_years = self.national_data.get_lost_participation_years(self.labor_participation,self.mortality_share_by_cohort)
		self.source_data.validate_lost_labor_participation(lost_participation_years)
		self.lost_participation_years = lost_participation_years

	def set_regional_config_data(self):

		#	Load and cohort and total population by county and aggregate to regions
		region_total_population		= RegionDefinitions.aggregate_dataframe(self.source_data.county_total_population,agglev=self.agglev)

		pop_by_cohort							= RegionDefinitions.aggregate_dataframe(self.source_data.county_cohort_population,agglev=self.agglev).sum(level='region')
		region_cohort_population	= pd.DataFrame(pd.concat({c:pop_by_cohort[c] for c in pop_by_cohort.columns},names=['cohort','region']),columns=['population'])
		# region_cohort_population.columns = ['population']
		
		#	Validate and assign population
		self.source_data.validate_region_population(self.agglev,region_total_population,region_cohort_population)
		self.region_total_population	= region_total_population.sum(level='region')
		self.region_cohort_population	= region_cohort_population.sum(level=['cohort','region'])

		#	Set and validate current value added per FTE-year
		self.fte_employment, self.value_added, self.value_per_fte = self._get_value_per_fte()

		#	Retrieve, validate, and set discounted_labor_lost and cohort_mortality_value, once for each discount rate
		self.discounted_labor_lost = {}
		self.cohort_mortality_value = {}

		for discount_rate in self.config_data.discount_rates:
			discounted_labor_lost, cohort_mortality_value = self._get_discounted_mort_value(discount_rate)
			# self.source_data.validate_cohort_mortality_value(cohort_mortality_value,discount_rate)

			self.discounted_labor_lost[discount_rate] = discounted_labor_lost
			self.cohort_mortality_value[discount_rate] = self.format_mortality_value(cohort_mortality_value)

	def deflate_config_data(self):
		self.value_per_fte = self.deflator * self.value_per_fte

		for discount_rate in self.config_data.discount_rates:
			self.cohort_mortality_value[discount_rate] = self.deflator * self.cohort_mortality_value[discount_rate]


	#########################################
	#       Private Instance Methods        #
	#########################################

	@staticmethod
	def vec_echo_by_state(states,state_vec):
		def echo_by_state(state):
			return state_vec.loc[state]
		f = np.vectorize(echo_by_state)
		return f(states)


	def _get_value_per_fte(self):

		if self.test_data:
			fte_employment, value_added = self.calculate_temp_value_data()

		else:
			try:
				cty_fte_employment	= RegionDefinitions.aggregate_dataframe(self.source_data.county_fte_employment,agglev=self.agglev)
				value_added					= self.source_data.cluster_value_added[self.agglev]

			except NameError:
				raise NameError('County-level GDP data not yet loaded into lib/data.py')

		fte_employment			= cty_fte_employment.sum(level='region')
		value_added_per_fte	= value_added['GDP'] * 1e6 / fte_employment['employment']

		return fte_employment, value_added, value_added_per_fte


	def _get_discounted_mort_value(self,discount_rate):

		#	Shift lost_participation_years by 1 year to take NPV assuming deaths occur at end of year
		shifted_lost_participation = self.lost_participation_years.copy()
		shifted_lost_participation.index = shifted_lost_participation.index + 1
		shifted_lost_participation = shifted_lost_participation.reindex(range(self.config_data.max_age+1),fill_value=0)

		#	Take the NPV of the time series of expected labor-force participation years lost given a death for each cohort
		discounted_labor_lost = pd.DataFrame([(cohort[0],np.npv(discount_rate,cohort[1])) for cohort in shifted_lost_participation.iteritems()])

		#	Clean up DataFrame
		discounted_labor_lost = discounted_labor_lost.set_index(0)
		discounted_labor_lost.index.name = 'cohort'

		#	Take the outer product to get the discounted value by state and cohort
		cohort_mortality_value = np.outer(self.value_per_fte, discounted_labor_lost)

		#	Convert back to DataFrame and clean up data
		cohort_mortality_value = pd.DataFrame(cohort_mortality_value, index=self.value_per_fte.index, columns=discounted_labor_lost.index)

		return discounted_labor_lost, cohort_mortality_value


	@staticmethod
	def echo_foreach(foreach,echoed):
	#	return vector function with echoed for each element of numpy vector foreach

		def return_echoed(each):
		#	Dummy function to add echoed column for each element of foreach
			return echoed

		f = np.vectorize(return_echoed)
		return f(foreach)

	def format_mortality_value(self,cohort_mortality_value):
	#	Re-orient cohort_mortality_values values to allow combination with run data (which has cohort, region index and quantile columns)
	#	Note that this function does not alter the values in each location, but only rearranges the indices.

		return pd.DataFrame(pd.concat({c:cohort_mortality_value[c] for c in cohort_mortality_value.columns},names=['cohort','region']),columns=['value'])


	def calculate_temp_value_data(self):
		#	The test data assumes that the state has the same average value added per fte, but that fte employment varies
		#	In actuality, the fte data used here is distributed using BLS QCEW jobs data, which is a measure of total employment, not fte employment.

		cty_fte_employment = RegionDefinitions.aggregate_dataframe(self.source_data.county_fte_employment,agglev=self.agglev)
		st_fte_employment = RegionDefinitions.aggregate_dataframe(self.source_data.county_fte_employment,agglev='state',new_index_name='state')

		#	state value added (change index from state_abbrev to state)
		st_valadd = self.source_data.state_value_added.copy()
		st_valadd['state'] = RegionDefinitions.get_ansi_from_state_abbrev_vec(st_valadd.index.get_level_values('state_abbrev'))
		st_valadd.set_index('state',inplace=True)

		#	multiply state GDP by county share of state fte employment to get proxy for GDP by county
		cty_valadd = st_fte_employment.copy()
		
		cty_valadd['value_added'] = self.vec_echo_by_state(cty_valadd.index.get_level_values('state'), st_valadd['GDP'])
		cty_valadd['value_added'] = cty_valadd['value_added'] * cty_fte_employment.sum(level='county')['employment'] / st_fte_employment.sum(level='state')['employment']

		del cty_valadd['employment']
		cty_valadd.reset_index('state',inplace=True)
		del cty_valadd['state']

		fte_employment			= cty_fte_employment.sum(level='region')
		value_added					= pd.DataFrame((RegionDefinitions.aggregate_dataframe(cty_valadd,agglev=self.agglev).sum(level='region'))['value_added'],columns=['GDP'])

		return fte_employment, value_added