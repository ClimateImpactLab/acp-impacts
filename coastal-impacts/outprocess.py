import numpy as np
import os, os.path, re, argparse

st_result_dir = 'outputs/mc_temp/'
percent_results_dir = 'outputs/percentiles/'

PER_TYPES = {'annual':[2030,2050,2100],'20yr':['{t}to{te}'.format(t=t,te=t+19) for t in range(2020,2100,20)]}
conversion = {'20yr':'20yr','annual':'single'}

def write_pct_file(inputfile,reg,rcp,hurr,pertype,regType):
	for i,dtype in enumerate(['IN','DI','BI','TOT']):
		for j,tperiod in enumerate(PER_TYPES[pertype]):
			tempdata = np.loadtxt(inputfile,dtype='float64',skiprows=2,usecols=((i*len(PER_TYPES[pertype])+j),),delimiter=',')
			if i==0 and j==0:
				print('{rcp} {hurr} {rg:<4} {per:>10} results read with {n:>5} entries'.format(rcp=rcp,hurr=hurr,rg=(reg+':'),n=np.size(tempdata),per=pertype))

			percentiles = [np.percentile(tempdata,p) for p in range(1,100)]

			with open('{p}{rt}_{r}_{h}_{d}_{per}_{t}.csv'.format(rt=regType,r=rcp,h=hurr,p=percent_results_dir,d=dtype,per=conversion[pertype],t=tperiod),'a') as writefile:
				writefile.write('{rg},{pct}\n'.format(rg=reg,pct=','.join([str(p) for p in percentiles])))


def prep_outfiles(rcp,hurr):
	for i,dtype in enumerate(['IN','DI','BI','TOT']):
		for k,pertype in enumerate(PER_TYPES.keys()):
			for j,tperiod in enumerate(PER_TYPES[pertype]):
				with open('{p}STATE_{r}_{h}_{d}_{per}_{t}.csv'.format(r=rcp,h=hurr,p=percent_results_dir,d=dtype,per=conversion[pertype],t=tperiod),'w+') as writefile:
					writefile.write('STATE,{pct}\n'.format(pct=','.join(['{p}%'.format(p=p) for p in range(1,100)])))

	for i,dtype in enumerate(['IN','DI','BI','TOT']):
		for k,pertype in enumerate(PER_TYPES.keys()):
			for j,tperiod in enumerate(PER_TYPES[pertype]):
				with open('{p}NCA_{r}_{h}_{d}_{per}_{t}.csv'.format(r=rcp,h=hurr,p=percent_results_dir,d=dtype,per=conversion[pertype],t=tperiod),'w+') as writefile:
					writefile.write('STATE,{pct}\n'.format(pct=','.join(['{p}%'.format(p=p) for p in range(1,100)])))

def main(rcp,hurr):
	if not os.path.isdir(percent_results_dir):
		os.mkdir(percent_results_dir)

	prep_outfiles(rcp,hurr)

	# COMPILE NCA FILES

	read = {p:set() for p in PER_TYPES.keys()}

	for mcFile in sorted(os.listdir(st_result_dir)):
		stmatch = re.search(r'(?P<rcp>rcp[0-9]{2})_(?P<hurr>\w+)_(?P<state>[A-Z]{2})_(?P<pertype>(annual|20yr))\.csv$',mcFile)
		if not stmatch:
			continue
		rcpmatch = stmatch.group('rcp')
		hurrmatch = stmatch.group('hurr')
		reg = stmatch.group('state')
		pertype = stmatch.group('pertype')

		if (rcpmatch != rcp) or (hurrmatch != hurr):
			continue

		write_pct_file(st_result_dir+mcFile,reg,rcp,hurr,pertype,'STATE')

		read[pertype].add(reg)

	for mcFile in os.listdir(st_result_dir):
		usmatch = re.search(r'(?P<rcp>rcp[0-9]{2})_(?P<hurr>\w+)_(?P<usa>USA)_(?P<pertype>(annual|20yr))\.csv$',mcFile)
		if not usmatch:
			continue
		rcpmatch = usmatch.group('rcp')
		hurrmatch = usmatch.group('hurr')
		reg = usmatch.group('usa')
		pertype = usmatch.group('pertype')

		if (rcpmatch != rcp) or (hurrmatch != hurr):
			continue

		write_pct_file(st_result_dir+mcFile,reg,rcp,hurr,pertype,'STATE')

		read[pertype].add(reg)

	#	CHECK FOR COMPLETE READ

	for per in PER_TYPES.keys():
		for reg in ['OR','WA','CA','TX','LA','MS','AL','ME','MA','NH','RI','CT','NY','NJ','DE','MD','DC','VA','NC','SC','GA','FL','PA','WV','VT','USA']:
			if not reg in read[per]:
				print('  ***  WARNING: {st} {per} NOT READ  ***  '.format(st=reg,per=per))

	#	COMPILE NCA FILES

	read = {p:set() for p in PER_TYPES.keys()}

	for mcFile in sorted(os.listdir(st_result_dir)):
		ncamatch = re.search(r'(?P<rcp>rcp[0-9]{2})_(?P<hurr>\w+)_(?P<nca>(NEA|SEA|MWE|GPL|NWE|SWE|ALK|HWI))_(?P<pertype>(annual|20yr))\.csv$',mcFile)
		if not ncamatch:
			continue
		rcpmatch = ncamatch.group('rcp')
		hurrmatch = ncamatch.group('hurr')
		reg = ncamatch.group('nca')
		pertype = ncamatch.group('pertype')

		if (rcpmatch != rcp) or (hurrmatch != hurr):
			continue

		write_pct_file(st_result_dir+mcFile,reg,rcp,hurr,pertype,'NCA')

		read[pertype].add(reg)

	for mcFile in os.listdir(st_result_dir):
		usmatch = re.search(r'(?P<rcp>rcp[0-9]{2})_(?P<hurr>\w+)_(?P<usa>USA)_(?P<pertype>(annual|20yr))\.csv$',mcFile)
		if not usmatch:
			continue
		rcpmatch = usmatch.group('rcp')
		hurrmatch = usmatch.group('hurr')
		reg = usmatch.group('usa')
		pertype = usmatch.group('pertype')

		if (rcpmatch != rcp) or (hurrmatch != hurr):
			continue

		write_pct_file(st_result_dir+mcFile,reg,rcp,hurr,pertype,'NCA')

		read[pertype].add(reg)

	#	CHECK FOR COMPLETE READ

	for per in PER_TYPES.keys():
		for reg in ['NEA','SEA','MWE','GPL','NWE','SWE','ALK','HWI','USA']:
			if not reg in read[per]:
				print('  ***  WARNING: {st} {per} NOT READ  ***  '.format(st=reg,per=per))

	
def arg():
	parser = argparse.ArgumentParser(description='Compile statistics on Monte Carlo results')
	parser.add_argument('-r','--rcp',type=str,default='rcp85',help='Set the RCP to run for this study')
	parser.add_argument('-s','--hurr',type=str,default='hist',help='Set the hurricane scenario to run for this study')
	return parser.parse_args()


if __name__=="__main__":
	args = arg()
	main(args.rcp,args.hurr)
