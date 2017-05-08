

with open(lslmedfile,'r') as readfile:
	csvreader = csv.reader(readfile,delimiter='\t',quotechar='"')
	unit = next(csvreader)[0]
	header = next(csvreader)
	
	data = {}

	for line in csvreader:
		GAUGEID = int(row[2])
		year = int(row[5])
		data[year] = dict('rcp26':int(row[6]),'rcp45':int(row[7]),'rcp85':int(row[8]))

for year in range(20)
