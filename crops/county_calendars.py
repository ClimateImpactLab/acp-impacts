# -*- coding: utf-8 -*-
"""Extracts the planting and harvesting dates for each crop at the county centroid.
"""
__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv
from lib import cropcal, area

# Map each local name to a Sacks data name
crops = {"cotton": ["Cotton"], "maize": ["Maize", "Maize.2"], "soy": ["Soybeans"], "wheat": ["Wheat", "Wheat.Winter"]}

# Collect the planting, harvesting, and area data for each crop
for crop in crops:
    plants = [] # the planting date data files
    harvests = [] # the harvesting date data files
    tars = [] # the tar containing the data files above (to be closed later)
    areas = [] # the CropCalendarArea objects

    # Open each calendar
    for calcrop in crops[crop]:
        (plant, harvest, tar) = cropcal.open_calendar(calcrop, filled=True)
        area = area.CropCalendarArea(calcrop)

        plants.append(plant)
        harvests.append(harvest)
        tars.append(tar)
        areas.append(area)

    # Write data to a file
    with open("../data/" + crop + ".csv", 'w') as resfp:
        # Use the centroids of each county
        with open("../data/centroids.csv", 'r') as fipsfp:
            reader = csv.reader(fipsfp, delimiter=',')
            for row in reader:
                longitude = float(row[1])
                latitude = float(row[2])

                # Search the crop variety with the maximum area
                maxarea = 0
                maxarea_ii = 0
                for ii in range(len(areas)):
                    # Which is the biggest
                    croparea = area.sum_ll9(latitude, longitude)
                    if croparea > maxarea:
                        maxarea = croparea
                        maxarea_ii = ii

                # Get the crop calendar for the variety with the maximum area
                (plantday, harvestday) = cropcal.get_calendar_opened(plants[maxarea_ii], harvests[maxarea_ii], latitude, longitude)
                line = ','.join([row[0], str(plantday), str(harvestday)])
                print line
                resfp.write(line + "\n")

