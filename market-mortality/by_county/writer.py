import pandas as pd, numpy as np, StringIO
import rundata, static, lib.config
import lib.pandas_tools as pandas_tools

DEFAULT_VALUE_WRITE_DIR = '../outputs/value/'
DEFAULT_PERCAP_WRITE_DIR = '../outputs/percap/'


CSV_VALUE_HEADER = '''"Heat-related change in mortality cost using labor-market impact estimate by region (2011 $US Million)"
	Value deflated using 2011/2012 GDP deflator - 0.982324529
'''

CSV_PERCAP_HEADER = '''"Heat-related change in mortality cost per capita using labor-market impact estimate by region (2011 $US per capita)"
	Value deflated using 2011/2012 GDP deflator - 0.982324529
'''

OUTPUT_REGION_ORDERING = {
		'states':			[lib.config.ConfigData.STATE_ABBREV_TO_ANSI[st] for st in ['AL','AK','AZ','AR','CA','CO','CT','DC','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']],
		'midwest':		['IL_Chicago','IN_Indianapolis','IA_DesMoines','MI_Detroit','MN_Minneapolis','MO_KansasCity','MO_StLouis','OH_ClevelandToledo','OH_ColumbusCinDayton','WI_MilwaukeeMadison','other'],
		'california':	['NorthCoast','Sierra','CentralValley','CentralCoast','SanJoaquinValley','InlandEmpire_Imperial','SouthCoast','other']
}

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
	def output_results(cls,mortality_cost_by_cohort,rcp,tp,discount_rate,agglev,static_data=None):
		#	initialize output formatting method cls.region_sorter()
		# cls.set_region_sorter(agglev)

		if static_data is None:
			static_data = static.StaticData()

		discname = 'undiscounted' if discount_rate == 0 else 'disc-{disc:2.0%}'.format(disc=discount_rate)

		for cohort in cls.config_data.mort_cohort_names:
			mortality_cost = mortality_cost_by_cohort.copy()
			mortality_cost.index = mortality_cost.index.reorder_levels(['cohort','region'])
			mortality_cost.sortlevel(inplace=True)
			mortality_cost = mortality_cost.loc[cohort].copy()
			cls.write_to_file(mortality_cost,cohort,rcp,tp,discname,static_data,agglev)

		mortality_cost = mortality_cost_by_cohort.copy()
		mortality_cost = mortality_cost.sum(level=['region'])
		cls.write_to_file(mortality_cost,'total',rcp,tp,discname,static_data,agglev)
		

	@classmethod
	def write_to_file(cls,output_data,cohort,rcp,tp,discname,static_data,agglev):
		
		region_sorter	= pandas_tools.sort_pd(key=OUTPUT_REGION_ORDERING[agglev].index)

		#	Total regional costs

		filename = 'mortality_value_{reg}-{c}-{r}-{y}-{d}.csv'.format(reg=agglev,c=cohort,r=rcp,y=tp,d=discname)
		write_buffer = StringIO.StringIO()
		(output_data.iloc[region_sorter(output_data.index.get_level_values('region'))]).to_csv(write_buffer)
		
		with open(cls.valuedir+filename,'w+') as csvfile:
			csvfile.write(CSV_VALUE_HEADER + write_buffer.getvalue())

		#	Per capita costs

		output_data_percap = pd.concat([output_data[i]/static_data.region_total_population['total']*1e6 for i in output_data.columns],axis=1)
		output_data_percap.columns = output_data.columns

		filename = 'mortality_value_{reg}-{c}-{r}-{y}-{d}-percap.csv'.format(reg=agglev,c=cohort,r=rcp,y=tp,d=discname)
		write_buffer = StringIO.StringIO()
		(output_data_percap.iloc[region_sorter(output_data_percap.index.get_level_values('region'))]).to_csv(write_buffer)
		
		with open(cls.percapdir+filename,'w+') as csvfile:
			csvfile.write(CSV_PERCAP_HEADER + write_buffer.getvalue())