'''
Control module for computing damages from changes in local sea level (LSL)
'''

import pandas as pd
import numpy as np
import metacsv
import os
import re
import click
from pandas import IndexSlice as idx

from lib import (
    gauge,
    rms)


class CoastRun(object):
    '''
    Base class for managing a LSL-based coastal damage scenario

    Use through subclasses Median and MonteCarlo
    '''

    def __init__(self, lsl_unit='mm', run_name=None, prev=None):
        '''
        Initialize a CoastRun object

        Use the prev argument to provide calibration data from a previous 
        instance of this class if reloading data is not necessary, e.g. 
        if module has been reloaded but calibration data from other 
        modules is unaffected.

        Example usage:

            import simulation
            m = simulation.Median()
            m.run()

            # make changes to module code

            reload(simulation)
            m = simulation.Median(prev=m)
            m.run() # faster speedup

        '''
        
        self.lsl_unit = lsl_unit
        self.run_name = run_name

        self.gauge_db = None
        self.storm_db = None
        self.gauge_data = None
        self.exposure_below = None
        self.state_risk = None

        self.gamswriter = None

        if prev is not None and hasattr(prev, 'lsl_unit'):        self.lsl_unit = prev.lsl_unit
        if prev is not None and hasattr(prev, 'gauge_db'):        self.gauge_db = prev.gauge_db
        if prev is not None and hasattr(prev, 'storm_db'):        self.storm_db = prev.storm_db
        if prev is not None and hasattr(prev, 'gauge_data'):      self.gauge_data = prev.gauge_data
        if prev is not None and hasattr(prev, 'exposure_below'):  self.exposure_below = prev.exposure_below
        if prev is not None and hasattr(prev, 'state_risk'):      self.state_risk = prev.state_risk

    def _load_storm_data(self):
        '''
        Load data from RMS into dev.lib.rms.StormDatabase object
        '''

        self.storm_db = rms.StormDatabase()
        self.storm_db.add_historical()
        self.storm_db.add_noreaster()
        self.storm_db.add_climatological(name = 'rcp45', clim_dir = '45_Climatology')
        self.storm_db.add_climatological(name = 'rcp85', clim_dir = '85_update/CMIP5.RCP8.5.MEAN.B.v2.Climatology-2014-05-22')

    def _state_damage(self, state_draw, index_names):
        '''
        Compute storm damages for a state's single 2010-2100 scenario

        Reads in RMS damages. Assumes that the data does not include 
        a linear 2010-2100 phase-in of changes in storm activity. As 
        of this writing, this effect is removed from the RMS data by 
        the RMS.StormDatabase class, then interpolated and re-applied 
        for each LSL scenario by the _storm_damages method of this 
        class.
        '''

        if 'RCP' in index_names:
            rcp = state_draw.name[index_names.index('RCP')]
        else:
            rcp = None

        assert 'STATE' in index_names, 'STATE not found in draw index passed to CoastRun._storm_damages'
        
        if isinstance(state_draw.name, str):
            assert len(index_names) == 1, "I just don't even know"
            state_name = state_draw.name
            indices = (state_draw.name,)
        else:
            st_i = index_names.index('STATE')
            state_name = state_draw.name[st_i]
            indices = state_draw.name

        damages = {}

        if state_name in self.storm_db.historical.index.get_level_values('STATE'):
            damages['historical'] = self.storm_db.historical.xs(state_name, level='STATE').apply(lambda y: pd.Series(y(state_draw), index=state_draw.index))

        if state_name in self.storm_db.noreaster.index.get_level_values('STATE'):
            damages['noreaster'] = self.storm_db.noreaster.xs(state_name, level='STATE').apply(lambda y: pd.Series(y(state_draw), index=state_draw.index))

        if (rcp in ('rcp45', 'rcp85')) and (state_name in self.storm_db.clim_adjusted[rcp].index.get_level_values('STATE')):
            damages['climatological'] = self.storm_db.clim_adjusted[rcp].xs(state_name, level='STATE').apply(lambda y: pd.Series(y(state_draw), index=state_draw.index))

        if len(damages) == 0:
            return None

        damages = pd.concat(damages, names = ['STORM'], axis=0)

        damages.set_index(pd.MultiIndex.from_tuples([indices for _ in range(len(damages))], names=index_names), append=True, inplace=True)
        return damages

    def _storm_damages(self, draw):
        '''
        Calculates storm damages for a given LSL scenario

        Groups storm damages by state and uses _state_damage
        to read in RMS damage info given the LSL scenario 
        "draw." Changes in damages from changes in projected
        hurricane activity (relative to historical) are 
        linearly phased in over the period 2010-2100.
        '''

        draw = draw.unstack('YEAR')

        draw = pd.concat([self._state_damage(draw.iloc[i], draw.index.names) for i in range(len(draw))])
        draw = draw.stack('YEAR')

        # Adjust climatological damages to linearly phase in from 2010 to 2100
        draw = draw.unstack('STORM')

        if 'climatological' in draw.columns:
            draw['climatological'] = (draw['climatological'] - draw['historical'])*((draw.index.get_level_values('YEAR').astype(np.float64)-2010)/(2100-2010)) + draw['historical']

            scenario = pd.concat({'hist': draw[['noreaster','historical']].stack('STORM'), 'proj': draw[['noreaster','climatological']].stack('STORM')}, names=['SCENARIO'], axis=0)

        else:
            scenario = pd.concat({'hist': draw.stack('STORM')}, names=['SCENARIO'], axis=0)

        # Sum across coastal/non-coastal values
        flags = scenario.index.get_level_values('COASTALFLAG').unique()
        invalid = flags[np.in1d(flags, [0,1], invert=True)]
        assert len(invalid) == 0, "Illegal values found in COASTALFLAG: {}".format(invalid)
        scenario = scenario.sum(level=[c for c in scenario.index.names if c != 'COASTALFLAG'])
        return scenario

    def _prep_exposure(self):
        '''
        '''
        
        exposure_coasts = []

        for coast in ['east','west']:
            exp = rms.Exposure(coast=coast)
            exp.read()
            exp.convert('mm')
            exp.interpolate()

            exposure_coasts.append(exp)

        self.exposure_below = {sl: pd.concat([exp.exposure[sl] for exp in exposure_coasts], axis=0).sort_index() for sl in rms.Exposure.SL_MEAS}

    def _exposure_run(self, lsl):
        '''
        '''
        
        exposure_below_run = {}
        
        assert 'STATE' in lsl.index.names
        assert 'YEAR' in lsl.index.names

        # get_state_name is a closure for finding the state name
        # from the Series name once the YEAR index has been grouped
        if len(lsl.index.names) <= 2:
            get_state_name = lambda lev: lev.name
        else:
            st_i = lsl.index.names.index('STATE')
            y_i = lsl.index.names.index('YEAR')
            st_i -= 1 if y_i < st_i else 0
            get_state_name = lambda lev: lev.name[st_i]

        for sl in rms.Exposure.SL_MEAS:
            exposure_by_state = self.exposure_below[sl].xs('ALL', level='LOB')
            exposure_below_run[sl] = lsl.groupby(level=[c for c in lsl.index.names if c != 'YEAR']).apply(lambda lev: pd.Series(exposure_by_state.loc[get_state_name(lev)](lev.values), index=lev.index))

        return exposure_below_run

    def _prep_value_at_risk(self, filepath='data/RMSData/valueAtRisk.csv'):
        '''
        '''
        
        risk = pd.read_csv(filepath, index_col=[0,1], header=[0,1])
        self.risk = risk.stack()
        self.state_risk = self.risk[['BUILDING','CONTENTS']].sum(axis=1).sum(level='STATE')

    def _export_to_gams(self, filepath, data, rcp, scen, sl):
        from lib import writegams

        if self.gamswriter is None:
            self.gamswriter = writegams.PyGDX()
            self.gams_damtypes  = self.gamswriter.add_set('coastDamTypes', ['inundation','direct','bi'], 'Types of damage suffered during coastal storms and due to LSL rise', exists='error')
            self.gams_states    = self.gamswriter.add_set('coastReg', gauge.GaugeDatabase.STATES, 'Coastal regions affected by LSL and storm damage', exists='error')
            self.gams_years     = self.gamswriter.add_set('tp', range(2011, 2101), 'Time periods in the model', exists='error')

        # Rebase all values to 2011 for CGE model
        data = data[data.index.get_level_values('YEAR') >= 2011]
        data = data.groupby(level=[c for c in data.index.names if c != 'YEAR']).apply(lambda x: x - x[x.index.get_level_values('YEAR') == 2011].iloc[0])
        data.index = data.index.reorder_levels(['DAMAGE','STATE','YEAR'])
        data.index.names = ['coastDamTypes', 'coastReg', 'tp']
        data.sort_index(inplace=True)

        self.gamswriter.reset_param('impact')
        self.gamswriter.dataframe_to_param('impact', data, 'Direct coastal damages (without lost capital accounting) for {} {} {}'.format(rcp,scen,sl), exists='replace', domain=[self.gams_damtypes, self.gams_states, self.gams_years], set_exists='validate')
        self.gamswriter.export(filepath)

    def _prep_gams_export(self, storm_damages, exposure_below, scenarios, draw):
        '''
        '''

        for scen in scenarios:
            for sl in rms.Exposure.SL_MEAS:
                storm = storm_damages.xs(scen, level='SCENARIO')
                storm = storm.sum(
                    level=[c for c in storm.index.names if c != 'STORM'])

                expos = exposure_below[sl]

                si = storm.index.names.index('SECTOR')
                before = [storm.index.levels[i] for i in range(si)]
                middle = [storm.index.levels[si].str.lower()]
                after = [storm.index.levels[i] for i in range(si+1,len(storm.index.names))]
                storm.index.set_levels(before+middle+after, inplace=True)
                storm.index.names = [storm.index.names[i] if i != si else 'DAMAGE' for i in range(len(storm.index.names))]
                storm.index = storm.index.reorder_levels(['RCP', 'DAMAGE', 'STATE', 'YEAR'])
                storm.sort_index(inplace=True)


                expos = pd.DataFrame(expos, columns = ['inundation'])
                expos.columns.names = ['DAMAGE']
                expos = expos.stack('DAMAGE')
                expos.index = expos.index.reorder_levels(['RCP', 'DAMAGE',  'STATE', 'YEAR'])
                expos.sort_index(inplace=True)

                damages = pd.concat([storm, expos], axis=0)

                for rcp in damages.index.get_level_values('RCP').unique():
                    self._export_to_gams('output/gams/coastal_{}_{}_{}_{}.gdx'.format(rcp,scen,sl,draw), damages.xs(rcp, level='RCP'), rcp, scen, sl)

    def _damage_simulation(self, lsl_scenario, gams=False, simulate=True):
        '''
        '''
        
        storm_damages = self._storm_damages(lsl_scenario)
        exposure_below = self._exposure_run(lsl_scenario)

        # Adjust exposure to remove base-year exposure below
        for sl in rms.Exposure.SL_MEAS:
            exposure_below[sl] = exposure_below[sl].groupby(level=[c for c in exposure_below[sl].index.names if c != 'YEAR']).apply(lambda x: x-x[x.index.get_level_values('YEAR') == 2010].iloc[0])

            # Require exposure_below monotonicity with year
            exposure_below[sl] = exposure_below[sl].groupby(level=[c for c in exposure_below[sl].index.names if c != 'YEAR']).apply(lambda x: x.rolling(window=100, min_periods=0).max())

        share_below = {}
        adjusted_damage = {sl:{} for sl in rms.Exposure.SL_MEAS}

        if 'proj' in storm_damages.index.get_level_values('SCENARIO'):
            scenarios = ['hist','proj']
        else:
            scenarios = ['hist']

        if gams:
            self._prep_gams_export(storm_damages, exposure_below, scenarios, lsl_scenario.name)

        for sl in rms.Exposure.SL_MEAS:

            # Get share of exposure set unavailable for damage due to inundation
            share_below[sl] = exposure_below[sl].div(self.state_risk, level='STATE')

            # Require share_below monotonicity with year
            assert share_below[sl].groupby(level=[c for c in share_below[sl].index.names if c != 'YEAR']).apply(lambda x: ((x.diff().fillna(0) >= 0).all())).all()

            # Scale damages 
            adjusted_damage[sl] = storm_damages * (1- share_below[sl].loc[[tuple([k[storm_damages.index.names.index(n)] for n in share_below[sl].index.names]) for k in storm_damages.index.values]]).values

            for scen in scenarios:

                scen_exposure = exposure_below[sl].copy()

                scen_exposure = pd.DataFrame(
                    scen_exposure.values,
                    index=scen_exposure.index,
                    columns=pd.MultiIndex.from_tuples(
                        [(scen,'IN', 'inundation')],
                        names=['SCENARIO', 'SECTOR', 'STORM'])
                    ).stack(['SCENARIO','SECTOR','STORM'])

                missing = np.array(adjusted_damage[sl].index.names)[np.in1d(adjusted_damage[sl].index.names, scen_exposure.index.names, invert=True)]
                assert len(missing) == 0, "['{}'] not found in scen_exposure index".format("', '".join(map(str, missing)))
                scen_exposure.index = scen_exposure.index.reorder_levels(adjusted_damage[sl].index.names)
                adjusted_damage[sl] = adjusted_damage[sl].append(scen_exposure)

        damage_scenario = pd.concat(adjusted_damage, axis=0, names=['SL_MEASURE'])

        return damage_scenario

    def postprocess(self):
        '''
        '''

        diff = self.damages.sort_index().groupby(
            level=[c for c in self.damages.index.names if c != 'YEAR']
            ).apply(lambda x: x - x.iloc[0,:])

        storm = diff.query(
            'STORM in ("historical","climatological","noreaster")'
            ).sum(level=[c for c in diff.index.names if c != 'STORM'])

        expos = diff.query(
            'STORM in ("inundation")'
            ).sum(level=[c for c in diff.index.names if c != 'STORM'])

        def operate_across(df, levels, axis=0, func=(lambda x: x.sum)):
            return func(df)(
                level=[c for c in df.index.names if c not in levels],
                axis=axis)

        storm = operate_across(storm, ['SECTOR', 'STATE'])
        expos = operate_across(expos, ['SECTOR', 'STATE'])

        def get_period(x):
            return pd.MultiIndex.from_tuples(
                [("None",) if y < 2020 or y > 2099 else (
                    '{} to {}'.format(
                        ((y-2020)//20*20+2020),
                        ((y-2020)//20*20+2039)),
                    ) for y in x.index.get_level_values('YEAR')],
                names=['PERIOD'])

        storm.set_index(get_period(storm), inplace=True, append=True)
        expos.set_index(get_period(expos), inplace=True, append=True)

        storm = operate_across(storm, ['YEAR'], func=(lambda x: x.mean))
        expos = operate_across(expos, ['YEAR'], func=(lambda x: x.mean))

        storm = storm.query('PERIOD != "None"')
        expos = expos.query('PERIOD != "None"')

        if storm.shape[1] > 1:
            storm = storm.quantile([0.05,0.167,0.5,0.833,0.95], axis=1).T
            expos = expos.quantile([0.05,0.167,0.5,0.833,0.95], axis=1).T

        self.storm = storm
        self.exposure = expos

    def load_data(self, refresh=False, *args, **kwargs):

        if refresh or (self.gauge_data is None):
            self._load_gauge_data(*args, **kwargs)
        if refresh or (self.storm_db is None):
            self._load_storm_data()
        if refresh or (self.exposure_below is None):
            self._prep_exposure()
        if refresh or (self.state_risk is None):
            self._prep_value_at_risk()

    def run(self, refresh=False, gams=False, simulate=True, *args, **kwargs):
        '''
        '''

        self.load_data(refresh=refresh, *args, **kwargs)

        damages = pd.concat({
            col: self._damage_simulation(
                self.gauge_data[col],
                gams=gams,
                simulate=simulate) for col in self.gauge_data.columns},
            axis=1,
            names=['DRAW'])

        ordering = [
            'RCP','SL_MEASURE','SCENARIO','STORM','SECTOR','STATE','YEAR']

        damages.index = damages.index.reorder_levels(
            [c for c in ordering if c in damages.index.names])

        damages.sort_index(inplace=True)

        self.damages = damages

        self.postprocess()


class Median(CoastRun):
    '''
    Single draw of median of LSL distributions

    Note that this is not necessarily guaranteed to be the median 
    of the damage distribution.

    Example usage:

      m = Median()
      m.run()
      
      # print summary statistics
      print(m.storm)
      print(m.exposure)
    '''

    def _load_gauge_data(self):
        if self.gauge_db is None:
            self.gauge_db = gauge.GaugeDatabase(self.lsl_unit)
        self.gauge_db.load_median_lsls()
        self.gauge_data = self.gauge_db.median_data


class MonteCarlo(CoastRun):
    '''
    Load specified LSL draws for MonteCarlo run

    Provide LSL draw range in [0,9999] for a sampled
    damage scenario consistent with Kopp et al (2014)

    Example usage:

        mc = MonteCarlo()
        mc.run(draws=range(100))
        
        # output results
        mc.damages.to_csv('first_100.csv')
      
      # print summary statistics
      print(m.storm)
      print(m.exposure)
    '''

    def _load_gauge_data(self, draws):
        if self.gauge_db is None:
            self.gauge_db = gauge.GaugeDatabase(self.lsl_unit)
        self.gauge_db.load_montecarlo_lsls(draws=draws)
        self.gauge_data = self.gauge_db.mc_data


class Replication(CoastRun):
    '''
    Replicate lsl data to check against source

    Example usage:

      r = Replication()
      r.run()
      
      # print summary statistics
      print(r.storm)
      print(r.exposure)

    '''

    def _load_gauge_data(self):
        if self.gauge_db is None:
            self.gauge_db = gauge.GaugeDatabase(self.lsl_unit)
        self.gauge_db.load_rms_lsls()

        # replicate LSL scenario for hist, rcp45, rcp85
        gauge_data = self.gauge_db.rms_data.copy()

        self.gauge_data = pd.concat(
            {scen: gauge_data for scen in ['rcp45','rcp85']},
            axis=0,
            names=['RCP'])


def do_montecarlo(start, end, outdir):
    mc = MonteCarlo()
    mc.run(draws=range(start, end))

    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    
    mc.damages.to_csv(os.path.join(
        outdir, 'coastal-damages-raw-{:04}-{:04}.csv'.format(start, end)))
    

@click.command()
@click.argument('start', type=int)
@click.argument('end', type=int)
@click.option(
    '--outdir',
    help='output directory',
    default='outputs/mc_run/{}/'.format(
        pd.datetime.today().strftime('%Y-%m-%d')))
def main(start, end, outdir):
    do_montecarlo(start, end, outdir)


if __name__ == '__main__':
    main()
