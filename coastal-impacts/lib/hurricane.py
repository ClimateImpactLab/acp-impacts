import pandas as pd, numpy as np
import scipy.interpolate as interpolate
import csv, os, re, math

RAWDIR = 'data/RMSData/'
ASSETS=['ALL']
COASTAL = [0,1]
LOSS=['DIRECT_LOSS','BI_LOSS']
DTYPE=None


class HurricaneFile(object):

	std_header	=	['LOB','STATE','COASTALFLAG','LOSS','DIRECT_LOSS','BI_LOSS','LOSS.wind','DIRECT_LOSS.wind','BI_LOSS.wind','LOSS.surge','BI_LOSS.surge','DIRECT_LOSS.surge']
	
	def __init__(self,directory,filename):
		self.directory = directory
		self.filename = filename

		self.filepath = os.path.join(self.directory, self.filename)

		fparse = re.match(r'(?P<fintype>(Insurable|Economic))\.(?P<type>AAL)\.((?P<year>[0-9]{4})_)?((q)?(?P<probability>(Base|(?<=[0-9]{4}_q)([0-9]+(\.[0-9](?=\.))?))))?(\.(?P<year2>[0-9]{4}))?\.csv',filename)
		try:
			self.fintype = fparse.group('fintype')
		except AttributeError:
			raise AttributeError(directory+filename)
		if fparse.group('year'):
			tp = fparse.group('year')
		elif fparse.group('year2'):
			tp = fparse.group('year2')
		else:
			tp = 'Base'
		
		if tp == 'Base':
			self.year = 2010
		else:
			self.year = int(tp)

		pval = fparse.group('probability')
		if pval == 'Base' or pval is None:
			self.probability = 50.0
		else:
			self.probability = float(pval)

	def read(self):
		data = pd.read_csv(self.filepath, index_col=[0,1,2])
		data.columns.names = ['LOSSTYPE']
		data = data.stack('LOSSTYPE')
		return data

class NoreasterFile(object):

	def __init__(self,directory,filename):
		self.directory = directory
		self.filename = filename
		self.filepath = os.path.join(self.directory, self.filename)

	def read(self):
		data         = pd.read_csv(self.filepath, sep='\t', index_col=[0,1,2], header=[0,1,2])
		index        = pd.read_csv('data/RMSData/noreaster/WinterStorm_Noreaster_LossEstimates_20140321.tsv', sep='\t', index_col=[0,1,2], header=None, nrows=3).fillna(method='pad', axis=1).reset_index(drop=True)
		data.columns = pd.MultiIndex.from_tuples([tuple(index.values[:,i]) for i in range(index.values.shape[1])])
		
		data.dropna(axis=1, how='all', inplace=True)

		data.index.names = ['ASSET','STATE','COAST']
		data.columns.names = ['VARIABLE','INDEX','DAMAGE']

		current = data.xs('Noreaster Loss (Wind Snow Ice & Freeze)',level='VARIABLE',axis=1)
		current.columns = current.columns.get_level_values('DAMAGE')

		surge_2100 = data.xs('Surge Losses : 2010 by Quantile', level='VARIABLE', axis=1)
		surge_q50 = data.xs('Surge Losses : Q50 by Decade', levelev='VARIABLE', axis=1)

		self.current    = current
		self.surge_2100 = surge_2100
		self.surge_q50  = surge_q50

class Workspace(object):
	def __init__(self):
		self.stateList = ['AL','CT','DC','DE','FL','GA','LA','MA','MD','ME','MS','NC','NH','NJ','NY','PA','RI','SC','TX','VA','VT','WV','OR','WA','CA']
		self.states = {st:State(st) for st in self.stateList}
	
	def run(self,rawdir=RAWDIR,assets=ASSETS,coastal=COASTAL,loss=LOSS,dtype=DTYPE):

		# data = {}

		for folder in os.listdir(rawdir):
			fsearch = re.search(r'^(?P<rcp>[0-9]{2}(?=_))?[_]*(?P<model>[A-Z0-9]+(?=_))?[_]*(?P<kind>[B](?=_))?[_]*(?P<phase>(Active|Climatology|Historical))$',folder)
			if fsearch:
				rcp = fsearch.group('rcp')
				model = fsearch.group('model')
				kind = fsearch.group('kind')
				phase = fsearch.group('phase')

			else:
				if re.search(r'historical',folder):
					rcp = None
					model = None
					kind = None
					phase = None
				else:
					print('Excluded '+folder)
					continue

			if model is None and not rcp is None:
				model = 'RCP45Ensemble'
			elif model is None:
				model = 'Hist'

			if rcp is None:
				rcp = 'Hist'
			else:
				rcp = 'rcp'+rcp

			print(' '.join([str(i) for i in [rcp,model,kind,phase]]))

			for f in [files for files in os.listdir(rawdir+folder) if files.endswith('.csv')]:
				print('\treading:\t'+f)

				d = HurricaneFile(rawdir + folder + '/' ,f,self.states,rcp,True)
				d.read(model,assets,coastal,loss,dtype)

		for folder in os.listdir(rawdir):
			fsearch = re.search(r'^(?P<noreaster>noreaster)$',folder)
			if fsearch:
				kind = fsearch.group('noreaster')

			else:
				continue

			for f in [files for files in os.listdir(rawdir+folder) if files.endswith('.tsv')]:
				print('\treading:\t'+f)

				d = NoreasterFile(rawdir + folder + '/' ,f,self.states,True)
				d.read(assets,coastal,loss,dtype)

	
	def output(self):
		with open('outputs/damage_by_sealevel.csv','w+') as wfile:
			wfile.write('STATE,RCP,MODEL,LSL [cm],DIRECT,BI')
			for state in self.states:
				wfile.write(str(self.states[state]))

if __name__=="__main__":
	with open('outputs/allout.csv','w+') as writefile:
		writefile.write('ST,CST,RCP,MODEL,YR,QUANT,BI,DIRECT\n')
	ws = Workspace()
	ws.run()
	ws.output()
