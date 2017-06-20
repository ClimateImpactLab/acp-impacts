import csv, os, re, math

RAWDIR = 'data/RMSData/'
ASSETS=['ALL']
COASTAL = [0,1]
LOSS=['DIRECT_LOSS','BI_LOSS']
DTYPE=None

class SeaLevelFile(object):
	@staticmethod
	def readsl(readfiles):
		sealev = {}
		inundation = {}
		for readfile in readfiles:
			with open(readfile,'r') as csvfile:
				csvreader = csv.reader(csvfile,delimiter='\t',quotechar='"')
			
				header = next(csvreader)

				for row in csvreader:

					year = int(row[0])
					LOB = row[2]
					if not LOB == 'ALL':
						continue
					quant = float(row[1])
					state = row[3]
					ExposureBelowMSL = float(row[5])
					LSL = float(row[9])		#	LSL rise from 2010, ft
					if not state in sealev:
						sealev[state] = {}
					if not year in sealev[state]:
						sealev[state][year] = {}
					sealev[state][year][quant] = LSL
					if not state in inundation:
						inundation[state] = {}
					inundation[state][LSL] = ExposureBelowMSL


		return sealev, inundation

	def __init__(self,readfiles=['data/RMSData/EastCoastExposureBelow.tsv','data/RMSData/WestCoastExposureBelow.tsv']):
	# def __init__(self,readfiles=['sealeveldist.csv']):
	#	sealeveldist.csv is written by read_slproj.py, and is a linear interpolation of the SLR projections in 
	#	NorthAmerica_LSLproj_weighted.tsv (read from slproj.tsv), which are given in irregular quantile intervals.
		self.sealev, self.inundation = SeaLevelFile.readsl(readfiles)
		#with open('outputs/sealevelinundation.csv','w+') as writefile:
		#	writefile.write('st,yr,quant,lsl,inundation\n')
		#	for state in sorted(self.sealev.keys()):
		#		for year in sorted(self.sealev[state].keys()):
		#			for quant in sorted(self.sealev[state][year].keys()):
		#				lsl = self.sealev[state][year][quant]
		#				writefile.write('{st},{yr},{quant},{lsl},{inundation}\n'.format(st=state,yr=year,quant=quant,lsl=lsl,inundation=self.inundation[state][lsl]))


class State(object):

	slf = SeaLevelFile()
	sealev = slf.sealev
	inundation = slf.inundation

	#	Map inland states to coastal gauges
	coastline = {st:st for st in ['HI','AK','OR','WA','CA','TX','LA','MS','AL','ME','MA','NH','RI','CT','NY','NJ','DE','MD','DC','VA','NC','SC','GA','FL','PA']}
 	coastline['WV'] = 'VA'
 	coastline['VT'] = 'NH'

 	@staticmethod
 	def cName(state,coast):
 		coastnames = ['inland','coast']
 		return state + '_' + coastnames[int(coast)]

	def __init__(self,state):
		self.state = state
		self.coast = State.coastline[state]
		self.hurrData = {}
		self.noreasterData = {}
	def postHurr(self,cstl,rcp,model,yr,prob,damage):
		with open('outputs/allout.csv','a') as writefile:
			writefile.write('{ST},{CST},{RCP},{MODEL},{YR},{QUANT},{BI},{DIRECT}\n'.format(ST=self.state,CST=cstl,RCP=rcp,MODEL=model,YR=yr,QUANT=prob,BI=damage['BI_LOSS'],DIRECT=damage['DIRECT_LOSS']))
		sealev = State.sealev[self.coast][yr][prob]
		with open('outputs/allout.csv','a') as writefile:
			writefile.write('{ST},{CST},{RCP},{MODEL},{YR},{QUANT},{LSL},{BI},{DIRECT}\n'.format(ST=self.state,CST=cstl,RCP=rcp,MODEL=model,YR=yr,QUANT=prob,LSL=sealev,BI=damage['BI_LOSS'],DIRECT=damage['DIRECT_LOSS']))
		if not rcp in self.hurrData:
			self.hurrData[rcp] = {}
		if not model in self.hurrData[rcp]:
			self.hurrData[rcp][model] = {}
		if not sealev in self.hurrData[rcp][model]:
			self.hurrData[rcp][model][sealev] = {}
		if not isinstance(damage,dict):
			raise TypeError('Damage entry must be dictionary: {s},{c},{r},{m},{y},{p}\n{d}'.format(s=self.state,c=cstl,r=rcp,m=model,y=yr,p=prob,d=damage))
		self.hurrData[rcp][model][sealev][cstl] = damage

	def postNoreaster(self,cstl,year,prob,dtype,damage):
		sealev = State.sealev[self.coast][year][prob]
		if not sealev in self.noreasterData:
			self.noreasterData[sealev] = {}
		if not cstl in self.noreasterData[sealev]:
			self.noreasterData[sealev][cstl] = {}
		self.noreasterData[sealev][cstl][dtype] = damage
		if 'BI_LOSS' in self.noreasterData[sealev][cstl] and 'DIRECT_LOSS' in self.noreasterData[sealev][cstl]:
			with open('outputs/allout.csv','a') as writefile:
				writefile.write('{ST},{CST},N\'estr,N\'estr,{YR},{QUANT},{LSL},{BI},{DIRECT}\n'.format(ST=self.state,CST=cstl,YR=year,QUANT=prob,LSL=sealev,BI=self.noreasterData[sealev][cstl]['BI_LOSS'],DIRECT=self.noreasterData[sealev][cstl]['DIRECT_LOSS']))

	def __str__(self):
		string = \
			'\n'.join(['{st},{rcp},{mod},{lev},{dir},{bi}'.format(
				st=State.cName(self.state,cst),
				rcp=rcp,
				mod=model,
				lev=lev,
				dir=self.hurrData[rcp][model][lev][cst]['DIRECT_LOSS'],
				bi=self.hurrData[rcp][model][lev][cst]['BI_LOSS'])
										for cst in [0,1]
										for rcp in sorted(self.hurrData.keys())
										for model in sorted(self.hurrData[rcp].keys())
										for lev in sorted(self.hurrData[rcp][model].keys())
										if cst in self.hurrData[rcp][model][lev].keys()]) + '\n' + \
			'\n'.join(['{st},Noreaster,Noreaster,{lev},{dir},{bi}'.format(
				st=State.cName(self.state,cst),
				lev=lev,
				dir=self.noreasterData[lev][cst]['DIRECT_LOSS'],
				bi=self.noreasterData[lev][cst]['BI_LOSS'])
										for cst in [0,1]
										for lev in sorted(self.noreasterData.keys())
										if cst in self.noreasterData[lev].keys()]) + '\n'
		if self.state == self.coast:
			string = string + '\n'.join(['{st},Inundation,Inundation,{lev},{dir},0'.format(
				st=State.cName(self.state,cst),
				lev=lev,
				dir=State.inundation[self.state][lev])
										for lev in sorted(State.inundation[self.state].keys())]) + '\n'
		return string


class HurricaneFile(object):

	std_header	=	['LOB','STATE','COASTALFLAG','LOSS','DIRECT_LOSS','BI_LOSS','LOSS.wind','DIRECT_LOSS.wind','BI_LOSS.wind','LOSS.surge','BI_LOSS.surge','DIRECT_LOSS.surge']
	

	def __init__(self,directory,filename,states,rcp,header=True):
		self.directory = directory
		self.filename = filename
		self.header = header
		self.states = states
		self.stateList = sorted(states.keys())
		self.rcp = rcp

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

	def read(self,model,assets=['ALL'],coastal=[0,1],loss=['DIRECT_LOSS','BI_LOSS'],dtype=None):
		with open(self.directory + self.filename,'r') as csvfile:
			csvreader = csv.reader(csvfile,delimiter=',',quotechar='"')
			
			hlist = next(csvreader)
			if not hlist == HurricaneFile.std_header:
				raise OSError('Header mismatch')

			for row in csvreader:
				state = row[1]
				if not state in self.stateList:
					raise OSError('State {st} not found'.format(st=state))

				asset = row[0]
				if not asset in assets:
					continue

				cstl = int(row[2])
				if not cstl in coastal:
					continue
				
				if dtype is None:
					indices = [HurricaneFile.std_header.index(l) for l in loss]
				else:
					indices = [HurricaneFile.std_header.index('{l}.{d}'.format(l=l,d=d)) for l in loss for d in dtype]

				damage = {HurricaneFile.std_header[i]:float(row[i]) for i in indices}

				self.states[state].postHurr(cstl,self.rcp,model,self.year,self.probability,damage)

class NoreasterFile(object):
	header = [
			(None,None,'LOB'),(None,None,'STATE'),(None,None,'COASTALFLAG'),(None,None,'AAL'),(None,None,'AAL (None,None,Direct)'),(None,None,'AAL (BI)'),
			(None,None,''),
			(2010,50,'LOSS'),			(2010,50,'DIRECT_LOSS'),			(2010,50,'BI_LOSS'),
			(2020,50,'LOSS'),			(2020,50,'DIRECT_LOSS'),			(2020,50,'BI_LOSS'),
			(2030,50,'LOSS'),			(2030,50,'DIRECT_LOSS'),			(2030,50,'BI_LOSS'),
			(2040,50,'LOSS'),			(2040,50,'DIRECT_LOSS'),			(2040,50,'BI_LOSS'),
			(2050,50,'LOSS'),			(2050,50,'DIRECT_LOSS'),			(2050,50,'BI_LOSS'),
			(2060,50,'LOSS'),			(2060,50,'DIRECT_LOSS'),			(2060,50,'BI_LOSS'),
			(2070,50,'LOSS'),			(2070,50,'DIRECT_LOSS'),			(2070,50,'BI_LOSS'),
			(2080,50,'LOSS'),			(2080,50,'DIRECT_LOSS'),			(2080,50,'BI_LOSS'),
			(2090,50,'LOSS'),			(2090,50,'DIRECT_LOSS'),			(2090,50,'BI_LOSS'),
			(2100,50,'LOSS'),			(2100,50,'DIRECT_LOSS'),			(2100,50,'BI_LOSS'),
			(None,None,''),
			(2050,0.5,'LOSS'),			(2050,0.5,'DIRECT_LOSS'),			(2050,0.5,'BI_LOSS'),
			(2050,5,'LOSS'),			(2050,5,'DIRECT_LOSS'),				(2050,5,'BI_LOSS'),
			(None,(2050,16.7),'LOSS'),	(None,(2050,16.7),'DIRECT_LOSS'),	(None,(2050,16.7),'BI_LOSS'),	#	Skip because of missing data
			(2050,33.3,'LOSS'),			(2050,33.3,'DIRECT_LOSS'),			(2050,33.3,'BI_LOSS'),
			(2050,50,'LOSS'),			(2050,50,'DIRECT_LOSS'),			(2050,50,'BI_LOSS'),
			(2050,66.7,'LOSS'),			(2050,66.7,'DIRECT_LOSS'),			(2050,66.7,'BI_LOSS'),
			(2050,83.3,'LOSS'),			(2050,83.3,'DIRECT_LOSS'),			(2050,83.3,'BI_LOSS'),
			(2050,95,'LOSS'),			(2050,95,'DIRECT_LOSS'),			(2050,95,'BI_LOSS'),
			(2050,99.5,'LOSS'),			(2050,99.5,'DIRECT_LOSS'),			(2050,99.5,'BI_LOSS')]

	dataHeaders = [i for i,h in enumerate(header) if not h[0] is None]

	def __init__(self,directory,filename,states,header=True):
		self.directory = directory
		self.filename = filename
		self.states = states
		self.stateList = sorted(states.keys())
	def read(self,assets=['ALL'],coastal=[0,1],loss=['DIRECT_LOSS','BI_LOSS'],dtype=None):
		with open(self.directory + '/' + self.filename,'r') as csvfile:
			csvreader = csv.reader(csvfile,delimiter='\t',quotechar='"')
			header = next(csvreader)
			header = next(csvreader)
			header = next(csvreader)
			for row in csvreader:

				state = row[1]

				cstl = int(row[2])
				if not cstl in coastal:
					continue

				asset = row[0]
				if not asset in assets:
					continue
				# print '\n'+','.join(row)[0:50],

				if dtype is None:
					indices = [i for i in NoreasterFile.dataHeaders if NoreasterFile.header[i][2] in loss]
				else:
					indices = [i for i in NoreasterFile.dataHeaders if NoreasterFile.header[i][2] in dtype]



				if not state in self.stateList:
					if not sum([float(row[i]) for i in indices]) == 0:
						raise OSError('State {st} not found'.format(st=state))
					else:
						continue


				# print str(indices),

				for i in indices:
					head = NoreasterFile.header[i]
					self.states[state].postNoreaster(cstl,head[0],head[1],head[2],row[i])
					# print '    POSTED',


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
