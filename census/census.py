# -*- coding: utf-8 -*-
"""Functions for handling census data

The `get_populations_2010` and `fill_missing` functions handle the
reading and processing of census data, contained in DataSet.txt.
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv, os

def get_populations_2010(drop_noncounty=False):
    """Return a dictionary of the population in 2010, with a key for each county FIPS code.
    If drop_noncounty is false, state-level entries (with FIPS of the form XX000) will be dropped."""

    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "DataSet.txt")) as countyfp:
        reader = csv.reader(countyfp, delimiter=',')
        reader.next() # skip header

        scales = {} # {fips: pop2010}
        for row in reader:
            if drop_noncounty and row[0][2:5] == '000':
                continue

            scales[row[0]] = float(row[6])

        return scales

def fill_missing(scales, callback, drop_noncounty=False):
    """Fill in missing values from a `scales` dictionary of the form {FIPS: weight}, using population data.

    Each missing county will produce a call to `callback` with its
    population in 2010, which should return the missing county weight.
    """

    populations = get_populations_2010(drop_noncounty)

    for fips in populations:
        if fips not in scales:
            scales[fips] = callback(populations[fips])

