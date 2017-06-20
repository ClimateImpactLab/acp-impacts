import pandas as pd, numpy as np
import rundata, writer, static, lib.config
from regions.regdefs import RegionDefinitions


class MortalityCostCalculator(object):
	def __init__(self,readdir, agglev='state', deflator=None, test_data=False):
		
		self.agglev					=	agglev
		self.config_data		= lib.config.ConfigData
		self.static_data		=	static.StaticData(agglev=self.agglev,deflator=deflator,test_data=test_data)

		self.readdir				=	readdir

		self.impact_reader	=	rundata.ImpactDirectoryReader(agglev=self.agglev,readdir=self.readdir)

	def run_simulation(self):
		cohort_mortality_value = {}

		cohort_mortality_value = self.static_data.cohort_mortality_value

		# Loop through impact files in rundata.ImpactDirectoryReader.filepath and 
		# create a set of results for each RCP, time period, and cohort or total
		for rcp, tp, run in self.impact_reader.get_impact_run():
			for discrate in self.config_data.discount_rates:
				mort_cost = self.calculate_mort_cost(discrate,run,cohort_mortality_value[discrate])
				writer.ImpactWriter.output_results(mort_cost,rcp,tp,discrate,self.agglev,self.static_data)



	def calculate_mort_cost(self,discrate,run,cohort_mortality_value):
		
		def calculate_mort_cost_by_column(impact_column):
			return impact_column*cohort_mortality_value['value']*self.static_data.region_cohort_population['population']*(np.float64(1)/100000/1e6)

		return run.mort_data.apply(calculate_mort_cost_by_column)



	def test(self):
		i = self.impact_reader.get_impact_run()
		v = self.static_data.cohort_mortality_value
		q = 'q0.01'
		discrate = 0.03
		return i,v,q,discrate
		
	def get_cohort(self):
		for cohort in ['0-0','1-44','45-64','65-inf']:
			yield cohort

		### 	Testing data to be run in the python interpreter

		# import by_county.calc as calc, pandas as pd, numpy as np
		# m = calc.MortalityCostCalculator(agglev='midwest')
		# self = m
		# g,v,q,discrate = self.test()
		# cohort_mortality_value = v[discrate]
		# i = self.get_cohort()
		# rcp, tp, run = next(g)
		# mort_cost = []

		# cohort = next(i)
		# cohort_cost = pd.concat([cohort_mortality_value.loc[cohort,'value']*run.mort_data.loc[cohort,q]*self.static_data.region_cohort_population[cohort]*(np.float64(1)/100000/1e6) for q in run.mort_data.columns],axis=1)
		# cohort_cost['cohort'] = [cohort for _ in cohort_cost.index]
		# cohort_cost.set_index(['cohort'],append=True,inplace=True)
		# cohort_cost.index = cohort_cost.index.reorder_levels(['cohort','region'])
		# cohort_cost.sortlevel(inplace=True)
		# cohort_cost.columns = run.mort_data.columns
		# mort_cost.append(cohort_cost)

		# mort_cost = pd.concat(mort_cost)
		# mort_cost.sortlevel(inplace=True)