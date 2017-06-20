import re, subprocess, csv
import os
from os import listdir, remove, mkdir, name
from shutil import copy, move, rmtree

import impact_handler

paths = listdir('.')


IMPACT_SUFFIX = 'state'

GAMS_OUTPUT_SUPPRESS = ['lo','2','lf']


fkeys = [	['yields-grains-{sfx}'.format(sfx=IMPACT_SUFFIX),						'.tar.gz', '.gdx'],
					['yields-oilcrop-{sfx}'.format(sfx=IMPACT_SUFFIX),					'.tar.gz', '.gdx'],
					['yields-cotton-{sfx}'.format(sfx=IMPACT_SUFFIX),						'.tar.gz', '.gdx'],
					['labor-high-productivity-{sfx}'.format(sfx=IMPACT_SUFFIX),	'.tar.gz', '.gdx'],
					['labor-low-productivity-{sfx}'.format(sfx=IMPACT_SUFFIX),	'.tar.gz', '.gdx'],
					['health-mortage-0-0-{sfx}'.format(sfx=IMPACT_SUFFIX),			'.tar.gz', '.gdx'],
					['health-mortage-1-44-{sfx}'.format(sfx=IMPACT_SUFFIX),			'.tar.gz', '.gdx'],
					['health-mortage-45-64-{sfx}'.format(sfx=IMPACT_SUFFIX),		'.tar.gz', '.gdx'],
					['health-mortage-65-inf-{sfx}'.format(sfx=IMPACT_SUFFIX),		'.tar.gz', '.gdx'],
					['mod_county_ncdc','.gms', None],
					['hdd','.gms', None],
					['energy','.gdx', '.gdx'],
					['slr','.gms', None],
					['coastal','.gdx', '.gdx']
					]

fnames = {'yields-grains-{sfx}'.format(sfx=IMPACT_SUFFIX):							'yields_grains_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'yields-oilcrop-{sfx}'.format(sfx=IMPACT_SUFFIX):							'yields_oilcrop_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'yields-cotton-{sfx}'.format(sfx=IMPACT_SUFFIX):							'yields_cotton_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'labor-high-productivity-{sfx}'.format(sfx=IMPACT_SUFFIX):		'labor_high_productivity_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'labor-low-productivity-{sfx}'.format(sfx=IMPACT_SUFFIX):			'labor_low_productivity_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'health-mortage-0-0-{sfx}'.format(sfx=IMPACT_SUFFIX):					'health_mortage_0_0_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'health-mortage-1-44-{sfx}'.format(sfx=IMPACT_SUFFIX):				'health_mortage_1_44_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'health-mortage-45-64-{sfx}'.format(sfx=IMPACT_SUFFIX):				'health_mortage_45_64_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'health-mortage-65-inf-{sfx}'.format(sfx=IMPACT_SUFFIX):			'health_mortage_65_inf_{sfx}'.format(sfx=IMPACT_SUFFIX),
					'mod_county_ncdc':																						'hdd_cdd',
					'hdd':																												'hdd_cdd',
					'energy':																											'energy',
					'slr':																												'slr',
					'coastal':																										'coastal'
					}

impact_types = {	
					re.compile(r'yields_'):  'AG',
					re.compile(r'labor_'):   'LABOR',
					re.compile(r'health_'):  'MORTALITY',
					re.compile(r'hdd_'):     'ENERGY',
					re.compile(r'energy'):   'ENERGY',
					re.compile(r'slr'):      'COASTAL',
					re.compile(r'coastal'):  'COASTAL'}

def getNewFilename(filename):

	standardized = None
	std_prefix = None
	impact = None
	final_suffix = None
	orig_prefix = None

	for prefix, ext0, ext1 in fkeys:
		if re.search(prefix,filename) and filename.endswith(ext0):
			standardized = fnames[prefix]+ext0
			std_prefix  = fnames[prefix]
			final_suffix = ext1
			orig_prefix = prefix
	if std_prefix is not None:
		for t in impact_types.keys():
			if re.search(t,std_prefix):
				impact = impact_types[t]

	return orig_prefix,standardized,std_prefix,impact,final_suffix

def makecall(function,args):
	if isinstance(args,str):
		return function(args)
	if isinstance(args,tuple):
		try:
			return function(*args)
		except Exception,e:
			print(function,args,e)
			raise OSError(e)
	return function(args)

def getFileAction(output_dir, impact_type,filepath,prefix,standardized,std_prefix,**kwargs):

	# format impact names the same way as impact_type
	impact_list = lambda impacts: ['{}_{}'.format(impact, IMPACT_SUFFIX) for impact in impacts]

	# Each impact requires a certain set of manipulations before it can be included in the model.
	# These lists provide a sort of mapping from impact types to action classes.
	divide   = impact_list(['yields_grains', 'yields_oilcrop', 'yields_cotton', 'labor_high_productivity', 'labor_low_productivity'])
	subtract = impact_list(['health_mortage_0_0','health_mortage_1_44','health_mortage_45_64','health_mortage_65_inf'])
	gams     = ['hdd_cdd','slr']
	gdx      = ['energy','coastal']

	# assign appropriate impact handler classes
	if impact_type in divide:
		ActionClass = impact_handler.TarDivider

	elif impact_type in subtract:
		ActionClass = impact_handler.TarSubtractor

	elif impact_type in gams:
		ActionClass = impact_handler.GamsFile

	elif impact_type in gdx:
		ActionClass = impact_handler.GDXFile

	else:
		raise ValueError('File type {} not recognized and no action assigned'.format(impact_type))

	# Return impact handler for on-demand impact preparation
	args = (output_dir, impact_type,filepath,prefix,standardized,std_prefix)
	return ActionClass(*args,**kwargs)


def getHurrScen(rcp):

	HURR_ACTIV_SCEN ={
		'rcp26':	['Hist'],
		'rcp45':	['Hist','RCP45Cl'],
		'rcp60':	['Hist'],
		'rcp85':	['Hist','CCMS','GDFL','MRI','MPI','HADGEM','MIROC']}

	return HURR_ACTIV_SCEN[rcp]

def test():
		oldFName		={}
		standardized		={}
		fileAction	={}
		name 				={}

		for path in [p for p in paths]:
			try:
				oldFName[path] = path.split(slash)[_1]
				standardized[path],name[path] = getNewFilename(oldFName[path])
			except:
				paths.pop(paths.index(path))


		for path in paths:
			fileAction[path] = getFileAction(standardized[path],name[path])
			for i in range(len(fileAction[path])):
				makecall(fileAction[path][i][0],fileAction[path][i][1])
			for f in [files for files in listdir('.') if files.endswith('.gdx') or files.endswith('.lst')]:
				remove(f)
 
