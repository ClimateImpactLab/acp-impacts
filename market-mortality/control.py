import by_state.calc, by_county.calc

class StateRun(object):

	@staticmethod
	def run_scenario(readdir):
		state_run = by_state.calc.MortalityCostCalculator(readdir=readdir)
		state_run.run_simulation()

class CountyRun(object):

	@staticmethod
	def run_scenario(readdir, agglev='state', deflator=None, test_data=False):
		county_run = by_county.calc.MortalityCostCalculator(readdir=readdir,agglev=agglev,deflator=deflator,test_data=test_data)
		county_run.run_simulation()