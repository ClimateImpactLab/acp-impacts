'''
Impact processing and run management for local (non-server) run

PROJECT:    US Climate Risk Assessment
GROUP:      RhG-ENR
CRETOR:     Michael Delgado
CONTACT:    mdelgado@rhg.com

TASK:       remoteExec      Abbreviated model directory for servers and distribution
FILE:       local.py        Impact processing and run management for local (non-server) run

This file allows the user to conduct a server run on a local system. After downloading
impact files to the specified impact directories configure this file to conduct a local
experiment. The classes BaseRun and MedianRun control either a run without impacts or 
an abbreviated Monte Carlo simulation using the median impact files contained in pmed/, 
slr/, and energy/. These files are not included in the git repository because of their
size and because their syncing with the server version of this file would be 
problematic. main() conducts a BaseRun or MedianRun depending on the choice of -b or 
-m flags, respectively.

* Note that this file will take no action without a run flavor specified

'''

from threading import Thread as Process, Event
from Queue import Queue as JoinableQueue
import Queue as QueueModule


import re, shutil, os, argparse, sys, time, threading, hashlib, base64
import subprocess, traceback
import parse, utils

try:
    from subprocess import DEVNULL # py3k
except ImportError:
    DEVNULL = open(os.devnull, 'wb') # python 2.7


IMPACT_SUFFIX = 'state'

ALL_IMPACTS = ['ENERGY','AG','LABOR','COASTAL','MORTALITY']

COSATAL_RCP_MAP = {'rcp26':'rcp26','rcp45':'rcp45','rcp60':'rcp45','rcp85':'rcp85'}

DEFAULT_ECON_DIR = 'pmed'
DEFAULT_ENERGY_DIR = 'energy'
DEFAULT_COASTAL_DIR = 'slr'
DEFAULT_HASH_DIR = 'cache'
DEFAULT_TMP_DIR = 'impacts'
DEFAULT_RESULTS_DIR = 'results'
DEFAULT_TRDBAL_DATASET = 'NCA'

class Config(object):
    def __init__(self, **kwargs):
        self.econdir = DEFAULT_ECON_DIR
        self.energy  = DEFAULT_ENERGY_DIR
        self.coastal = DEFAULT_COASTAL_DIR
        self.hashdir = DEFAULT_HASH_DIR
        self.tmpdir  = DEFAULT_TMP_DIR
        self.results = DEFAULT_RESULTS_DIR
        self.dataset = DEFAULT_TRDBAL_DATASET

        self.debug   = False

        # Override defaults for provided keyword arguments
        for var, val in kwargs.items():
            self.__dict__[var] = val


class SubCaller(object):
    @staticmethod
    def call(line, silent=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, *args, **kwargs):
        if not silent:  
            print('Calling ' + ': '.join(line[:2]))
        proc = subprocess.Popen(line, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.wait()

import random

class GamsWorker(utils.Consumer):

    def __init__(self, threadID=0, job_queue=None, job_done=None, kill_signal=None):
        utils.Consumer.__init__(self, action=self.printer, job_queue=job_queue, job_done=job_done, kill_signal=kill_signal)
        self.threadID = threadID
        self.working_dir = 'gams/thread-{}/'.format(self.threadID)
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def printer(self, job):
        time.sleep(random.randint(1,5))
        print(job)

    def call_gams(self, job):
        line = job[:0]

        assert not os.path.isdir(self.working_dir), "Directory {} already exists".format(self.working_dir)
        os.makedirs(self.working_dir)

        thread_opts = []
        for gamsdir in ['Procdir', 'Scrdir']:
            thread_opts.append(gamsdir)
            thread_opts.append(os.path.abspath(os.path.join(self.working_dir, gamsdir.lower())))
        
        SubCaller.call(line + thread_opts, silent=True)
        
        for _ in range(20):
            if not os.path.isdir(self.working_dir):
                return

            shutil.rmtree(self.working_dir, ignore_errors=True)
            time.sleep(1)

        raise OSError('The directory {} could not be removed'.format(self.working_dir))


class GamsQueuer(object):
    def __init__(self, threads=1):
        self.threads = threads
        self.workers = []
        self.job_done = Event()
        self.job_queue = JoinableQueue()
        self.kill_signal = Event()

    def start(self):
        for i, _ in enumerate(range(self.threads)):
            w = GamsWorker(i, job_queue=self.job_queue, job_done=self.job_done, kill_signal=self.kill_signal)
            w.start()
            self.workers.append(w)

    def call(self, line, silent=False, *args, **kwargs):
        if not silent:  
            print('Enqueing ' + ': '.join(line[:2]))

        self.job_queue.put(line)


class Printout(object):
    @staticmethod
    def call(line,*args,**kwargs):
        printstr = ' '.join(line[:2]) + ' '
        printstr += ' '.join(['='.join(line[i:i+2]) for i in range(2,len(line),2)])
        print(printstr)
        return 0


def main():

    default_dataset = 'NCA'

    args = getArguments(default_dataset)
    config = Config(debug=args.debug, dataset=args.dataset)

    if args.debug:
        callAction = Printout
    elif args.threaded:
        queuer = GamsQueuer(threads=args.threads)
        queuer.start()
        callAction = queuer
    else:
        callAction = SubCaller

    run = False

    years = None
    if args.years is not None:
        if re.search(r':',args.years):
            yearrange = [int(i) for i in args.years.split(':')]
            assert len(yearrange) in (2,3), "year arguments separated by colons must be of the form start:end:step"
            years = [str(y) for y in range(*tuple(yearrange))]
        else:
            years = args.years.split(',')

    args.hscens = args.hscens if args.hscens is None else args.hscens.split(',')
    args.runmodel = args.runmodel if args.runmodel is None else args.runmodel.split(',')
    args.combo = args.combo if args.combo is None else args.combo.split(',')
    args.eID = args.eID if args.eID is None else args.eID.split(',')

    sID = None
    if args.sID is not None:
        if re.search(r':',args.sID):
            sIDrange = [int(i) for i in args.sID.split(':')]
            assert len(sIDrange) in (2,3), "year arguments separated by colons must be of the form start:end:step"
            sID = [str(y) for y in range(*tuple(sIDrange))]
        else:
            sID = args.sID.split(',')

    l = None

    if args.base == True:
        l = BaseRun(config=config, callAction=callAction)
    if args.iter == True or not (args.sImpact is None):
        l = MedianRun(config=config, together=False,iterate=True,callAction=callAction,single=args.single,impact=args.sImpact,runmodel=args.runmodel,allSLR=args.allSLR,skipAll=args.skipAll,check=args.check,years=years,sID=sID,hscens=args.hscens)
    if args.pmed == True:
        l = MedianRun(config=config, together=True,iterate=False,callAction=callAction,single=args.single,runmodel=args.runmodel,allSLR=args.allSLR,skipAll=args.skipAll,check=args.check,years=years,sID=sID,hscens=args.hscens)
    if not args.combo is None:
        l = MedianRun(config=config, together=False,iterate=False,callAction=callAction,single=args.single,combo=args.combo,runmodel=args.runmodel,allSLR=args.allSLR,skipAll=args.skipAll,check=args.check,years=years,sID=sID,hscens=args.hscens)

    if args.exp == True:
        if args.eID is None:
            l = Experiment(config=config, together=True,iterate=False,callAction=callAction,single=args.single,combo=None,years=years)
        else:
            l = Experiment(config=config, together=False,iterate=False,callAction=callAction,single=args.single,combo=args.eID,years=years)


    if l is not None:
        try:
            l.run()
        except (KeyboardInterrupt, SystemExit):
            print('Waiting for GAMS to exit...')
            if args.threaded:
                queuer.kill_signal.set()
            return
        except:
            traceback.print_exc()
            if args.threaded:
                queuer.kill_signal.set()
            return

    else:
        print('\n\tNo run instructions provided - terminating execution.')
        print('\tRun with flags \n\t\t-b (base - no impacts), \n\t\t-i (iterate through impacts one at a time),\n\t\t-s (run one impact using flag -S=LABOR, e.g.), or \n\t\t-m (run all impacts)')
        print('\n\tSee the help dialog for more instructions and options by entering')
        print('\n\t\tpython local.py -h\n')


    if args.threaded:
        queuer.job_done.set()


class LocalRun(object):
    def __init__(self, config=None, impact_set=None, threadID=1,runID=1,impactrun=False,together=True,iterate=False,hscen='Hist',callAction=Printout,skipAll=False,years=None):
        
        # Global properties/set defaults if not provided
        self.config     = config if config is not None else Config()
        self.impact_set = impact_set
        
        if self.impact_set is None and impactrun is True:
            self.impact_set = ImpactSet()
            self.impact_set.prep_all_impacts()

        #   Run properties
        self.threadID       = threadID
        self.runID      = runID
        self.impactrun  = impactrun
        self.together       = together
        self.iterate        = iterate
        self.hscen      = hscen
        self.skipAll        = skipAll
        self.years      = years

        #   Runtime properties
        self.errors         = False
        self.callAction = callAction


    def run(self,target='NCA',silent=True):

        # Reset threadID for impacts and prepare input files        
        self.impact_set.threadID = self.threadID
        self.impact_set.prep_all_impacts()

        model_call = ['gams.exe','modelControl']

        spec = [
            'o','{list}'.format(list=os.path.join('listings','modelrun_{tID}.lst'.format(tID=self.threadID))),
            '--isuffix','{isuffix}'.format(isuffix=IMPACT_SUFFIX),
            '--threadID','{tID}'.format(tID=self.threadID),
            '--aggr','{t}'.format(t=target)
            ]

        if self.years is not None:
            years = self.years
        else:
            years = ['0']

        if silent:
            spec.extend(['lo','2','lf',os.path.join('listings','modelrun_{tID}.out'.format(tID=self.threadID))])


        if self.impactrun:

            if self.iterate:
                for impact in self.impact_set.run_impacts:
                    for year in years:              
                        year_spec = ['--DAMAGE_YEAR',year]
                        print('> Running impact {i} of job {rID}{time}'.format(i=impact,rID=self.runID,time='' if self.years is None else ' in {}'.format(year)))
                        status = self.errorCheck(self.callAction.call((model_call + spec + year_spec + ['--runID','{rID}_{d}'.format(rID=self.runID, d=impact),'--HURR_ACTIV_SCEN',self.hscen,'--SINGLE_DAMAGE','TRUE','--SDAMAGE_TYPE',impact]), silent=silent),impact)
                        if status:
                            return status

            if self.together or (self.iterate and not self.skipAll):
                
                for year in years:              
                    year_spec = ['--DAMAGE_YEAR',year]
                    print('> Running combined impacts for job {rID}{time}'.format(rID=self.runID,time='' if self.years is None else ' in {}'.format(year)))
                    status = self.errorCheck(self.callAction.call((model_call + spec + year_spec + ['--runID','{rID}'.format(rID=self.runID),'--HURR_ACTIV_SCEN',self.hscen,'--SINGLE_DAMAGE','FALSE']), silent=silent))
                    if status:
                        return status

            if (not self.together) and (not self.iterate):
                combos = []
                for i in ALL_IMPACTS:
                    if i in self.impact_set.run_impacts:
                        combos.extend(['--RUN_{}'.format(i),'TRUE'])
                for year in years:
                    year_spec = ['--DAMAGE_YEAR',year]
                    print('> Running combo for job {rID}{time}'.format(rID=self.runID,time='' if self.years is None else ' in {}'.format(year)))
                    status = self.errorCheck(self.callAction.call((model_call + spec + combos + year_spec + ['--runID','{rID}'.format(rID=self.runID),'--HURR_ACTIV_SCEN',self.hscen,'--DAMAGE_OFF','TRUE','--SINGLE_DAMAGE','FALSE']), silent=silent))
                    if status:
                        return status

        else:
            print('\nRunning base scenario\n{l}'.format(l='-'*60))
            status = self.errorCheck(self.callAction.call(model_call + spec + ['--runID','{rID}'.format(rID=self.runID),'--HURR_ACTIV_SCEN','Hist','--DAMAGE_OFF','TRUE']))
            if status:
                return status

    def errorCheck(self,errorlev,impact='ALL'):
        if errorlev > 0:
            print('\nERRORS REPORTED BY GAMS SYSTEM ----\nGAMS ERROR:\t{l}'.format(l=errorlev))
            if self.errors == False:
                with open('errors.log','w+') as writefile:
                    writefile.write('RUNID,THREADID,IMPACT,HURRICANE,ERRORLEV\n')
                    self.errors == True
            with open('errors.log','a') as writefile:
                writefile.write('{r},{t},{i},{h},{l}\n'.format(r=self.runID,t=self.threadID,i=impact,h=self.hscen,l=errorlev))

            return errorlev
        return None



class Experiment(object):
    def __init__(self,tmpdir=DEFAULT_ECON_DIR,expDir='experiments',expIDs=None,together=False,iterate=True,callAction=Printout,impact=None,single=False,combo=None,sea_level='MSL'):
        self.tmpdir     = tmpdir
        self.expDir     = expDir
        self.expIDs     = expIDs
        self.together   = together
        self.iterate    = iterate
        self.callAction = callAction
        self.impact     = impact
        self.single     = single
        self.combo      = combo
        self.sea_level = sea_level
    
    def run(self):
        try: os.remove('models.log')
        except: pass

        for experiment in os.listdir(self.expDir):
            match = re.match(r'(?P<rcp>rcp[0-9]{2})_(?P<hurr>(hist|rcp[0-9]{2}))_(?P<model>[^_]*)_(?P<www>[0-9]{3})_(?P<slr>[0-9]+)',experiment)
            rcp = match.group('rcp')
            hurr = match.group('hurr')
            model = match.group('model')
            www = match.group('www')
            slr = match.group('slr')

            slrfile = os.path.join(self.expDir,experiment,'coastal_{rcp}_{hurr}_{sl}_{slr}.gdx'.format(rcp=rcp,hurr=hurr,sl=self.sea_level,slr=slr))
            efile = os.path.join(self.expDir,experiment,'energy_{rcp}_{model}_{sl}_{slr}.gdx'.format(rcp=rcp,model=model,sl=self.sea_level,slr=int(www)))

            # threadID,runID,impactrun=False,together=True,iterate=False,econdir=None,slrfile=None,hcddfile=None,tmpdir=None,callAction=Printout,impact=None,combo=None):
            L = LocalRun(1,model,True,self.together,self.iterate,os.path.join(self.expDir,experiment),slrfile,efile,self.tmpdir,callAction=self.callAction,impact=self.impact,combo=self.combo)
            L.run()

            if self.single:
                return

class ImpactSet(object):

    # Hashes of impact data
    tmpfiles = {}

    required = set([
        'yields-grains-state','yields-oilcrop-state','yields-cotton-state',
        'labor-high-productivity-state','labor-low-productivity-state',
        'health-mortage-0-0-state','health-mortage-1-44-state',
        'health-mortage-45-64-state','health-mortage-65-inf-state',
        'energy','coastal'])

    impact = {
        'yields-grains-state':           'AG',
        'yields-oilcrop-state':          'AG',
        'yields-cotton-state':           'AG',
        'labor-high-productivity-state': 'LABOR',
        'labor-low-productivity-state':  'LABOR',
        'health-mortage-0-0-state':      'MORTALITY',
        'health-mortage-1-44-state':     'MORTALITY',
        'health-mortage-45-64-state':    'MORTALITY',
        'health-mortage-65-inf-state':   'MORTALITY',
        'energy':                        'COASTAL',
        'coastal':                       'ENERGY'}

    def __init__(self, config=None, threadID=1, runID='test', tmpdir=None, econdir=None, energyfile=None, slrfile=None, run_impacts=ALL_IMPACTS, prep_impacts=ALL_IMPACTS):
        
        # Global properties/set defaults if not provided
        self.config       = config if config is not None else Config()

        #   Run properties
        self.threadID         = threadID
        self.runID        = runID
        self.run_impacts  = run_impacts
        self.prep_impacts = prep_impacts

        if econdir is None:
            econdir = os.path.join(self.config.econdir, 'cnrm-cm5/001')

        if energyfile is None:
            energyfile = os.path.join(self.config.energy, 'energy_rcp85_cnrm-cm5_1.gdx')

        if slrfile is None:
            slrfile = os.path.join(self.config.coastal, 'coastal_rcp85_hist_MSL_Median.gdx')

        self.tmpdir = tmpdir if tmpdir is not None else DEFAULT_TMP_DIR

        self.econdir = econdir
        self.energyfile = energyfile
        self.slrfile = slrfile

        self.make_dirs()

    @staticmethod
    def hashfile(filepath):
        assert os.path.exists(filepath), 'filepath {} does not exist'.format(filepath)
        return base64.urlsafe_b64encode(hashlib.sha256(filepath+open(filepath, 'r').read()).digest())

    def getimpact(self):
        impacts = []

        if (self.prep_impacts is None) or ('ENERGY' in self.prep_impacts):
            impacts.append(self.energyfile)
    
        if (self.prep_impacts is None) or ('COASTAL' in self.prep_impacts):
            impacts.append(self.slrfile)

        for f in os.listdir(self.econdir):
            prefix = re.search(r'(?P<impact>[^.]+)\.',f)
            if not prefix:
                continue
            prefix = prefix.group('impact')
            if prefix not in self.required:
                continue

            impact = self.impact[prefix]
            if self.prep_impacts is not None and impact not in self.prep_impacts:
                continue

            impacts.append(os.path.join(self.econdir, f))

        for impact in impacts:
            yield impact

    def make_dirs(self):
        for newdir in [self.config.hashdir, self.config.tmpdir]:
            if not os.path.isdir(os.path.dirname(os.path.abspath(newdir))):
                raise OSError('Parent directory of temporary impacts directory {} not found'.format(newdir))

            if not os.path.isdir(os.path.abspath(newdir)):
                os.makedirs(os.path.abspath(newdir))

    def prep_all_impacts(self):

        for old_impact in os.listdir(self.config.tmpdir):
            if re.match(str(self.threadID)+'_',old_impact):
                os.remove(os.path.join(self.config.tmpdir,old_impact))


        print('\nPreparing job {id} '.format(id=self.runID))

        for filepath in self.getimpact():
            self.prep_impact(filepath)

    def prep_impact(self, filepath):
        '''
        Load a cached impact file or process a new impact file if not cached
        '''

        filename = os.path.basename(filepath)
        prefix, standardized, std_prefix, impact_type, final_suffix = parse.getNewFilename(filepath)
        
        if standardized is None:
            return  #   Only impact files specified in parse will be used
        
        id_filename, id_prefix = ('{ID}_{name}'.format(ID=self.threadID,name=f) for f in (std_prefix+final_suffix,std_prefix))


        hashed = self.hashfile(filepath)

        final = None

        newpath = os.path.join(self.config.tmpdir,id_filename)

        if hashed in self.tmpfiles:
            if os.path.exists(os.path.join(self.config.hashdir, hashed)):
                final = self.tmpfiles[hashed]
                shutil.copy(final, newpath)

        if final is None:
            for h in os.listdir(self.config.hashdir):
                self.tmpfiles[h] = os.path.join(self.config.hashdir, h)

            if hashed in self.tmpfiles:
                final = os.path.join(self.config.hashdir, hashed)
                self.tmpfiles[hashed] = final
                shutil.copy(final, newpath)

            else:
                impact_handler = parse.getFileAction(self.config.tmpdir, std_prefix,filepath,prefix,id_filename,id_prefix)  #   overload move function to keep impacts in place
                final = impact_handler.run()
                hashpath = os.path.join(self.config.hashdir, hashed)
                shutil.copy(final, hashpath)
                self.tmpfiles[hashed] = hashpath

        
        print('- Impact file {f} prepared from {o}'.format(f=standardized,o=os.path.dirname(final)))

    def clear(self, impacts=None):
        for f in os.listdir(self.tmpdir):
            parser = re.match(r'{}_(?P<impact>[^.]+).'.format(self.threadID),f)
            if not parser:
                continue

            if impacts is None:
                os.remove(os.path.join(self.tmpdir, f))
            else:
                if parser.group('impact') in impacts:
                    os.remove(os.path.join(self.tmpdir, f))


class MedianRun(object):
    def __init__(self,config=None, tmpdir=DEFAULT_ECON_DIR,together=False,iterate=True,callAction=Printout,impact=None,single=False,combo=None,runmodel=None,allSLR=False,skipAll=False,check=False,years=None,sea_levels=None,sID=None,hscens=None):
        self.config     = config
        self.together       =   together
        self.iterate        =   iterate
        self.callAction =   callAction
        self.impact         =   impact
        self.single         =   single
        self.combo          =   combo
        self.runmodel       =   runmodel
        self.allSLR         =   allSLR
        self.skipAll        =   skipAll
        self.check      = check
        self.years      = years
        self.hscens     = hscens if hscens is not None else ['Hist']
        self.sID        = sID if sID is not None else ['Median']
        self.sea_levels = sea_levels if sea_levels is not None else ['MSL']

        self.rcp        = 'rcp85'
        self.srcp       = COSATAL_RCP_MAP[self.rcp]

    def merge(self, outfile, mergefiles, newname_func):

        time.sleep(5)

        tmppath = 'results-tmp-{}'.format(outfile)
        if not os.path.isdir(tmppath):
            os.makedirs(tmppath)
        
        resultfiles = os.listdir('results')

        found = False
        for f in resultfiles:
            for p in mergefiles:
                if not re.search(p,f):
                    continue

                tmpname = newname_func(f)
                assert (isinstance(tmpname, str) and len(tmpname) > 0), "Result of newname_func for {} is invalid: {}".format(f,tmpname)

                found = True

                tmpfile = os.path.join(tmppath, tmpname + '.gdx')
                if os.path.exists(tmpfile):
                    os.remove(tmpfile)

                os.rename(os.path.join('results',f), tmpfile)

        def cleanup():
            for _ in range(5):
                try:
                    shutil.rmtree(tmppath)
                    break
                except:
                    time.sleep(5)

        if found:
            self.callAction.call(['gdxmerge',os.path.join(tmppath,'*.gdx'),'o',os.path.join('results','{}.gdx'.format(outfile))], stdout=DEVNULL)
        
        threading.Thread(target=cleanup).start()

    def choose_impacts_for_run(self):
        if not (self.combo is None):
            for c in self.combo:
                if not c in ALL_IMPACTS:
                    raise OSError('impact {c} not a valid impact. Choose one of {i}'.format(c=c,i=','.join(ALL_IMPACTS)))
            impacts = self.combo
        elif self.impact is None:
            impacts = ALL_IMPACTS
        elif self.impact in ALL_IMPACTS:
            impacts = [self.impact]
        else:
            raise OSError('impact argument must be one of {i}'.format(i=', '.join(ALL_IMPACTS)))

        return impacts, set(impacts + ([] if self.skipAll else ALL_IMPACTS))

    def get_slr_files(self):
        if not self.allSLR:
            return [(os.path.join(self.config.coastal,'coastal_{}_{}_{}_{}.gdx'.format(self.srcp,hscen,sl,sID)),hscen,sID,sl,self.srcp) for hscen in self.hscens for sl in self.sea_levels for sID in self.sID]
            
        slrfiles = []
        for f in os.listdir(self.config.coastal):

            # skip median draws for allSLR run, parse others for rcp, hscen, sl type, and sID
            slmatch = re.search(r'^coastal_(?P<rcp>rcp(26|45|60|85))_(?P<hscen>(hist|rcp(45|85)))_(?P<sl>M(HHW|SL))_(?P<sli>[0-9]{1,5})\.gdx$',f)
            if not slmatch: continue
            
            rcp = slmatch.group('rcp')
            hscen = 'Hist' if (slmatch.group('hscen')[0].upper() == 'H') else rcp

            sl = slmatch.group('sl')
            if sl not in self.sea_levels:
                continue
            if slmatch.group('sli').upper() == 'MEDIAN':
                sli = 'Median'
            else:
                sli = int(slmatch.group('sli'))
            slrfiles.append((os.path.join(self.config.coastal,f),hscen,sli,sl,rcp))

        slrfiles.sort(key=lambda x: x[2])

        return slrfiles

    def iter_model(self, path):
        for model in os.listdir(path):
            model_run = False
            if not self.runmodel is None:
                if not model in (self.runmodel):
                    continue
            yield model, os.path.join(self.config.econdir,model)

    def iter_wdraw(self, path):
        for f in os.listdir(path):
            if os.path.isdir(os.path.join(path, f)):
                yield f, os.path.join(path, f)

    def run(self):
        try: os.remove('models.log')
        except: pass

        required = [
            'yields-grains-state','yields-oilcrop-state','yields-cotton-state',
            'labor-high-productivity-state','labor-low-productivity-state',
            'health-mortage-0-0-state','health-mortage-1-44-state',
            'health-mortage-45-64-state','health-mortage-65-inf-state']

        run_impacts, prep_impacts = self.choose_impacts_for_run()
        slrfiles = self.get_slr_files()

        if (run_impacts == ['COASTAL']) and (self.together is False):
            self.single = True

        for model, modelpath in self.iter_model(self.config.econdir):
            model_run = False

            for wdraw, wpath in self.iter_wdraw(modelpath):
                run_ok = False

                impactfiles = os.listdir(wpath)
                for f in impactfiles:
                    if re.search(r'cgechk',f):
                        run_ok = True
                        break
                
                for r in required:
                    if not '{}.tar.gz'.format(r) in impactfiles:
                        run_ok = False
                        print('{} not found in {}/{}'.format(r,model,wdraw))

                if not run_ok:
                    continue

                if self.check:
                    model_run = True
                    continue

                for slrfile, hscen, sli, sl, rcp in slrfiles:

                    if rcp != self.srcp: continue

                    if (prep_impacts == ['COASTAL']) and (self.together is False):
                        model = 'coastal'
                        wdraw = 0
                    runID = '{m}_{w}_{r}_{h}_{l}_{s}'.format(r=self.rcp, m=model, w=wdraw, h=hscen, l=sl, s=sli)

                    #try:
                    efile = None
                    if ('ENERGY' in prep_impacts) or (self.together is True):
                        for f in os.listdir(self.config.energy):
                            if re.search(r'^energy_rcp(26|45|60|85)_{m}_{w}\.gdx$'.format(m=model,w=int(wdraw)),f):
                                efile = os.path.join(self.config.energy,f)
                        if efile is None:
                            raise OSError('Energy file not found for model {m} wdraw {w}'.format(m=model, w=wdraw))
                            continue

                    impact_set = ImpactSet(threadID=None, runID=runID, econdir=wpath, energyfile=efile, slrfile=slrfile, run_impacts=run_impacts, prep_impacts=prep_impacts)

                    L = LocalRun(config=self.config, impact_set=impact_set, threadID=1, runID=runID, impactrun=True, together=self.together, iterate=self.iterate, hscen=hscen, callAction=self.callAction, skipAll=self.skipAll, years=self.years)
                    status = L.run()
                    impact_set.clear(['COASTAL'])
                    if status:
                        print('Errors encountered by GAMS')
                        return

                    if self.years is not None:
                        for impact in ALL_IMPACTS + ['ALL']:
                            year_search = re.compile(r'{rID}_{impact}_y(?P<year>[0-9]{{4}})\.gdx'.format(rID=runID, impact=impact))
                            self.merge(
                                '{}_{}'.format(runID, impact),
                                [year_search],
                                lambda f: (re.search(year_search, f).group('year'))
                                )

                    impact_search = re.compile(r'{rID}(_(?P<impact>[A-Z]+))?\.gdx'.format(rID=runID))
                    impact_search_strict = re.compile(r'{rID}(_(?P<impact>[A-Z]+))\.gdx'.format(rID=runID))
                    self.merge(
                        '{}'.format(runID), 
                        [impact_search], 
                        lambda f: (re.search(impact_search, f).group('impact') if re.search(impact_search_strict, f) else 'ALL')
                        )
                
                    model_run = True

                if self.check: continue
                sli_search = re.compile(r'{}_{}_{}_{}_{}_(?P<slr>(Median|[0-9]+))\.gdx'.format(model,wdraw,rcp,hscen,sl))
                self.merge('{}_{}_{}_{}_{}'.format(model,wdraw,rcp,hscen,sl),[sli_search],lambda f: (re.search(sli_search, f).group('slr')))

                slev_search = re.compile(r'{}_{}_{}_{}_(?P<sl>(MSL|MHHW))\.gdx'.format(model,wdraw,rcp,hscen))
                self.merge('{}_{}_{}_{}'.format(model,wdraw,rcp,hscen),[slev_search],lambda f: (re.search(slev_search, f).group('sl')))

                hscen_search = re.compile(r'{}_{}_{}_(?P<hscen>Hist|rcp(4|8)5)\.gdx'.format(model,wdraw,rcp))
                self.merge('{}_{}_{}'.format(model,wdraw,rcp),[hscen_search],lambda f: (re.search(hscen_search, f).group('hscen')))

                rcp_search = re.compile(r'{}_{}_(?P<rcp>rcp(26|45|60|85))\.gdx'.format(model,wdraw))
                self.merge('{}_{}'.format(model,wdraw),[rcp_search],lambda f: (re.search(rcp_search, f).group('rcp')))

                if self.single:
                    return

            if not model_run:
                print('No valid input file sets found for model {m}. Check econdir cgechk file presence.'.format(m=model))
                continue


            impact_set.clear()

            if self.check: continue
            wdraw_search = re.compile(r'{}_(?P<wdraw>[0-9]+)\.gdx'.format(model))
            self.merge('{}'.format(model),[wdraw_search],lambda f: (re.search(wdraw_search, f).group('wdraw')))

        if self.check: return

        model_search = re.compile(r'(?P<model>({}))\.gdx'.format('|'.join([re.escape(d) for d in os.listdir(wpath) if (os.path.isdir(os.path.join(wpath,d)) and (len(d) > 0) and (d[0] != '.'))])))
        self.merge('muse',[model_search],lambda f: (re.search(model_search, f).group('model')))

class BaseRun(object):
    def __init__(self, config=None, callAction=Printout):
        self.config = config
        self.callAction=callAction

    def run(self):
        L = LocalRun(config=self.config, threadID=1, runID='Base', impactrun=False, callAction=self.callAction)
        L.run()

def getArguments(default_dataset):
    parser = argparse.ArgumentParser(description='Impact processing and run management for local (non-server) run')
    flavor = parser.add_argument_group('run flavor arguments')
    flavor.add_argument('-b','--base',help='run the base run with no impacts',action='store_true')
    flavor.add_argument('-i','--iter',help='iterate through impacts, running the median of each impact distribution with all other impacts turned off',action='store_true')
    flavor.add_argument('-m','--pmed',help='run the median of each impact distribution together in a single run',action='store_true')
    flavor.add_argument('-c','--combo',default=None,help='run the median of the impacts provided by the comma-separated list')
    flavor.add_argument('-e','--exp',help='run specific experiments downloaded and placed in the experiments directory',action='store_true')
    flavor.add_argument('-E','--eID',default=None,help='comma-separated list of experiment IDs (no spaces or brackets). By default, run all.')
    flavor.add_argument('-s','--single',help='run a single run. Run will be first model, wdraw encountered in econdir.',action='store_true')
    flavor.add_argument('-r','--runmodel',default=None,help='specify a model to run')
    flavor.add_argument('-S','--sImpact',default=None,help='impact to run in a --single experiment')
    flavor.add_argument('-a','--allSLR', default=False, help='Run all models/slr files matching the given run parameters', action='store_true')
    flavor.add_argument('-y','--years',default=None, help='Run a single-year delta experiment')
    # flavor.add_argument('-R','--randSLR',default=False, help='Run a random SLR draw for each run. Run both Hist and projected scenarios',action='store_true')
    flavor.add_argument('-H','--hscens',default=None, help='Hurricane scenarios to include in a median run or experiment')
    flavor.add_argument('-I','--sID',default=None,help='Draw ID for SLR scenarios. Default Median unless -a flag specified.')
    flavor.add_argument('-k','--skipAll', default=False, help='Do not run combined all-impact run after iter/single impact runs', action='store_true')
    config = parser.add_argument_group('configuration options')
    config.add_argument('-x','--dataset',default=default_dataset,type=str,help='choose the *_trdbal.gdx dataset to use')
    config.add_argument('-d','--debug', default=False, help='print, rather than execute, the GAMS commands',action='store_true')
    config.add_argument('-C','--check', default=False, help='check input files, but do not execute runs', action='store_true')
    config.add_argument('-t','--threaded', default=False, help='Threaded run', action='store_true')
    config.add_argument('-n','--threads', default=1, type=int, help='Number of threads in a threaded run')
    return parser.parse_args()

if __name__=="__main__":
    main()