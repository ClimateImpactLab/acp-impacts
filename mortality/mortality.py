# -*- coding: utf-8 -*-
"""Helper functions for mortality impacts
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv, os

"""Map from age names to file group names: agename is one of 0-0, 1-44, 45-64, 65-inf"""
age_group_mapping = {'0-0': ["< 1 year"], '1-44': ["1-4 years", "5-9 years", "10-14 years", "15-19 years", "20-24 years", "25-34 years", "35-44 years"], '45-64': ["45-54 years", "55-64 years"], '65-inf': ["65-74 years", "75-84 years", "85+ years"]}

def load_mortality_rates():
    """Load the mortality rates.
    Return a dictionary from fips to mortality rate."""

    scales = {}
    # Collect total deaths from 1990 to 2010
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "cmf-1999-2010.txt")) as countyfp:
        reader = csv.reader(countyfp, delimiter='\t')
        reader.next() # skip header

        total_numer = 0
        total_denom = 0
        for row in reader:
            if len(row) < 5:
                continue
            numer = float(row[3]) # deaths
            denom = float(row[4]) # population
            total_numer += numer
            total_denom += denom
            scales[row[2]] = numer / denom # county-specific death rate

        scales['mean'] = total_numer / total_denom # Average death rate (total deaths / total population)

        return scales

def load_mortality_age_rates(agename):
    """Load the mortality rates for a given age group.
    Return a dictionary from fips to age-specific mortality rate."""

    # Collect the non-age-specific rates
    scales = load_mortality_rates()
    groups = age_group_mapping[agename] # Get the columns we want

    scales_numer = {}
    scales_denom = {}
    # Load file of age-specific deaths
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "cmf-age-1999-2010.txt")) as countyfp:
        reader = csv.reader(countyfp, delimiter='\t')
        reader.next() # skip header

        total_numer = 0
        total_denom = 0
        for row in reader:
            if len(row) < 5 or row[1] not in groups: # only take one of our groups
                continue
            numer = float(row[5]) # age-specific deaths
            denom = float(row[6]) # age-specific population
            # Add to totals
            total_numer += numer
            total_denom += denom
            # Add to county-specific values across ages
            scales_numer[row[4]] = scales_numer.get(row[4], 0) + numer
            scales_denom[row[4]] = scales_denom.get(row[4], 0) + denom

    # Create death rates
    for fips in scales:
        if fips in scales_numer and fips in scales_denom:
            scales[fips] = scales_numer[fips] / scales_denom[fips]

    scales['mean'] = total_numer / total_denom

    return scales

def load_age_populations(agename, total_populations=None):
    """Load the total population for a given age group.
    Return a dictionary from fips to age-specific population."""

    groups = age_group_mapping[agename] # Get the columns we want

    populations = {}
    # Load populations from county death files
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "cmf-age-1999-2010.txt")) as countyfp:
        reader = csv.reader(countyfp, delimiter='\t')
        reader.next() # skip header

        for row in reader:
            if len(row) < 5 or row[1] not in groups: # Only take rows for given age
                continue
            population = float(row[6])
            populations[row[4]] = populations.get(row[4], 0) + population / 12.0 # summed over 12 years, so take average population


    # Fill in using average age-population rates (age_population / total_population) where unavailable
    if total_populations is not None:
        # Use a census dataset
        rate_numer = 0
        rate_denom = 0
        for fips in populations:
            if fips in total_populations:
                rate_numer += populations[fips]
                rate_denom += total_populations[fips]

        rate = float(rate_numer) / rate_denom

        # Fill in missing fipes
        for fips in total_populations:
            if fips not in populations:
                populations[fips] = rate * total_populations[fips]

    return populations

if __name__ == '__main__':
    # Report the average death rates by age group
    for group in age_group_mapping:
        print group, load_mortality_age_rates(group)['mean']
