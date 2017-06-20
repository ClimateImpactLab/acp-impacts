# -*- coding: utf-8 -*-
"""Helper functions for result handling
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import os, csv
import numpy as np
from statsmodels.distributions.empirical_distribution import StepFunction

# The names of the RCP scenarios
rcps = ['rcp26', 'rcp45', 'rcp60', 'rcp85']

def make_pval_file(targetdir, pvals):
    """Create a file to contain the quantile information."""
    with os.fdopen(os.open(os.path.join(targetdir, "pvals.txt"), os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'w') as fp:
        for key in pvals:
            fp.write(key + ":\t" + str(pvals[key]) + "\n")

def read_pval_file(targetdir):
    """Read the quantile information from a file."""
    with open(os.path.join(targetdir, "pvals.txt"), 'r') as fp:
        pvals = {}
        for line in fp:
            parts = line.split("\t") # formated as "key:\tvalue"
            try:
                pvals[parts[0][0:-1]] = float(parts[1])
            except:
                pvals[parts[0][0:-1]] = parts[1]

    return pvals

def iterate(root):
    """Iterator through all results under a given root directory."""
    iterate_montecarlo(root)
    iterate_byp(root)

def iterate_montecarlo(root, batches=None):
    """Iterator through all Monte Carlo results under a given root directory."""
    # If truehist is request, only return this scenario
    if batches == 'truehist':
        # Look for batches under root
        batches = os.listdir(root)

        for batch in batches:
            if batch[0:6] != 'batch-':
                continue

            # Point to the truehist scenario
            targetdir = os.path.join(root, batch, 'truehist')
            if not os.path.exists(targetdir) or 'pvals.txt' not in os.listdir(targetdir):
                continue # Only consider results with pvals

            # Return all result set information
            pvals = read_pval_file(targetdir)

            yield (batch, 'truehist', 'truehist', 'truehist', pvals, targetdir)

        return

    if batches is None:
        # Iterate through all batches
        batches = os.listdir(root)

        for batch in batches:
            if batch[0:5] != 'batch':
                continue

            # Results returned by iterate_batch
            for result in iterate_batch(root, batch):
                yield result

    else:
        ## batches should be sequence of numbers
        for batchnum in batches:
            if os.path.exists(os.path.join(root, str(batchnum))):
                batch = batchnum
            else:
                batch = 'batch-' + str(batchnum)
                if not os.path.exists(os.path.join(root, batch)):
                    continue

            # Results returned by iterate_batch
            for result in iterate_batch(root, batch):
                yield result

def iterate_byp(root, batches=None):
    """Iterator through all constant-quantile results under a given root directory."""
    # The quantile value used by each named directory
    pdirs = dict(pmed=.5, plow=.33333, phigh=.66667)

    if batches == 'truehist':
        # If the truehist scenario is request, only look for this
        for pdir in pdirs.keys():
            targetdir = os.path.join(root, pdir, 'truehist')
            if not os.path.exists(targetdir) or 'pvals.txt' not in os.listdir(targetdir):
                continue # Ignore if no pval file

            # Yield the result set information
            pvals = read_pval_file(targetdir)

            yield (pdir, 'truehist', 'truehist', 'truehist', pvals, targetdir)

        return

    # Look only for the named directories
    for pdir in pdirs.keys():
        if not os.path.exists(os.path.join(root, pdir)):
            continue

        # Results returned by iterate_batch
        for result in iterate_batch(root, pdir):
            yield result

def iterate_batch(root, batch):
    """Find result, in a tree of the form <root>/<batch>/<rcp>/<model>/<realization>/<results>."""
    for rcp in os.listdir(os.path.join(root, batch)):
        try:
            for model in os.listdir(os.path.join(root, batch, rcp)):
                try:
                    for realization in os.listdir(os.path.join(root, batch, rcp, model)):
                        targetdir = os.path.join(root, batch, rcp, model, realization)
                        if 'pvals.txt' not in os.listdir(targetdir):
                            continue # Skip if no pvals information

                        # Return all the rest of the information
                        pvals = read_pval_file(targetdir)

                        yield (batch, rcp, model, realization, pvals, targetdir)
                except OSError:
                        continue
        except OSError:
            continue

def directory_contains(targetdir, oneof):
    """Check if a target directory contains at least one of the list of files."""
    files = os.listdir(targetdir)

    for filename in oneof:
        if filename in files:
            return True # We found one!

    return False

def get_weights(rcp):
    """Get the weights associated with models in this scenario.
    Return a dictionary of GCM -> weight
    """
    if rcp == 'truehist':
        return dict(truehist=1.0) # Degenerate case

    weights = {}

    # Read in the weights for this RCP
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'weights', rcp + 'w.csv')) as csvfp:
        reader = csv.reader(csvfp)
        for row in reader:
            weights[row[0]] = float(row[1])

    return weights

def weighted_values(values, weights):
    """Returns paired lists of results and their GCM weights.

    Args:
      values: Dictionary of GCM -> result value
      weights: Dictionary of GCM -> GCM weight
    """
    models = values.keys()
    values_list = [values[model] for model in models if model in weights]
    weights_list = [weights[model] for model in models if model in weights]

    return (values_list, weights_list)

class WeightedECDF(StepFunction):
    """Constructs a step function which is a empirical cummulative distribution function, with weighted steps."""
    def __init__(self, values, weights):
        """Takes a list of values and weights"""
        # Calculate the expected value of the distribution
        self.expected = sum(np.array(values) * np.array(weights)) / sum(weights)

        # Creat the cummulative sum that represents this ECDF
        order = sorted(range(len(values)), key=lambda ii: values[ii])
        self.values = np.array([values[ii] for ii in order])
        self.weights = [weights[ii] for ii in order]

        self.pp = np.cumsum(self.weights) / sum(self.weights)
        super(WeightedECDF, self).__init__(self.values, self.pp, sorted=True)

    def inverse(self, pp):
        """Determine the value at a given probability.
        pp may be an array of probabilities
        """
        if len(np.array(pp).shape) == 0:
            pp = np.array([pp])

        # Determine the index for interior solutions
        indexes = np.searchsorted(self.pp, pp) - 1

        useiis = indexes
        # Handle points below the lowest stp
        useiis[indexes < 0] = 0

        results = np.array(self.values[useiis], dtype=float)
        results[indexes < 0] = -np.inf

        return results

def get_yearses(fp, yearses):
    """Get the given years of results, for collections of year sets."""
    if yearses[0][0] < 1000:
        # Just head and tail or tail of results
        reader = csv.reader(fp)
        reader.next()
        values = [float(row[1]) for row in reader]

        # Return a list of all requested subsets
        results = []
        for years in yearses:
            if years[0] > 0:
                results.append(values[years[0]:years[1]])
            elif years[1] == 0:
                results.append(values[years[0]:])
            else:
                results.append(values[years[0]:years[1]])

        return results

    # Create a list of results
    results = []
    reader = csv.reader(fp) # Read the results

    yearses_ii = 0
    found = False
    values = []
    for row in reader:
        if not found: # We are still looking for the start of this year-set
            try:
                if int(row[0]) >= yearses[yearses_ii][0]:
                    found = True # We found it
            except:
                pass

        if found: # Add on this values
            if row[1] != 'NA':
                values.append(float(row[1]))
            if int(row[0]) == yearses[yearses_ii][1]: # That's the last year of this set
                found = False
                results.append(values)
                values = []
                yearses_ii += 1

    if found: # If there are any left over results
        results.append(values)

    return results

def get_years(fp, years, column=2):
    """Return the results for the given years, as specifically requested years."""
    results = []
    reader = csv.reader(fp)
    reader.next()

    years_ii = 0 # Start by looking for the first year
    for row in reader:
        # Oops, we're asking for a year outside of the range
        while years_ii < len(years) and int(row[0]) > years[years_ii]:
            results.append(None)
            years_ii += 1

        # We have no more years to collect
        if years_ii == len(years):
            break

        # Look for the given year
        if int(row[0]) == years[years_ii]:
            if row[column-1] != 'NA':
                results.append(float(row[column-1]))
            else:
                results.append(None)
            years_ii += 1
        else:
            results.append(None) # row[0] < year

    return results

def iterate_bundle(targetdir, impact, suffix, working_suffix=''):
    """Yield a file pointer to each file in the given result bundle."""

    # Create a working directory to extract into
    if os.path.exists('working' + working_suffix):
        os.system('rm -r working' + working_suffix)
    os.mkdir('working' + working_suffix)
    os.chdir('working' + working_suffix)
    os.system("tar -xzf " + os.path.join(targetdir, impact + suffix + ".tar.gz"))
    os.chdir('..')

    # Go through all region files
    for name in os.listdir(os.path.join('working' + working_suffix, impact + suffix)):
        if name == impact:
            continue # just the directory

        region = name[0:-4]

        # Open this result and produce it
        with open(os.path.join('working' + working_suffix, impact + suffix, name)) as fp:
            yield (region, fp)

    # Remove the working directory
    os.system('rm -r working' + working_suffix)
