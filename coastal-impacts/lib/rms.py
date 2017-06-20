'''
Proecss RMS storm data for the slimpacts package
'''


import pandas as pd, numpy as np
import re
import os, traceback

DEFAULT_RMS_DATA = 'data/RMSData'
DEFAULT_NOREASTER_FILE = 'noreaster/WinterStorm_Noreaster_LossEstimates_20140321.tsv'

coastline = {st:st for st in ['HI','AK','OR','WA','CA','TX','LA','MS','AL','ME','MA','NH','RI','CT','NY','NJ','DE','MD','DC','VA','NC','SC','GA','FL','PA']}
coastline['WV'] = 'VA'
coastline['VT'] = 'NH'

class HurricaneFile(object):
	'''
	Reads in an RMS hurricane damage projection file

	Designed to parse hurricane damage projections from within the RMSData/Historical,
	RMSData/45_Climatology, and RMSData/85_MEAN_B_Climatology directories. For these
	files, the file name is parsed to return metadata, and the data is formatted into
	a standardized pandas DataFrame.

	Instances of this class are designed to be controlled by HurricaneSet objects, but
	may stand alone for inspection of specific hurricane files. That this class is not 
	intended to be used for Noreasters. These should be parsed with NoreasterFile 
	objects.

	Note that data is presented as-is in objects of this type, and no adjustment has 
	been made for the RMS Climatology phase-in from 2010 to 2100. This phase-in 
	adjustment is made in the StormDatabase class.
	'''

	HURRICANE_PARSER = re.compile(r'(?P<fintype>(Insurable|Economic))\.(?P<type>AAL)\.((?P<year>[0-9]{4})_)?((q)?(?P<probability>(Base|(?<=[0-9]{4}_q)([0-9]+(\.[0-9](?=\.))?))))?(\.(?P<year2>[0-9]{4}))?\.csv')

	def __init__(self, filepath):
		''' Initialize a HurricaneFile object with the full path to the individual hurricane file '''
		self.filepath = filepath

	def parse_name(self):
		''' Parse the filename to recover hurricane metadata '''

		filename = os.path.basename(self.filepath)

		fparse = re.match(self.HURRICANE_PARSER,filename)
		
		if not fparse:
			raise ValueError('File name {f} not parsed successfully. Check name specification.'.format(f=filename))

		self.fintype = fparse.group('fintype')
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
		''' Read data into a pandas DataFrame and check data consistency '''

		data = pd.read_csv(self.filepath, index_col=range(3))
		data['YEAR'] = self.year
		data['QUANTILE'] = self.probability
		data.set_index(['YEAR','QUANTILE'], inplace=True, append=True)

		rename_loss = lambda l: l[:-5] if len(l) > 5 else 'TOTAL'
		data.columns = pd.MultiIndex.from_tuples([(rename_loss(c[0]).upper(), c[1].upper() if len(c) == 2 else 'TOTAL') for c in data.columns.str.split('.')])
		data.columns.names = ['SECTOR', 'MECHANISM']


		totals = data.xs('TOTAL', axis=1, level='SECTOR')
		non_totals = data.iloc[:,data.columns.get_level_values('SECTOR') != 'TOTAL'].sum(level='MECHANISM', axis=1)

		try:
			assert (abs(non_totals - totals) < 1e0).all().all(), "Mechanism totals (wind, surge) do not add up to totals for each loss sector in {}".format(self.filepath)
			assert (abs(totals[[c for c in totals.columns if c != 'TOTAL']].sum(axis=1) - totals['TOTAL']) < 1e0).all(), "Loss sectors (BI, DIRECT) do not add up to total in {}".format(self.filepath)
		except AssertionError, e:
			print(e)
			return data

		data = pd.DataFrame(data.stack(['SECTOR','MECHANISM']), columns = ['VALUE'])

		# Drop totals - handle each subsector separately
		data = data.query('SECTOR != "TOTAL"')
		
		self.data = data



class HurricaneSet(object):
	'''
	Reads in the complete set of hurricane files for a historical or climatological run

	For each file in the directory passed to __init__, a HurricaneFile object is created 
	to parse the filepath and format the data into a pandas DataFrame object. These are 
	concatenated into a complete hurricane dataset and are then paired with the local 
	sea level values corresponding to the state, year, and quantile.

	Note that data is presented as-is in objects of this type, and no adjustment has 
	been made for the RMS Climatology phase-in from 2010 to 2100. This phase-in 
	adjustment is made in the StormDatabase class.
	'''

	def __init__(self, directory='RMSData/Historical'):
		''' Initialize a HurricaneSet object with the enclosing directory of all hurricane files '''
		self.directory = directory

	def read_all(self):
		''' Iterate and parse all files in self.directory and assign LSL values by state/year/quantile '''

		self.data = pd.DataFrame([])

		ee = Exposure('data/RMSData/EastCoastExposureBelow.tsv')
		ee.read()
		ee.convert('mm')
		we = Exposure('data/RMSData/WestCoastExposureBelow.tsv')
		we.read()
		we.convert('mm')

		assert ee.unit == we.unit, 'Different units found for East Coast and West Coast LSL measures. Align units.'


		exposure = pd.concat([ee.data, we.data], axis=0)

		for f in os.listdir(self.directory):
			if not re.search(HurricaneFile.HURRICANE_PARSER, f):
				continue
			h = HurricaneFile(os.path.normpath(os.path.join(self.directory, f)))

			try:
				h.parse_name()
				if h.fintype == 'Economic':
					continue

				h.read()
				self.data = self.data.append(h.data)
			except (AssertionError, ValueError), e:
				print(e)

		# return exposure

		self.data['LSL'] = exposure.loc[[(y, q, 'ALL', coastline[st]) for y, q, st in self.data.reset_index()[['YEAR','QUANTILE','STATE']].values]]['LSL'].values
		self.data.set_index('LSL', inplace=True, append=True)



class NoreasterFile(object):
	'''
	Read in RMS Noreaster damage file and format data into pandas DataFrame

	All data associated with Noreaster damages are contained in a single file, so objects
	of this type are not meant to be driven by a corresponding NoreasterSet file as are 
	the HurricaneFile objects. Instead, this data is used directly.
	'''

	def __init__(self, filepath=None):
		''' Initialize NoreasterFile object with full path to noreaster damage file '''
		
		self.filepath = filepath if filepath is not None else os.path.join(DEFAULT_RMS_DATA, DEFAULT_NOREASTER_FILE)

	def parse_name(self):
		''' Parse file name to ensure file is a valid Noreaster file '''
		
		filename = os.path.basename(self.filepath)
		assert re.search(r'^WinterStorm_Noreaster_LossEstimates_[0-9]+.tsv$', filename), "Filename not parsed correctly. Check name specification."

	def read(self):
		''' Read in data, format, and associate with LSL values by state/year/quantile '''

		data         = pd.read_csv(self.filepath, sep='\t', index_col=[0,1,2], header=[0,1,2])
		index        = pd.read_csv(self.filepath, sep='\t', index_col=[0,1,2], header=None, nrows=3).fillna(method='pad', axis=1).reset_index(drop=True)
		data.columns = pd.MultiIndex.from_tuples([tuple(index.values[:,i]) for i in range(index.values.shape[1])])
		
		mechanisms = {'AAL': 'TOTAL', 'AAL (Direct)': 'DIRECT', 'AAL (BI)': 'BI'}

		data.dropna(axis=1, how='all', inplace=True)

		data.index.names = ['LOB','STATE','COASTALFLAG']
		data.columns.names = ['VARIABLE','INDEX','SECTOR']

		wind = data.xs('Noreaster Loss (Wind Snow Ice & Freeze)',level='VARIABLE',axis=1).copy()
		wind.columns = [mechanisms.get(c) for c in wind.columns.get_level_values('SECTOR')]
		wind.columns.names = ['SECTOR']
		data.columns = data.columns.set_levels([float(q.strip('Q')) for q in data.columns.levels[data.columns.names.index('INDEX')]], level='INDEX')

		surge_q50  = data.xs('Surge Losses : Q50 by Decade', level='VARIABLE', axis=1).copy()

		# surge_2100 is inaccurately labeled 2010 by Quantile, except for the median, which is 2050
		# This was validated by graphing LSL by damage and checking monotonicity
		# Therefore we exclude 2050's median from the quantile distribution and then set the other
		# quantiles to correspond to 2100
		surge_2100 = data.xs('Surge Losses : 2010 by Quantile', level='VARIABLE', axis=1).copy()

		# since we just asserted the 2050 medians are duplicates, drop one of them
		surge_2100 = surge_2100[[c for c in surge_2100.columns if c[0] != 50]]

		wind['YEAR'] = 2010
		wind['QUANTILE'] = 50
		wind['MECHANISM'] = 'WIND'
		wind.set_index(['YEAR','QUANTILE','MECHANISM'], inplace=True, append=True)
		wind = pd.DataFrame(wind.stack(), columns = ['VALUE'])
		wind.index = wind.index.reorder_levels(['LOB','STATE','COASTALFLAG','YEAR','QUANTILE','SECTOR','MECHANISM'])


		surge_2100.columns.names = ['QUANTILE','DAMAGE_TYPE']
		surge_2100 = pd.DataFrame(surge_2100.stack(['QUANTILE','DAMAGE_TYPE']), columns=['VALUE'])
		
		surge_2100['YEAR'] = 2100 # 2050
		split_dtype = surge_2100.index.get_level_values('DAMAGE_TYPE').str.split('.', 1).tolist()
		finder = re.compile(r'^(?P<sector>.*)_LOSS$')
		parser = lambda dam: 'TOTAL' if not re.search(finder, dam) else re.search(finder, dam).group('sector').upper()
		split_index = pd.MultiIndex.from_tuples([(parser(s[0]), s[1].upper()) for s in split_dtype], names=['SECTOR','MECHANISM'])
		surge_2100.set_index(split_index, append=True, inplace=True)
		surge_2100.reset_index('DAMAGE_TYPE', drop=True, inplace=True)
		surge_2100.set_index('YEAR', inplace=True, append=True)
		surge_2100.index = surge_2100.index.reorder_levels(['LOB','STATE','COASTALFLAG','YEAR','QUANTILE','SECTOR','MECHANISM'])


		surge_q50.columns.names = ['YEAR','DAMAGE_TYPE']
		surge_q50 = pd.DataFrame(surge_q50.stack(['YEAR','DAMAGE_TYPE']), columns=['VALUE'])
		
		surge_q50['QUANTILE'] = 50.0
		split_dtype = surge_q50.index.get_level_values('DAMAGE_TYPE').str.split('.', 1).tolist()
		finder = re.compile(r'^(?P<sector>.*)_LOSS$')
		parser = lambda dam: 'TOTAL' if not re.search(finder, dam) else re.search(finder, dam).group('sector').upper()
		split_index = pd.MultiIndex.from_tuples([(parser(s[0]), s[1].upper()) for s in split_dtype], names=['SECTOR','MECHANISM'])
		surge_q50.set_index(split_index, append=True, inplace=True)
		surge_q50.reset_index('DAMAGE_TYPE', drop=True, inplace=True)
		surge_q50.set_index('QUANTILE', inplace=True, append=True)
		surge_q50.index = surge_q50.index.reorder_levels(['LOB','STATE','COASTALFLAG','YEAR','QUANTILE','SECTOR','MECHANISM'])

		# ignore Nor'easter wind damage - it doesn't change with year/LSL

		data = pd.concat([surge_2100, surge_q50], axis=0)

		# Drop totals - handle each subsector separately
		data = data.query('SECTOR != "TOTAL"')

		# Get LSL data and add to index

		ee = Exposure('data/RMSData/EastCoastExposureBelow.tsv')
		ee.read()
		ee.convert('mm')
		we = Exposure('data/RMSData/WestCoastExposureBelow.tsv')
		we.read()
		we.convert('mm')

		assert ee.unit == we.unit, 'Different units found for East Coast and West Coast LSL measures. Align units.'

		exposure = pd.concat([ee.data, we.data], axis=0)

		# Drop noreaster data for states with no storm gauge (assume unaffected by sea level rise)
		data = data.iloc[np.in1d(data.index.get_level_values('STATE'), coastline.keys()), :]

		data['LSL'] = exposure.loc[[(y, q, 'ALL', coastline[st]) for y, q, st in data.reset_index()[['YEAR','QUANTILE','STATE']].values]]['LSL'].values
		data.set_index('LSL', inplace=True, append=True)

		data.index = data.index.reorder_levels(['LOB','STATE','COASTALFLAG','YEAR','QUANTILE','SECTOR','MECHANISM','LSL'])
		data.sort_index(inplace=True)

		self.data = data



class Exposure(object):
	STANDARD_UNIT = 'cm'
	STANDARDIZE = {
		'ft': np.float64('30.48'), 
		'in': np.float64('2.54'), 
		'mm': np.float64('0.1'), 
		'm':  np.float64('100'), 
		'cm': np.float64('1')}

	DEFAULT_EXPOSURE_FILES = {
		'west': 'data/RMSData/WestCoastExposureBelow.tsv',
		'east': 'data/RMSData/EastCoastExposureBelow.tsv'
	}

	COASTS = {
		'west' : ['HI','AK','OR','WA','CA'],
		'east' : ['TX','LA','MS','AL','ME','MA','NH','RI','CT','NY','NJ','DE','MD','DC','VA','NC','SC','GA','FL','PA','WV','VT']
	}

	SL_MEAS = ['MSL','MHHW']

	LOBS = ['ALL','AUTO','RES','COM']

	def __init__(self, filepath=None, unit=None, coast=None):
		assert ((filepath is not None) or (coast is not None)), "Filepath or coast argument required"
		
		self.coast = coast

		if filepath is None:
			assert self.coast.lower() in self.DEFAULT_EXPOSURE_FILES.keys(), "Coast {} not recognized. Choose 'west' or 'east'".format(coast)
			filepath = self.DEFAULT_EXPOSURE_FILES[self.coast.lower()]

		if self.coast is None:
			for coast in self.COASTS.keys():
				if filepath.lower().find(coast) > -1:
					self.coast = coast
					break

		assert self.coast is not None, "Provide coast argument or specify filepath with coast name embedded."

		self.filepath = filepath

		if unit is not None:
			assert unit in self.STANDARDIZE, "Exposure standard unit {} not recognized. Check unit definitions.".format(unit)
		self.unit = unit

	def read(self):
		self.data = pd.read_csv(self.filepath, sep='\t', index_col=range(4), na_values=['-','-'])

		assert list(self.data.columns[:-1]) == ['ExposureBelowMSL','ExposureBelowMSL+TideBuffer','CoastalExposurebyLOB','%ofexposurebelowMSL','%ofexposurebelowMSL.1'], "Columns not recognized. Do your job. {}".format(self.data.columns)
		self.data.columns = ['ExposureMSL', 'ExposureMHHW', 'ExposureByLOB', 'PctExposureMSL','PctExposureMHHW', self.data.columns[-1]]
		
		# correct types
		for col in ['ExposureMSL', 'ExposureMHHW', 'ExposureByLOB']:
			if self.data[col].apply(lambda x: isinstance(x, str)).all():
				self.data[col] = self.data[col].replace(re.compile(r'^[a-zA-Z\W\s]+$'), np.nan).astype(np.float64)
		for col in ['PctExposureMSL','PctExposureMHHW']:
			if self.data[col].apply(lambda x: isinstance(x, str)).all():
				self.data[col] = self.data[col].str.strip('%').replace(re.compile(r'^[a-zA-Z\W\s]+$'), np.nan).astype(np.float64)/100

	def convert(self, unit='mm'):
		if self.unit is None:
			ufinder = re.compile(r'^MSL\((?P<unit>({}))\)$'.format('|'.join(self.STANDARDIZE.keys())))
			for c in self.data.columns:
				if re.search(ufinder, c):
					self.unit = re.search(ufinder, c).group('unit')
					break

		if self.unit is None:
			raise ValueError('Unit not recognized. Check spelling and rms.Exposure.STANDARDIZE specification.'.format(unit))

		else:
			assert 'MSL({})'.format(self.unit) in self.data.columns, '"MSL({})" not found in exposure dataset header. Check units.'.format(self.unit)

		self.data.columns = [c if c != 'MSL({})'.format(self.unit) else 'LSL' for c in self.data.columns]
		assert unit in self.STANDARDIZE, "Conversion unit {} not recognized. Check unit definitions.".format(unit)

		self.data['LSL'] = self.data['LSL']*(self.STANDARDIZE[self.unit]/self.STANDARDIZE[unit])

		self.unit = unit

	def interpolate(self):
		self.exposure = {}

		exposure_data = self.data.copy()
		exposure_data.set_index('LSL', append=True, inplace=True)

		def make_interpolator(series):
			return lambda lsl: np.interp(lsl, series.index.get_level_values('LSL').values, series.values)

		def dummy_interpolator(lsl):
			''' Return 0 for any lsl '''
			return np.interp(lsl, [-10,10], [0,0])

		exposure_data = exposure_data[['ExposureMSL','ExposureMHHW']].fillna(0)
		exposure_data = exposure_data.reset_index(['YEAR','MSL.Q'], drop=True)
		exposure_data = exposure_data.sort_index()

		self.exposure['MSL']  = exposure_data['ExposureMSL'].groupby(level=['STATE','LOB']).apply(make_interpolator)
		self.exposure['MHHW'] = exposure_data['ExposureMHHW'].groupby(level=['STATE','LOB']).apply(make_interpolator)

		for sl in self.SL_MEAS:
			missing = [(st,lob) for st in self.COASTS[self.coast] for lob in self.LOBS if not (st, lob) in self.exposure[sl].index]
			self.exposure[sl] = self.exposure[sl].append(pd.Series([dummy_interpolator for _ in missing], index=pd.MultiIndex.from_tuples(missing)))



class StormDatabase(object):
	'''
	Read in all RMS storm damage files and adjust Climatology estimates for phase-in

	Usage:

		[1] db = StormDatabase()
		[2] db.add_historical()
		[3] db.historical.loc[('ALL','FL',1,'TOTAL','total')]
		<function <lambda> at 0x0000000000000000>
		
		[4] db.historical.loc[('ALL','FL',1,'TOTAL','total')](500)
		19207013219.051346
		
		[5] db.historical.loc[('ALL','FL',1,'TOTAL','total')](np.arange(0,1000,100))
		array([  1.28822663e+10,   1.36922779e+10,   1.46080328e+10,
		         1.61752378e+10,   1.78289241e+10,   1.92070132e+10,
		         2.07314345e+10,   2.22885991e+10,   2.40252953e+10,
		         2.58686233e+10])

	'''

	def __init__(self, directory=DEFAULT_RMS_DATA):
		self.directory = directory

		self._read_historical = False
		self.clim_source = {}
		self.climatological = {}
		self.clim_adjusted = {}

	def add_historical(self, hist_dir='Historical'):
		'''
		Read all historical hurricane files and create interpolator Series

		Accepts a directory path, which is passed to a HurricaneSet object and read

		Returns a pandas Series object indexed by LOB, STATE, COASTALFLAG, SECTOR, and MECHANISM 
		containing lambda functions of numpy.interp objects

		'''

		hist = HurricaneSet(os.path.join(self.directory, hist_dir))
		hist.read_all()
		self.hist_source = hist.data.sort_index()

		# Exclude LOB != ALL,  MECHANISM != TOTAL
		self.hist_source = self.hist_source.xs('ALL', level='LOB')
		self.hist_source = self.hist_source.xs('TOTAL', level='MECHANISM')

		self.historical = self.get_interpolator(self.hist_source.copy())

		self._read_historical = True


	def add_climatological(self, name = 'rcp85', clim_dir = '85_update/CMIP5.RCP8.5.MEAN.B.v2.Climatology-2014-05-22'):
		if (not self._read_historical):
			raise ValueError('Read historical estimates before adding climatological data')

		if not ((hasattr(self.historical, 'shape')) and (len(self.historical) > 0)):
			raise ValueError('Historical estimates not read correctly')

		clim = HurricaneSet(os.path.join(self.directory, clim_dir))
		clim.read_all()

		data = clim.data.sort_index()

		# Exclude LOB != ALL,  MECHANISM != TOTAL
		data = data.xs('ALL', level='LOB')
		data = data.xs('TOTAL', level='MECHANISM')

		adj = self.adjust_climatological(data.copy())

		# return data, adj
		assert (abs(data.xs(2100, level='YEAR') - adj.xs(2100, level='YEAR')) < 1).all().all(), "2100 data improperly adjusted. Check methodology."

		self.clim_source[name] = data
		# self.climatological[name] = self.get_interpolator(data)
		self.clim_adjusted[name] = self.get_interpolator(adj)

	def add_noreaster(self, noreaster_file = DEFAULT_NOREASTER_FILE):
		noreaster = NoreasterFile(os.path.join(self.directory,noreaster_file))
		noreaster.parse_name()
		noreaster.read()

		self.noreaster_source = noreaster.data


		# Exclude LOB != ALL,  MECHANISM != SURGE
		self.noreaster_source = self.noreaster_source.xs('ALL', level='LOB')
		self.noreaster_source = self.noreaster_source.xs('SURGE', level='MECHANISM')

		self.noreaster = self.get_interpolator(self.noreaster_source)

	def get_interpolator(self, data):

		def enforce_monotonic_increase(data):
		  return data.groupby(level=['STATE','COASTALFLAG','SECTOR']).apply(lambda x: x.where(x.diff().fillna(0)>=0, np.nan))

		# interpolate to fill missing points:
		# data[data == 0] = np.nan
		data.index = data.index.reorder_levels(['STATE','COASTALFLAG','SECTOR','LSL','YEAR','QUANTILE'])
		data.reset_index(['YEAR','QUANTILE'], drop=True, inplace=True)
		data = data.sort_index()

		data = enforce_monotonic_increase(data)

		while np.isnan(data.values).any():
		  data = data.dropna()
		  data = enforce_monotonic_increase(data)
		
		def fill_df(df):
			if len(df.dropna()) < 2:
				return df
			else:
				return pd.Series(df.reset_index([c for c in df.index.names if c != 'LSL'])['VALUE'].interpolate('slinear').values, index=df.index)

		data = data.groupby(level=['STATE','COASTALFLAG','SECTOR']).apply(fill_df)
		data = data.fillna(0)

		# create interpolating function of LSL
		interp = lambda g: (lambda x: np.interp(x, g.index.get_level_values('LSL').values, g.values if len(g.shape) == 1 else g.iloc[:,0].values))
		interpolated = data.sort_index().groupby(level=['STATE','COASTALFLAG','SECTOR']).apply(interp)
		return interpolated

	def adjust_climatological(self, data):
		'''
		Adjust for RMS Climatology phase-in
		
		We accomplish this by dividing by the value used in scaling, (year-2010)/(2100-2010), and 
		replacing NaN and divide by zero errors with 0 (setting Climatological damages with 0 LSL 
		change to the Historical value). This neglects differences in the hurricane activity at these 
		levels, but there is no way to recover this data from the format provided by RMS. Also, 
		because we subtract hurricane damages from base-year damages to derive changes in damages 
		attributable to climate change, the impact of this error is zero in the final results.
		'''

		data = data.copy()
		
		scalefactor = (1.0 / (((data.index.get_level_values('YEAR').values) - 2010).astype('float64') / (2100 - 2010)))
		scalefactor[np.isinf(scalefactor) | np.isnan(scalefactor)] = 0
		data['VALUE'] = (data['VALUE'] - self.hist_source['VALUE']) * scalefactor + self.hist_source['VALUE']

		return data