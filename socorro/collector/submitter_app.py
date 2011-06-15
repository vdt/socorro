#! /usr/bin/env python

import time as tm
import datetime as dt
import json
import os
import signal

import socorro.lib.util as sutil
import socorro.lib.iterator_worker_framework as iwf
import socorro.lib.filesystem as sfs
import socorro.lib.stats as stats

import poster
import urllib2

existingHangIdCache = {}

#-------------------------------------------------------------------------------
def doSubmission (formData, binaryFilePathName, url, logger=sutil.FakeLogger(),
                  posterModule=poster):
    fields = dict([(t[0],t[1]) for t in formData.items()])
    with open(binaryFilePathName, 'rb') as dump_fp:
        fields['upload_file_minidump'] = dump_fp
        datagen, headers = posterModule.encode.multipart_encode(fields);
        request = urllib2.Request(url, datagen, headers)
        print urllib2.urlopen(request).read(),
    try:
        logger.debug('submitted %s', formData['uuid'])
    except KeyError:
        logger.debug('submitted unknown')

#-------------------------------------------------------------------------------
def submissionDryRun (formData, binaryFilePathName, url):
    print formData['ProductName'], formData['Version']

#-------------------------------------------------------------------------------
def createSubmitterFunction (config):
    statsPools = config.statsPool
    def func (paramsTuple):
        jsonFilePathName, binaryFilePathName = paramsTuple[0]
        with open(jsonFilePathName) as jsonFile:
            formData = json.load(jsonFile)
        if config.uniqueHang:
            try:
                if formData['HangId'] in existingHangIdCache:
                    formData['HangId'] = existingHangIdCache
                else:
                    formData['HangId'] =  \
                    existingHangIdCache[formData['HangId']] = uuid.uuid4()
            except Exception:
                pass
        processTimeStatistic = statsPools.processTime.getStat()
        submittedCountStatistic = statsPools.submittedCount.getStat()
        try:
            processTimeStatistic.start()
            config.submissionFunc(formData, binaryFilePathName, config.url,
                                  config.logger)
            submittedCountStatistic.increment()
        except Exception:
            sutil.reportExceptionAndContinue(sutil.FakeLogger())
            failureCountStatistic = statsPools.failureCount.getStat()
            failureCountStatistic.increment()
            return iwf.OK
        finally:
            processTimeStatistic.end()
        return iwf.OK
    return func

#-------------------------------------------------------------------------------
def createFileSystemIterator (config,
                              timeModule=tm,
                              fsModule=sfs):
    def anIter():
        for aPath, aFileName, aJsonPathName in \
            fsModule.findFileGenerator(config.searchRoot,
                                       lambda x: x[2].endswith("json")):
            dumpfilePathName = os.path.join(aPath, "%s%s" %
                                            (aFileName[:-5], ".dump"))
            yield (aJsonPathName, dumpfilePathName)
            if config.sleep:
                timeModule.sleep(config.sleep)
    return anIter

#-------------------------------------------------------------------------------
def createInfiniteFileSystemIterator (config,
                                      timeModule=tm):
    anIterator = createFileSystemIterator(config,
                                          timeModule)
    def infiniteIterator():
        while True:
            for x in anIterator():
                yield x
    # Why not use itertools.cycle?  Two reasons.  The IteratorWorkerFramework
    # has a design flaw where it wants a funciton that produces an iterator,
    # rather than an actual iterator.  itertool.cycle only deals with real
    # iterators not iterator factories.  Second, the cycle function caches all
    # the values from the first run of the target iterator.  It then serves out
    # the cached values for subsequent runs.  If the original iterator produces
    # a huge number of values, the cache will also be huge.  I'm avoiding that.
    return infiniteIterator

#-------------------------------------------------------------------------------
def createLimitedFileSystemIterator (config,
                                     timeModule=tm):
    anIterator = createInfiniteFileSystemIterator(config,
                                                  timeModule)
    def limitedIterator():
        for i, x in enumerate(anIterator()):
            if i >= config.numberOfSubmissions:
                break
            yield x
    return limitedIterator

#-------------------------------------------------------------------------------
def submitter (config):
    logger = config.logger
    signal.signal(signal.SIGTERM, iwf.respondToSIGTERM)
    signal.signal(signal.SIGHUP, iwf.respondToSIGTERM)

    statsPool = sutil.DotDict(
        { 'submittedCount': stats.CounterPool(config),
          'failureCount': stats.CounterPool(config),
          'processTime': stats.DurationAccumulatorPool(config),
        })
    config.statsPool = statsPool

    reportigCounter = 0
    def statsReportingWaitingFunc():
        if not statsReportingWaitingFunc.reportingCounter % 60:
            submittedCountPool = statsPool.submittedCount
            numberOfMinutes = submittedCountPool.numberOfMinutes()
            if numberOfMinutes:
                logger.info('running for %d minutes', numberOfMinutes)
                numberSubmitted = submittedCountPool.read()
                logger.info('average submitted per minute: %s', \
                      (float(numberSubmitted) / numberOfMinutes))
                numberOfFailures = statsPool.failureCount.read()
                logger.info('failures in the last five minutes: %d', \
                      numberOfFailures)
                processTime = statsPool.processTime.read()
                logger.info('average time in last five minutes: %s', \
                      processTime)
        statsReportingWaitingFunc.reportingCounter += 1
    statsReportingWaitingFunc.reportingCounter = 0

    theIterator = config.iteratorFunc (config)
    theWorkerFunction = createSubmitterFunction(config)

    submissionMill = iwf.IteratorWorkerFramework(config,
                                                 jobSourceIterator=theIterator,
                                                 taskFunc=theWorkerFunction,
                                                 name='submissionMill')

    try:
        submissionMill.start()
        submissionMill.waitForCompletion(statsReportingWaitingFunc)
            # though, it only ends if someone
            # hits ^C or sends SIGHUP or SIGTERM
            # - any of which will get translated
            # into a KeyboardInterrupt exception
    except KeyboardInterrupt:
        while True:
            try:
                submissionMill.stop()
                break
            except KeyboardInterrupt:
                logger.warning('We heard you the first time.  There is no need '
                               'for further keyboard or signal interrupts.  We '
                               'are waiting for the worker threads to stop.  '
                               'If this app does not halt soon, you may have '
                               'to send SIGKILL (kill -9)')

#-------------------------------------------------------------------------------
def main(config):
    poster.streaminghttp.register_openers()

    if config.numberOfSubmissions == 'forever':
        config.iteratorFunc = createInfiniteFileSystemIterator
    elif config.numberOfSubmissions == 'all':
        config.iteratorFunc = createFileSystemIterator
    else:
        config.iteratorFunc = createLimitedFileSystemIterator
        config.numberOfSubmissions = int(config.numberOfSubmissions)

    if config.dryrun:
        config.submissionFunc = submissionDryRun
    else:
        config.submissionFunc = doSubmission

    config.sleep = float(config.delay)/1000.0

    config.uniqueHang = 'uniqueHangId' in config

    if config.searchRoot:
        submitter(config)
    else:
        try:
            import json
            with open(config.jsonfile) as jsonFile:
                formData = json.load(jsonFile)
            config.submissionFunc(formData,
                                  config.dumpfile,
                                  config.url,
                                  config.logger)
        except Exception, x:
            sutil.reportExceptionAndContinue(config.logger)

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'submitter'
version = '2.1'
doc = """will submit crashes to a collector"""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('url',
          doc='The url of the server to load test',
          default ='https://crash-reports.stage.mozilla.com/submit',
          short_form='u')
rc.option('delay',
          doc="pause between submission queing in milliseconds",
          default=0)
rc.option('dryrun',
          doc="don't actually submit, just print product/version",
          default=False,
          short_form='D')
rc.option('numberOfThreads',
          doc='the number of threads to use',
          default=4)
rc.option('numberOfSubmissions',
          doc='the number of crashes to submit (all, forever, 1...)',
          default='all',
          short_form='n')
rc.option('jsonfile',
          doc='the pathname of a json file to submit',
          default=None,
          short_form='j')
rc.option('dumpfile',
          doc='the pathname of a dumpfile to submit',
          default=None,
          short_form='d')
rc.option('searchRoot',
          doc='a filesystem location to begin a search for json/dump pairs',
          default = None,
          short_form='s')
rc.option('uniqueHangId',
          doc='cache and uniquify hangids',
          default=True)

#-------------------------------------------------------------------------------
def get_required_config():
    n = cm.Namespace()
    n.update(rc)
    return n

if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])