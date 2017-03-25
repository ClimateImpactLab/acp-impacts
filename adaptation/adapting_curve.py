# -*- coding: utf-8 -*-
"""Adapting Curves

This module defines two classes dervied from AdaptableCurve.  Both use
the update call to incrementally adjust the shape of a curve to
reflect adaptation occurring over time.

SimpleAdaptingCurve produces a unidirectional adaptation, with a given
time-contant.

AdaptingCurve applies a temperature-depending adaptation, using a
collection of regionally adapted curves.
"""
__author__ = "James Rising"
__credits__ = ["James Rising", "Amir Jina"]
__maintainer__ = "James Rising"
__email__ = "jar2234@columbia.edu"

__status__ = "Production"
__version__ = "$Revision$"
# $Source$

import csv
import numpy as np
from scipy.stats import linregress

from iam import effect_bundle, weather
from openest.models.curve import CurveCurve, AdaptableCurve, StepCurve

class SimpleAdaptingCurve(AdaptableCurve):
    """A curve that updates asymptotically from curve_baseline to curve_future."""

    def __init__(self, xx, curve_baseline, curve_future, gamma_curve):
        super(SimpleAdaptingCurve, self).__init__(xx)

        self.curve_baseline = curve_baseline # Original curve
        self.curve_future = curve_future # Asymptotic curve
        self.gamma_curve = gamma_curve # Rate coefficient

    def setup(self, yyyyddd, temps):
        """Reset the curve to curve_baseline."""
        self.last_curve = self.curve_baseline
        self.curr_curve = self.curve_baseline

    def update(self):
        """Call after first year."""

        # Construct a new curve, in between curve_baseline and curve_future
        self.curr_curve = SimpleAdaptingCurve.construct_stepwise_curve(self.xx, self.curve_baseline, self.curve_future, self.gamma_curve, self.last_curve)
        # Save this for future computation
        self.last_curve = self.curr_curve

    def __call__(self, x):
        return self.curr_curve(x)

    @staticmethod
    def construct_stepwise_curve(xx, curve_baseline, curve_future, gamma_curve, last_curve=None):
        """Iteratively move curve toward curve_future."""
        if last_curve is None:
            curr_curve = curve_baseline
        else:
            curr_curve = AdaptingCurve.apply_stepwise(xx, last_curve, curve_future, gamma_curve)

        return curr_curve

class AdaptingCurve(AdaptableCurve):
    """
    AdaptingCurve uses cross-sectional variation to estimate the
    surface that describes "fully adapted" curves, and
    long-differences to estimate the rate at which curves converge to
    the fully adapted curve.
    """

    num_years = 15 # Years for averaging recent temperature to describe climate

    def __init__(self, xx, curve_baseline, curve_others, Wbar_baseline, Wbar_others, gamma_curve, Wbar_make_generator=weather.yearly_daily_ncdf, weather_change=lambda temps: temps - 273.15, clip_zero=False):
        super(AdaptingCurve, self).__init__(xx)

        self.curve_baseline = curve_baseline # Original curve
        self.curve_others = curve_others # Collection of asymptotic curves
        self.Wbar_baseline = Wbar_baseline # Parameter describing current climate
        self.Wbar_others = Wbar_others # Parameters describing climates of asymptotic curvs
        self.gamma_curve = gamma_curve # Rate coefficient curve
        self.Wbar_make_generator = Wbar_make_generator # Generator to produce weather data
        self.weather_change = weather_change # Optional weather translation
        self.clip_zero = clip_zero # Should the curve be clipped at 0

    def setup(self, yyyyddd, temps):
        """Prepare to start adapting the curve."""
        self.generator_Wbar = AdaptingCurve.make_full_Wbar_generator(self.Wbar_make_generator, self.Wbar_baseline, yyyyddd, temps)
        self.last_curve = self.curve_baseline
        self.curr_curve = self.curve_baseline

    def update(self):
        """Call after first year."""
        year_Wbar_now = self.generator_Wbar.next()

        # Determine the true state of full adaptation
        Wbar_now = np.mean(self.weather_change(year_Wbar_now[1]))

        self.curr_curve = AdaptingCurve.construct_stepwise_curve(self.xx, self.curve_baseline, self.curve_others, self.Wbar_baseline, self.Wbar_others, Wbar_now, self.gamma_curve, self.last_curve, clip_zero=self.clip_zero)
        self.last_curve = self.curr_curve

    def __call__(self, x):
        """Evaluate the curve."""
        return self.curr_curve(x)

    @staticmethod
    def make_full_Wbar_generator(Wbar_make_generator, Wbar_baseline, yyyyddd, temps):
        """Set up the climate generator from weather data."""
        # Using weather_change, so would prefer a kind of inverse_weather_change (not just +273.15)
        return effect_bundle.runaverage(Wbar_make_generator(yyyyddd, temps), (Wbar_baseline + 273.15) * np.ones(AdaptingCurve.num_years), np.ones(AdaptingCurve.num_years))

    @staticmethod
    def construct_stepwise_curve(xx, curve_baseline, curve_others, Wbar_baseline, Wbar_others, Wbar_now, gamma_curve, last_curve=None, clip_zero=False):
        """Iteratively adjust the curve toward its current asymptotic."""
        star_curve = AdaptingCurve.extrapolate_adaptation_curve(xx, curve_baseline, curve_others, Wbar_baseline, Wbar_others, Wbar_now, clip_zero=clip_zero)

        if last_curve is None:
            curr_curve = curve_baseline
        else:
            curr_curve = AdaptingCurve.apply_stepwise(xx, last_curve, star_curve, gamma_curve)

        return curr_curve

    @staticmethod
    def extrapolate_adaptation_curve(xx, curve_baseline, curve_others, Wbar_baseline, Wbar_others, Wbar_now, clip_zero=False):
        """Determine asymptotic curve, based on a linear surface through observed curves."""
        betas = []
        for x in xx:
            betas.append(AdaptingCurve.extrapolate_adaptation_beta(curve_baseline(x), [curve(x) for curve in curve_others], Wbar_baseline, Wbar_others, Wbar_now, clip_zero=clip_zero))

        return CurveCurve.make_linear_spline_curve(xx, betas, (-40, 100))

    @staticmethod
    def extrapolate_adaptation_beta(beta_baseline, beta_others, Wbar_baseline, Wbar_others, Wbar_now, clip_zero=False):
        """Returns the ideal beta (beta*) for this Wbar"""
        if np.all(np.array(beta_others) == 0): # force 0 in this case
            return 0

        x = [Wbar_baseline] + Wbar_others
        y = np.array([beta_baseline] + beta_others)

        slope, intercept, r_value, p_value, std_err = linregress(x, y)

        beta = intercept + slope * Wbar_now
        if clip_zero and beta < 0:
            beta = 0

        return beta

    @staticmethod
    def apply_stepwise(xx, last_curve, star_curve, gamma_curve):
        """Create a new curve, by stepping toward the asymptotic curve."""
        betas = []
        for x in xx:
            gamma = gamma_curve(x)
            betas.append(last_curve(x) * gamma + star_curve(x) * (1 - gamma))

        if isinstance(last_curve, StepCurve):
            return StepCurve([-40, 29, 100], betas) # XXX: Totally arbitrary-- for maize
        return CurveCurve.make_linear_spline_curve(xx, betas, (-40, 100))

    @staticmethod
    def calculate_gammas(betas_before, time_before, betas_after, time_after, betas_infinity):
        """Calculate the rate coefficients:
        beta = beta_infinity + (beta_before - beta_infinity) * exp(-(t - t_before) / tau) =>
        tau = -(t_after - t_before) / log ((beta_after - beta_infinity)/(beta_before - beta_infinity))"""

        print time_after, betas_after, betas_before
        taus = -(time_after - time_before) / np.log(float(betas_after - betas_infinity)/float(betas_before - betas_infinity))
        return np.exp(-1.0 / taus) # return gamma

    @staticmethod
    def get_betas(curve, cut_point):
        """Get coefficients describing a curve."""
        xx = curve.get_xx()
        betas_left = curve(xx[xx < cut_point])
        betas_right = curve(xx[xx > cut_point])

        return betas_left, betas_right

if __name__ == "__main__":
    # Example of the adapting curve system

    from openest.models.curve import StepCurve

    xx = [-20, 0, 60]

    # Calculate rate coefficient that got us from 90 to 60 in 30 years.
    gamma = AdaptingCurve.calculate_gammas(90, 1950, 60, 1980, 0)
    print gamma

    # Use the same gamma for high and low coefficients
    gamma_curve = StepCurve([-40, 0, 80], [gamma, gamma])

    # The baseline curve goes up to 60; the adapted to 30.
    curve_baseline = CurveCurve.make_linear_spline_curve(xx, [0, 0, 60], (-40, 80))
    curve_adapted = CurveCurve.make_linear_spline_curve(xx, [0, 0, 30], (-40, 80))

    # Two different adapting curves, to represent different regions
    curve1 = AdaptingCurve(xx, curve_baseline, [curve_adapted], 0, [30], gamma_curve)
    curve2 = AdaptingCurve(xx, curve_baseline, [curve_adapted], 0, [30], gamma_curve)

    # Two different make_generators for the two different regions
    def make_generator1(fips, yyyyddd, inputs):
        curve1.setup(yyyyddd, inputs)
        for (year, avg) in weather.yearly_daily_ncdf(yyyyddd, inputs):
            yield (year, curve1(np.mean(avg)))
            curve1.update()

    def make_generator2(fips, yyyyddd, inputs):
        curve2.setup(yyyyddd, inputs)
        for (year, avg) in weather.yearly_daily_ncdf(yyyyddd, inputs):
            yield (year, curve2(np.mean(avg)))
            curve2.update()

    # Two different sets of weather data
    yyyyddd = []
    temps1 = []
    temps2 = []
    for yyyy in range(2000, 2100):
        yyyyddd += [yyyy * 1000 + ddd for ddd in range(365)]
        if yyyy < 2005:
            temps1 += [0 for ddd in range(365)]
        elif yyyy < 2040:
            temps1 += [15 for ddd in range(365)]
        elif yyyy < 2060:
            temps1 += [30 for ddd in range(365)]
        else:
            temps1 += [45 for ddd in range(365)]

        if yyyy < 2005:
            temps2 += [0 for ddd in range(365)]
        else:
            temps2 += [15 for ddd in range(365)]

    # Two different generators for the weather data
    generator1_Ts = weather.yearly_daily_ncdf(yyyyddd, temps1)
    generator2_Ts = weather.yearly_daily_ncdf(yyyyddd, temps2)

    # Adpat everything and write out the results
    with open("diagnostic/diagnostic-adaptation.csv", 'w') as fp:
        writer = csv.writer(fp)
        writer.writerow(['year', 'Tbar1', 'value1', 'Tbar2', 'value2'])

        generator2 = make_generator2(None, yyyyddd, temps2)
        for (year, value1) in make_generator1(None, yyyyddd, temps1):
            (year, T1s) = generator1_Ts.next()
            (year, T2s) = generator2_Ts.next()
            (year, value2) = generator2.next()
            writer.writerow([year, np.mean(T1s), value1, np.mean(T2s), value2])
