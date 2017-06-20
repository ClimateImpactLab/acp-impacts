import pandas as pd, numpy as np, os
import lib.config

class MortRun(object):
	def __init__(self,filepath, rcp='rcp85', tp='2080'):
		
		self.config_data = lib.config.ConfigData

		self.filepath = os.path.normpath(os.path.expanduser(filepath))
		self.rcp = rcp
		self.tp = tp
	
	def read_data(self):
		data = []
		for cohort in self.config_data.mort_cohort_names:
			filename = 'health-mortage-{c}-{r}-{y}b.csv'.format(c=cohort,r=self.rcp,y=self.tp)
			cohort_data = pd.io.parsers.read_csv(os.path.join(self.filepath,filename))

			#	Remove state abbreviation from dataframe columns, and rename ANSI code 'region' as 'state'
			del cohort_data['state']
			cohort_data.columns = ['state'] + list(cohort_data.columns[1:])

			#	Add cohort column
			cohort_data['cohort'] = [cohort for _ in cohort_data.index]
			
			#	Set 'state' ANSI code as primary axis, cohort secondary axis, and sort by ANSI>cohort>state
			cohort_data.set_index(['state', 'cohort'], inplace=True)
			cohort_data.sortlevel(inplace=True)

			#	Set cohort as primary axis, preserving sort by ANSI code
			cohort_data.index = cohort_data.index.swaplevel(1,0)

			#	Add formatted DataFrame to list of data indexed by cohort
			data.append(cohort_data)

		#	Concatenate dataframes along cohort axis
		self.mort_data = pd.concat(data)