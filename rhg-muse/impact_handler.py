
import shutil, subprocess, csv, os, re, tarfile
import pandas as pd
import writegams

class ImpactHandler(object):

	@classmethod
	def call(cls,action,tmpdirs=None):

		if not tmpdirs is None:
			for d in tmpdirs:
				shutil.rmtree(d,True)
				os.makedirs(d,True)
		proc = subprocess.Popen(action, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		return proc.wait()

	def __init__(self, output_dir, impact_type, filepath, prefix, standardized, std_prefix, **kwargs):
		self.output_dir     = output_dir
		self.impact_type    = impact_type
		self.filepath       = filepath
		self.prefix         = prefix
		self.standardized   = standardized
		self.std_prefix     = std_prefix

		for kw, arg in kwargs.items():
			assert hasattr(self,kw), "Illegal parameter {} supplied to ImpactHandler".format(kw)
			self.__dict__[kw] = arg

		prfxmatch = re.search(r'(?P<origprefix>[a-zA-Z\-0-9_]+(?=\.))',filepath)
		self.origprefix = prfxmatch.group('origprefix')

class Tarfile(ImpactHandler):
	def __init__(self, *args, **kwargs):
		ImpactHandler.__init__(self, *args, **kwargs)

	@staticmethod
	def operator(df):
		''' Generic operator intended to be overloaded '''
		raise NotImplemented('Tarfile operator not implemented. Use through subclasses TarSubtractor or TarDivider')

	def run(self, remove=False, thread=1):

		tarball = tarfile.open(self.filepath, 'r:gz')
		data = {}

		parser = re.search(r'^(?P<impact>[^.]+)\.tar\.gz$', os.path.basename(self.filepath))
		assert parser is not None, 'File name not understood: {}'.format(self.filepath)
		fileprefix = parser.group('impact')
		assert fileprefix in tarball.getnames(), "{} not found in {} - {}".format(fileprefix, self.filepath, tarball.getnames())

		for state_file in tarball:
			if state_file.name == fileprefix:
				assert state_file.isdir(), "What? I really thought this would be a directory... I dunno, ask James?"
				continue

			assert state_file.isfile(), "Unexpected file type found: {}".format(state_file.name)
			
			parser = re.search(r'^{}/(?P<state>[0-9]{{2}}).csv$'.format(re.escape(fileprefix)), state_file.name)
			assert parser is not None, "Impact TarFile {} contains unexpected file: {}".format(self.filepath, state_file.name)
			state = int(parser.group('state'))

			st_data = pd.read_csv(tarball.extractfile(state_file), index_col=[0])

			# convert index name to uppercase			
			assert st_data.index.names[0].upper() == 'YEAR'
			st_data.index.names = ['years']

			st_data = self.operator(st_data)

			assert st_data.columns[0] in ('relative','addlrate','fraction'), 'Column 0: {} in {}:{} not recognized'.format(st_data.columns[0], self.filepath, state_file.name)
			
			st_data = st_data[st_data.index.get_level_values('years') >= 2011]
			data[state] = st_data[st_data.columns[0]]

		data = pd.concat(data, axis=0, names=['rg'])

		gdx = writegams.PyGDX()

		states = gdx.add_set('rg',sorted(data.index.get_level_values('rg').unique()), 'Regions in the data')
		years  = gdx.add_set('years',sorted(data.index.get_level_values('years').unique()), 'Years in the data')
		gdx.dataframe_to_param(self.impact_type, data, explanatory_text='Impact data for impact type {} (\% change from 2011)'.format(self.impact_type), domain=[states, years])

		dest = os.path.join(self.output_dir, self.std_prefix + '.gdx')
		gdx.export(dest)

		if remove:
			os.remove(self.filepath)

		return dest


class TarDivider(Tarfile):
	def __init__(self, *args, **kwargs):
		Tarfile.__init__(self, *args, **kwargs)
		self.action_type = 'divide'

	@staticmethod
	def operator(df):
		return df / df.loc[2011]


class TarSubtractor(Tarfile):
	def __init__(self, *args, **kwargs):
		Tarfile.__init__(self, *args, **kwargs)
		self.action_type = 'subtract'

	@staticmethod
	def operator(df):
		return df - df.loc[2011]


class GamsFile(ImpactHandler):
	def __init__(self, *args, **kwargs):
		ImpactHandler.__init__(self,*args,**kwargs)
	def run(self, remove=False, thread=1):
		dest = '{outdir}/{std_prefix}.gdx'.format(outdir=self.output_dir, std_prefix=self.std_prefix)
		self.call('gams {outdir}/{std_prefix} o={std_prefix}.lst Procdir=225_{impact_type} Scrdir=tmpscdr_{impact_type} gdx={dest}  lo=2'.format(outdir=self.output_dir, std_prefix=self.std_prefix,gdx=self.standardized,impact_type=self.impact_type),'225_{f},tmpscdr_{f}'.format(f=self.impact_type).split(','))


class GDXFile(ImpactHandler):
	def __init__(self, *args, **kwargs):
		ImpactHandler.__init__(self,*args,**kwargs)
	def run(self, remove=False, thread=1):
		dest = os.path.join(self.output_dir, self.std_prefix + '.gdx')
		shutil.copy(self.filepath, dest)
		return dest