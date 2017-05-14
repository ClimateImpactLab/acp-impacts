# -*- coding: utf-8 -*-
"""Functions for handling county definitions
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv, os

def state_abbr(acradir):
    """Get a mapping from each state name to its 2-letter abbreviation."""
    result = {}

    with open(os.path.join(acradir, "iam/geography/states.csv"), 'rU') as fipsfp:
        reader = csv.reader(fipsfp, dialect=csv.excel_tab, delimiter=',')
        for row in reader:
            result[row[0].upper()] = row[1]

    return result

def abbr_state(acradir):
    """Get a mapping from each 2-letter abbreviation to its state name."""
    result = {}

    with open(os.path.join(acradir, "iam/geography/states.csv"), 'rU') as fipsfp:
        reader = csv.reader(fipsfp, dialect=csv.excel_tab, delimiter=',')
        for row in reader:
            result[row[1]] = row[0].upper()

    return result

def state_fipsdict(acradir):
    """Returns a dictionary of dictionaries of the form {STATE ABBR: {FIPS: County Name}}."""
    result = {}

    with open(os.path.join(acradir, "iam/geography/fips_codes.csv"), 'rU') as fipsfp:
        reader = csv.reader(fipsfp, dialect=csv.excel_tab, delimiter=',')
        reader.next()
        for row in reader:
            if row[-1] != "County":
                continue

            if row[0] not in result:
                result[row[0]] = {}

            result[row[0]][row[1] + row[2]] = row[5]

    return result

def state_countydict(acradir):
    """Returns a dictionary of dictionaries of the form {STATE ABBR: {County Name: FIPS}}."""
    result = {}

    with open(os.path.join(acradir, "iam/geography/fips_codes.csv"), 'rU') as fipsfp:
        reader = csv.reader(fipsfp, dialect=csv.excel_tab, delimiter=',')
        reader.next()
        for row in reader:
            if row[-1] not in ["County", "consolidated government", "unified government", "Parish", "metropolitan government", "Borough", "city and borough", "borough"] and not (row[0] == 'RI' and row[-1] == 'town'):
                continue

            if row[0] not in result:
                result[row[0]] = {}

            result[row[0]][row[5]] = row[1] + row[2]

    # Provide convenience mappings for common spelling differences
    result['AL']['De Kalb'] = result['AL']['DeKalb']
    result['GA']['Chattahoochee'] = result['GA']['Cusseta-Chattahoochee']
    result['GA']['Cusseta'] = result['GA']['Cusseta-Chattahoochee']
    result['GA']['Athens'] = result['GA']['Athens-Clarke']
    result['GA']['Clarke'] = result['GA']['Athens-Clarke']
    result['IL']['De Kalb'] = result['IL']['DeKalb']
    result['IL']['Du Page'] = result['IL']['DuPage']
    result['IL']['La Salle'] = result['IL']['LaSalle']
    result['MN']['Lac Qui Parle'] = result['MN']['Lac qui Parle']
    result['MO']['De Kalb'] = result['MO']['DeKalb']
    result['MT']['Deer Lodge'] = result['MT']['Anaconda-Deer Lodge']
    result['MT']['Silver Bow'] = result['MT']['Butte-Silver Bow']
    result['ND']['Lamoure'] = result['ND']['LaMoure']
    result['TN']['Moore'] = result['TN']['Lynchburg-Moore']
    result['DC'] = {'District of Columbia': '11001'}

    return result
