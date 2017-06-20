# -*- coding: utf-8 -*-
"""Script to calculate the standard deviation for uncertain.py results.
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv, os
import numpy as np
from statsmodels.distributions.empirical_distribution import StepFunction

# Print as a table
print "\t".join(['name', 'model', 'weather', 'impact', 'total'])

# Results stored under uncertain/
path = "uncertain"

# Look for each file
for filename in os.listdir(path):
    # Only collect on set of assumptions and then infer the filenames of the others
    if filename[0:6] != 'model-':
        continue

    # Our full set of assumptions
    parts = ['model', 'weather', 'impact', 'total']

    # Collect the ECDF for each assumption
    values = {} # assumption -> std. dev.
    for part in parts:
        with open(os.path.join(path, part + filename[5:]), 'r') as csvfp:
            reader = csv.reader(csvfp)
            pp = map(float, reader.next()[1:])
            xx = map(float, reader.next()[1:])

            # Take 100000 draws from ECDF
            samples = np.random.choice(xx, 100000, replace=True)
            values[part] = np.std(samples)

    # Report this impact
    print "\t".join([filename[6:-4]] + map(str, [values['model'], values['weather'], values['impact'], values['total']]))

