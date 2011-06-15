import web
import datetime as dt
import urllib2 as u2
import logging

logger = logging.getLogger("collector")

import socorro.lib.datetimeutil as sdt
import socorro.lib.util as util
import socorro.lib.datetimeutil as dtutil
import socorro.lib.util as sutil
import socorro.lib.ooid as sooid
import socorro.storage.crashstorage as cstore
import socorro.lib.config_manager as cm

#===============================================================================
class CollectorService(cm.RequiredConfig):
    #---------------------------------------------------------------------------
    # static data
    required_config = _rc = cm.Namespace()
    _rc.option('storageClass',
            doc='the fully qualified name of the crash '
                'storage class',
            default='socorro.storage.crashstorage.HBaseCrashStorage',
            from_string_converter = cm.class_converter),
    _rc.option('dumpField',
            doc='the name of the POST field that has the crash dump',
            default='upload_file_minidump'),
    _rc.option('dumpIDPrefix',
            doc='a prefix to add to the returned OOID of the crash dump',
            default='bp-')

    #---------------------------------------------------------------------------
    uri = '/submit'

    #---------------------------------------------------------------------------
    def __init__(self, config):
        self.config = config
        self.logger = self.config.setdefault('logger', logger)
        #self.logger.debug('Collector __init__')
        self.legacyThrottler = config.legacyThrottler # save 1 level of lookup
        self.dumpIDPrefix = config.dumpIDPrefix # save 1 level of lookup

    #---------------------------------------------------------------------------
    def POST(self, *args):
        crashStorage = self.config.crashStoragePool.crashStorage()
        theform = web.input()

        dump = theform[self.config.dumpField]
        #currentTimestamp = dt.datetime.now(utctz)
        currentTimestamp = dt.datetime.now()
        jsonDataDictionary = crashStorage.makeJsonDictFromForm(theform)
        jsonDataDictionary.submitted_timestamp = currentTimestamp.isoformat()
        #for future use when we start sunsetting products
        #if crashStorage.terminated(jsonDataDictionary):
            #return "Terminated=%s" % jsonDataDictionary.Version
        ooid = sooid.createNewOoid(currentTimestamp)
        if self.legacyThrottler:
            jsonDataDictionary.legacy_processing = \
                              self.legacyThrottler.throttle(jsonDataDictionary)
        self.logger.info('%s received', ooid)
        result = crashStorage.save_raw(ooid,
                                       jsonDataDictionary,
                                       dump,
                                       currentTimestamp)
        if result == cstore.CrashStorageBase.DISCARDED:
            return "Discarded=1\n"
        elif result == cstore.CrashStorageBase.ERROR:
            raise Exception("CrashStorageSystem ERROR")
        return "CrashID=%s%s\n" % (self.dumpIDPrefix, ooid)

