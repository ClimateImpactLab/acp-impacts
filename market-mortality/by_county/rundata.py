import pandas as pd, numpy as np, os
import scenario, lib.config


class ImpactDirectoryReader(object):
	def __init__(self, readdir=None, agglev = 'state'):

		self.config_data	= lib.config.ConfigData
		
		self.impactfiles	= None
		self.agglev				=	agglev
		self.readdir			= readdir

	def get_impact_run(self):

		if self.impactfiles is None:
			self.search_for_impactfiles()

		for rcp in self.config_data.rcps:
			for tp in self.config_data.tps:
				if self.validate_impact_files(rcp,tp):
					r = scenario.MortRun(self.readdir,rcp,tp,agglev=self.agglev)
					r.read_data()
					yield rcp, tp, r

	def search_for_impactfiles(self):
	#	retrieve list of files in mort_dir
		self.impactfiles = os.listdir(self.readdir)

	def validate_impact_files(self,rcp,tp):
		if self.impactfiles is None:
			self.search_for_impactfiles()

		missing = []
		for cohort in self.config_data.mort_cohort_names:
			filename = 'health-mortage-{c}-{r}-{y}b.csv'.format(c=cohort,r=rcp,y=tp)
			if not filename in self.impactfiles:
				missing.append(filename)

		if len(missing) > 0:
			raise OSError('files missing from impactdir for scenario {s} {t}:\n\t{f}'.format(s=rcp,t=tp,f='\n\t'.join(missing)))

		return True