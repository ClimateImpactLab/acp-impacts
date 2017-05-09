'''
Prepares local sea level (LSL) data for coastal damage simulations

Includes classes, data, and helper functions to prepare LSL data 
for use by the dev.simulation module of this package. Use the 
GaugeDatabase class to construct valid LSL scenarios.
'''



import os, re, StringIO
import pandas as pd, numpy as np, scipy.interpolate as interpolate
from collections import Iterable

import rms

HEADER = [(r, q)  for r in ('rcp85','rcp45','rcp26') for q in [0.001,0.005,0.01,0.025] + [float(i)/20 for i in range(1,20)] + [0.975,0.99,0.995,0.999]]

LSL_GAUGEDIR = 'data/NorthAmerica'
LSL_QUANTS = 'data/NorthAmerica/NorthAmerica_LSLproj_full_allquants.tsv'


def set_index_levels(index, level, levels, inplace=False):
	before = [index.levels[i].tolist() for i, lev in enumerate(index.names) if i < index.names.index(level)]
	after = [index.levels[i].tolist() for i, lev in enumerate(index.names) if i > index.names.index(level)]
	return index.set_levels(before + [levels] + after, inplace=inplace)

def replace_index_levels(index, level, by, inplace=False):
	if isinstance(by, dict):
		by = by.get
	return set_index_levels(index, level, [by(ele) for ele in index.levels[index.names.index(level)]], inplace=inplace)


class Gauge(object):
	'''
	'''
	def __init__(self, name, gauge_id, lat, lon, data, unit, coast=None, rcp=None):
		self.name = name
		self.gauge_id = gauge_id
		self.lat = lat
		self.lon = lon
		self.data = data
		self.unit = unit
		self.coast = coast
		self.rcp = rcp



class GaugeDatabase(object):
	'''
	Formatter for Kopp et al (2014) and RMS LSL scenarios

	Can be used as a stand-alone LSL examiner, but is designed to be 
	used by the dev.simulation module in this package.

	Usage:

		db = GaugeDatabase()

		# Load Kopp et al (2014) median LSLs
		db.load_median_lsls()
		print(db.median_data)           # formatted median values

		# Load Kopp et al (2014) monte carlo draws by draw id [0,9999]
		db.load_montecarlo_lsls(range(10))
		print(db.mc_data)               # formatted Monte Carlo draws 0-9

		# Load input LSL values for RMS hurricane scenarios (for diagnostics)
		db.load_rms_lsls()
		print(db.rms_data)              # formatted RMS lsl assumptions
	'''

	def __init__(self, unit='mm'):
		assert unit in self.STANDARDIZE, "GaugeDatabase standard unit {} not recognized. Check unit definitions.".format(unit)
		self.unit = unit

	@staticmethod
	def _get_quantfile_header(filename):
		''' parse quantfile header and format for pandas dataframe '''

		line1_finder = r'^\s*(?P<unit>([cm])?(m|in|ft))\s*(?P<rcpvals>(rcp(26|45|60|85)\s*)+)$'
		line2_finder = r'^\s*(?P<quantiles>(\s+[0-9]{1,2}\.[0-9]{1,2}){2,})\1+$'

		with open(filename, 'r') as lslfile:
			line = next(lslfile)
			
			try:
				while not re.search(line1_finder, line):
					line = next(lslfile)

				found = re.search(line1_finder, line)
				unit = found.group('unit')
				rcpvals = re.split(r'\s+',found.group('rcpvals').strip())

				while not re.search(line2_finder, line):
					line = next(lslfile)

				found = re.search(line2_finder, line)
				quantiles = [float(q) for q in re.split(r'\s+', found.group('quantiles').strip())]

			except StopIteration:
				raise ValueError('Valid header not found in {f}. Make sure file is formatted correctly.'.format(f=filename))

			return unit, pd.MultiIndex.from_tuples([(r, q) for r in rcpvals for q in quantiles])

	@classmethod
	def _get_quantfile_data(cls, filename=LSL_QUANTS, unit=None, header=None):

		if header is None:
			unit, header = cls._get_quantfile_header(filename)

		with open(filename, 'r') as lslfile:
			lsl_full = lslfile.read()

		block_str = r'(?P<gauge>[A-Z0-9\-\.\' ]+)\s+\[(?P<gaugeid>[0-9]{1,5})\s*(\]|/)\s*(?P<lat>((-)?[0-9\.]+))([,\s]+)(?P<lon>((-)?[0-9\.]+))(\])?\s*(?P<data>(\n[0-9]{4}(\t ([0-9\.\-]+|NaN))+){20})'
		coast_str = r'(?P<coast>[A-Za-z ]+)\n\s*(?P<block>(\n*({}))+)'.format(block_str)
		block_parser = re.compile(block_str)
		coast_parser = re.compile(coast_str)

		coasts = re.finditer(coast_parser,lsl_full)
		for c in coasts:

			coast = c.group('coast')
			data_block = c.group('block')

			gauges = re.finditer(block_parser, data_block)

			for g in gauges:
				gauge = g.group('gauge')
				gauge_id = int(g.group('gaugeid'))
				lat = float(g.group('lat'))
				lon = float(g.group('lon'))
				data = g.group('data')

				parsed = pd.read_csv(StringIO.StringIO(data), header=None, index_col=0, sep='\t', dtype=np.float64, na_values=['NaN',' NaN','NaN ',' NaN '],engine='c')
				parsed.columns = header
				parsed.columns.names = ['RCP','QUANTILE']
				parsed.index.names = ['YEAR']


				yield Gauge(gauge, gauge_id, lat, lon, parsed, unit, coast)

	@classmethod
	def _get_montecarlo_gauge(cls, filepath, gauge_id, rcp, draws = np.arange(10000)):
		if (not isinstance(draws, Iterable)) or (hasattr(draws, 'shape') and len(draws.shape) == 0):
			draws = np.array([draws])
		else:
			draws = np.array(draws)

		header_parser = re.compile(r'^\s*(?P<gauge>[A-Z0-9\-\.\' ]+)\s+(?P<rcp>rcp(26|45|60|85))\s+\((?P<unit>[cm]m)\)\s*$')

		with open(filepath, 'r') as lslfile:
			line = next(lslfile)

		header = re.search(header_parser, line)
		if not header:
			raise ValueError('Header not parsed correctly for {}'.format(filepath))

		gauge = header.group('gauge').strip()
		assert cls.GAUGE_ID_MAP[gauge] == gauge_id
		assert rcp == header.group('rcp')
		unit = header.group('unit')

		data = pd.read_csv(filepath, header=None, index_col=0, sep='\t', skiprows=1, dtype=np.float64, usecols = np.insert(np.array(draws+1), 0, 0), na_values=['NaN',' NaN','NaN ',' NaN '], engine='c')
		data.columns = list(draws)
		data.index.names = ['YEAR']
		data.columns.names = ['DRAW']

		# interp = data.apply(lambda x: interpolate.interp1d(x.index.values, x.values)(range(2010,2101)), axis=0)

		return Gauge(gauge, gauge_id, None, None, data, unit, rcp=rcp)

	@classmethod
	def _interpolate_yearly_lsl(cls, data, years=np.arange(2010, 2101), year_index='YEAR'):
		data = cls._deepstack(data)

		data = data.unstack(year_index)
		data = data.sub(data[2010], axis=0)
		data = data.apply(lambda x: pd.Series(np.interp(years, x.index.values, x.values), index=years), axis=1)
		data.columns.names = ['YEAR']
		return data

	@classmethod
	def _reindex_gauge_data_to_states(cls, data, gauge_index = 'GAUGE'):
		data = cls._deepstack(data)

		data = data.unstack(gauge_index)
		data = pd.concat({st:data[cls.STATE_STATION_MAP[st]] for st in cls.STATES}, axis=1)
		data.columns.names = ['STATE']
		return data

	@classmethod
	def _get_all_montecarlo_gauges(cls, directory=LSL_GAUGEDIR, include=None, draws = np.arange(10000)):
		pattern = re.compile(r'LSLprojMC_(?P<gID>[0-9]+)_(?P<rcp>rcp(26|45|60|85))\.tsv')
		
		new_gauges = {}

		files = os.listdir(directory)
		for f in files:
			match = re.search(pattern, f)
			if not match:
				continue

			filepath = os.path.join(directory, f)
			gauge_id = int(match.group('gID'))

			if include is not None:
				if not gauge_id in include:
					continue

			rcp = match.group('rcp')

			yield cls._get_montecarlo_gauge(filepath, gauge_id, rcp, draws = draws)

	@staticmethod
	def _deepstack(data):
		while (len(data.shape) > 1) and len(data.columns.names) > 0:
			data = data.stack()
		return data

	# INSTANCE METHODS
	
	def load_montecarlo_lsls(self, directory=LSL_GAUGEDIR, draws=np.arange(10000)):
		state_gauges = set(self.STATE_STATION_MAP.values())
		
		gauges = {}
		gauge_data = {}

		for gauge in self._get_all_montecarlo_gauges(directory=directory, include=state_gauges, draws=draws):
			if not gauge.rcp in gauges:
				gauges[gauge.rcp] = {}
			assert gauge.unit in self.STANDARDIZE, "Gauge {} LSL unit {} not recognized. Check unit definitions.".format(gauge.gauge_id, gauge.unit)
			gauges[gauge.rcp][gauge.gauge_id] = gauge.data * self.STANDARDIZE[gauge.unit] / self.STANDARDIZE[self.unit]

		for rcp in sorted(gauges.keys()):
			gauge_data[rcp] = pd.concat(gauges[rcp], axis=0, names=['GAUGE'])

		mc_data = pd.concat(gauge_data, axis=0, names=['RCP'])

		mc_data = self._interpolate_yearly_lsl(mc_data)
		mc_data = self._reindex_gauge_data_to_states(mc_data)

		mc_data = self._deepstack(mc_data)

		self.mc_data = mc_data.unstack('DRAW')

	def load_median_lsls(self, filepath=LSL_QUANTS):
		median_data = {}

		for rcp in ['rcp85']:
			data = {}

			for gauge in self._get_quantfile_data(filepath):
				assert gauge.unit in self.STANDARDIZE, "Gauge {} LSL unit {} not recognized. Check unit definitions.".format(gauge.gauge_id, gauge.unit)
				data[gauge.gauge_id] = gauge.data[(rcp, 50)] * self.STANDARDIZE[gauge.unit] / self.STANDARDIZE[self.unit]

			median_data[rcp] = pd.concat(data, axis=0, names=['GAUGE'])
		median_data = pd.concat(median_data, axis=0, names=['RCP'])

		median_data = self._interpolate_yearly_lsl(median_data)
		median_data = self._reindex_gauge_data_to_states(median_data)
		
		median_data = self._deepstack(median_data)

		median_data = pd.DataFrame(median_data, columns = ['Median'])
		median_data.columns.names = ['DRAW']

		self.median_data = median_data

	def load_rms_lsls(self):
		'''
		Format LSL values used by RMS for diagnostics run
		'''

		# Gather RMS LSL data from exposure dataset
		lsls = []

		for coast in ['east','west']:
			exposure = rms.Exposure(coast=coast)
			exposure.read()
			exposure.convert()
			lsls.append(exposure.data.xs(50, level='MSL.Q').xs('ALL', level='LOB')[['LSL']])

		# Format LSL data into a pd.Series object
		rms_data = pd.concat(lsls, axis=0)['LSL']

		# Fill in missing states according to coastline
		data_states = rms_data.index.get_level_values('STATE').unique()
		mapped = {st:st if st in data_states else rms.coastline[st] for st in self.STATES}
		rms_data = pd.concat({st:rms_data.xs(mapped[st], level='STATE') for st in mapped.keys()}, axis=0, names=['STATE'])
		rms_data.sort_index(inplace=True)

		# Remove duplicate entries, reformat to pd.Series
		names = rms_data.index.names
		rms_data = rms_data.sort_index().reset_index().drop_duplicates().set_index(names).sort_index()
		if len(rms_data.shape) == 2:
			assert np.in1d(rms_data.columns, ['LSL']).all()
			rms_data = rms_data['LSL']

		# Linearly interpolate between years
		rms_data = self._interpolate_yearly_lsl(rms_data)
		rms_data = self._deepstack(rms_data)
		
		# Format for draw-based run
		rms_data = pd.DataFrame(rms_data, columns = ['RMS'])
		rms_data.columns.names = ['DRAW']

		self.rms_data = rms_data



	STANDARD_UNIT = 'cm'
	STANDARDIZE = {
		'ft': np.float64('30.48'), 
		'in': np.float64('2.54'), 
		'mm': np.float64('0.1'), 
		'm':  np.float64('100'), 
		'cm': np.float64('1')}

	STATE_STATION_MAP = {

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
		'PA':	135,		#	'PHILADELPHIA'
		'WV':	299,
		'VT':	235}

	STATES = sorted(STATE_STATION_MAP.keys())

	GAUGE_ID_MAP = {
		"HONOLULU"                 :   155,
		"HILO"                     :   300,
		"KAHULUI HARBOR"           :   521,
		"MIDWAY ISLAND"            :   523,
		"JOHNSTON ISLAND"          :   598,
		"NAWILIWILI BAY"           :   756,
		"MOKUOLOE ISLAND"          :   823,
		"FRENCH FRIGATE SHOALS"    :  1372,
		"KAWAIHAE"                 :  2128,
		"DUTCH HARBOR"             :   390,
		"ADAK  SWEEPER COVE"       :   487,
		"MASSACRE BAY"             :   491,
		"UNALASKA"                 :   757,
		"KETCHIKAN"                :   225,
		"SEWARD"                   :   266,
		"JUNEAU"                   :   405,
		"SITKA"                    :   426,
		"YAKUTAT"                  :   445,
		"SKAGWAY"                  :   495,
		"CORDOVA"                  :   566,
		"KODIAK ISLAND"            :   567,
		"ANCHORAGE"                :  1067,
		"SELDOVIA"                 :  1070,
		"NIKISKI"                  :  1350,
		"VALDEZ"                   :  1353,
		"SAND POINT"               :  1634,
		"NOME"                     :  1800,
		"PRUDHOE BAY"              :  1857,
		"TOFINO"                   :   165,
		"VICTORIA"                 :   166,
		"PRINCE RUPERT"            :   167,
		"VANCOUVER"                :   175,
		"POINT ATKINSON"           :   193,
		"PORT ALBERNI"             :   527,
		"ALERT BAY"                :   554,
		"FULFORD HARBOUR"          :   688,
		"QUEEN CHARLOTTE CITY"     :   829,
		"PORT RENFREW"             :   842,
		"SOOKE"                    :   921,
		"BELLA BELLA"              :   984,
		"PORT HARDY"               :  1071,
		"PATRICIA BAY"             :  1152,
		"BAMFIELD"                 :  1242,
		"NEW  WESTMINSTER"         :  1245,
		"STEVESTON"                :  1255,
		"CAMPBELL RIVER"           :  1323,
		"WINTER HARBOUR"           :  1799,
		"SAN FRANCISCO"            :    10,
		"SEATTLE"                  :   127,
		"SAN DIEGO"                :   158,
		"LOS ANGELES"              :   245,
		"LA JOLLA"                 :   256,
		"ASTORIA"                  :   265,
		"SANTA MONICA"             :   377,
		"CRESCENT CITY"            :   378,
		"FRIDAY HARBOR"            :   384,
		"NEAH BAY"                 :   385,
		"ALAMEDA"                  :   437,
		"PORT SAN LUIS"            :   508,
		"ALAMITOS BAY ENTRANCE"    :   717,
		"NEWPORT BAY"              :   766,
		"RINCON ISLAND"            :  1013,
		"SOUTH BEACH"              :  1196,
		"CHARLESTON II"            :  1269,
		"PORT TOWNSEND"            :  1325,
		"MONTEREY"                 :  1352,
		"TOKE POINT"               :  1354,
		"POINT REYES"              :  1394,
		"CHERRY POINT"             :  1633,
		"N. SPIT"                  :  1639,
		"PORT ORFORD"              :  1640,
		"ARENA COVE"               :  2125,
		"SANTA BARBARA"            :  2126,
		"PORT ANGELES"             :  2127,
		"GALVESTON II"             :   161,
		"KEY WEST"                 :   188,
		"CEDAR KEY I"              :   199,
		"PENSACOLA"                :   246,
		"CEDAR KEY II"             :   428,
		"EUGENE ISLAND"            :   440,
		"PORT ISABEL"              :   497,
		"ST. PETERSBURG"           :   520,
		"GRAND ISLE"               :   526,
		"ROCKPORT"                 :   538,
		"FREEPORT"                 :   725,
		"GALVESTON I"              :   828,
		"PADRE ISLAND"             :   919,
		"SABINE PASS"              :   920,
		"PORT MANSFIELD"           :  1038,
		"FORT MYERS"               :  1106,
		"NAPLES"                   :  1107,
		"DAUPHIN ISLAND"           :  1156,
		"APALACHICOLA"             :  1193,
		"KEY COLONY BEACH"         :  1424,
		"CLEARWATER BEACH"         :  1638,
		"PANAMA CITY"              :  1641,
		"VACA KEY"                 :  1701,
		"SABINE PASS NORTH"        :  1835,
		"CORPUS CHRISTI"           :  1903,
		"NEW YORK"                 :    12,
		"FERNANDINA BEACH"         :   112,
		"PHILADELPHIA"             :   135,
		"BALTIMORE"                :   148,
		"ATLANTIC CITY"            :   180,
		"PORTLAND"                 :   183,
		"LEWES"                    :   224,
		"CHARLESTON I"             :   234,
		"BOSTON"                   :   235,
		"DAYTONA BEACH"            :   270,
		"SEAVEY ISLAND"            :   288,
		"SEWELLS POINT"            :   299,
		"ANNAPOLIS"                :   311,
		"MAYPORT"                  :   316,
		"EASTPORT"                 :   332,
		"NEWPORT"                  :   351,
		"WASHINGTON DC"            :   360,
		"WILLETS POINT"            :   362,
		"MIAMI BEACH"              :   363,
		"SANDY HOOK"               :   366,
		"WOODS HOLE"               :   367,
		"FORT PULASKI"             :   395,
		"WILMINGTON"               :   396,
		"PORTSMOUTH"               :   399,
		"SOLOMON'S ISLAND"         :   412,
		"NEW LONDON"               :   429,
		"PROVIDENCE"               :   430,
		"RICHMOND"                 :   462,
		"MONTAUK"                  :   519,
		"BAR HARBOR"               :   525,
		"GLOUCESTER POINT"         :   597,
		"KIPTOPEKE BEACH"          :   636,
		"JACKSONVILLE"             :   716,
		"SANDWICH MARINA"          :   775,
		"BUZZARDS BAY"             :   776,
		"REEDY POINT"              :   786,
		"PORT JEFFERSON"           :   848,
		"NEW ROCHELLE"             :   856,
		"MYRTLE BEACH"             :   862,
		"BRIDGEPORT"               :  1068,
		"CUTLER"                   :  1081,
		"NANTUCKET ISLAND"         :  1111,
		"CAPE MAY"                 :  1153,
		"DAYTONA BEACH SHORES"     :  1182,
		"ROCKLAND"                 :  1279,
		"CAMBRIDGE II"             :  1295,
		"SPRINGMAID PIER"          :  1444,
		"CUTLER II"                :  1524,
		"CHESAPEAKE BAY BR. TUN."  :  1635,
		"DUCK PIER OUTSIDE"        :  1636,
		"BERGEN POINT"             :  1637,
		"VIRGINIA KEY"             :  1858,
		"TRIDENT PIER"             :  2123,
		"HALIFAX"                  :    96,
		"TROIS-RIVIERES"           :   126,
		"POINTE-AU-PERE"           :   138,
		"BATISCAN"                 :   144,
		"QUEBEC"                   :   173,
		"HARRINGTON HBR"           :   176,
		"NEUVILLE"                 :   192,
		"SAINT JOHN"               :   195,
		"CAP A LA ROCHE"           :   201,
		"GRONDINES"                :   387,
		"PORT-AUX-BASQUES"         :   392,
		"ST. JOHN'S"               :   393,
		"CHARLOTTETOWN"            :   427,
		"CHURCHILL"                :   447,
		"RESOLUTE"                 :   863,
		"PORTNEUF"                 :   951,
		"ST-FRANCOIS"              :   999,
		"TUKTOYAKTUK"              :  1000,
		"CHAMPLAIN"                :  1005,
		"LARK HARBOUR"             :  1044,
		"PICTOU"                   :  1121,
		"YARMOUTH"                 :  1158,
		"STE-ANNE-DES-MONTS"       :  1199,
		"RIVIERE-AU-RENARD"        :  1213,
		"BAIE COMEAU"              :  1218,
		"TADOUSSAC"                :  1219,
		"ST-JOSEPH-DE-LA-RIVE"     :  1244,
		"RIVIERE-DU-LOUP"          :  1284,
		"NORTH SYDNEY"             :  1299,
		"ARGENTIA"                 :  1321,
		"SEPT-ILES"                :  1322,
		"SHEDIAC BAY"              :  1326,
		"RUSTICO"                  :  1330,
		"LOWER ESCUMINAC"          :  1349,
		"PORT-ALFRED"              :  1392,
		"RIMOUSKI"                 :  1597,
		"BECANCOUR"                :  1798,
		"KUSHIMOTO"                :   134,
		"COCHIN"                   :   438, 
		"SEVASTOPOL"               :    42, 
		"VALPARAISO"               :   499, 
		"STOCKHOLM"                :    78, 
		"CUXHAVEN 2"               :     7}

