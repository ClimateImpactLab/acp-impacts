# -*- coding: utf-8 -*-
"""Functions for handling weather files.
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import os, csv
import numpy as np

# An example surface temperature dataset
county_dir = "/home/dmr/county_text/access1-3/rcp45/tas"

def date_to_datestr(date):
    """Standard format for data strings."""
    return ''.join([date.year, date.month, date.day])

def get_tas(datestr1, datestr2=None):
    """Yield tuples of (fips, data) for each county, where data consists
    of weather values from the date `datestr1` to date `datestr2`."""

    # Iterate through county files
    for filename in os.listdir(county_dir):
        parts = filename.split('.')[0].split('_')
        fips = parts[4]
        if len(fips) < 5:
            fips = '0' + fips
        print parts[4:-3]

        # Read this county's data
        with open(os.path.join(county_dir, filename), 'rU') as weatherfp:
            weatherfp.readline()
            reader = csv.reader(weatherfp, delimiter=',')

            for row in reader:
                if row[0] == datestr1:
                    break

            if row[1] == '-99.99':
                continue # Ignore missing data

            if datestr2 is None: # Just return single value
                yield (fips, float(row[1]))
                continue

            # Collect data up to (but not including) given date 2
            data = [float(row[1])]

            for row in reader:
                if row[0] == datestr2:
                    break
                data.append(float(row[1]))

            yield (fips, data)

def get_crop_calendar(cropfile):
    """Returns a dictionary from fips to (planting day of year, harvesting
    day of year) from the given pre-processed data file."""

    cropcals = {}
    with open(cropfile, 'rU') as fipsfp:
        reader = csv.reader(fipsfp, delimiter=',')
        for row in reader:
            if row[1] == "None":
                continue

            plantday = int(row[1])
            harvestday = int(row[2])
            cropcals[row[0]] = (plantday, harvestday)

    return cropcals

def growing_season(cropfile, year):
    """Yield the weather data for the growing season of each county."""

    # Get planting and harvesting dates
    cropcals = get_crop_calendar(cropfile)

    # Iterate through full year of data
    for fips, data in get_tas(str(year) + '0101', str(year + 1) + '0101'):
        if fips not in cropcals:
            continue

        (plantday, harvestday) = cropcals[fips]
        if plantday < 1:
            continue

        # Subset out the days we need
        yield (fips, np.mean(data[(plantday-1):harvestday]))

def growing_seasons_mean_reader(reader, plantday, harvestday):
    """Takes a CSV reader of weather data and yields each year's growing season values.
    Assumes temppath has rows YYYYMMDD,#### and yields (year, temp)
    Allows negative plantday
    """
    prevtemps = None
    row = reader.next()
    # Iterate until exhausted all years
    more_rows = True
    while more_rows:
        year = row[0][0:4]
        temps = [float(row[1]) if row[1] != '-99.99' else float('NaN')]

        # Collect all rows with the same year
        more_rows = False
        for row in reader:
            if row[0][0:4] != year:
                more_rows = True # There are more years to collect
                break

            temps.append(float(row[1]) if row[1] != '-99.99' else float('NaN'))

        # Handle negative (previous year) planting dates
        if plantday < 0:
            if prevtemps is not None:
                temp = np.mean(prevtemps[plantday:] + temps[0:harvestday])
                yield (int(year), temp)

            prevtemps = temps
        else:
            temp = np.mean(temps[plantday:harvestday])
            yield (int(year), temp)

def growing_seasons_mean_ncdf(yyyyddd, weather, plantday, harvestday):
    """Takes a matrix from a NetCDF file and yields each year's average growing season weather.
    Allows negative plantday.
    """

    # If planting date < 0, take from previous year
    if plantday < 0:
        year0 = yyyyddd[0] // 1000
        seasons = np.array_split(weather, range(plantday - 1, len(yyyyddd), 365))
    else:
        year0 = yyyyddd[0] // 1000 + 1
        seasons = np.array_split(weather, range(plantday - 1 + 365, len(yyyyddd), 365))
    year1 = yyyyddd[-1] // 1000

    # Return values for each year
    for chunk in zip(range(year0, year1 + 1), seasons):
        yield (chunk[0], np.mean(chunk[1][0:harvestday-plantday+1]))

    # Version 1 (slower but more intuitive)
    #ii = 0
    #while ii < len(yyyyddd):
    #    year = yyyyddd[ii] // 1000
    #    if ii + plantday - 1 >= 0 and ii + harvestday <= len(yyyyddd):
    #        mean = np.mean(weather[ii:ii+365][plantday-1:harvestday])
    #        ii += 365
    #        yield (year, mean)
    #    else:
    #        ii += 365

def growing_seasons_daily_ncdf(yyyyddd, weather, plantday, harvestday):
    """Takes a matrix from a NetCDF file and yields each year's set of daily growing season weather values.
    Allows negative plantday.
    """

    # If planting date < 0, take from previous year
    if plantday < 0:
        year0 = yyyyddd[0] // 1000
        index0 = plantday - 1
    else:
        year0 = yyyyddd[0] // 1000 + 1
        index0 = plantday - 1 + 365
    year1 = yyyyddd[-1] // 1000

    # `weather` may be just a collection of data, or a dictionary of variable -> data
    if isinstance(weather, list):
        # Return the subsetted data
        seasons = np.array_split(weather, range(plantday - 1, len(yyyyddd), 365))
        for chunk in zip(range(year0, year1 + 1), seasons):
            yield (chunk[0], chunk[1][0:harvestday-plantday+1])
    else:
        # Create a new dictionary of subsetted data for each variable
        seasons = {}
        for variable in weather:
            seasons[variable] = np.array_split(weather[variable], range(plantday - 1, len(yyyyddd), 365))

        for year in range(year0, year1 + 1):
            yield (year, {variable: seasons[variable][year - year0][0:harvestday-plantday+1] for variable in seasons})

    # Version 1 (slower but more intuitive)
    #ii = 0
    #while ii < len(yyyyddd):
    #    year = yyyyddd[ii] // 1000
    #    if ii + plantday - 1 >= 0 and ii + harvestday <= len(yyyyddd):
    #        if isinstance(weather, list):
    #            yield (year, weather[ii:ii+365][plantday-1:harvestday])
    #        else:
    #            season = {}
    #            for variable in weather:
    #                season[variable] = weather[variable][ii:ii+365][plantday-1:harvestday]
    #            yield (year, season)
    #        ii += 365
    #    else:
    #        ii += 365

def yearly_daily_ncdf(yyyyddd, weather):
    """Yield each year's data, assuming each year has 365 days."""

    year0 = int(yyyyddd[0]) // 1000
    year1 = int(yyyyddd[-1]) // 1000
    chunks = zip(range(year0, year1+1), np.array_split(weather, range(365, len(yyyyddd), 365)))
    for chunk in chunks:
        yield chunk

    # Version 2 (slower but more intuitive)
    #for ii in xrange(0, len(yyyyddd), 365):
    #    yield (yyyyddd[ii] // 1000, weather[ii:ii+365])

    # Version 1 (slower but more intuitive)
    #ii = 0
    #while ii < len(yyyyddd):
    #    year = yyyyddd[ii] // 1000
    #    if ii + 365 <= len(yyyyddd):
    #        yield (year, weather[ii:ii+365])
    #        ii += 365
    #    else:
    #        ii += 365

def combo_effects(effect_dicts, scale_gens):
    """Combine multiple impacts, using the given scalings to make all commensurate.
    effect_dicts and scale_gens must be lists of same length, containing iterators (key, val) with same keys.
    """
    numers = {}
    denoms = {}
    # Go through the impacts
    for ii in range(len(effect_dicts)):
        # Apply scaling for each region
        for (key, scale) in scale_gens[ii]:
            if scale == 0 or key not in effect_dicts[ii]:
                continue

            if key not in numers:
                numers[key] = 0
                denoms[key] = 0

            # Construct region-specific weighted average
            numers[key] += effect_dicts[ii][key] * scale
            denoms[key] += scale

    # Return weighted averages
    return {key: numers[key] / denoms[key] for key in numers}

def read_scale_file(filepath, factor):
    """Read a file of scalings into a dictionary of fips -> weight."""

    with open(filepath, "r") as fp:
        reader = csv.reader(fp, delimiter=',')
        for row in reader:
            # Ignore NAs
            if row[1] == 'NA':
                continue

            fips = row[0]
            if len(fips) == 4:
                fips = '0' + fips
            # Multiply all by `factor`
            yield (fips, float(row[1]) * factor)
