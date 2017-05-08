

import time
from threading import Thread as Process, Event
from Queue import Queue as JoinableQueue
import Queue as QueueModule

class ConsumerInterface(object):
	@staticmethod
	def printer(x, *args, **kwargs):
		raise NotImplementedError


class Consumer(Process):

	def __init__(self, action=None, job_queue=None, job_done=None, kill_signal=None):
		Process.__init__(self)

		self.job_queue   = job_queue   if job_queue   is not None else JoinableQueue()
		self.job_done    = job_done    if job_done    is not None else Event()
		self.kill_signal = kill_signal if kill_signal is not None else Event()
		
		self.action      = action

	@staticmethod
	def printer(x,*args,**kwargs):
		print(x)
		
	def initialize(self):
		pass

	def _initialize(self):
		self.initialize()

		# if self.job_queue   is None: self.job_queue    = JoinableQueue()
		# if self.job_done    is None: self.job_done     = Event()
		# if self.kill_signal is None: self.kill_signal  = Event()
		if self.action is None: self.action = ConsumerInterface.printer

	def run(self):
		self._initialize()
		
		last_try = False

		while True:
			if self.kill_signal.is_set(): return

			try:
				job = self.job_queue.get(True, 1)
				self.action(job)
				self.job_queue.task_done()
				last_try = False

			except (QueueModule.Empty):
				if last_try: return
				if self.kill_signal.is_set(): return
				if self.job_done.is_set() and self.job_queue.qsize() == 0:
					last_try = True

			except (SystemExit, KeyboardInterrupt):
				self.kill_signal.set()
				return

	def clear(self):
		while not self.job_queue.empty():
			try:
				self.job_queue.get(False)
				self.job_queue.task_done()
			except QueueModule.Empty:
				pass

	def join_consumer(self, timeout=None):
		return queue_joinif(self.job_queue, self.kill_signal, timeout)

	def log(self, message, *args, **kwargs):
		''' public log method that can be overloaded with other logging methods '''
		print(message)

	def report(self, *args):
		print('Errors reported:\n{}'.format('\n'.join(args)))


def queue_joinif(this_queue, kill_signal=None, timeout=None):
	assert (kill_signal is not None) or (timeout is not None), "queue_joinif requires either a kill_signal or timout argument."
	t = Process(target=this_queue.join)
	t.start()
	start_time = time.time()
	while True:
		if kill_signal is not None:
			if kill_signal.is_set():
				return False
		if timeout is not None:
			if (time.time() - start_time > timeout):
				return False
		try:
			t.join(1)
			assert not t.is_alive()
			return True
		except AssertionError:
			pass
	return False

