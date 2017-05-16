# -*- coding: utf-8 -*-
"""Script to extract the variance contributions from a collection of results.
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import tarfile, os, csv
import numpy as np

import results

# Set of results to report for
impacts = ['health-mortage-0-0', 'health-mortage-1-44', 'health-mortage-45-64', 'health-mortage-65-inf', 'crime-violent', 'crime-property', 'health-mortality', 'labor-total-productivity', 'labor-high-productivity', 'labor-low-productivity', 'yields-cotton', 'yields-grains', 'yields-oilcrop', 'yields-cotton-noco2', 'yields-grains-noco2', 'yields-oilcrop-noco2', 'yields-maize', 'yields-wheat', 'yields-maize-noco2', 'yields-wheat-noco2', 'yields-total', 'yields-total-noco2']
# Set of years limits to report
yearses = [(2020, 2039), (2040, 2059), (2080, 2099)]
# Only use reslts that have one of these check files
checks = ['check-20140609', 'chkcge-20140609']
# Collect results from all MC batches
batches = map(lambda i: 'batch-' + str(i), range(25))
# Only take national results
suffix = '-national'
# Place the results in uncertain/
outdir = 'uncertain'
# Use working directories with the prefix uncwork
workdir = 'uncwork'
# Evaluate the result at each percentile
evalpvals = list(np.linspace(.01, .99, 99))

base_model = 'hadgem2-ao' # Choose a model to compare variance against
base_realization = '001' # Choose a realization to compare variance against

def collect_result(impact, batch, rcp, model, realization, targetdir, data):
    """Collect the results for a paricular target directory, and filter them into data."""
    print targetdir

    collection = batch + '-' + realization

    # Extract the values
    os.mkdir(workdir + suffix)
    os.chdir(workdir + suffix)
    os.system("tar -xzf " + os.path.join(targetdir, impact + suffix + ".tar.gz"))
    os.chdir('..')

    # Go through all regions
    for name in os.listdir(os.path.join(workdir + suffix, impact + suffix)):
        if name == impact:
            continue # just the directory

        region = name[0:-4]

        # Open up this region's results
        with open(os.path.join(workdir + suffix, impact + suffix, name)) as fp:
            # Get the values for our year sets
            values = results.get_yearses(fp, yearses)
            if not values:
                continue

            # Store everything in the data dictionary-of-dictionaries-of-...
            for ii in range(len(yearses)):
                dist = rcp + '-' + str(yearses[ii][0])

                if dist not in data:
                    data[dist] = {}
                if region not in data[dist]:
                    data[dist][region] = {}
                if collection not in data[dist][region]:
                    data[dist][region][collection] = {}

                data[dist][region][collection][model] = np.mean(values[ii])

    os.system('rm -r ' + workdir + suffix)

def write_result(impact, prefix, dist, data):
    """Report the results for a given rcp-year set."""
    if dist not in data:
        return

    # Write the results out to a CSV file
    with open(os.path.join(outdir, prefix + '-' + impact + '-' + dist + '.csv'), 'w') as csvfp:
        writer = csv.writer(csvfp, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['region'] + evalpvals)

        # Go through all known regions
        for region in data[dist].keys():
            allvalues = []
            allweights = []

            # Get the GCM-weighted values
            for collection in data[dist][region]:
                (values, valueweights) = results.weighted_values(data[dist][region][collection], weights)
                allvalues += values
                allweights += valueweights

            if len(allvalues) == 0:
                continue

            print dist, region, len(allvalues)

            # Construct an ECDF
            distribution = results.WeightedECDF(allvalues, allweights)

            # Evaluate all percentiles
            writer.writerow([region] + list(distribution.inverse(evalpvals)))

# Set up the result directory
if not os.path.exists(outdir):
    os.mkdir(outdir)

# Report result for every impact
for impact in impacts:
    print impact

    # Collect all available results
    # { rcp-year0 => { region => { batch-realization => { model => value } } } }
    hold_model_realization = {}
    hold_model_impact = {}
    hold_realization_impact = {}
    hold_nothing = {}

    # Go through all median result sets for a baseline
    for (pdir, rcp, model, realization, pvals, targetdir) in results.iterate_byp("/home/jrising/impacts"):
        if pdir != 'pmed':
            continue

        if impact + suffix + ".tar.gz" not in os.listdir(targetdir):
            continue

        # Collect the result into the hold_model_impact and hold_realization_impact data structures
        if model == base_model:
            collect_result(impact, pdir, rcp, model, realization, targetdir, hold_model_impact)
        if realization == base_realization:
            collect_result(impact, pdir, rcp, model, realization, targetdir, hold_realization_impact)

    # Go through all Monte Carlo result sets to understand the variance
    for (batch, rcp, model, realization, pvals, targetdir) in results.iterate_montecarlo("/home/jrising/impacts", batches=batches):
        # Make sure this is a valid result set
        if not results.directory_contains(targetdir, checks):
            continue

        if batch not in batches:
            continue

        if impact + suffix + ".tar.gz" not in os.listdir(targetdir):
            continue

        # Filter the result into the hold_model_realization data structure
        if model == base_model and realization == base_realization:
            collect_result(impact, batch, rcp, model, realization, targetdir, hold_model_realization)
        # Filter the result into the hold_nothing data structure
        collect_result(impact, batch, rcp, model, realization, targetdir, hold_nothing)

    # Combine across all batch-realizations that have all models
    for rcp in results.rcps:
        weights = results.get_weights(rcp)

        for years in yearses:
            dist = rcp + '-' + str(years[0])

            # Write out the distributions for each set of held assumptions
            write_result(impact, 'model', dist, hold_realization_impact)
            write_result(impact, 'weather', dist, hold_model_impact)
            write_result(impact, 'impact', dist, hold_model_realization)
            write_result(impact, 'total', dist, hold_nothing)
