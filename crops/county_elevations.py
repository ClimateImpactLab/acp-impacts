# -*- coding: utf-8 -*-
"""Estimate elevations for each county.

This script queries the GLOBE digital elevation model in the IRI data
library to get the elevation of each county centroid.
"""
__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import sys
sys.path.append("lib")

import csv, urllib

# Write out the results to data/elevation.csv
with open("../data/elevation.csv", 'w') as resfp:
    # Centroids are in data/centroids.csv
    with open("../data/centroids.csv", 'r') as fipsfp:
        reader = csv.reader(fipsfp, delimiter=',')
        for row in reader:
            longitude = float(row[1])
            latitude = float(row[2])

            # This uses the IRI data library API to get a single elevation
            elevation = urllib.urlopen("http://iridl.ldeo.columbia.edu/expert/SOURCES/.NOAA/.NGDC/.GLOBE/.topo/Y/%f/VALUE/X/%f/VALUE/[X]data.tsv" % (latitude, longitude)).read().strip()

            line = ','.join([row[0], elevation])
            print line
            resfp.write(line + "\n")

