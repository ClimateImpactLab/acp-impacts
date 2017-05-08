from os import chdir,getcwd, mkdir, remove, listdir
from sys import stdout
import time, threading, re, parse
from subprocess import call
from shutil import rmtree
from random import randint

from jobDispatcher import JobDispatch
#from studyrun import Study
#from serverSettings import Options

# hello!

NUM_THREADS 	= 1
MASTER_URL 		= 'http://192.237.176.103'
TEMP_FILE_DIR 	= 'C:\\Users\\Administrator\\Documents\\modeldev\\serverRoot\\impacts'
START_DIR 		= getcwd()
WORKING_DIR 	= 'C:\\Users\\Administrator\\Documents\\modeldev\\serverRoot'
LOCAL_RESULTS = 'C:\\Users\\Administrator\\Documents\\modeldev\\serverRoot\\results'
RESULTS_DIR		= '/mnt/extra/cgeOutput/'
LISTINGS_DIR	= 'listings\\'



class ThreadDispatcher():
	def main(self):
		sleeper = randint(1,15)
		print('sleeping {s} seconds...'.format(s=sleeper))
		time.sleep(sleeper)
		self.threads = []

		removeprefix = ['Hist','CCMS','GDFL','MRI','MPI','HADGEM','MIROC','RCP45Cl','SENS','rcp']

		for f in listdir(LOCAL_RESULTS):
			for r in removeprefix:
				if re.search(r,f):
					try:
						remove(LOCAL_RESULTS+'\\'+f)
					except:
						continue
		for f in listdir(LISTINGS_DIR):
			for r in removeprefix:
				if re.search(r,f):
					try:
						remove(LISTINGS_DIR+'\\'+f)
					except:
						continue

		for i in range(0,NUM_THREADS):
			stdout.write('spawning thread {thread_id}\n'.format(thread_id = i))
			self.threads.append(GamsWorker(serverURL = MASTER_URL,threadID=i))
			self.threads[-1].start()

		for t in self.threads:
			t.join()

#class GamsWorker(threading.Thread):
class GamsWorker(object):
	def __init__(self, serverURL, threadID):
		#threading.Thread.__init__(self)
		self.dispatcher = JobDispatch(MASTER_URL)
		self.threadID = threadID
		self.removelist = []
	def run(self):
		for job in self.dispatcher.jobGenerator():
			#print job

			for old_impact in listdir(TEMP_FILE_DIR):
				if re.match(str(self.threadID)+'_',old_impact):
					remove(TEMP_FILE_DIR+'\\'+old_impact)
			for jobid, tmpFileName, tmpFilePath, hscen_jobs, in self.dispatcher.saveAndGenerate(job, TEMP_FILE_DIR, self.threadID):	# impacts.tar.gz, ./data/, id
				stdout.write("\nJOB {jobid}: {mo}/{dd}/{yyyy} {hh}:{mm}:{ss}\n  saved {tid}_{name} at {path}\n".format(
					jobid = jobid, 
					mo = time.localtime()[1], dd = time.localtime()[2], yyyy = time.localtime()[0],
					hh = time.localtime()[3], mm = time.localtime()[4], ss = time.localtime()[5],
					name = tmpFileName, path = tmpFilePath, tid = self.threadID))


			for f in listdir('.'):
				if re.match(r'slr_rcp[0-9]{2}_[0-9]{1,4}.gdx',f):
					remove(f)

			#for hscen in hscen_jobs:

			rmtree('225_{tID}'.format(tID=self.threadID),True)				#	second argument suppresses errors - 
			rmtree('tmpscdr_{tID}'.format(tID=self.threadID),True)		#	no exception raised if file does not already exist

			mkdir('225_{tID}'.format(tID=self.threadID))
			mkdir('tmpscdr_{tID}'.format(tID=self.threadID))

			print('Running job {jid}...'.format(jid=jobid))
			errlev = call('gams modelControl o=listings\\modelrun.lst --runID={rID} --HURR_ACTIV_SCEN=HIST --threadID={tID} Procdir=225_{tID} Scrdir=tmpscdr_{tID} lo=2'.format(rID=jobid, tID=self.threadID))
			try:
				self.dispatcher.pushlisting(self.threadID,jobid,LISTINGS_DIR,RESULTS_DIR,self.removelist)
			except:
				pass

			if errlev > 0:
				self.dispatcher.posterror(jobid)
				raise OSError('ERRORS REPORTED BY THE GAMS SYSTEM. EXITING EXECUTION')

			#call('gdxmerge o={rID}.gdx *_{rID}.gdx'.format(rID=jobid),shell=True)
			#call('gdxdump {results}\\{rID}.gdx > {results}\\{rID}.txt'.format(results=LOCAL_RESULTS,rID=jobid),shell=True)

			try:
				self.dispatcher.pushresults(jobid,LOCAL_RESULTS,RESULTS_DIR)
				self.dispatcher.postcomplete(jobid)
			except Exception, e:
				print('\n\n ---- JOB {job} FAILED TO POST ----\n\n{e}\n\n'.format(job=jobid,e=e))
				with open('errlog.txt','a+') as logfile:
					logfile.write('JOB {job} failed to post using pscp\n{e}\n'.format(job=jobid,e=e))
				self.dispatcher.posterror(jobid)
				time.sleep(10)

	# Thread emulators
	def join(self):
		pass
	def start(self):
		self.run()


if __name__ == "__main__":
	
	#call('gams modelControl o=modelrun.lst')

	t = ThreadDispatcher()

	chdir(WORKING_DIR)

	t.main()

	chdir(START_DIR)