#! /usr/bin/env python

import json
import os

import signal

import socorro.storage.json_dump_storage as jds
import socorro.storage.crashstorage as cstore
import socorro.lib.util as sutil
import socorro.lib.iterator_worker_framework as iwf


#-------------------------------------------------------------------------------
def move (conf,
          sourceCrashStorageClass=cstore.FSRawCrashStorageWithFallback,
          destCrashStorageClass=cstore.HBaseCrashStorage):
    logger = conf.logger
    crashStoragePoolForSource = cstore.CrashStoragePool(conf,
                                                        sourceCrashStorageClass)
    crashStoragePoolForDest = cstore.CrashStoragePool(conf,
                                                      destCrashStorageClass)
    signal.signal(signal.SIGTERM, iwf.respond_to_SIGTERM)
    signal.signal(signal.SIGHUP, iwf.respond_to_SIGTERM)

    #---------------------------------------------------------------------------
    def theIterator():
        """This infinite iterator will walk through the file system storage,
        yielding the ooids of every new entry in the filelsystem.  If there
        are no new entries, it yields None"""
        destinationCrashStore = crashStoragePoolForDest.crashStorage()
        for dir,dirs,files in os.walk(conf.localFS):
            print dir, files
            for aFile in files:
                if aFile.endswith('json'):
                    ooid = aFile[:-5]
                    logger.debug('the ooid is %s', ooid)
                    try:
                        if destinationCrashStore.get_meta():
                            logger.info('skipping %s - already in hbase', ooid)
                            pass
                    except Exception:
                        logger.info('yielding %s', ooid)
                        yield ooid
    #---------------------------------------------------------------------------

    #---------------------------------------------------------------------------
    def doSubmission(ooidTuple):
        logger.debug('received: %s', str(ooidTuple))
        try:
            sourceStorage = crashStoragePoolForSource.crashStorage()
            destStorage = crashStoragePoolForDest.crashStorage()
            ooid = ooidTuple[0]
            try:
                logger.debug('trying to fetch %s', ooid)
                jsonContents = sourceStorage.get_meta(ooid)
            except ValueError:
                logger.warning('the json for %s is degenerate and cannot be '
                               'loaded - saving empty json', ooid)
                jsonContents = {}
            dumpContents = sourceStorage.get_raw_dump(ooid)
            if conf.dryrun:
                logger.info("dry run - pushing %s to dest", ooid)
            else:
                logger.debug('pushing %s to dest', ooid)
                result = destStorage.save_raw(ooid, jsonContents, dumpContents)
                if result == cstore.CrashStorageBase.ERROR:
                    return iwf.FAILURE
                elif result == cstore.CrashStorageBase.RETRY:
                    return iwf.RETRY
                try:
                    sourceStorage.quickDelete(ooid)
                except Exception:
                    sutil.reportExceptionAndContinue(self.logger)
            return iwf.OK
        except Exception, x:
            sutil.reportExceptionAndContinue(logger)
            return iwf.FAILURE
    #---------------------------------------------------------------------------

    submissionMill = iwf.IteratorWorkerFramework(conf,
                                                 jobSourceIterator=theIterator,
                                                 taskFunc=doSubmission,
                                                 name='submissionMill')

    try:
        submissionMill.start()
        submissionMill.wait_for_completion() # though, it only ends if someone
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
    move(config,
         sourceCrashStorageClass=config.source.storageClass,
         destCrashStorageClass=config.destination.storageClass)

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'orphan_mover_app'
version = '1.4'
doc = """sometimes in json dump storage, crashes can get 'orphaned'.  A crash
may not get submitted, but its links in the date section have been destroyed.
 This app will find them and move them on to another storage system."""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('dryrun',
        doc="if True, just go through the motions and log, don't actually do it",
        default=False,
        short_form='d',
        from_string_converter=cm.boolean_converter)
rc.option('numberOfThreads',
          doc="the number of threads to use",
          default=4)
rc.namespace('source')
rc.source.option('storageClass',
        doc='the class of the source (only file system based sources '
            'are appropriate)',
        default='socorro.storage.crashstorage.FSRawCrashStorageWithFallback',
        from_string_converter=cm.class_converter)
rc.namespace('destination')
rc.destination.option('storageClass',
        doc='the class of the destination',
        default='socorro.storage.crashstorage.FSRawCrashStorageWithFallback',
        from_string_converter=cm.class_converter)
rc.option('daysIntoPast',
          'number of days to look into the past for bugs (0 - '
          'use last run time)',
          default=0)
#-------------------------------------------------------------------------------
def get_required_config():
    n = cm.Namespace()
    n.update(rc)
    return n
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])