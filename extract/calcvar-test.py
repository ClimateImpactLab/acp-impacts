# -*- coding: utf-8 -*-
"""Script to calculate the standard deviation for uncertain-test.py results.
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
print "\t".join(['name', 'basemod', 'model', 'impact', 'total'])

# Results stored under uncertain-test/
path = "uncertain-test"

# Look for each file
for filename in os.listdir(path):
    # Only collect on set of assumptions and then infer the filenames of the others
    if '-impact-' not in filename:
        continue

    # Our full set of assumptions
    parts = ['model', 'impact', 'total']

    # Collect the ECDF for each assumption
    values = {} # assumption -> std. dev.
    for part in parts:
        partpath = os.path.join(path, filename.replace('-impact-', '-' + part + '-'))
        if not os.path.exists(partpath):
            values[part] = 'NA'
            continue

        with open(partpath, 'r') as csvfp:
            reader = csv.reader(csvfp)
            pp = map(float, reader.next()[1:])
            xx = map(float, reader.next()[1:])

            # Take 10000000 draws from ECDF
            samples = np.random.choice(xx, 10000000, replace=True)
            values[part] = np.std(samples)

    front = filename.index('-impact-')
    back = front + 8

    # Report this impact
    print "\t".join([filename[:front], filename[back:-15]] + map(str, [values['model'], values['impact'], values['total']]))

