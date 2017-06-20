import pandas as pd, numpy as np, os, re
import lib.config


class MortRun(object):
	def __init__(self,filepath,rcp='rcp85',tp='2080',agglev='state'):
		
		self.config_data	=	lib.config.ConfigData

		self.rcp					=	rcp
		self.tp						=	tp
		self.agglev				=	agglev
		self.filepath			=	filepath

	@staticmethod
	def region_sub(region):
		region = re.sub(r'\s','',region)
		region = re.sub(r'\-','_',region)
		region = re.sub(r'\+','_',region)
		return region

	@classmethod
	def region_vec(cls,region_vec):
		func = np.vectorize(cls.region_sub)
		return func(region_vec)

	def read_data(self):
		data = []
		for cohort in self.config_data.mort_cohort_names:
			
			#	prepare to read file
			filename = 'health-mortage-{c}-{r}-{y}b.csv'.format(c=cohort,r=self.rcp,y=self.tp)
			file_header = pd.io.parsers.read_csv(self.filepath+filename,nrows=1).columns
			header_columns = []
			for h in file_header:
				if re.search(r'(region|q0\.[0-9]+)',h):
					header_columns.append(h)

			cohort_data = pd.io.parsers.read_csv(self.filepath+filename,usecols=header_columns)

			#	Add cohort column
			cohort_data['cohort'] = [cohort for _ in cohort_data.index]
			if self.agglev in ['midwest','california']:
				cohort_data['region'] = self.region_vec(cohort_data['region'])
			
			#	Set 'region' as primary axis, cohort secondary axis, and sort by region>cohort>state
			cohort_data.set_index(['region','cohort'],inplace=True)
			cohort_data.sortlevel(inplace=True)

			#	Set cohort as primary axis, preserving sort by ANSI code
			cohort_data.index = cohort_data.index.swaplevel(1,0)

			#	Add formatted DataFrame to list of data indexed by cohort
			data.append(cohort_data)

		#	Concatenate dataframes along cohort axis
		self.mort_data = pd.concat(data)