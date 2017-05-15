# -*- coding: utf-8 -*-
"""Helper functions for agriculture impacts
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
from ..iam import effect_bundle, weather
from ..adaptation.adapting_curve import SimpleAdaptingCurve
from openest.models.model import Model
from openest.models.integral_model import IntegralModel
from openest.models.spline_model import SplineModel
from openest.models.memoizable import MemoizedUnivariate

# Path to this directory, for accessing relative file data
scriptdirpath = os.path.dirname(os.path.realpath(__file__))

# Seasonal Temperature Impacts

def make_generator_single_crop(crop, id, pval):
    """Make a generator function, which yields results (tuples of (year, result)) for a single crop.

    Args:
      crop: Crop calendar crop
      id: Response model
      pval: Quantile of the response model
    """
    # Load calendar
    calendar = weather.get_crop_calendar(scriptdirpath + "../iam/cropdata/" + crop + ".csv")

    # Load the model
    if isinstance(id, Model):
        model = id
    else:
        model = remote.view_model('model', id)
        model = MemoizedUnivariate(model)
        model.set_x_cache_decimals(1)

    # Create a generator function
    def generate(fips, yyyyddd, dailys, lat=None, lon=None):
        # Skip if we don't know the calendar
        if fips not in calendar:
            return

        # Handle adapting curves
        if isinstance(model, SimpleAdaptingCurve):
            model.setup(yyyyddd, dailys['tas'])

        # Collect the weather
        seasons = weather.growing_seasons_mean_ncdf(yyyyddd, dailys['tas'], calendar[fips][0], calendar[fips][1])
        for (year, temp) in seasons:
            # Evaluate for the weather
            result = model.eval_pval(temp - 273.15, pval, 1e-2)
            if not np.isnan(result):
                yield (year, result)

            # Update adapting curves as needed
            if isinstance(model, SimpleAdaptingCurve):
                model.update()

    return generate

def make_generator_combo_crops(generators, scale_files, scale_factors, dont_divide=False):
    """Make a generator function, which yields results (tuples of (year, result)) for a combination of crops.

    Args:
      generators: list of single-crop generators
      scale_files: weights for each crop (list with same length as generators)
      scale_factors: Additional scaling (list with same length as generators)
      dont_divide: Return the sum of result products, not the weighted average
    """

    # Load the relative weighting of each crop
    scales = []
    for ii in range(len(generators)):
        generator = weather.read_scale_file(scriptdirpath + "../iam/cropdata/" + scale_files[ii] + ".csv", scale_factors[ii])
        scales.append({fips: scale for (fips, scale) in generator})

    # Create the generator function
    def generate(fips, yyyyddd, dailys, **kw):
        # If we are done, tell all sub-generators
        if fips == effect_bundle.FIPS_COMPLETE:
            print "completing combo"
            for generator in generators:
                try:
                    generator(fips, yyyyddd, dailys).next()
                except:
                    pass
            return

        # Pass location to sub-generators
        lat = kw['lat']
        lon = kw['lon']
        singles = [generator(fips, yyyyddd, dailys, lat, lon) for generator in generators]

        currvals = [(-1, None) for ii in range(len(generators))]
        minyear = -1
        while True:
            # Go next for all with the lowest year
            for ii in range(len(generators)):
                if currvals[ii][0] == minyear:
                    try:
                        currvals[ii] = singles[ii].next()
                    except StopIteration:
                        currvals[ii] = (float('inf'), None)

            # Find the new lowest year
            minyear = float('inf')
            for ii in range(len(generators)):
                minyear = min(minyear, currvals[ii][0])

            if minyear == float('inf'):
                raise StopIteration()

            # Generate a result with all from this lowest year
            numer = 0
            denom = 0
            for ii in range(len(generators)):
                if currvals[ii][0] == minyear:
                    if fips in scales[ii]:
                        numer += currvals[ii][1] * scales[ii][fips]
                        denom += scales[ii][fips]

            if denom > 0:
                if dont_divide:
                    yield (minyear, numer)
                else:
                    yield (minyear, numer / denom)

    return generate

# Generate integral over daily temperature

def make_daily_degreedaybinslog(crop, id_temp, id_precip, scaling, pvals):
    """Create a generator for a crop with a degree-day model and a precipitation response.

    Args:
      crop: Crop calendar crop
      id_temp: Response to temperature model
      id_precip: Response to precipitation model
      scaling: value to multiply each result by
      pvals: Quantile of the two response models
    """

    # Load the crop calendar
    calendar = weather.get_crop_calendar(scriptdirpath + "../iam/cropdata/" + crop + ".csv")

    # Load the response models
    if isinstance(id_temp, Model):
        model_temp = id_temp
    else:
        model_temp = remote.view_model('model', id_temp)
        model_temp = MemoizedUnivariate(model_temp)
        model_temp.set_x_cache_decimals(1)

    model_precip = remote.view_model('model', id_precip)
    model_precip = MemoizedUnivariate(model_precip)
    model_precip.set_x_cache_decimals(1)

    # Create the generator
    def generate(fips, yyyyddd, dailys, *args, **kw):
        # Skip if we don't know the calendar
        if fips not in calendar:
            return

        # Handle adapting curves
        if isinstance(model_temp, SimpleAdaptingCurve):
            model_temp.setup(yyyyddd, dailys['tas'])

        # Collect the weather
        seasons = weather.growing_seasons_daily_ncdf(yyyyddd, dailys, calendar[fips][0], calendar[fips][1])
        # Calcualte the result
        for (year, result) in degreedaybinslog_result(model_temp, model_precip, seasons, pvals, scaling):
            yield (year, result)

    return generate

def make_daily_degreedaybinslog_conditional(crop, ids_temp, ids_precip, conditional, scaling, pvals):
    """Create a generator for a crop with a degree-day model and a precipitation response.
    Multiple temperature and precipitation models are allowed, and selected by the conditional function.

    Args:
      crop: Crop calendar crop
      ids_temp: Dictionary of response to temperature models
      ids_precip: Dictionary of response to precipitation models
      conditional: function which takes fips and location and returns a key into the previous two dicts
      scaling: value to multiply each result by
      pvals: Quantile of the two response models
    """

    # Load the crop calendar
    calendar = weather.get_crop_calendar(scriptdirpath + "../iam/cropdata/" + crop + ".csv")

    # Load the response models
    models_temp = []
    for ii in range(len(ids_temp)):
        if isinstance(ids_temp[ii], Model):
            models_temp.append(ids_temp[ii])
        else:
            models_temp.append(MemoizedUnivariate(remote.view_model('model', ids_temp[ii])))
            models_temp[ii].set_x_cache_decimals(1)

    models_precip = map(lambda id: MemoizedUnivariate(remote.view_model('model', id)), ids_precip)
    for model in models_precip:
        model.set_x_cache_decimals(1)

    # Create the generator function
    def generate(fips, yyyyddd, dailys, lat=None, lon=None):
        # Skip if don't know calendar
        if fips not in calendar:
            return

        # Decide which models to use
        condition = conditional(fips, lat, lon)
        model_temp = models_temp[condition]
        model_precip = models_precip[condition]

        # Handle adapting curves
        if isinstance(model_temp, SimpleAdaptingCurve):
            model_temp.setup(yyyyddd, dailys['tas'])

        # Calculate the result
        seasons = weather.growing_seasons_daily_ncdf(yyyyddd, dailys, calendar[fips][0], calendar[fips][1])
        for (year, result) in degreedaybinslog_result(model_temp, model_precip, seasons, [pvals[condition], pvals[condition + 2]], scaling):
            yield (year, result)

    return generate

def degreedaybinslog_result(model_temp, model_precip, seasons, pvals, scaling=1):
    """Result calculations for a degree-day model.

     Args:
      model_temp: Response to temperature model
      model_precip: Response to precipitation model
      seasons: weather within the growing season for each year as a tuple of (year, weather)
      pvals: Quantile of the two response models
      scaling: value to multiply each result by
    """

    # This should be a degree-day model
    assert(isinstance(model_temp, SimpleAdaptingCurve) or len(model_temp.xx) == 3)

    # Collect the coefficients of the model
    xxs = np.array(model_temp.xx) if not isinstance(model_temp, SimpleAdaptingCurve) else np.array([10, 29, 50]) # XXX: for maize
    midpoints = (xxs[0:len(xxs)-1] + xxs[1:len(xxs)]) / 2
    multiple = np.array(model_temp.eval_pvals(midpoints, pvals[0], 1e-2))

    # Get each year's weather
    for (year, weather) in seasons:
        # Determine how many GDDs and KDDs we have
        tasmin = weather['tasmin'] - 273.15
        tasmax = weather['tasmax'] - 273.15
        dd_lowup = above_threshold(tasmin, tasmax, xxs[0])
        dd_above = above_threshold(tasmin, tasmax, xxs[1])
        dd_lower = dd_lowup - dd_above

        # Calculate the temperature response
        result = (multiple[0] * dd_lower + multiple[1] * dd_above) * scaling

        # Calculate the precipitation response
        prpos = weather['pr']
        prpos = prpos * (prpos > 0)
        precip = sum(prpos) / 1000.0
        result += model_precip.eval_pval(precip, pvals[1], 1e-2)

        if not np.isnan(result):
            yield (year, np.exp(result))

        # Handle adapting curve
        if isinstance(model_temp, SimpleAdaptingCurve):
            model_temp.update()
            multiple = np.array(model_temp.eval_pvals(midpoints, pvals[0], 1e-2))

def above_threshold(mins, maxs, threshold):
    """Calculate the number of degree-days above a given threshold."""

    # Determine crossing points
    aboves = mins > threshold
    belows = maxs < threshold
    plus_over_2 = (mins + maxs)/2
    minus_over_2 = (maxs - mins)/2
    two_pi = 2*np.pi
    d0s = np.arcsin((threshold - plus_over_2) / minus_over_2) / two_pi
    d1s = .5 - d0s

    d0s[aboves] = 0
    d1s[aboves] = 1
    d0s[belows] = 0
    d1s[belows] = 0

    # Integral
    F1s = -minus_over_2 * np.cos(2*np.pi*d1s) / two_pi + plus_over_2 * d1s
    F0s = -minus_over_2 * np.cos(2*np.pi*d0s) / two_pi + plus_over_2 * d0s
    return np.sum(F1s - F0s - threshold * (d1s - d0s))

def make_modelscale_byyear(make_generator, id, pval, func=lambda x, y, year: x*y):
    """Create a generator which scales another generator by a value which
    can change by year and provided by a model.

    Args:
      make_generator: Make-generator function for contained calculation
      id: model of scaling
      pval: quantile of scaling model
      func: function of the form f(response, scaling, year) which scales the response

    """
    # Load the model and scaling
    if isinstance(id, Model):
        model = id
    else:
        model = remote.view_model('model', id)
    factor = model.eval_pval(None, pval, 1e-2)

    # Create the wrapping generator
    def generate(fips, yyyyddd, temps, lat=None, lon=None):
        generator = make_generator(fips, yyyyddd, temps, lat, lon)
        for (year, result) in generator:
            # Scale each result
            yield (year, func(result, factor, year))

    return generate

def aggregate_tar_with_scale_file(name, scale_files, scale_factors, targetdir=None, get_region=None, collabel="fraction", return_it=False):
    """Create a aggregated result file, averaging results according to the
    given scalings.  Used to combine counties to states

    Args:
      name: name of the result file
      scale_files: list of weight-by-county files
      scale_factors: additional factors for scaling
      targetdir: location of the result
      get_region: function which determines how regions are grouped
      collabel: name of the result
      return_it: Rather than produce a tar, return the scale dictionaries
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

    # Return or generate a new result
    if return_it:
        return scales

    effect_bundle.aggregate_tar(name, scales, targetdir, collabel=collabel, get_region=get_region, report_all=True)
