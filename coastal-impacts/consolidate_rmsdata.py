'''
Utility for consolidating RMS Hurricane damage directories into a single CSV
'''

import sys, os, re, pandas as pd

def get_all_data(directory):
	
	files = {y:{} for y in range(2010,2110,10)}
	data = {}

	fpaths = os.listdir(directory)
	
	for f in fpaths:
		filepath = os.path.join(directory, f)
		if re.search(r'Base\.',filepath):
			files[2010][50] = pd.read_csv(filepath).set_index(['STATE','COASTALFLAG','LOB']).sort_index()
		else:
			parsed = re.search(r'Insurable\.AAL\.(?P<year>[0-9]{4})\_q(?P<prob>(50|([0-9]+\.[0-9]+)))(\.[0-9]{4})?\.csv', filepath)
			if not parsed:
				print('Error parsing ' + filepath)
				continue
			year = int(parsed.group('year'))
			quant = float(parsed.group('prob'))
			files[year][quant] = pd.read_csv(filepath).set_index(['STATE','COASTALFLAG','LOB']).sort_index()

	for y in range(2010,2110,10):
		data[y] = pd.concat(files[y], axis=0, names = ['QUANTILE'])

	all_data = pd.concat(data, axis=0, names = ['YEAR']).sort_index()

	return all_data

def write_data(data, fpath):
	data.to_csv(fpath)

def main(directory):
	data = get_all_data(directory)
	writedir = os.path.dirname(os.path.normpath(directory))
	newfpath = os.path.join(writedir, os.path.basename(os.path.normpath(directory)) + '.csv')
	write_data(data, newfpath)

if __name__ == "__main__":
	if len(sys.argv) > 0:
		main(sys.argv[1])
	else:
		print('Read directory path required. Aborting...')