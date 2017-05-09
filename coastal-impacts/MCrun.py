import numpy as np
import scipy.interpolate as interpolate
import lib.damageParse, config.StateExposure
#import matplotlib.pyplot as plt
import math, os, os.path, argparse, subprocess, re

mm_to_ft = 1.0/25.4/12

MC_DIR = '../working_outputs/mc_temp/'
tempdir = '../temp/'
GAMSDIR = {
	'rcp85':'/mnt/superBlock04B/coastal/',
	'rcp60':'/mnt/superBlock03/coastal/',
	'rcp45':'/mnt/superBlock02B/coastal/',
	'rcp26':'/mnt/superBlock01/coastal/'}

if not os.path.isdir(MC_DIR):
	os.mkdir(MC_DIR)

class LSLProjection(object):
  '''
  Reads LSLprojMC files into numpy arrays column-by-column and provides an interpolated interface to individual Monte-Carlo samples
  '''

	@classmethod
	def getGaugeByID(cls,gaugeID,rcp):
		'''return a LSLProjection object matching the tide gauge ID and RCP arguments'''
		return cls('../NorthAmerica/LSLprojMC_{id}_{rcp}.tsv'.format(id=gaugeID,rcp=rcp))
	def __init__(self,filename,numProjections=10000):
		self.filename = filename
		self.numProjections = numProjections
		self.years = np.loadtxt(self.filename,dtype=int,delimiter='\t',skiprows=1,usecols=(0,))
	def getProjectionByID(self,ID):
		'''returns a scipy.interpolate.interp1d object linearly interpolating LSL[ft] as a function of year'''
		#	load projected LSL -- AND CONVERT TO FEET --
		raw = np.loadtxt(self.filename,dtype=float,delimiter='\t',skiprows=1,usecols=(ID+1,))*mm_to_ft

		return interpolate.interp1d(self.years,np.array(raw))
	def getProjection(self):
		'''yields the next scipy.interpolate.interp1d object in the (ordered) list of runs'''
		for proj in range(self.numProjections):
			yield self.getProjectionByID(proj)

class Impact(object):
#	Impact					Provides an interface to the set of 5 damage types as scipy.interpolate.interp1d objects
#	Methods:				allDamage						provides complete set of inundation, direct, and BI damages given lsl[, hurricane type, and year]			

	def __init__(self,state,inundation,noreaster,hist,rcp45,rcp85):
		self.state = state
		self.inundation	= inundation
		self.noreaster	=	noreaster
		self.hist				=	hist
		self.rcp45			=	rcp45
		self.rcp85			=	rcp85

	def getDamage(self,damageType,category,lsl,year=None):
		if damageType in ['inundation','noreaster','hist']:
			damage = 0
			if self.state+'_coast' in self.__dict__[damageType]:
				damage += self.__dict__[damageType][self.state+'_coast'][category](lsl)
			if self.state+'_inland' in self.__dict__[damageType]:
				damage += self.__dict__[damageType][self.state+'_inland'][category](lsl)
		elif damageType in ['rcp45','rcp85']:
			if year is None:
				raise OSError('Year parameter required to retrieve damages from Climatological damage functions')

			#	Find historical damage
			histDamage = 0
			if self.state+'_coast' in self.__dict__['hist']:
				histDamage += self.__dict__['hist'][self.state+'_coast'][category](lsl)
			if self.state+'_inland' in self.__dict__['hist']:
				histDamage += self.__dict__['hist'][self.state+'_inland'][category](lsl)

			#	Find damages with potential activity changes
			activDamage = 0
			if self.state+'_coast' in self.__dict__[damageType]:
				activDamage += math.fsum([self.__dict__[damageType][self.state+'_coast'][m][category](lsl) 
						for m in self.__dict__[damageType][self.state+'_coast'].keys()])/len(self.__dict__[damageType][self.state+'_coast'].keys())
			if self.state+'_inland' in self.__dict__[damageType]:
				activDamage += math.fsum([self.__dict__[damageType][self.state+'_inland'][m][category](lsl) 
						for m in self.__dict__[damageType][self.state+'_inland'].keys()])/len(self.__dict__[damageType][self.state+'_inland'].keys())

			#	Linearly combine the two given the year
			damage = histDamage + float(year-2010)/(2100-2010) * (activDamage-histDamage)

		else:
			raise OSError('damageType {t} not recognized'.format(t=damageType))

		return damage

	def alldamage(self,lsl,hurr='hist',year=None):
		inundation = self.getDamage('inundation','Direct',lsl)
		direct = self.getDamage(hurr,'Direct',lsl,year) + self.getDamage('noreaster','Direct',lsl)
		BI = self.getDamage(hurr,'BI',lsl,year) + self.getDamage('noreaster','BI',lsl)
		return inundation, direct, BI

class ConfigData(object):
	'''
	Initialize data for use in the monte carlo simulation

	Instance vars:	
		state_station_map														Mapping of states to tide gauge IDs
		station_map																	Mapping of tide gauge IDs to a list of states using that gauge as an indicator
		inundation, noreaster, hist, rcp45, rcp85		dicts of scipy.interpolate.interp1d objects projecting damage by LSL
		proj																				dict of LSLProjection objects projecting LSL by year
		exposure																		dict of property exposed by coastal state region
		impacts																			dict of Impact objects by state
		ncaRegs																			dict of lists of states indexed by NCA region
		getNCAreg																		dict of NCA regions indexed by state
	'''
	
	def __init__(self,rcp):																			
		#	Get gaugeIDs by state, [states] by gaugeID (respectively) from getStationMap()
		self.state_station_map,self.station_map = getStationMap()

		#	Get damage extrapolators from lib.damageParse.getDamage()
		self.inundation,self.noreaster,self.hist,self.rcp45,self.rcp85 = lib.damageParse.getDamage()

		#	Initialize LSL projectors for each gauge
		self.proj = {}
		for gauge in self.station_map:
			self.proj[gauge] = LSLProjection('../NorthAmerica/LSLprojMC_{id}_{rcp}.tsv'.format(id=gauge,rcp=rcp))

		#	Get state capital exposure totals:
		self.exposure = {}
		self.exposure = {st[0:2]:0 for st in config.StateExposure.Exposure.keys()}
		for st in self.exposure.keys():
			if st+'_Inland' in config.StateExposure.Exposure.keys():
				self.exposure[st] += math.fsum([v for k,v in config.StateExposure.Exposure[st+'_Inland'].items() if k in ['Building','Contents']])
			if st+'_Coastal' in config.StateExposure.Exposure.keys():
				self.exposure[st] += math.fsum([v for k,v in config.StateExposure.Exposure[st+'_Coastal'].items() if k in ['Building','Contents']])

		#	Initialize impact extrapolator for each state
		self.impacts = {}
		for state in self.state_station_map:
			self.impacts[state] = Impact(state,self.inundation,self.noreaster,self.hist,self.rcp45,self.rcp85)

		#	Create NCA regions
		self.ncaRegs = getNCA()

		self.getNCAreg = {i:k for k,v in self.ncaRegs.items() for i in v}

class OutputData(object):
	def __init__(self,rcp,hurr,histograms=True,gamsfiles=False):
		ncaregs = getNCA()
		self.state_station_map,self.station_map = getStationMap()
		self.yrs = [2030,2050,2100]
		self.txtyrs = [str(yr) for yr in self.yrs]
		self.yrranges = {yr:[yr] for yr in self.yrs}
		self.tps = range(2020,2100,20)
		self.tpranges = {tp:range(tp,tp+20) for tp in self.tps}
		self.txttps = ['{tp1}to{tp2}'.format(tp1=tp,tp2=tp+19) for tp in self.tps]
		self.allyears = range(2010,2101)

		if histograms:

			self.periodFiles = {}
			self.yearlyFiles = {}

			for state in self.state_station_map:
				self.periodFiles[state] = WriteFile(MC_DIR,rcp,hurr,state,self.txttps,'20yr')
				self.yearlyFiles[state] = WriteFile(MC_DIR,rcp,hurr,state,self.txtyrs,'annual')

			for nca in ncaregs.keys():
				self.periodFiles[nca] = WriteFile(MC_DIR,rcp,hurr,nca,self.txttps,'20yr')
				self.yearlyFiles[nca] = WriteFile(MC_DIR,rcp,hurr,nca,self.txtyrs,'annual')

			self.periodFiles['USA'] = WriteFile(MC_DIR,rcp,hurr,'USA',self.txttps,'20yr')
			self.yearlyFiles['USA'] = WriteFile(MC_DIR,rcp,hurr,'USA',self.txtyrs,'annual')

class GamsFile(object):
	def __init__(self,gmsdir,rcp,hurr,mcrun,yearset,regset):
		self.gmsdir		=	gmsdir
		self.rcp			=	rcp
		self.hurr			=	hurr
		self.mcrun		=	mcrun
		self.yearset	= yearset
		self.regset		=	regset

		self.filepaths = ['{gmsdir}{rcp}_{h}_{r}_{imp}.gms'.format(gmsdir=self.gmsdir,rcp=self.rcp,h=self.hurr,r=self.mcrun,imp=imp)
				for imp in ['inundation','direct','bi']]

		self.createFiles()

	def createFiles(self):
		for fp in self.filepaths:
			with open(fp,'w+') as wfile:
				wfile.write('set years "years in the projection" /{yrs}/;\n\nset regions "regions in the projection" /{regs}/;\n\nparameter impact /\n'.format(yrs=','.join([str(i) for i in self.yearset]),regs=','.join([str(i) for i in self.regset])))

	def post(self,state,year,inund,direct,bi):
		with open(self.filepaths[0],'a') as wfile:
			wfile.write('{st}.{y} {i}\n'.format(st=state,y=year,i=inund))

		with open(self.filepaths[1],'a') as wfile:
			wfile.write('{st}.{y} {i}\n'.format(st=state,y=year,i=direct))

		with open(self.filepaths[2],'a') as wfile:
			wfile.write('{st}.{y} {i}\n'.format(st=state,y=year,i=bi))

	def close(self):
		gdxes = []
		for fp in self.filepaths:
			with open(fp,'a') as wfile:
				wfile.write('/;')
			pmatch = re.match(r'(?P<path>[\\\/]*([a-zA-Z0-9]+[\\\/])+)(?P<prefix>rcp[0-9]{2}_[^_]+_[0-9]+_)(?P<dType>(inundation|bi|direct))(\.gms)',fp)
			if pmatch is None:
				raise OSError('file name not recognized:\t'+fp)
			path = pmatch.group('path')
			prefix = pmatch.group('prefix')
			dType = pmatch.group('dType')
			subprocess.call('gams {fp} -gdx={gdx} -o={lst}'.format(fp=path+prefix+dType,gdx=tempdir+dType+'.gdx',lst='slfile.lst'),shell=True)
			gdxes.append(tempdir+dType+'.gdx')
		subprocess.call('gdxmerge output={gmsdir}coastal_{rcp}_{h}_{r}.gdx {files}'.format(gmsdir=self.gmsdir,rcp=self.rcp,h=self.hurr,r=self.mcrun,files=' '.join(gdxes)),shell=True)


class WriteFile(object):
	def __init__(self,mcdir,rcp,hurr,reg,periods,pertype):
		self.mcdir		= mcdir
		self.rcp			= rcp
		self.hurr			= hurr
		self.reg			= reg
		self.periods	= periods
		self.pertype	= pertype

		self.filepath	= '{mcdir}{rcp}_{h}_{rg}_{pt}.csv'.format(mcdir=MC_DIR,rcp=rcp,h=hurr,rg=reg,pt=pertype)

		self.createFile()

	def createFile(self):
		with open(self.filepath,'w+') as wfile:
			wfile.write(','.join([','.join([dtype for yr in self.periods]) for dtype in ['IN','DI','BI','TOT']]))
			wfile.write('\n{yrs},{yrs},{yrs},{yrs}\n'.format(yrs=','.join(self.periods)))

	def writeoutdata(self,data):
		with open(self.filepath,'a') as wfile:
			wfile.write(data)

def main(args):
	rcp 				= args.rcp
	if args.rcp == 'rcp60':
		rcp = 'rcp45'
	hurr 				= args.hurr
	iterstart		=	args.start
	iterations	= args.iter
	histograms 	= args.hist
	gamsfiles 	= args.gams

	data = ConfigData(rcp)
	outdata = OutputData(rcp,hurr)
	#plotdata()
	#return

	for run in range(iterstart,iterations):

		if histograms:

			natInund = {y:0 for y in outdata.allyears}
			natDirect = {y:0 for y in outdata.allyears}
			natBI = {y:0 for y in outdata.allyears}
			natInundInc = {y:0 for y in outdata.allyears}

			ncaInund = {nca:{y:0 for y in outdata.allyears} for nca in data.ncaRegs.keys()}
			ncaDirect = {nca:{y:0 for y in outdata.allyears} for nca in data.ncaRegs.keys()}
			ncaBI = {nca:{y:0 for y in outdata.allyears} for nca in data.ncaRegs.keys()}
			ncaInundInc = {nca:{y:0 for y in outdata.allyears} for nca in data.ncaRegs.keys()}

		if gamsfiles:

			gamsfile = GamsFile(GAMSDIR[args.rcp],rcp,hurr,run,outdata.allyears,sorted(data.state_station_map.keys()))

		for gauge in data.station_map:
			lsl = data.proj[gauge].getProjectionByID(run)
			lsl2010 = lsl(2010)	#	Index year for Sea level used in CALIBRATING damage curve is 2010
			for state in data.station_map[gauge]:
				stInund = {}
				stInundInc = {}
				if histograms:
					stDirect = {}
					stBI = {}

				inund2010, direct2010, bi2010 = data.impacts[state].alldamage(max(0,lsl(2010)-lsl2010),hurr,2010)
				inund2011, direct2011, bi2011 = data.impacts[state].alldamage(max(0,lsl(2011)-lsl2010),hurr,2011)

				maxInundLev = 0
				gamsInundLev = 0

				for yr in outdata.allyears:

					#	Get impacts from state damage curve corresponding to sea level in state (constrained to be positive)
					i,d,b = data.impacts[state].alldamage(max(0,lsl(yr)-lsl2010),hurr,yr)

					# if yr%20 == 0:
					# 	print(state,gauge,yr,lsl(yr)-lsl2010,i,d,b)

					#	Tabulate state data.exposure below sea level (inundation losses)
					stInund[yr] = max(i - inund2010,0)
					stInundInc[yr] = max(0,stInund[yr] - maxInundLev)
					maxInundLev = max(maxInundLev,stInund[yr])

					gamsInundLev = max((i-inund2011),gamsInundLev)

					if gamsfiles and yr >= 2011:
						gamsfile.post(state,yr,gamsInundLev,max(d-direct2011,0),max(b-bi2011,0))

					if histograms:

						#	Tabulate direct and BI costs, and discount by inundated property
						stDirect[yr] = max(d - direct2010,0)*max(0,data.exposure[state]-stInund[yr])/data.exposure[state]
						stBI[yr] = max(b - bi2010,0)*max(0,data.exposure[state]-stInund[yr])/data.exposure[state]
						

						natInund[yr] += stInund[yr]
						natDirect[yr] += stDirect[yr]
						natBI[yr] += stBI[yr]
						natInundInc[yr] += stInundInc[yr]

						ncaInund[data.getNCAreg[state]][yr] += stInund[yr]
						ncaDirect[data.getNCAreg[state]][yr] += stDirect[yr]
						ncaBI[data.getNCAreg[state]][yr] += stBI[yr]
						ncaInundInc[data.getNCAreg[state]][yr] += stInundInc[yr]

				if histograms:

					outdata.periodFiles[state].writeoutdata('{IN},{DI},{BI},{TOT}\n'.format(
							IN=','.join(['{i}'.format(i=(math.fsum([float(stInund[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
							DI=','.join(['{i}'.format(i=(math.fsum([float(stDirect[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
							BI=','.join(['{i}'.format(i=(math.fsum([float(stBI[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
							TOT=','.join(['{i}'.format(i=(math.fsum([float(stDirect[yr]+stBI[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps])))

					outdata.yearlyFiles[state].writeoutdata('{IN},{DI},{BI},{TOT}\n'.format(
							IN=','.join(['{i}'.format(i=(math.fsum([float(stInund[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
							DI=','.join(['{i}'.format(i=(math.fsum([float(stDirect[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
							BI=','.join(['{i}'.format(i=(math.fsum([float(stBI[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
							TOT=','.join(['{i}'.format(i=(math.fsum([float(stDirect[yr]+stBI[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs])))

		if gamsfiles:
			gamsfile.close()

		if histograms:

			for nca in data.ncaRegs.keys():

				outdata.periodFiles[nca].writeoutdata('{IN},{DI},{BI},{TOT}\n'.format(
					IN=','.join(['{i}'.format(i=(math.fsum([float(ncaInund[nca][yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
					DI=','.join(['{i}'.format(i=(math.fsum([float(ncaDirect[nca][yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
					BI=','.join(['{i}'.format(i=(math.fsum([float(ncaBI[nca][yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
					TOT=','.join(['{i}'.format(i=(math.fsum([float(ncaDirect[nca][yr]+ncaBI[nca][yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps])))

				outdata.yearlyFiles[nca].writeoutdata('{IN},{DI},{BI},{TOT}\n'.format(
					IN=','.join(['{i}'.format(i=(math.fsum([float(ncaInund[nca][yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
					DI=','.join(['{i}'.format(i=(math.fsum([float(ncaDirect[nca][yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
					BI=','.join(['{i}'.format(i=(math.fsum([float(ncaBI[nca][yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
					TOT=','.join(['{i}'.format(i=(math.fsum([float(ncaDirect[nca][yr]+ncaBI[nca][yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs])))

	
			outdata.periodFiles['USA'].writeoutdata('{IN},{DI},{BI},{TOT}\n'.format(
				IN=','.join(['{i}'.format(i=(math.fsum([float(natInund[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
				DI=','.join(['{i}'.format(i=(math.fsum([float(natDirect[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
				BI=','.join(['{i}'.format(i=(math.fsum([float(natBI[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps]),
				TOT=','.join(['{i}'.format(i=(math.fsum([float(natDirect[yr]+natBI[yr]) for yr in outdata.tpranges[tp]])/20)) for tp in outdata.tps])))

			outdata.yearlyFiles['USA'].writeoutdata('{IN},{DI},{BI},{TOT}\n'.format(
				IN=','.join(['{i}'.format(i=(math.fsum([float(natInund[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
				DI=','.join(['{i}'.format(i=(math.fsum([float(natDirect[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
				BI=','.join(['{i}'.format(i=(math.fsum([float(natBI[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs]),
				TOT=','.join(['{i}'.format(i=(math.fsum([float(natDirect[yr]+natBI[yr]) for yr in outdata.yrranges[tp]]))) for tp in outdata.yrs])))




def getStationMap():
	STATE_STATION_MAP = {	#	From Bob Kopp email "Re: LSL projection files corrupted" Tue 6/3/2014 6:26 AM

		#'HI':	155,		#	'HONOLULU - Hawaii',

		#'AK':	1067,		#	'ANCHORAGE - Alaska',
		
		'OR':	265,		#	'ASTORIA - Oregon',
		'WA':	127,		#	'SEATTLE - Washington',
		'CA':	10,			#	'SAN FRANCISCO - California',
		
		'TX':	161,		#	'GALVESTON II - Texas',
		'LA':	526,		#	'GRAND ISLE - Louisiana ',
		'MS':	246,		#	'PENSACOLA - Mississippi and Alabama',
		'AL':	246,		#	'PENSACOLA - Mississippi and Alabama',
		
		'ME':	183,		#	'PORTLAND - Maine',
		'MA':	235,		#	'BOSTON - Massachussets and New Hampshire',
		'NH':	235,		#	'BOSTON - Massachussets and New Hampshire',
		'RI':	351,		#	'NEWPORT - Rhode Island and Connecticut',
		'CT':	351,		#	'NEWPORT - Rhode Island and Connecticut',
		'NY':	12,			#	'NEW YORK - New York',
		'NJ':	180,		#	'ATLANTIC CITY - New Jersey',
		'DE':	224,		#	'LEWES - Delaware',
		'MD':	148,		#	'BALTIMORE - Maryland',
		'DC':	360,		#	'WASHINGTON DC - DC',
		'VA':	299,		#	'SEWELLS POINT - Virginia',
		'NC':	396,		#	'WILMINGTON - North Carolina',
		'SC':	234,		#	'CHARLESTON I - South Carolina',
		'GA':	395,		#	'FORT PULASKI - Georgia',
		'FL':	363,		#	'MIAMI BEACH - Florida'

		#	Additionally, we need a station for PA:
		'PA':	135,			#	'PHILADELPHIA', as per "You should use the Philadelphia tide gauge (135) for Pennsylvania." -- Tue 6/3/2014 6:26 AM

		#	Finally, map inland states to coastal gauges
		'WV':	299,
		'VT':	235

	}

	STATION_MAP = {}
	for state,station in STATE_STATION_MAP.items():
		if not station in STATION_MAP:
			STATION_MAP[station] = []
		STATION_MAP[station].append(state)

	return STATE_STATION_MAP,STATION_MAP

def plotdata(hurr):
	data = ConfigData()
	maplsl = np.linspace(0,20,50)
	lsl = np.linspace(0,20,200)
	slsmooth = np.linspace(0,20,1000)
	for st in data.impacts.keys():
		for i,imp in enumerate(['inundation', 'direct', 'BI']):
			try:
				plt.figure()
				smoother=interpolate.UnivariateSpline(maplsl,data.impacts[st].alldamage(maplsl,hurr)[i].flatten(),s=25,k=1)
				plt.plot(lsl,data.impacts[st].alldamage(lsl,hurr)[i].flatten(),'-',slsmooth,smoother(slsmooth),'-')
				plt.savefig('../curveFits/{st}_{i}.pdf'.format(st=st,i=imp))
			except AttributeError:
				pass
			except ValueError:
				pass
		try:
			plt.figure()
			smoother=interpolate.UnivariateSpline(maplsl,sum(data.impacts[st].alldamage(maplsl,hurr)),s=25,k=1)
			plt.plot(lsl,sum(data.impacts[st].alldamage(lsl,hurr)),'-',slsmooth,smoother(slsmooth),'-')
			plt.savefig('../curveFits/{st}_total.pdf'.format(st=st))
		except AttributeError:
			pass
		except ValueError:
			pass

def smooth(interp,x):
	return 0.1*interp(x-1) + 0.2*interp(x-0.5) + 0.4*interp(x) + 0.2*interp(x+0.5) + 0.1*interp(x+1)


def getNCA():

	NCAREGS = {}

	#	NCA Final Report
	#	Region Composition
	#	http://nca2014.globalchange.gov/system/files_force/downloads/low/NCA3_Full_Report_Intro_to_Regions_LowRes.pdf?download=1
	#	Page 370, Table 1



	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Northeast:
	#	Connecticut, Delaware, Maine, Maryland, Massachusetts, New Hampshire, New Jersey, New York, Pennsylvania, Rhode Island, Vermont, West Virginia, District of Columbia

	NCAREGS['NEA'] = set([
		'CT', 'DE', 'ME', 'MD', 'MA', 'NH', 'NJ', 'NY', 'PA', 'RI', 'VT', 'WV', 'DC'
	])

	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Southeast and Caribbean:
	#	Alabama, Arkansas, Florida, Georgia, Kentucky, Louisiana, Mississippi, North Carolina, South Carolina, Tennessee, Virginia, Puerto Rico, U.S. Virgin Islands

	NCAREGS['SEA'] = set([
		'AL', 'AR', 'FL', 'GA', 'KY', 'LA', 'MS', 'NC', 'SC', 'TN', 'VA'
	])

	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Midwest:
	#	Illinois, Indiana, Iowa, Michigan, Minnesota, Missouri, Ohio, Wisconsin

	NCAREGS['MWE'] = set([
		'IL', 'IN', 'IA', 'MI', 'MN', 'MO', 'OH', 'WI'
	])

	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Great Plains:
	#	Kansas, Montana, Nebraska, North Dakota, Oklahoma, South Dakota, Texas, Wyoming

	NCAREGS['GPL'] = set([
		'KS', 'MT', 'NE', 'ND', 'OK', 'SD', 'TX', 'WY'
	])

	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Northwest:
	#	Idaho, Oregon, Washington

	NCAREGS['NWE'] = set([
		'ID', 'OR', 'WA'
	])

	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Southwest:
	#	Arizona, California, Colorado, Nevada, New Mexico, Utah

	NCAREGS['SWE'] = set([
		'AZ', 'CA', 'CO', 'NV', 'NM', 'UT'
	])

	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Alaska:
	#	Alaska
	
	NCAREGS['ALK'] = set([
		'AK'
	])

	# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

	#	Hawai'i:
	#	Commonwealth of the Northern Mariana Islands, Federated States of Micronesia, Republic of the Marshall Islands, Republic of Palau, Territory of American Samoa, Territory of Guam

	NCAREGS['HWI'] = set([
		'HI'
	])

	return NCAREGS

def arg():
	parser = argparse.ArgumentParser(description='Read coastal impact data and run Monte Carlo Simulation of direct effects')
	parser.add_argument('-r','--rcp',type=str,default='rcp85',help='Set the RCP to run for this study')
	parser.add_argument('-s','--hurr',type=str,default='hist',help='Set the hurricane scenario to run for this study')
	parser.add_argument('-i','--iter',type=int,default=1000,help='Set the number of simulations to run in this study')
	parser.add_argument('-n','--start',type=int,default=0,help='start number for monte carlo export')
	#parser.add_argument('-I','--iter_all',default=False,help='Run all available monte carlo draws')
	parser.add_argument('-g','--gams',default=False,help='Export GAMS files',action='store_true')
	parser.add_argument('-t','--hist',default=False,help='Export histogram files',action='store_true')
	return parser.parse_args()


if __name__=="__main__":
	args = arg()
	main(args)
