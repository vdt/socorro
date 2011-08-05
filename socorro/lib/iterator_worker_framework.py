#import signal
import time
import threading

import socorro.lib.util as sutil
import socorro.lib.threadlib as thr

#------------------------------------------------------------------------------
OK = 1
FAILURE = 0
RETRY = 2


#------------------------------------------------------------------------------
def default_task_func(job_tuple):
    pass


#------------------------------------------------------------------------------
def default_iterator():
    for x in range(10):
        yield x
    while True:
        yield None


#------------------------------------------------------------------------------
def respond_to_SIGTERM(signal_number, frame):
    """ these classes are instrumented to respond to a KeyboardInterrupt by
        cleanly shutting down.  This function, when given as a handler to for
        a SIGTERM event, will make the program respond to a SIGTERM as neatly
        as it responds to ^C.
    """
    #signame = 'SIGTERM'
    #if signalNumber != signal.SIGTERM:
        #signame = 'SIGHUP'
    #self.logger.info("%s detected", signame)
    raise KeyboardInterrupt


#==============================================================================
class IteratorWorkerFramework(object):
    """ """

    #--------------------------------------------------------------------------
    def __init__(self, config, name='mill',
                 job_source_iterator=default_iterator,
                 task_func=default_task_func):
        """
        Note about 'jobSourceIterator': this is perhaps a design flaw.  It
        isn't really an iterator.  It is a function that returns an iterator.
        Just passing in an iterator that's already activated or a generator
        expression will fail.
        """
        super(IteratorWorkerFramework, self).__init__()
        self.config = config
        self.logger = config.logger
        self.name = name
        self.job_source_iterator = job_source_iterator
        self.task_func = task_func
        # setup the task manager to a queue size twice the size of the number
        # of threads in use.
        self.worker_pool = thr.TaskManager(self.config.numberOfThreads,
                                          self.config.numberOfThreads * 2)
        self.quit = False
        self.logger.debug('finished init')

    #--------------------------------------------------------------------------
    def quit_check(self):
        if self.quit:
            raise KeyboardInterrupt

    #--------------------------------------------------------------------------
    def responsive_sleep(self, seconds, wait_log_interval=0, wait_reason=''):
        for x in xrange(int(seconds)):
            self.quit_check()
            if wait_log_interval and not x % wait_log_interval:
                self.logger.info('%s: %dsec of %dsec',
                                 wait_reason,
                                 x,
                                 seconds)
            time.sleep(1.0)

    #--------------------------------------------------------------------------
    def responsive_join(self, thread, waiting_func=None):
        while True:
            try:
                thread.join(1.0)
                if not thread.isAlive():
                    #self.logger.debug('%s is dead', str(thread))
                    break
                if waiting_func:
                    waiting_func()
            except KeyboardInterrupt:
                self.logger.debug('quit detected by responsiveJoin')
                self.quit = True

    #--------------------------------------------------------------------------
    @staticmethod
    def backoff_seconds_generator():
        seconds = [10, 30, 60, 120, 300]
        for x in seconds:
            yield x
        while True:
            yield seconds[-1]

    #--------------------------------------------------------------------------
    def retry_task_func_wrapper(self, *args):
        backoff_generator = self.backoff_seconds_generator()
        try:
            while True:
                result = self.task_func(*args)
                if self.quit:
                    break
                if result in (OK, FAILURE):
                    return
                wait_in_seconds = backoff_generator.next()
                self.logger.critical('failure in task - retry in %s seconds',
                                     wait_in_seconds)
                self.responsive_sleep(wait_in_seconds,
                                     10,
                                     "waiting for retry after failure in task")
        except KeyboardInterrupt:
            return

    #--------------------------------------------------------------------------
    def start(self):
        self.logger.debug('start')
        self.queuing_thread = threading.Thread(name="%sQueuingThread" %
                                                   self.name,
                                              target=self.queuing_thread_func)
        self.queuing_thread.start()

    #--------------------------------------------------------------------------
    def wait_for_completion(self, waiting_func=None):
        self.logger.debug("waiting to join queuingThread")
        self.responsive_join(self.queuing_thread, waiting_func)

    #--------------------------------------------------------------------------
    def stop(self):
        self.quit = True
        self.wait_for_completion()

    #--------------------------------------------------------------------------
    def queuing_thread_func(self):
        self.logger.debug('queuing_thread_func start')
        try:
            try:
                # may never raise StopIteration
                for a_job in self.job_source_iterator():
                    if a_job is None:
                        self.logger.info("there is nothing to do.  Sleeping "
                                         "for 7 seconds")
                        self.responsive_sleep(7)
                        continue
                    self.quit_check()
                    try:
                        self.logger.debug("queuing standard job %s", a_job)
                        self.worker_pool.newTask(self.retry_task_func_wrapper,
                                                (a_job,))
                    except Exception:
                        self.logger.warning('%s has failed', a_job)
                        sutil.reportExceptionAndContinue(self.logger)
            except Exception:
                self.logger.warning('The jobSourceIterator has failed')
                sutil.reportExceptionAndContinue(self.logger)
            except KeyboardInterrupt:
                self.logger.debug('queuingThread gets quit request')
        finally:
            self.quit = True
            self.logger.debug("we're quitting queuingThread")
            self.logger.debug("waiting for standard worker threads to stop")
            self.worker_pool.waitForCompletion()
            self.logger.debug("all worker threads stopped")
