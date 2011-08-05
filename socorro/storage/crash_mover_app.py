#! /usr/bin/env python

import json
import signal

import socorro.storage.json_dump_storage as jds
import socorro.storage.crashstorage as cstore
import socorro.lib.util as sutil
import socorro.lib.iterator_worker_framework as iwf
import socorro.lib.config_manager as cm


#===============================================================================
def main (conf):
    logger = conf.logger
    conf.source.logger = logger
    crashStoragePoolForSource = cstore.CrashStoragePool(conf.source,
                                                    conf.source.storageClass)
    conf.destination.logger = logger
    crashStoragePoolForDest = cstore.CrashStoragePool(conf.destination,
                                                conf.destination.storageClass)
    signal.signal(signal.SIGTERM, iwf.respond_to_SIGTERM)
    signal.signal(signal.SIGHUP, iwf.respond_to_SIGTERM)

    #---------------------------------------------------------------------------
    def theIterator():
        """This infinite iterator will walk through the file system storage,
        yielding the ooids of every new entry in the filelsystem.  If there
        are no new entries, it yields None"""
        sourceStorage = crashStoragePoolForSource.crashStorage() # thread local
        while True:
            i = 0
            for i, ooid in enumerate(sourceStorage.newOoids()):
                yield ooid
            if i == 0:
                yield None
    #---------------------------------------------------------------------------

    #---------------------------------------------------------------------------
    def doSubmission(ooidTuple):
        logger.debug('received: %s', str(ooidTuple))
        try:
            sourceStorage = crashStoragePoolForSource.crashStorage()
            destStorage = crashStoragePoolForDest.crashStorage()
            ooid = ooidTuple[0]
            try:
                jsonContents = sourceStorage.get_meta(ooid)
            except ValueError:
                logger.warning('the json for %s is degenerate and cannot be '
                               'loaded  - saving empty json', ooid)
                jsonContents = {}
            dumpContents = sourceStorage.get_raw_dump(ooid)
            logger.debug('pushing %s to dest', ooid)
            result = destStorage.save_raw(ooid, jsonContents, dumpContents)
            if result == cstore.CrashStorageBase.ERROR:
                return iwf.FAILURE
            elif result == cstore.CrashStorageBase.RETRY:
                return iwf.RETRY
            sourceStorage.quickDelete(ooid)
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
                                           #- any of which will get translated
                                           # into a KeyboardInterrupt exception
    except KeyboardInterrupt:
        while True:
            try:
                submissionMill.stop()
                break
            except KeyboardInterrupt:
                logger.warning('We heard you the first time.  There is no need '
                               'for further keyboard or signal interrupts.  We '
                               'are waiting for the worker threads to stop.  If'
                               ' this app does not halt soon, you may have to '
                               'send SIGKILL (kill -9)')

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'crash_mover_app'
version = '2.1'
doc = """This app can move "new" crashes from one storage system
to another.  It is primarily used to move crashes from the collector's
local storage to HBase"""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.namespace('source', doc='the source')
rc.source.option(name='storageClass',
            doc='the fully qualified name of the source '
                'storage class',
            default='',
            from_string_converter = cm.class_converter)
rc.namespace('destination', doc='the destination')
rc.destination.option(name='storageClass',
            doc='the fully qualified name of the '
                'destination storage class',
            default='',
            from_string_converter = cm.class_converter)
rc.option(name='numberOfThreads',
          doc='the number of threads to use',
          default=4)
#-------------------------------------------------------------------------------
def get_required_config():
    return rc
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])

