# -*- coding: utf-8 -*-
"""Helper functions for using daily weather data
"""
__author__ = "James Rising"
__maintainer__ = "James Rising"
__email__ = "jrising@berkeley.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import os, csv, random
import numpy as np
from openest.dmas import remote
from openest.models.model import Model
from openest.models.spline_model import SplineModel
from openest.models.memoizable import MemoizedUnivariate
from openest.models.curve import AdaptableCurve
from ..iam import effect_bundle, weather
import config

# Path to this directory, for accessing relative file data
scriptdirpath = os.path.dirname(os.path.realpath(__file__))

# Generate integral over daily temperature

def make_daily_bymonthdaybins(id, func=lambda x: x, pval=None, weather_change=lambda temps: temps - 273.15):
    """Make-generator to apply daily weather data to a curve, and report
    as the sum over days for the average month.

    Args:
      id: The response curve
      func: Post-response transform
      pval: Quantile of the response
      weather_change: Pre-application transform of weather
    """
    # Load the model
    if isinstance(id, AdaptableCurve):
        spline = id
    else:
        if isinstance(id, Model):
            model = id
        else:
            model = remote.view_model('model', id)

        model = MemoizedUnivariate(model)
        model.set_x_cache_decimals(1)
        spline = model.get_eval_pval_spline(pval, (-40, 80), threshold=1e-2, linextrap=config.linear_extrapolation)

    # Create the make-generator
    def generate(fips, yyyyddd, temps, **kw):
        if fips == effect_bundle.FIPS_COMPLETE:
            return # We're done!

        # Handle adapting curves
        if isinstance(spline, AdaptableCurve):
            spline.setup(yyyyddd, temps)

        # Read this year's data
        for (year, temps) in weather.yearly_daily_ncdf(yyyyddd, temps):
            # apply it to the model
            temps = weather_change(temps)
            results = spline(temps)

            result = np.sum(results) / 12 # report as averge month

            if not np.isnan(result):
                yield (year, func(result))

            # Handle adapting curves
            if isinstance(spline, AdaptableCurve):
                spline.update()

    return generate

def make_daily_yearlydaybins(id, func=lambda x: x, pval=None):
    """Make-generator to apply daily weather data to a curve, and report
    as the sum over days for the sum over all days per year.

    Args:
      id: The response curve
      func: Post-response transform
      pval: Quantile of the response
    """
    # Load the model
    if isinstance(id, AdaptableCurve):
        spline = id
    else:
        if isinstance(id, Model):
            model = id
        else:
            model = remote.view_model('model', id)

        model = MemoizedUnivariate(model)
        model.set_x_cache_decimals(1)
        spline = model.get_eval_pval_spline(pval, (-40, 80), threshold=1e-2, linextrap=config.linear_extrapolation)

    # Create the make-generator
    def generate(fips, yyyyddd, temps, **kw):
        if fips == effect_bundle.FIPS_COMPLETE:
            return

        # Handle adapting curves
        if isinstance(spline, AdaptableCurve):
            spline.setup(yyyyddd, temps)

        # Read this year's data
        for (year, temps) in weather.yearly_daily_ncdf(yyyyddd, temps):
            # apply it to the model
            result = np.sum(spline(temps - 273.15))

            if not np.isnan(result):
                yield (year, func(result))

            # Handle adapting curves
            if isinstance(spline, AdaptableCurve):
                spline.update()

    return generate

def make_daily_averagemonth(id, func=lambda x: x, pval=None):
    """Make-generator to apply average month weather data to a curve, and
    report as the average response for any month.

    Args:
      id: The response curve
      func: Post-response transform
      pval: Quantile of the response
    """
    # Days per month and which day-of-year we switch months
    days_bymonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    transitions = np.cumsum(days_bymonth)

    # Load the model
    if isinstance(id, AdaptableCurve):
        spline = id
    else:
        if isinstance(id, Model):
            model = id
        else:
            model = remote.view_model('model', id)

        model = MemoizedUnivariate(model)
        model.set_x_cache_decimals(1)
        spline = model.get_eval_pval_spline(pval, (-40, 80), threshold=1e-2, linextrap=config.linear_extrapolation)

    # Create the make-generator
    def generate(fips, yyyyddd, temps, **kw):
        if fips == effect_bundle.FIPS_COMPLETE:
            return # We're done!

        # Handle adapting curves
        if isinstance(spline, AdaptableCurve):
            spline.setup(yyyyddd, temps)

        # Read this year's data
        for (year, temps) in weather.yearly_daily_ncdf(yyyyddd, temps):
            # Compute the response for each month
            bymonth = []
            for mm in range(12):
                avgmonth = np.mean(temps[transitions[mm]-days_bymonth[mm]:transitions[mm]])
                bymonth.append(spline(avgmonth - 273.15))
                #bymonth.append(model.eval_pval(avgmonth - 273.15, pval, threshold=1e-2))

            # Average all months
            result = np.mean(bymonth)
            if not np.isnan(result):
                yield (year, func(result))

            # Handle adapting curves
            if isinstance(spline, AdaptableCurve):
                spline.update()

    return generate

def make_daily_percentwithin(endpoints):
    """Make-generator to determine the percent of days within a set of endpoints.

    Args:
      endpoints: a list of division points; result will have one fewer percentages than endpoints.
    """
    # Create the make-generator
    def generate(fips, yyyyddd, temps, **kw):
        if fips == effect_bundle.FIPS_COMPLETE:
            return # We're done!

        # Get this year's data
        for (year, temps) in weather.yearly_daily_ncdf(yyyyddd, temps):
            # Calculate the number of days within each pair of endpoints
            results = []
            for ii in range(len(endpoints)-1):
                result = np.sum(temps - 273.15 > endpoints[ii]) - np.sum(temps - 273.15 > endpoints[ii+1])
                results.append(result)

            # Return as portions
            results = list(np.array(results) / float(len(temps)))

            yield tuple([year] + results)

    return generate

# Combine counties to states

def aggregate_tar_with_scale_file(name, scale_files, scale_factors):
    """Create an aggregated result file, averaging results according to the
    given scalings.  Used to combine counties to states.

    Args:
      name: name of the result file
      scale_files: list of weight-by-county files
      scale_factors: additional factors for scaling
    """
    # Create a dictionary of fips -> scale
    scales = {}
    for ii in range(len(scale_files)):
        # Load the weight file
        generator = weather.read_scale_file(scriptdirpath + "../iam/cropdata/" + scale_files[ii] + ".csv", scale_factors[ii])
        for (fips, scale) in generator:
            # Add the weight from this generator
            if fips in scales:
                scales[fips] += scale
            else:
                scales[fips] = scale

    # Generate a aggregated tar
    effect_bundle.aggregate_tar(name, scales)
