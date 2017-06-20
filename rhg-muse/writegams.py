'''
Provides utilities for writing pandas data to GAMS GDX files
'''

import os
import gams

class PyGDX(object):
	EXISTS_OPTS = ['update','replace','validate','error']

	def __init__(self, ws=None, db=None, filepath=None):
		self.ws = ws if ws is not None else gams.GamsWorkspace()
		self.db = db
		self.filepath = filepath

	def load(self, filepath=None):
		self.filepath = filepath if filepath is not None else self.filepath
		if self.filepath is None:
			raise IOError('No filepath supplied and no default available')
		assert os.path.exists(self.filepath), '{} not found'.format(self.filepath)
		self.db = self.ws.add_database_from_gdx(self.filepath)

	def clear_database(self):
		del self.db
		self.db = self.ws.add_database()

	def reset_param(self, param):
		self.reset_symbol(param, gams.GamsParameter)

	def reset_set(self, set):
		self.reset_symbol(set, gams.GamsSet)
		
	def reset_symbol(self, symb, symbol_type=None):
		sym = self._get_if_exists(symb, symbol_type)
		if sym:
			sym.clear()


	@classmethod
	def _check_exists_arg(cls, arg):
		check = (arg in cls.EXISTS_OPTS) if len(arg) > 1 else (arg in [s[0] for s in cls.EXISTS_OPTS])
		assert check, "{} not a valid exists argument. Use {}".format(arg, cls.EXISTS_OPTS)

	def _get_if_exists(self, name, symbol_type=None):
		if symbol_type is None:
			symbol_type = gams.database._GamsSymbol
		try:
			symb = self.db.get_symbol(name)
		except gams.workspace.GamsException, e:
			assert e.message == "Cannot find symbol {}".format(name), "An unexpected error occurred: {}".format(e)
			return None

		assert isinstance(symb, symbol_type), "Invalid name: record '{}' already exists as type {}".format(name, type(symb))
		return symb

	@staticmethod
	def _deepstack(data):
		while (len(data.shape) > 1) and len(data.columns.names) > 0:
			data = data.stack()
		return data

	def export(self, filepath):
		if not filepath.endswith('.gdx'):
			filepath = filepath + '.gdx'

		if not os.path.isdir(os.path.dirname(filepath)):
			os.makedirs(os.path.dirname(filepath))
		self.db.export(os.path.abspath(os.path.expanduser(filepath)))


	@staticmethod
	def _get_record_to_df(data, properties, domain=None):
		indexing_sets = [k.name if isinstance(k,gams.GamsSet) else k for k in data.domains]
		domain = domain if not domain is None else indexing_sets
		build_data = lambda x: tuple(x.keys + [x.__getattribute__(p) for p in properties])

		data = pd.DataFrame(
				data = [build_data(r) for r in data],
				columns = domain+properties
			).convert_objects(convert_numeric=True)

		data.set_index(domain, inplace=True)

		return data

	def get_parameter(self, parname, domain=None):
		data = self.database.get_parameter(parname)
		properties = ['value']
		return self._get_record_to_df(data, properties, domain)
		

	def add_set(self, name, values, explanatory_text='', exists='update'):
		symb = self._get_if_exists(name, gams.GamsSet)

		if not symb:
			symb = self.db.add_set(name, 1, explanatory_text)
			exists = 'update'

		if exists == 'update':
			for val in values:
				try:
					symb.add_record((str(val),))
				except gams.workspace.GamsException, e:
					assert 'exists in symbol \'{}\''.format(name) in e.message, "An unexpected error occurred: {}".format(e)
		
		elif exists == 'replace':
			symb.clear()
			for val in values:
				symb.add_record((str(val),))

		elif exists == "validate":
			for val in values:
				symb.get_record(str(val))

		else:
			raise ValueError('Set "{}" already present in database.'.format(name))

		return symb

	def dataframe_to_param(self, name, df, explanatory_text='', exists='update', domain=None, set_exists=None, set_text=None):
		if set_exists is None: set_exists = exists
		self._check_exists_arg(exists)
		self._check_exists_arg(set_exists)
		
		series = self._deepstack(df.copy())

		symb = self._get_if_exists(name, gams.GamsParameter)
		if exists == 'error' and symb:
			ValueError('Parameter "{}" already present in database.'.format(name))

		if domain is None:
			if symb is not None:
				domain = symb.domains
			else:
				domain = series.index.names

		if len(domain) != len(series.index.names):
			raise ValueError("Length of domain must equal number of column and index levels")

		domain_names = []
		domain_sets = []

		for i, s in enumerate(domain):
			if isinstance(s, gams.GamsSet):
				domain_sets.append(s)
				domain_names.append(s.name)
			elif isinstance(s, str):
				if s == '*':
					domain_sets.append(s)
					domain_names.append(s)
				else:
					if ((isinstance(set_text, dict)) and (s in set_text)):
						text = set_text[s]
					elif ((isinstance(set_text, list) or (hasattr(set_text, 'shape') and len(set_text.shape) == 1))) and (len(set_text) == len(domain)):
						if (hasattr(set_text, 'iloc')):
							text = set_text.iloc[i]
						else:
							text = set_text[i]
					elif (isinstance(set_text, str)):
						text = set_text
					else:
						text = ''

					domain_sets.append(self.add_set(s, series.index.levels[series.index.names.index(s)], text, set_exists))
					domain_names.append(s)

		series.index = series.index.reorder_levels(domain_names)
		series.sort_index(inplace=True)

		if symb is None:
			symb = self.db.add_parameter_dc(name, domain_sets, explanatory_text)
			exists = 'update'

		if exists == 'replace':
			symb.clear()

		def add_record(val, keys):
			keys = [str(v) for v in keys]
			if exists == 'validate':
				assert symb.get_record(keys) == val, "Value at ({}) does not match existing value".format(','.join(keys))
			else:
				try:
					rec = symb.add_record(keys)
				except gams.workspace.GamsException, e:
					assert 'exists in symbol \'{}\''.format(name) in e.message, "An unexpected error occurred: {}".format(e)
					rec = symb.find_record(keys)
				rec.value = val
		
		for i in range(len(series)):
			add_record(series.iloc[i], series.index[i])

		return symb


	def series_to_param(self, name, series, explanatory_text='', exists='update', domain=None, set_exists=None, set_text=None):
		return self.dataframe_to_param(name, series, explanatory_text, exists, domain, set_exists, set_text)