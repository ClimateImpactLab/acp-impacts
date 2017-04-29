# -*- coding: utf-8 -*-
"""Interface to the crop calendar data from Sacks et al. 2010, Crop planting dates: an analysis of global patterns.
"""
__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import tarfile
import datahelp

# All available crops
crops = ["Barley.Winter", "Barley", "Cassava", "Cotton", "Groundnuts", "Maize.2", "Maize", "Millet", "Oats.Winter", "Oats", "Potatoes", "Pulses", "Rapeseed.Winter", "Rice.2", "Rice", "Rye.Winter", "Sorghum.2", "Sorghum", "Soybeans", "Sugarbeets", "Sunflower", "Sweet.Potatoes", "Wheat.Winter", "Wheat", "Yams"]

def opentar(crop, filled=False):
    """Open the tar containing the given data."""
    if crop == "Soybean":
        crop = "Soybeans"

    if filled:
        return tarfile.open(datahelp.datapath("ALL_CROPS_ArcINFO_0.5deg_filled/%s.crop.calendar.fill.tar.gz" % (crop)))
    else:
        return tarfile.open(datahelp.datapath("ALL_CROPS_ArcINFO_0.5deg_unfilled/%s.crop.calendar.tar.gz" % (crop)))

def get_calendar(crop, latitude, longitude, tar=None, filled=False):
    """Get the planting date and harvesting date for a given location."""
    # Use .5 degrees, unfilled

    # From the top of the file
    ncols = 720
    nrows = 360
    x0_corner = -180
    y1_corner = -90
    sizex = sizey = .5

    # Only open (and close) a new tar if one is not given
    closetar = False
    if tar is None:
        tar = opentar(crop, filled)
        closetar = True

    # Correct spelling of soybeans
    if crop == "Soybean":
        crop = "Soybeans"

    # Open the planting date file
    if filled:
        plant = tar.extractfile("%s.crop.calendar.fill/plant.asc" % (crop))
    else:
        plant = tar.extractfile("%s.crop.calendar/plant.asc" % (crop))

    # Extract the given value
    value = datahelp.get_ssv(plant, False, latitude, longitude, nrows, ncols, x0_corner, y1_corner, sizex, sizey)
    if "e" in value or value == "\n":
        if closetar:
            tar.close()
        return (None, None)

    plantday = int(float(value))
    plant.close()

    # Open the harvest date file
    if filled:
        harvest = tar.extractfile("%s.crop.calendar.fill/harvest.asc" % (crop))
    else:
        harvest = tar.extractfile("%s.crop.calendar/harvest.asc" % (crop))

    # Extract the given value
    harvestday = int(float(datahelp.get_ssv(harvest, False, latitude, longitude, nrows, ncols, x0_corner, y1_corner, sizex, sizey)))
    harvest.close()

    if harvestday < plantday:
        plantday = plantday - 365

    if closetar:
        tar.close()

    # Return the values
    return (plantday, harvestday)

def get_calendar_plus(crop, latitude, longitude, plus):
    """Get the planting date and harvesting date for a given location, with sensible fall-backs."""
    if plus == 'Required': # Just use the interpolated data
        return get_calendar(crop, latitude, longitude, filled=True)

    # Try to collect the data normally
    plantday, harvestday = get_calendar(crop, latitude, longitude)

    if plus and plantday is None:
        # If date is not available, try a different variety
        if crop == "Wheat" or crop == "Barley" or crop == "Oats":
            plantday, harvestday = get_calendar(crop + ".Winter", latitude, longitude)
        elif crop == "Maize" or crop == "Rice" or crop == "Sorghum":
            plantday, harvestday = get_calendar(crop + ".2", latitude, longitude)

    if plus and plantday is None:
        # If date is still not available, try neighboring locations
        plantday, harvestday = get_calendar(crop, latitude, longitude - .5)
        if plantday is None:
            plantday, harvestday = get_calendar(crop, latitude, longitude + .5)
        if plantday is None:
            plantday, harvestday = get_calendar(crop, latitude - .5, longitude)
        if plantday is None:
            plantday, harvestday = get_calendar(crop, latitude + .5, longitude)
        if not plantday is None:
            print "Using a neighboring calendar"

    return plantday, harvestday

def open_calendar(crop, tar=None, filled=False):
    """Open the relevant calendar file, to extract several items."""
    if tar is None:
        tar = opentar(crop, filled)

    if crop == "Soybean":
        crop = "Soybeans"

    if filled:
        plant = tar.extractfile("%s.crop.calendar.fill/plant.asc" % (crop))
    else:
        plant = tar.extractfile("%s.crop.calendar/plant.asc" % (crop))

    if filled:
        harvest = tar.extractfile("%s.crop.calendar.fill/harvest.asc" % (crop))
    else:
        harvest = tar.extractfile("%s.crop.calendar/harvest.asc" % (crop))

    return (plant, harvest, tar)

def get_calendar_opened(plant, harvest, latitude, longitude):
    """Get the planting date and harvesting date for a given location, given pre-opened files."""
    plant.seek(0)
    harvest.seek(0)

    # Use .5 degrees, unfilled
    # From the top of the file
    ncols = 720
    nrows = 360
    x0_corner = -180
    y1_corner = -90
    sizex = sizey = .5

    # Collect the value
    value = datahelp.get_ssv(plant, False, latitude, longitude, nrows, ncols, x0_corner, y1_corner, sizex, sizey)
    if "e" in value or value == "\n":
        return (None, None)

    # Get the plant date
    plantday = int(float(value))
    # Get the harvest date
    harvestday = int(float(datahelp.get_ssv(harvest, False, latitude, longitude, nrows, ncols, x0_corner, y1_corner, sizex, sizey)))
    # Make sure that the plant date is a day-of-year before the harvest date (will be negative if a previous year)
    if harvestday < plantday:
        plantday = plantday - 365

    return (plantday, harvestday)

if __name__ == "__main__":
    print get_calendar_plus("Wheat", 31.125,74.625, True)
    print get_calendar_plus("Wheat.Winter", -32.125, -60.375, True)
