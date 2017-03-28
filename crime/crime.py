# -*- coding: utf-8 -*-
"""Functions for handling crime data

The `load_crime_rates` reports a crime rate, as a number of crimes per
year, for every county, using average crime rates.

"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv, os

def load_crime_rates(crime_type, census):
    """Constructs a dictionary of {fips => scale}.  The scales are the number of crimes in a year.
    crime_type: 0 for violent, 1 for property
    census: the census module
    """

    # Rates for all missing counties, estimated prepate_ranson.R
    adjusted_rates = [0.000746744, 0.001751664] # average rates (violent, property) * mean(2000-2005 pop) / 2010 pop

    # Construct the county-specific scales dictionary
    scales = {}
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "baseline.csv")) as countyfp:
        reader = csv.reader(countyfp, delimiter=',')
        reader.next() # skip header

        for row in reader:
            if row[crime_type + 1] == 'NA':
                continue
            scales[row[0]] = float(row[crime_type + 1])

    census.fill_missing(scales, lambda pop: pop * adjusted_rates[crime_type], drop_noncounty=True)

    return scales
