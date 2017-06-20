# -*- coding: utf-8 -*-
"""Script to extract the variance contributions, holding each GCM as the baseline GCM in turn.
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import tarfile, os, csv
import numpy as np
import results, impacts

# Period to estimate results for
yearses = [(2080, 2099)]
only_rcp = 'rcp85'
only_realization = '001' # Choose a realization to compare variance against

# Only use reslts that have one of these check files
checks = ['check-20140609', 'chkcge-20140609']
# Collect results from all MC batches
batches = map(lambda i: 'batch-' + str(i), range(25))
# Only take national results
suffix = '-national'
# Place the results in uncertain-test/
outdir = 'uncertain-test'
# Use working directories with the prefix uncwork
workdir = 'uncwork'
# Evaluate the result at each percentile
evalpvals = list(np.linspace(.01, .99, 99))

# All climate models to hold as the baseline
models = ['access1-0', 'access1-3', 'bcc-csm1-1', 'bcc-csm1-1-m', 'bnu-esm', 'canesm2', 'ccsm4', 'cesm1-bgc', 'cesm1-cam5', 'cmcc-cm', 'cnrm-cm5', 'csiro-mk3-6-0', 'fgoals-g2', 'fio-esm', 'gfdl-cm3', 'gfdl-esm2g', 'gfdl-esm2m', 'giss-e2-r', 'hadgem2-ao', 'hadgem2-cc', 'hadgem2-es', 'inmcm4', 'ipsl-cm5a-lr', 'ipsl-cm5a-mr', 'ipsl-cm5b-lr', 'miroc5', 'miroc-esm', 'miroc-esm-chem', 'mpi-esm-lr', 'mpi-esm-mr', 'mri-cgcm3', 'noresm1-m', 'noresm1-me', 'pattern1', 'pattern2', 'pattern3', 'pattern38', 'pattern39', 'pattern4', 'pattern40', 'pattern41', 'pattern42', 'pattern43', 'pattern44']

# Collect the results for a given Monte Carlo run into our data dictionary
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

def write_result(impact, model, prefix, dist, data):
    """Report the results for a given rcp-year set for a given model."""
    if dist not in data:
        return

    # Write the results out to a CSV file
    with open(os.path.join(outdir, impact + '-' + prefix + '-' + model + '-' + dist + '.csv'), 'w') as csvfp:
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
for impact in impacts.allimpacts:
    # Consider each GCM to be the baseline
    for base_model in models:
        # Collect all available results
        # { rcp-year0 => { region => { batch-realization => { model => value } } } }
        hold_model = {}
        hold_impact = {}
        hold_nothing = {}

        # Go through all median result sets for a baseline
        for (pdir, rcp, model, realization, pvals, targetdir) in results.iterate_byp("/home/jrising/impacts"):
            if pdir != 'pmed' or rcp != only_rcp or realization != only_realization:
                continue

            if impact + suffix + ".tar.gz" not in os.listdir(targetdir):
                continue

            collect_result(impact, pdir, rcp, model, realization, targetdir, hold_impact)

        # Go through all Monte Carlo result sets to understand the variance
        for (batch, rcp, model, realization, pvals, targetdir) in results.iterate_montecarlo("/home/jrising/impacts", batches=batches):
            # Make sure this is a valid result set
            if rcp != only_rcp or realization != only_realization:
                continue

            if not results.directory_contains(targetdir, checks):
                continue

            if batch not in batches:
                continue

            if impact + suffix + ".tar.gz" not in os.listdir(targetdir):
                continue

            # Filter the result into the hold_model if we are at th base model
            if model == base_model:
                collect_result(impact, batch, rcp, model, realization, targetdir, hold_model)
            collect_result(impact, batch, rcp, model, realization, targetdir, hold_nothing)

        # Combine across all batch-realizations that have all models
        weights = results.get_weights(only_rcp)

        for years in yearses:
            dist = only_rcp + '-' + str(years[0])

            # Write out the distributions for each set of held assumptions
            write_result(impact, base_model, 'model', dist, hold_impact)
            write_result(impact, base_model, 'impact', dist, hold_model)
            write_result(impact, base_model, 'total', dist, hold_nothing)
