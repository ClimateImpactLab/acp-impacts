# -*- coding: utf-8 -*-
"""Interface to crop area data from Sacks et al. 2010, Crop planting dates: an analysis of global patterns.
"""
__author__ = "James Rising"
__credits__ = ["James Rising"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import tarfile, datahelp

class CropCalendarArea:
    """Read from the non-interpolated (unfilled) 5 minute data."""
    # From the top of the file
    ncols = 4320
    nrows = 2160
    x0_corner = -180
    y0_corner = 90
    sizex = sizey = 0.083333333

    def __init__(self, crop, use_fraction=True):
        # Cache the crop data file
        bigtar = tarfile.open(datahelp.datapath("ALL_CROPS_ArcINFO_5min_unfilled.tar"))
        openfile = bigtar.extractfile(crop + ".crop.calendar.tar.gz")

        with tarfile.open(name=None, fileobj=openfile) as tar:
            if use_fraction:
                area = tar.extractfile(crop + ".crop.calendar/harvested.area.fraction.asc")
            else:
                area = tar.extractfile(crop + ".crop.calendar/harvested.area.asc")

            # Drop the first 6 lines (same information as "From the top" above
            for ii in range(6):
                area.readline()

            line = area.readline()
            self.values = line.split(" ") # All remaining data is here
            area.close()

        bigtar.close()

    def getll(self, latitude, longitude):
        """Return the area entry for a given location"""

        # Translate lat, lon into row, col
        row0 = int(round((self.y0_corner - self.sizey/2 - latitude) / self.sizey))
        col0 = int(round((longitude - (self.x0_corner + self.sizex/2)) / self.sizex))

        value = self.values[row0 * self.ncols + col0]
        # Translate a single entry to floating point.
        if value != "9e+20" and value != "":
            if value == "0":
                return 0
            else:
                return float(value)

    def sum_ll9(self, latitude, longitude):
        """Return a total across a 3x3 grid centered at the given location."""
        # Translate lat, lon into row, col
        row0 = int(round((self.y0_corner - .25/2 - latitude) / self.sizey))
        col0 = int(round((longitude - (self.x0_corner + .25/2)) / self.sizex))

        # Sum over 3x3 grid
        areas = 0
        for ii in range(3):
            for jj in range(3):
                value = self.values[(row0 + ii) * self.ncols + col0 + jj]
                # Translate a single entry to floating point.
                if value != "9e+20" and value != "" and value != "0":
                    areas = areas + float(value)

        return areas

    def get_values(self):
        """Return all of the value as a vector of floats."""
        return map(lambda x: float(x) if (x != "9e+20" and x != "" and x != "0" and x != "\n") else 0, self.values)
        #return map(cvt, self.values)

    def get_max(self):
        """Return the maximum value observed."""
        maxval = 0
        for ii in range(len(self.values)):
            # Ignore anything with e... (this is a not-available value)
            if not "e" in self.values[ii]:
                try:
                    # Update the largest observed value
                    if float(self.values[ii]) > maxval:
                        maxval = float(self.values[ii])
                        print maxval
                except:
                    pass

        return maxval

if __name__ == "__main__":
    area = CropCalendarArea("Wheat")
    print area.getll(31.125,74.625)
