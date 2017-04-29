# -*- coding: utf-8 -*-
"""Construct a data file of the portion of each state used for each crop.
"""
__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv

# Read in crop areas for each crop by state
states = {}
with open("croparea-2007-state.csv") as areas:
    reader = csv.reader(areas)
    reader.next()
    for row in reader:
        # row[5] is the state, row[14] is the crop, row[18] is the area
        if row[5] not in states: # Add a dictionary for this state
            states[row[5]] = {}
        if row[18] == ' (D)': # If the data is missing, ignore the row
            continue
        states[row[5]][row[14]] = float(row[18].replace(',', ''))

# Information about the number and sizes of farms by state
with open("farmarea-state.csv") as farms:
    reader = csv.reader(farms, delimiter="\t")
    reader.next()
    for row in reader:
        if row[1].upper() not in states: # Ignore any new states
            continue
        state = states[row[1].upper()]
        if float(row[5]) == 0: # Ignore empty states
            continue
        denom = float(row[5])*1e6 # What is the total area of farms in the sate
        total = sum(state.values()) / denom # If only have 1/4 of data, ignore state
        if total < .25:
            continue
        # Report the portion of the state for each crop
        print ','.join(map(str, [row[0], state.get("COTTON", 0) / denom, state.get("CORN", 0) / denom, state.get("SOYBEANS", 0) / denom, state.get("WHEAT", 0) / denom, 1 - total]))

