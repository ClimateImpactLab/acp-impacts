# -*- coding: utf-8 -*-
"""Handler of region-specific results information

Region-specific results use region-specific regional definitions.
These definitions are sets of counties which collectively define a
large region.  The region definitions are stored in the CSV files in
this directory.

See the docstring for `load_region_definitions` for more information.

"""
__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv

def load_region_definitions(csvpath, region_column, fips_column, title=None):
    """
    Return a dictionary with the region for each county, as a mapping
    of FIPS code to region name.

    Args:
        csvpath: Path to one of the CSV files in this directory
        region_column: Column defining the names of regions
        fips_column: Column listing each FIPS code
        title: The region definition title, used by functions that use this mapping.
    """
    with open(csvpath, "r") as fp:
        reader = csv.reader(fp)
        reader.next()

        regions = {'_title_': title}
        for row in reader:
            fips = row[fips_column]
            if len(fips) == 4:
                fips = '0' + fips

            if fips in regions:
                print "Duplicate region for FIPS", fips

            regions[fips] = row[region_column]

        return regions
