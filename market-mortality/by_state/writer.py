import pandas as pd, numpy as np, StringIO
import rundata, static, lib.config

DEFAULT_VALUE_WRITE_DIR = '../outputs/value/'
DEFAULT_PERCAP_WRITE_DIR = '../outputs/percap/'


CSV_HEADER = '''"Heat-related change in mortality cost using labor-market impact estimate by region (2011 $US Million)"
	Value deflated using 2011/2012 GDP deflator - 0.982324529
'''

class ImpactWriter(object):

	config_data		= lib.config.ConfigData
	
	valuedir			=	DEFAULT_VALUE_WRITE_DIR
	percapdir			=	DEFAULT_PERCAP_WRITE_DIR

	@classmethod
	def reassign_output_directories(cls,valuedir=None,percapdir=None):
		if not valuedir is None:
			cls.valuedir = valuedir
		if not percapdir is None:
			cls.percapdir = percapdir

	@classmethod
	def output_results(cls,mortality_cost_by_cohort,rcp,tp,discount_rate,static_data=None):
		if static_data is None:
			static_data = static.StaticData()

		discname = 'undiscounted' if discount_rate == 0 else 'disc-{disc:2.0%}'.format(disc=discount_rate)

		for cohort in cls.config_data.mort_cohort_names:
			mortality_cost = mortality_cost_by_cohort.copy()
			mortality_cost.index = mortality_cost.index.reorder_levels(['cohort','state','state_abbrev'])
			mortality_cost.sortlevel(inplace=True)
			mortality_cost.index = mortality_cost.index.reorder_levels(['cohort','state_abbrev','state'])
			mortality_cost = mortality_cost.loc[cohort].copy()
			cls.write_to_file(mortality_cost,cohort,rcp,tp,discname,static_data)

		mortality_cost = mortality_cost_by_cohort.copy()
		mortality_cost = mortality_cost.sum(level=['state','state_abbrev'])
		mortality_cost.index = mortality_cost.index.reorder_levels(['state','state_abbrev'])
		mortality_cost.sortlevel(inplace=True)
		mortality_cost.index = mortality_cost.index.reorder_levels(['state_abbrev','state'])
		cls.write_to_file(mortality_cost,'total',rcp,tp,discname,static_data)
		
		
		# self.last_abs = self.write_to_file(mortality_cost_by_cohort,'total',rcp,tp,discname)
		# self.last_abs, self.last_percap = self.write_to_file(mortality_cost_by_cohort,'total',rcp,tp,discname)

	@classmethod
	def write_to_file(cls,output_data,cohort,rcp,tp,discname,static_data):
		
		filename = 'mortality_value-{c}-{r}-{y}-{d}.csv'.format(c=cohort,r=rcp,y=tp,d=discname)
		write_buffer = StringIO.StringIO()
		output_data.to_csv(write_buffer)
		
		with open(cls.valuedir+filename,'w+') as csvfile:
			csvfile.write(CSV_HEADER + write_buffer.getvalue())

		# return output_data

		output_data_percap = pd.concat([output_data[i]/static_data.total_population['population']*1e6 for i in output_data.columns],axis=1)
		output_data_percap.columns = output_data.columns

		filename = 'mortality_value-{c}-{r}-{y}-{d}-percap.csv'.format(c=cohort,r=rcp,y=tp,d=discname)
		write_buffer = StringIO.StringIO()
		output_data_percap.to_csv(write_buffer)
		
		with open(cls.percapdir+filename,'w+') as csvfile:
			csvfile.write(CSV_HEADER + write_buffer.getvalue())

		return output_data, output_data_percap