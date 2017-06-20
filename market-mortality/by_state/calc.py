import pandas as pd, numpy as np, os
import rundata, writer, static, lib.config
from regions.regdefs import RegionDefinitions


class MortalityCostCalculator(object):
	def __init__(self,readdir,deflator=None):

		self.config_data		= lib.config.ConfigData
		self.static_data		=	static.StaticData(deflator=deflator)
		self.impact_reader	=	rundata.ImpactDirectoryReader()
		self.readdir				=	os.path.normpath(os.path.expanduser(readdir))

	def run_simulation(self):
		cohort_mortality_value = {}

		for discrate in self.config_data.discount_rates:
			cohort_mortality_value[discrate] = self.format_mortality_value(discrate)

		#	Loop through impact files in rundata.ImpactDirectoryReader.filepath and 
		#	create a set of results for each RCP, time period, and cohort or total
		for rcp, tp, run in self.impact_reader.get_impact_run():
			for discrate in self.config_data.discount_rates:
				mort_cost = self.calculate_mort_cost(discrate,run,cohort_mortality_value)
				writer.ImpactWriter.output_results(mort_cost,rcp,tp,discrate,self.static_data)

		#	save last used for testing:
		self.mort_cost = mort_cost

	def calculate_mort_cost(self,discrate,run,cohort_mortality_value):
		# mort_cost = []
		# for cohort in self.config_data.mort_cohort_names:
			
			
		# 	cohort_cost = pd.concat([cohort_mortality_value[discrate].loc[cohort]['value']*run.mort_data.loc[cohort][q]*self.static_data.cohort_population[cohort]/100000/1e6 for q in run.mort_data.columns],axis=1)
			
		# 	#	add cohort column and fill with current cohort, then make index
		# 	cohort_cost['cohort'] = [cohort for _ in cohort_cost.index]
		# 	cohort_cost.set_index(['cohort'],append=True,inplace=True)

		# 	#	re-order indices to cohort, ANSI, state_abbrev for sorting
		# 	cohort_cost.index = cohort_cost.index.reorder_levels(['cohort','state','state_abbrev'])
		# 	cohort_cost.sortlevel(inplace=True)
		# 	cohort_cost.columns = run.mort_data.columns
		# 	mort_cost.append(cohort_cost)
		# mort_cost = pd.concat(mort_cost)
		# mort_cost.sortlevel(inplace=True)
		# cohort_cost.index = cohort_cost.index.reorder_levels(['cohort','state_abbrev','state'])

		# return mort_cost
		
		# does the same thing, just wayyyyyyy better:
		return run.mort_data.mul(cohort_mortality_value[discrate], axis=0)

	@staticmethod
	def echo_foreach(foreach,echoed):
	#	return vector function with echoed for each element of numpy vector foreach

		def return_echoed(each):
		#	Dummy function to add echoed column for each element of foreach
			return echoed

		f = np.vectorize(return_echoed)
		return f(foreach)

	def format_mortality_value(self,discrate):
	#	Re-orient cohort_mortality_values values to allow combination with run data (which has cohort, state index and quantile columns)
		mortval = self.static_data.cohort_mortality_value[discrate].copy()
		mortval.index = pd.Series(RegionDefinitions.stateLookup).loc[mortval.index.values]
		mortval = pd.concat({c:mortval[c] for c in mortval.columns}, axis=0)
		mortval.index.names = ['cohort','state']

		return mortval
