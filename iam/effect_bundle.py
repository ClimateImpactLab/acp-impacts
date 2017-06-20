# -*- coding: utf-8 -*-
################################################################################
# Copyright 2014, Distributed Meta-Analysis System
################################################################################

"""Software structure for generating Monte-Carlo collections of results.

NOTE: Items flagged -D- are specific to directory structure of the ACP
project, and should be extracted to a 'forecasts.py' module.

NOTE: Items flagged -I- assume specific input file structures, and
should be extracted to an 'inputs.py' module.

NOTE: Highest resolution regions are implicitly assumed to be
FIPS-coded counties, but the logic does not require them to be.  FIPS
language should be replaced with generic ID references.

A key structure is the make_generator(fips, times, values) function.
make_generator is passed to the functions that iterate through
different weather forecasts, such as make_tar_ncdf.  It is then called
with each location and daily weather data.  fips is a single county
code, times is a list of yyyyddd formated date values, values is a
list of weather values.

The output of make_generator() is a generator, producing tuples (year,
effect), for whichever years an effect can be computed.

-D-
Input file directory structure:

Input weather files are within a directory structure [WDS]:
  <realization>/<scenario>/<model>/*

The final model subdirectory is the weather forecast directory [WFD].
This directory is assumed to have directories (named for variables),
which each include a single file with the following filename structure:
county_ncdc_daily_<realization>_<variable>_<full-model-name>_<scenario>_\d{6}-2\d{5}\.nc

-I-
Input file organization:

CSV files are organized in directories, with separate files for each
FIPS-coded county.

NetCDFs are organized in arrays, with daily rows and a column for each
county.

Days are listed in yyyyddd form, with ddd from 0 to 364.  All years
(both reconstructed historical and forecasts) are 365 days long.

Output file structure:

Each bundle of output impact results of a given type and for a given
weather forecast are in a gzipped tar file containing a single
directory <name>, containing a separate csv file (an effect file) for each
region.  The format of the csv file is:
  year,<label>[,<other labels>]*
  <year>,<impact>[,<prior calculated impact>]*

Basic processing logic:

Some functions, like find_ncdfs_allreal, discover collections of
forecasted variables (within the WDS directory structure), and provide
through enumerators.  Variable collections are dictionaries {variable:
REFERENCE}, where REFERENCE may be a filename, a netCDF, or a
dictionary of {original: netCDF object, data: [days x counties],
times: [yyyyddd]}. [VRD]

Controllers (elsewhere) loop through these, and for each available
forecast call a make_tar_* function passing in a make_generator
function.  The make_tar_* functions call make_generator with each
individual region, retrieving a set of results, and then package those
results into the output file format.

Temporary directories (characterized by random letters) are used to
hold the results as they're being generated (before being bundled into
tars).
"""

__copyright__ = "Copyright 2014, Distributed Meta-Analysis System"

__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import tarfile, os, csv, re, random, string, gzip, tempfile, shutil, warnings
import numpy as np
try:
    # this is required for nc4's, but we can wait to fail
    from netCDF4 import Dataset
except:
    pass

FIPS_COMPLETE = '__complete__' # special FIPS code for the last county

### Variable Discovery

# -D-
short_historical_pr_ncdf = '/home/dmr/county/ncdf/obs/daily/prcp/county_ncdc_daily_prcp_obs_198101-201012.nc'
short_historical_tas_ncdf = '/home/dmr/county/ncdf/obs/daily/tas/county_ncdc_daily_tas_obs_198101-201012.nc'
short_historical_tasmax_ncdf = '/home/dmr/county/ncdf/obs/daily/tasmax/county_ncdc_daily_tasmax_obs_198101-201012.nc'
short_historical_tasmin_ncdf = '/home/dmr/county/ncdf/obs/daily/tasmin/county_ncdc_daily_tasmin_obs_198101-201012.nc'

long_historical_pr_ncdf = '/home/dmr/county/ncdf/obs/daily/prcp/county_ncdc_daily_prcp_1961-2013.nc'
long_historical_tas_ncdf = '/home/dmr/county/ncdf/obs/daily/tas/county_ncdc_daily_tas_1961-2013.nc'
long_historical_tasmax_ncdf = '/home/dmr/county/ncdf/obs/daily/tasmax/county_ncdc_daily_tasmax_1961-2013.nc'
long_historical_tasmin_ncdf = '/home/dmr/county/ncdf/obs/daily/tasmin/county_ncdc_daily_tasmin_1961-2013.nc'

# -D-
default_weather_ncdf = "/home/dmr/county_climate/smme/15032014/daily/001/rcp45/access1-3/tas/county_ncdc_daily_001_tas_access1-3_rcp45_200001-210012.nc"
default_weather_pr_ncdf = "/home/dmr/county_climate/smme/15032014/daily/001/rcp45/access1-3/pr/county_ncdc_daily_001_pr_access1-3_rcp45_200001-210012.nc"
default_weather_tasmin_ncdf = "/home/dmr/county_climate/smme/15032014/daily/001/rcp45/access1-3/tasmin/county_ncdc_daily_001_tasmin_access1-3_rcp45_200001-210012.nc"
default_weather_tasmax_ncdf = "/home/dmr/county_climate/smme/15032014/daily/001/rcp45/access1-3/tasmax/county_ncdc_daily_001_tasmax_access1-3_rcp45_200001-210012.nc"

# -I-
def canonical_fips(fips):
    """Construct a standardized 5-digit fips code."""

    fips = str(fips)
    if len(fips) < 5:
        fips = '0' + fips

    return fips

# -I-
def make_tar_text(name, weather_dir, make_generator):
    """Construct a tar bundle <name>.tar.gz, using text weather files in <weather_dir>.
    make_generator(fips, reader) returns generator of (year, effect) pairs
    """

    # Put files into <name> directory
    if not os.path.exists(name):
        os.mkdir(name)

    # Each file in <weather_dir> describes a forecast for a different FIPS
    for filename in os.listdir(weather_dir):
        # Extract the FIPS from the filename
        parts = filename.split('.')[0].split('_')
        fips = canonical_fips(parts[4]) # FIPS is the 5th element
        print fips, parts[5], ' '.join(parts[6:-2])

        # Read all of the data as a CSV file
        with open(os.path.join(weather_dir, filename), 'rU') as weatherfp:
            weatherfp.readline()
            reader = csv.reader(weatherfp, delimiter=',')

            # Pass data to make_generator to get yearly result
            generator = make_generator(fips, reader)
            if generator is None:
                continue

            # Output the data to a file <name>/<fips>.csv
            write_effect_file(name, fips, generator, "fraction")

    # tar and gzip all of the generated files
    os.system("tar -czf " + name + ".tar.gz " + name)
    os.system("rm -r " + name)

# -D-
def find_ncdfs_allreal(root='/home/dmr/county_climate/smme/15032014/daily/', ncdfset=None):
    """Crawls through a weather directory structure (see [WDS]) to find all forecasts.
    Yields ({variable: filename}, realization, scenario, model),
    Unless ncdfset is a historical set; then realization is list of years; scenario is 'noccscen' or 'truehist'.
    """

    if ncdfset is not None:
        if ncdfset == 'truehist':
            # Return the true history, 1961 - 2014
            years = range(1961, 2014)

            variables = get_historical_variables(years, 1961, True)

            yield (variables, years, ncdfset, None)
            return
        elif ncdfset == "modelhist":
            # Just set a different root, but treat identical to normal sets
            root = "/home/dmr/county/ncdf/16052014/daily/"
        elif ncdfset == "mcpr":
            for ncdfs in find_ncdfs_onereal("/home/dmr/acp_climate/", "mcpr"):
                yield (ncdfs[0], 'mcpr', ncdfs[1], ncdfs[2])
            return
        else:
            # Return 100 MC generated histories, sampled from the 1981 - 2011 "baseline" period
            for jj in range(100):
                years = [random.sample(range(1981, 2011), 1)[0] for ii in range(100)]

                variables = get_historical_variables(years, 2000, False)

                yield (variables, years, ncdfset + str(jj + 1), None)
            return

    # Within each realization, call find_ncdfs_onereal()
    for realization in os.listdir(root):
        for ncdfs in find_ncdfs_onereal(root, realization):
            yield (ncdfs[0], realization, ncdfs[1], ncdfs[2])

# -D-
def find_ncdfs_onereal(root='/home/dmr/county_climate/smme/15032014/daily/', realization='001'):
    """Crawls through a weather directory structure (see [WDS]) to
    find all forecasts under a given realization subdirectory.
    Yields ({variable: filename}, scenario, model).
    """

    # Assumes that files are located in <realization>/<scenario>/<model>/*
    # Look through all files in <realization>
    for scenario in os.listdir(os.path.join(root, realization)):
        scenariodir = os.path.join(root, realization, scenario)
        # Look through all files in <realization>/<scenario>
        for model in os.listdir(scenariodir):
            modeldir = os.path.join(scenariodir, model)

            # Identify defined variables within <realization>/<scenario>/<model>
            vartuple = get_variables(realization, scenario, model, root=root)
            if vartuple is not None:
                yield vartuple

# -D-
def get_variables(realization, scenario, model, root='/home/dmr/county_climate/smme/15032014/daily/'):
    """Identifies all of the variables in a weather forecast directory (see [WFD]).
    Construct a dictionary of {variable: filename} to each netcdf file.
    Returns ({variable: filename}, scenario, model)
    """

    modeldir = os.path.join(root, realization, scenario, model)
    if not os.path.exists(modeldir):
        return None # This forecast doesn't exist!

    try:
        variables = {} # result of the function
        fullmodel = None # name of the model

        # Find all netcdfs within this directory
        for variable in os.listdir(modeldir):
            vardir = os.path.join(modeldir, variable)

            # We assume that there's just one
            for filename in os.listdir(vardir):
                # Check the filename and extract the full-model name
                match = re.match(r'county_ncdc_daily_' + realization + '_' + variable + '_(.*?)_' + scenario + '_\d{6}-2\d{5}\.nc', filename)
                if not match:
                    match = re.match(r'' + variable + '_mcpr-(.*?)_daily_county_' + scenario + '_19810101-22001231\.nc\.gz', filename)
                if match:
                    if fullmodel is None:
                        fullmodel = match.group(1) # we've figured out the full-model name
                    elif fullmodel != match.group(1):
                        raise "Inconsistent full-models" # different netcdfs from different models?
                    variables[variable] = os.path.join(vardir, filename) # add to the result set

        if variables: # Make sure we found something
            return (variables, scenario, fullmodel)
        else: # if there were no variables
            print "No match:", 'county_ncdc_daily_' + realization + '_' + variable + '_' + model + '.*?_' + scenario + '_DDDDDD-2DDDDD.nc'
    except Exception as e:
        print e
        print "No daily:", dailydir

    return None # Something went wrong

## Another version in cclib
def get_arbitrary_variables(path):
    variables = {} # result of the function

    # Find all netcdfs within this directory
    for root, dirs, files in os.walk(path):
        for filename in files:
            # Check the filename
            match = re.match(r'.+?(pr|tasmin|tasmax).+?\.nc', filename)
            if match:
                variable = match.group(1)
                filepath = os.path.join(root, filename)
                variables[variable] = filepath # add to the result set
                print "Found %s: %s" % (variable, filepath)
            else:
                match = re.match(r'.+?(tas).+?\.nc', filename)
                if match:
                    variable = match.group(1)
                    filepath = os.path.join(root, filename)
                    variables[variable] = filepath # add to the result set
                    print "Found %s: %s" % (variable, filepath)

    return variables

# -D-
def get_historical_variables(years, year0, use_long):
    """Construct the variables dictionary for historical observations;
    years is list of years to use from historical observations, year0
    is the initial year to list results at, use_long if drawing from
    'extended' historical observations
    Result contains pr, tas, tasmax, and tasmin.
    """

    if use_long: # Long-history is from 1961
        return {'pr': get_historical_variable(years, year0, long_historical_pr_ncdf, 'prcp', 1961),
                'tas': get_historical_variable(years, year0, long_historical_tas_ncdf, 'tas', 1961),
                'tasmax': get_historical_variable(years, year0, long_historical_tasmax_ncdf, 'tasmax', 1961),
                'tasmin': get_historical_variable(years, year0, long_historical_tasmin_ncdf, 'tasmin', 1961)}
    else: # Short-history is from 1981
        return {'pr': get_historical_variable(years, year0, short_historical_pr_ncdf, 'prcp', 1981),
                'tas': get_historical_variable(years, year0, short_historical_tas_ncdf, 'tas', 1981),
                'tasmax': get_historical_variable(years, year0, short_historical_tasmax_ncdf, 'tasmax', 1981),
                'tasmin': get_historical_variable(years, year0, short_historical_tasmin_ncdf, 'tasmin', 1981)}

# -I-
def get_historical_variable(years, year0, filename, var, datayear0):
    """Extract a single historical variable from an observation netcdf.
    If year0 != datayear0, the years are renumbered to appear to begin at year0

    years is list of years to use from historical observations
    year0 is the initial year to list results at
    filename is a single netcdf file
    var is a variable contained in the file
    datayear0 is the initial year to collect results at
    """

    # Open the netcdf file
    rootgrp = Dataset(filename, 'r+', format='NETCDF4')
    # Extract the variable
    allyears = rootgrp.variables[var][:,:]

    results = [] # list of years across all counties [365 x #FIPS]
    times = [] # continuous yyyyddd numbering of days in results

    for year in years: # for each year we want a result for...
        start = int((year - datayear0)*365.25) # Identify the year to retrieve
        results.append(allyears[start:(start + 365),:]) # Extract the data
        times += range(year0 * 1000, year0 * 1000 + 365)
        year0 += 1

    # Return a variable reference in {original, data, times} form (see VRF)
    return dict(original=rootgrp, data=np.concatenate(results), times=times)

def close_ncdf(variables):
    """Takes a variable dictionary (see VRD) and closes any open netcdfs.
    """

    for var in variables:
        # Check which convention is used for this variable
        if isinstance(variables[var], str) or isinstance(variables[var], unicode): # Just a filename
            pass
        elif isinstance(variables[var], dict) and 'original' in variables[var]:
            variables[var]['original'].close() # Only need to close the original netcdf
        else:
            variables[var].close()

### Effect Bundle Generation

## Temporary directory management

def enter_local_tempdir(prefix=''):
    """Create and set the working directory as a new temporary directory.

    Returns the name of the temporary directory (to be passed to
    exit_local_tempdir).
    """

    suffix = ''.join(random.choice(string.lowercase) for i in range(6))

    os.mkdir(prefix + suffix)
    os.chdir(prefix + suffix)

    return prefix + suffix

def exit_local_tempdir(tempdir, killit=True):
    """Return to the root output directory (and optionally delete the
    temporary directory).

    tempdir is the output of enter_local_tempdir.
    """

    os.chdir("..")
    if killit:
        kill_local_tempdir(tempdir)

def kill_local_tempdir(tempdir):
    """Remove all contents of a temporary directory.

    Call after exit_local_tempdir is called, only if killit=False.
    """

    os.system("rm -r " + tempdir)

## General helper functions for creation

def send_fips_complete(make_generator):
    """Call after the last county of a loop of counties, to clean up any memory.
    """

    print "Complete the FIPS"
    try:
        make_generator(FIPS_COMPLETE, None, None).next()
        print "Success"
    except StopIteration, e:
        pass
    except Exception, e:
        print e
        pass

def get_target_path(targetdir, name):
    """Helper function to use the targetdir directory if its provided.
    """

    if targetdir is not None:
        return os.path.join(targetdir, name)
    else:
        return name

def write_effect_file(path, fips, generator, collabel):
    """Write the effects for a single FIPS-coded county.

    path: relative path for file
    fips: the unique id of the region
    generator: a enumerator of tuples/lists with individual rows
    collabel: label for one (string) or more (list) columns after the
    year column
    """

    # Create the CSV file
    with open(os.path.join(path, fips + '.csv'), 'wb') as csvfp:
        writer = csv.writer(csvfp, quoting=csv.QUOTE_MINIMAL)

        # Write the header row
        if not isinstance(collabel, list):
            writer.writerow(["year", collabel])
        else:
            writer.writerow(["year"] + collabel)

        # Write all data rows
        for values in generator:
            writer.writerow(values)

## Top-level bundle creation functions

def make_tar_dummy(name, acradir, make_generator, targetdir=None, collabel="fraction"):
    """Constructs a tar of files for each county, using NO DATA.
    Calls make_generator for each county, using a filename of
    counties.

    name: the name of the effect bundle.
    acradir: path to the DMAS acra directory.
    make_generator(fips, times, daily): returns an iterator of (year, effect).
    targetdir: path to a final destination for the bundle
    collabel: the label for the effect column
    """

    tempdir = enter_local_tempdir()
    os.mkdir(name) # directory for county files

    # Generate a effect file for each county in regionsA
    with open(os.path.join(acradir, 'regions/regionsANSI.csv')) as countyfp:
        reader = csv.reader(countyfp)
        reader.next() # ignore header

        # Each row is a county
        for row in reader:
            fips = canonical_fips(row[0])
            print fips

            # Call generator (with no data)
            generator = make_generator(fips, None, None)
            if generator is None:
                continue

            # Construct the effect file
            write_effect_file(name, fips, generator, collabel)

    send_fips_complete(make_generator)

    # Generate the bundle tar
    target = get_target_path(targetdir, name)
    os.system("tar -czf " + os.path.join("..", target) + ".tar.gz " + name)

    # Remove the working directory
    exit_local_tempdir(tempdir)

def make_tar_duplicate(name, filepath, make_generator, targetdir=None, collabel="fraction"):
    """Constructs a tar of files for each county that is described in
    an existing bundle.  Passes NO DATA to make_generator.

    name: the name of the effect bundle.
    filepath: path to an existing effect bundle
    make_generator(fips, times, daily): returns an iterator of (year, effect).
    targetdir: path to a final destination for the bundle
    collabel: the label for the effect column
    """

    tempdir = enter_local_tempdir()
    os.mkdir(name)

    # Iterate through all FIPS-titled files in the effect bundle
    with tarfile.open(filepath) as tar:
        for item in tar.getnames()[1:]:
            fips = item.split('/')[1][0:-4]
            print fips

            # Call make_generator with no data
            generator = make_generator(fips, None, None)
            if generator is None:
                continue

            # Construct the effect file
            write_effect_file(name, fips, generator, collabel)

    send_fips_complete(make_generator)

    # Generate the bundle tar
    target = get_target_path(targetdir, name)
    os.system("tar -czf " + os.path.join("..", target) + ".tar.gz " + name)

    # Remove the working directory
    exit_local_tempdir(tempdir)

def make_tar_ncdf(name, weather_ncdf, var, make_generator, targetdir=None, collabel="fraction"):
    """Constructs a tar of files for each county, describing yearly results.

    name: the name of the effect bundle.
    weather_ncdf: str for one, or {variable: filename} for calling
      generator with {variable: data}.
    var: str for one, or [str] for calling generator with {variable: data}
    make_generator(fips, times, daily): returns an iterator of (year, effect).
    targetdir: path to a final destination for the bundle, or a
      function to take the data
    collabel: the label for the effect column
    """

    # If this is a function, we just start iterating
    if hasattr(targetdir, '__call__'):
        call_with_generator(name, weather_ncdf, var, make_generator, targetdir)
        return

    # Create the working directory
    tempdir = enter_local_tempdir()
    os.mkdir(name)

    # Helper function for calling write_effect_file with collabel
    def write_csv(name, fips, generator):
        write_effect_file(name, fips, generator, collabel)

    # Iterate through the data
    call_with_generator(name, weather_ncdf, var, make_generator, write_csv)

    # Create the effect bundle
    target = get_target_path(targetdir, name)
    os.system("tar -czf " + os.path.join("..", target) + ".tar.gz " + name)

    # Remove the working directory
    exit_local_tempdir(tempdir)

def call_with_generator(name, weather_ncdf, var, make_generator, targetfunc):
    """Helper function for calling make_generator with each variable
    set.  In cases with multiple weather datasets, assumes all use the
    same clock (sequence of times) and geography (sequence of
    counties).

    name: the name of the effect bundle.
    weather_ncdf: str for one, or {variable: filename} for calling
      generator with {variable: data}.
    var: str for one, or [str] for calling generator with {variable: data}
    make_generator(fips, times, daily): returns an iterator of (year, effect).
    targetfunc: function(name, fips, generator) to handle results
    """

    if isinstance(weather_ncdf, dict) and isinstance(var, list):
        # In this case, we generate a dictionary of variables
        weather = {}
        times = None # All input assumed to have same clock

        # Filter by the variables in var
        for variable in var:
            # Retrieve the netcdf object (rootgrp) and add to weather dict
            if isinstance(weather_ncdf[variable], str) or isinstance(weather_ncdf[variable], unicode):
                if weather_ncdf[variable][-3:] == '.gz':
                    filename = "mytemp" + ''.join(random.choice(string.lowercase) for i in range(6)) + ".nc"
                    with gzip.open(weather_ncdf[variable]) as gfp:
                        with open(filename, 'wb') as nfp:
                            shutil.copyfileobj(gfp, nfp)
                else:
                    filename = weather_ncdf[variable]
                # Open this up as a netCDF and read data into array
                rootgrp = Dataset(filename, 'r+', format='NETCDF4')
                weather[variable] = rootgrp.variables[variable][:,:]
                # Delete temporary file, if used
                if filename != weather_ncdf[variable]:
                    os.unlink(filename)
            elif isinstance(weather_ncdf[variable], dict):
                # This is an {original, data, times} dictionary
                rootgrp = weather_ncdf[variable]['original']
                weather[variable] = weather_ncdf[variable]['data']
                if 'times' in weather_ncdf[variable]:
                    times = weather_ncdf[variable]['times']
            else:
                # This is already a netcdf object
                rootgrp = weather_ncdf[variable]
                weather[variable] = rootgrp.variables[variable][:,:]

            # Collect additional information from netcdf object
            counties = rootgrp.variables['fips']
            lats = rootgrp.variables['lat']
            lons = rootgrp.variables['lon']
            if times is None:
                times = rootgrp.variables['time']
    else:
        # We just want a single variable (not a dictionary of them)
        # Retrieve the netcdf object (rootgrp) and add to weather dict
        if isinstance(weather_ncdf, str) or isinstance(weather_ncdf, unicode):
            if weather_ncdf[-3:] == '.gz':
                filename = "mytemp" + ''.join(random.choice(string.lowercase) for i in range(6)) + ".nc"
                with gzip.open(weather_ncdf) as gfp:
                    with open(filename, 'wb') as nfp:
                        shutil.copyfileobj(gfp, nfp)
            else:
                filename = weather_ncdf
            # Open this up as a netCDF and read into array
            rootgrp = Dataset(filename, 'r+', format='NETCDF4')
            weather = rootgrp.variables[var][:,:]
            # Delete temporary file, if used
            if filename != weather_ncdf:
                os.unlink(filename)
        elif isinstance(weather_ncdf, dict):
            # This is an {original, data, times} dictionary
            rootgrp = weather_ncdf['original']
            weather = weather_ncdf['data']
        else:
            # This is already a netcdf object
            rootgrp = weather_ncdf
            weather = rootgrp.variables[var][:,:]

        # Collect additional information from netcdf object
        counties = rootgrp.variables['fips']
        lats = rootgrp.variables['lat']
        lons = rootgrp.variables['lon']
        times = rootgrp.variables['time']

    # Loop through counties, calling make_generator with each
    for ii in range(len(counties)):
        fips = canonical_fips(counties[ii])
        print fips

        # Extract the weather just for this county
        if not isinstance(weather, dict):
            daily = weather[:,ii]
        else:
            daily = {}
            for variable in weather:
                daily[variable] = weather[variable][:,ii]

        # Call make_generator for this county
        generator = make_generator(fips, times, daily, lat=lats[ii], lon=lons[ii])
        if generator is None:
            continue

        # Call targetfunc with the result
        targetfunc(name, fips, generator)

    # Signal the end of the counties
    send_fips_complete(make_generator)

def make_tar_ncdf_profile(weather_ncdf, var, make_generator):
    """Like make_tar_ncdf, except that just goes through the motions,
    and only for 100 counties
    weather_ncdf: str for one, or {variable: filename} for calling
      generator with {variable: data}.
    var: str for one, or [str] for calling generator with {variable: data}
    """

    # Open a single netCDF if only one filename passed in
    if isinstance(weather_ncdf, str):
        # Collect the necessary info
        rootgrp = Dataset(weather_ncdf, 'r+', format='NETCDF4')
        counties = rootgrp.variables['fips']
        lats = rootgrp.variables['lat']
        lons = rootgrp.variables['lon']
        times = rootgrp.variables['time']
        weather = rootgrp.variables[var][:,:]
    else:
        # Open all netCDF referenced in var
        weather = {} # Construct a dictionary of [yyyyddd x county] arrays
        for variable in var:
            rootgrp = Dataset(weather_ncdf[variable], 'r+', format='NETCDF4')
            counties = rootgrp.variables['fips']
            lats = rootgrp.variables['lat']
            lons = rootgrp.variables['lon']
            times = rootgrp.variables['time']
            weather[variable] = rootgrp.variables[variable][:,:]

    # Just do 100 counties
    for ii in range(100):
        # Always using 5 digit fips
        fips = canonical_fips(counties[ii])
        print fips

        # Construct the input array for this county
        if not isinstance(weather, dict):
            daily = weather[:,ii]
        else:
            daily = {}
            for variable in weather:
                daily[variable] = weather[variable][:,ii]

        # Generate the generator
        generator = make_generator(fips, times, daily, lat=lats[ii], lon=lons[ii])
        if generator is None:
            continue

        # Just print out the results
        print "year", "fraction"

        for (year, effect) in generator:
            print year, effect

### Effect calculation functions

## make_generator functions

def load_tar_make_generator(targetdir, name, column=None):
    """Load existing data for additional calculations.
    targetdir: relative path to a directory of effect bundles.
    name: the effect name (so the effect bundle is at <targetdir>/<name>.tar.gz
    """

    # Extract the existing tar into a loader tempdir
    tempdir = enter_local_tempdir('loader-')
    os.system("tar -xzf " + os.path.join("..", targetdir, name + ".tar.gz"))
    exit_local_tempdir(tempdir, killit=False)

    def generate(fips, yyyyddd, temps, *args, **kw):
        # When all of the counties are done, kill the local dir
        if fips == FIPS_COMPLETE:
            print "Remove", tempdir
            # We might be in another tempdir-- check
            if os.path.exists(tempdir):
                kill_local_tempdir(tempdir)
            else:
                kill_local_tempdir(os.path.join('..', tempdir))
            return

        # Open up the effect for this bundle
        fipspath = os.path.join(tempdir, name, fips + ".csv")
        if not os.path.exists(fipspath):
            fipspath = os.path.join('..', fipspath)
            if not os.path.exists(fipspath):
                # If we can't find this, just return a single year with 0 effect
                print fipspath + " doesn't exist"
                yield (yyyyddd[0] / 1000, 0)
                raise StopIteration()

        with open(fipspath) as fp:
            reader = csv.reader(fp)
            reader.next() # ignore header

            # yield the same values that generated this effect file
            for row in reader:
                if column is None:
                    yield [int(row[0])] + map(float, row[1:])
                else:
                    yield (int(row[0]), float(row[column]))

    return generate

def make_scale(make_generator, scale_dict, func=lambda x, y: x*y):
    """Scale the results by the value in scale_dict, or the mean value (if it is set).
    make_generator: we encapsulate this function, passing in data and opporting on outputs
    func: default operation is to multiple (scale), but can do other things (e.g., - for re-basing)
    """

    def generate(fips, yyyyddd, temps, **kw):
        # Prepare the generator from our encapsulated operations
        generator = make_generator(fips, yyyyddd, temps, **kw)
        # Scale each result
        for (year, result) in generator:
            if fips in scale_dict:
                yield (year, func(result, scale_dict[fips]))
            else:
                yield (year, func(result, scale_dict['mean']))

    return generate


## make-apply logic for generating make_generators

def make(handler, make_generator, *handler_args, **handler_kw):
    """Construct a generator from a function, operating on the results of another generator.
    handler(generator, *handler_args, **handler_kw) takes an enumerator and returns an enumerator
    """

    # The make_generator function to return
    def generate(fips, yyyyddd, temps, *args, **kw):
        if fips == FIPS_COMPLETE:
            # Pass on signal for end
            print "completing make"
            make_generator(fips, yyyyddd, temps, *args, **kw).next()
            return

        # Pass on data
        generator = make_generator(fips, yyyyddd, temps, *args, **kw)
        # Apply function to results of data
        for yearresult in handler(generator, *handler_args, **handler_kw):
            yield yearresult

    return generate

def apply(generator, func, unshift=False):
    """Apply a non-enumerator to all elements of a function.
    if unshift, tack on the result to the front of a sequence of results.
    Calls func with each year and value; returns the newly computed value
    """

    for yearresult in generator:
        # Call func to get a new value
        newresult = func(yearresult[0], yearresult[1])

        # Construct a new year, value result
        if unshift:
            yield [yearresult[0], newresult] + yearresult[1:]
        else:
            yield (yearresult[0], newresult)

def make_instabase(make_generator, baseyear, func=lambda x, y: x / y):
    """Re-base the results of make_generator(...) to the values in baseyear
    Default func constructs a porportional change; x - y makes simple difference.
    """

    # Use the instabase function to do operations
    return make(instabase, make_generator, baseyear, func)

def instabase(generator, baseyear, func=lambda x, y: x / y, skip_on_missing=True):
    """Re-base the results of make_generator(...) to the values in baseyear
    baseyear is the year to use as the 'denominator'; None for the first year
    Default func constructs a porportional change; x - y makes simple difference.
    skip_on_missing: If we never encounter the year and this is false,
      still print out the existing results.
    Tacks on the value to the front of the results
    """

    denom = None # The value in the baseyear
    pastresults = [] # results before baseyear

    for yearresult in generator:
        year = yearresult[0]
        result = yearresult[1]

        # Should we base everything off this year?
        if year == baseyear or (baseyear is None and denom is None):
            denom = result

            # Print out all past results, relative to this year
            for pastresult in pastresults:
                yield [pastresult[0], func(pastresult[1], denom)] + list(pastresult[1:])

        if denom is None:
            # Keep track of this until we have a base
            pastresults.append(yearresult)
        else:
            # calculate this and tack it on
            yield [year, func(result, denom)] + list(yearresult[1:])

    if denom is None and skip_on_missing:
        # Never got to this year: just write out results
        for pastresult in pastresults:
            yield pastresult

def make_runaverage(make_generator, priors, weights, unshift=False):
    """Generate results as an N-year running average;
    priors: list of size N, with the values to use before we get data
    weights: list of size N, with the weights of the years (earliest first)
    """

    # Use the runaverage function to do all the operations
    return make(runaverage, make_generator, priors, weights, unshift)

def runaverage(generator, priors, weights, unshift=False):
    """Generate results as an N-year running average;
    priors: list of size N, with the values to use before we get data (first value not used)
    weights: list of size N, with the weights of the years (earliest first)
    unshift: if true, tack on result at front of result list
    """

    values = list(priors) # Make a copy of the priors list
    totalweight = sum(weights) # Use as weight denominator

    for yearresult in generator:
        # The set of values to average ends with the new value
        values = values[1:] + [yearresult[1]]
        # Calculate weighted average
        smoothed = sum([values[ii] * weights[ii] for ii in range(len(priors))]) / totalweight

        # Produce the new result
        if unshift:
            yield [yearresult[0], smoothed] + list(yearresult[1:])
        else:
            yield (yearresult[0], smoothed)

def make_weighted_average(make_generators, weights):
    """This produces a weighted average of results from *multiple generators*.
    make_generators: list of make_generator functions; all must produce identical years
    weights: list of weight dictionaries ({FIPS: weight})
    len(make_generators) == len(weights)
    """

    def generate(fips, yyyyddd, weather, **kw):
        # Is this county represented in any of the weight dictionaries?
        inany = False
        for weight in weights:
            if fips in weight and weight[fips] > 0:
                inany = True
                break

        if not inany:
            return # Produce no results

        # Construct a list of generators from make_generators
        generators = [make_generators[ii](fips, yyyyddd, weather, **kw) for ii in range(len(make_generators))]

        # Iterate through all generators simultaneously
        for values in generators[0]:
            # Construct a list of the value from each generator
            values = [values] + [generator.next() for generator in generators[1:]]
            # Ensure that year is identical across all
            for ii in range(1, len(generators)):
                assert(values[0][0] == values[ii][0])

            # Construct (year, result) where result is a weighted average using weights
            yield (values[0][0], np.sum([values[ii][1] * weights[ii].get(fips, 0) for ii in range(len(generators))]) /
                   np.sum([weights[ii].get(fips, 0) for ii in range(len(generators))]))

    return generate

def make_product(vars, make_generators):
    """This produces a product of results from *multiple generators*.
    vars: a list of single variables to pass into each generator
    make_generators: list of make_generator functions; all must produce identical years
    len(make_generators) == len(vars)
    """

    def generate(fips, yyyyddd, weather, **kw):
        # Construct a list of generators from make_generators
        generators = [make_generators[ii](fips, yyyyddd, weather[vars[ii]], **kw) for ii in range(len(make_generators))]

        # Iterate through all generators simultaneously
        for values in generators[0]:
            values = [values] + [generator.next() for generator in generators[1:]]
            # Ensure that year is identical across all
            for ii in range(1, len(generators)):
                assert(values[0][0] == values[ii][0])

            # Construct (year, result) where result is a product
            yield (values[0][0], np.product([values[ii][1] for ii in range(len(generators))]))

    return generate

### Aggregation from counties to larger regions

def aggregate_tar(name, scale_dict=None, targetdir=None, collabel="fraction", get_region=None, report_all=False):
    """Aggregates results from counties to larger regions.
    name: the name of an impact, already constructed into an effect bundle
    scale_dict: a dictionary of weights, per county
    targetdir: directory holding both county bundle and to hold region bundle
    collabel: Label for result column(s)
    get_region: either None (uses first two digits of FIPS-- aggregates to state),
      True (combine all counties-- aggregate to national),
      or a function(fips) => code which aggregates each set of counties producing the same name
    report_all: if true, include a whole sequence of results; otherwise, just take first one
    """

    # Get a region name and a get_region function
    region_name = 'region' # final bundle will use this as a suffix

    if get_region is None: # aggregate to state
        get_region = lambda fips: fips[0:2]
        region_name = 'state'
    elif get_region is True: # aggregate to nation
        get_region = lambda fips: 'national'
        region_name = 'national'
    else:
        # get a title, if get_region returns one for dummy-fips "_title_"
        try:
            title = get_region('_title_')
            if title is not None:
                region_name = title
        except:
            pass

    regions = {} # {region code: {year: (numer, denom)}}
    # This is the effect bundle to aggregate
    target = get_target_path(targetdir, name)

    # Generate a temporary directory to extract county results
    tempdir = enter_local_tempdir()
    # Extract all of the results
    os.system("tar -xzf " + os.path.join("..", target) + ".tar.gz")

    # Go through all counties
    for filename in os.listdir(name):
        # If this is a county file
        match = re.match(r'(\d{5})\.csv', filename)
        if match:
            code = match.groups(1)[0] # get the FIPS code

            # Check that it's in the scale_dict
            if scale_dict is not None and code not in scale_dict:
                continue

            # Check which region it is in
            region = get_region(code)
            if region is None:
                continue

            # Prepare the dictionary of results for this region, if necessary
            if region not in regions:
                regions[region] = {} # year => (numer, denom)

            # Get out the current dictioanry of years
            years = regions[region]

            # Go through every year in this effect file
            with open(os.path.join(name, filename)) as csvfp:
                reader = csv.reader(csvfp, delimiter=',')
                reader.next()

                if report_all: # Report entire sequence of results
                    for row in reader:
                        # Get the numerator and denominator for this weighted sum
                        if row[0] not in years:
                            numer, denom = (np.array([0] * (len(row)-1)), 0)
                        else:
                            numer, denom = years[row[0]]

                        # Add on one more value to the weighted sum
                        try:
                            numer = numer + np.array(map(float, row[1:])) * (scale_dict[code] if scale_dict is not None else 1)
                            denom = denom + (scale_dict[code] if scale_dict is not None else 1)
                        except Exception, e:
                            print e

                        # Put the weighted sum calculation back in for this year
                        years[row[0]] = (numer, denom)
                else: # Just report the first result
                    for row in reader:
                        # Get the numerator and denominator for this weighted sum
                        if row[0] not in years:
                            numer, denom = (0, 0)
                        else:
                            numer, denom = years[row[0]]

                        # Add on one more value to the weighted sum
                        numer = numer + float(row[1]) * (scale_dict[code] if scale_dict is not None else 1)
                        denom = denom + (scale_dict[code] if scale_dict is not None else 1)

                        # Put the weighted sum calculation back in for this year
                        years[row[0]] = (numer, denom)

    # Remove all county results from extracted tar
    os.system("rm -r " + name)

    # Start producing directory of region results
    dirregion = name + '-' + region_name
    if not os.path.exists(dirregion):
        os.mkdir(dirregion)

    # For each region that got a result
    for region in regions:
        # Create a new CSV effect file
        with open(os.path.join(dirregion, region + '.csv'), 'wb') as csvfp:
            writer = csv.writer(csvfp, quoting=csv.QUOTE_MINIMAL)
            # Include a header row
            if not isinstance(collabel, list):
                writer.writerow(["year", collabel])
            else:
                writer.writerow(["year"] + collabel)

            # Construct a sorted list of years from the keys of this region's dictionary
            years = map(str, sorted(map(int, regions[region].keys())))

            # For each year, output the weighted average
            for year in years:
                if regions[region][year][1] == 0: # the denom is 0-- never got a value
                    writer.writerow([year, 'NA'])
                else:
                    # Write out the year's result
                    if report_all:
                        writer.writerow([year] + list(regions[region][year][0] / float(regions[region][year][1])))
                    else:
                        writer.writerow([year, float(regions[region][year][0]) / regions[region][year][1]])

    # Construct the effect bundle
    target = get_target_path(targetdir, dirregion)
    os.system("tar -czf " + os.path.join("..", target) + ".tar.gz " + dirregion)

    # Clean up temporary directory
    exit_local_tempdir(tempdir)
