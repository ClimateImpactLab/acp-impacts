import json, urllib2, parse, random, time
from pullFiles import FilePuller
from subprocess import call
from shutil import move
from os import listdir, remove

# prep for gams execution

serverpass = {
		'23.253.221.79':	'Xiybk97MUkuS',	# 	superFile04
		'192.237.176.103':	'wm7TbvPGAG3X',	#	ubuntuMaster
		'23.253.34.244':	'3EtX5Wd3TAEb',	#	filehost2
		'23.253.42.245':	'N36uw9STCDU8',	#	filehost3
		'23.253.160.246':	'UTCe5CCibE3r'}	#	filehost04


MASTER_IP = '192.237.176.103'

POST_IPs = ['23.253.221.79','23.253.34.244']	#	filehost2 and superFile04 used to reduce load on filehost04


class JobDispatch():
	def __init__(self, masterURL):
		self.master_url = masterURL
	def jobGenerator(self):
		geturl = self.master_url + '/' + 'getjob'
		while True:
			try:
				self.data = json.load(urllib2.urlopen(geturl))
				yield self.data
			except Exception, e:
				break
	def scpDirectly(self,remotepath,localpath,serverIP):
		errlev = None
		tries = 0
		while not errlev == 0:
			errlev = call('echo yes | pscp -l root -pw {pw} {remotepath} {localpath}'.format(pw=serverpass[serverIP],remotepath=remotepath,localpath=localpath), shell=True)
			if errlev != 0:
				sleeper = random.randint(1,10)
				print('sleeping {s} seconds...'.format(s=sleeper))
				time.sleep(sleeper)
				tries += 1
				if tries > 10:
					raise OSError('Number of allowed post attempt exceeded')

	def saveAndGenerate(self, job, tmpdir, threadID):
		serverIP = job['serv']
		job_id = job['id']
		rcp = job['rcp']
		for filename, filepath in zip(job['filenames'],job['path']):
			geturl = 'http://{root}/file?path={path}&id={job_id}'.format(root = serverIP, path = urllib2.quote(filepath), job_id = job_id)

			try:
				p = parse.getNewFilename(filename)
				if p[0] is None:
					raise ValueError
				renamed, prefix = ('{ID}_{name}'.format(ID=threadID,name=f) for f in p)
				ftype = parse.getNewFilename(filename)[1]

				remotepath = 'root@{ip}:{path}'.format(ip=serverIP, path=filepath)
				outfile = "{dir}\\".format(dir = tmpdir)
				#print 'starting download of {filename} from {url}'.format(filename = filename, url = geturl)

				self.scpDirectly(remotepath,outfile,serverIP)
				move(*tuple('{dir}\\{old},{dir}\\{new}'.format(dir=tmpdir, old=filename, new=renamed).split(',')))

				def null(*args,**kwargs):
					pass

				fileAction = parse.getFileAction(ftype,filename,renamed,prefix,move=null)
				for i in range(len(fileAction)):
					parse.makecall(fileAction[i][0],fileAction[i][1])
				#for f in [files for files in listdir(tmpdir) if files.endswith('.gdx') or files.endswith('.lst')]:
				#	remove(tmpdir+'\\'+f)

				hscenlist = parse.getHurrScen(rcp)

				#FilePuller.save(geturl,outfile)
				#print 'downloaded {filename} as {outfile}'.format(filename = filename, outfile = outfile)
				yield (job_id, filename, outfile, hscenlist)
			except ValueError:
				pass	#	only impact files specified in parse will be downloaded

	def postSCP(self,localpath,remotepath,serverIP):
		return call('echo yes | pscp -l root -pw {pw} {localpath} {remotepath}'.format(localpath = localpath, pw = serverpass[serverIP], remotepath=remotepath), shell=True)

	def postcomplete(self,jobid):
		posturl = '{masterURL}/complete?id={id}'.format(masterURL=self.master_url, id=jobid)
		postdata = json.dumps({'id':jobid})
		req = urllib2.Request(posturl,postdata)
		r = urllib2.urlopen(req,postdata)

	def pushlisting(self,threadID,jobID,listingdir,resultsdir,removelist = []):
		serverIP = self.getPostIP()
		localpath = '{listingdir}\\modelrun_{threadID}.lst'.format(listingdir=listingdir,threadID=threadID)
		localrename = '{listingdir}\\{jobID}.lst'.format(listingdir=listingdir,jobID=jobID)
		remotepath = 'root@{IP}:{resultsdir}'.format(IP=serverIP,resultsdir=resultsdir)
		try:
			move(localpath,localrename)
			self.postSCP(localrename,remotepath,serverIP)
			removelist.append(localrename)
		except:
			pass

		while len(removelist) > 5:
			try:
				remove(removelist.pop(0))
			except:
				break

	def posterror(self,jobid):
		posturl = '{masterURL}/err?id={id}'.format(masterURL=self.master_url, id=jobid)
		postdata = json.dumps({'id':jobid})
		req = urllib2.Request(posturl,postdata)
		r = urllib2.urlopen(req,postdata)

	def getPostIP(self):
		return random.choice(POST_IPs)

	def pushresults(self,jobid,localresults,resultsdir,removelist = []):
		serverIP = self.getPostIP()
		localpath = '{localresults}\\{jobid}.gdx'.format(localresults=localresults,jobid=jobid)
		remotepath = 'root@{IP}:{resultsdir}'.format(IP=serverIP,resultsdir=resultsdir)
		errlev = None
		tries = 0
		while not errlev == 0:
			errlev = self.postSCP(localpath,remotepath,serverIP)
			if errlev != 0:
				sleeper = random.randint(5,15)
				print('error level:\t{e}\tserver:\t{serv}\nsleeping {s} seconds...'.format(e=errlev,serv=serverIP,s=sleeper))
				time.sleep(sleeper)
				serverIP = self.getPostIP()
				tries += 1
				if tries > 15:
					raise OSError('Number of allowed post attempt exceeded')
		removelist.append(localpath)

		#except:
		#	raise OSError('{localpath} failed to post'.localpath)

		while len(removelist) > 5:
			try:
				remove(removelist.pop(0))
			except:
				break

