# -*- coding: utf-8 -*-
"""Utility functions for handling crop data files.
"""
__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import math, os

def get_ssv(fp, byline, latitude, longitude, nrows, ncols, x0_corner, y1_corner, sizex, sizey):
    """Extract a single grid-located value out of a file of space-separated values."""
    # Translate lat, lon into row, col
    row = nrows - int(math.floor((latitude - y1_corner) / sizey)) - 1
    col = int(math.floor((longitude - x0_corner) / sizex))

    # Ignore the first 6 lines (define spacing of grid, given in arguments)
    for ii in range(6):
        fp.readline()

    if byline: # each line is a row
        for ii in range(row):
            fp.readline()
        index = col
    else: # all of the values are on 1 line
        index = row*ncols + col

    line = fp.readline()
    values = line.split(" ")
    return values[index]

def datapath(datarel):
    """Return a path relative to the data directory."""
    dir = os.path.dirname(__file__)
    return os.path.join(dir, '../data/', datarel)

def rootpath(datarel):
    """Return a path relative to the root directory."""
    dir = os.path.dirname(__file__)
    return os.path.join(dir, '../', datarel)
