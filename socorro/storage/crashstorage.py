import json

import socorro.lib.ooid as ooid
import socorro.lib.util as sutil
import socorro.lib.datetimeutil as sdt
import socorro.storage.json_dump_storage as jds
import socorro.storage.processed_dump_storage as pds
import socorro.lib.config_manager as cm
import socorro.storage.hbase_client as hbc
import socorro.collector.throttler as throt

import os
import stat
import datetime as dt
import time as tm
import re
import logging
import threading
import base64

logger = logging.getLogger("collector")

#-------------------------------------------------------------------------------
def benchmark(fn):
    def t(*args, **kwargs):
        before = tm.time()
        result = fn(*args, **kwargs)
        logger.info("%s for %s", tm.time() - before, str(fn))
        return result
    return t

#===============================================================================
class OoidNotFoundException(Exception):
    pass

#===============================================================================
class NotImplementedException(Exception):
    pass

#===============================================================================
class CrashStorageBase(cm.RequiredConfig):

    #---------------------------------------------------------------------------
    def __init__ (self, config):
        self.config = config
        self.hostname = os.uname()[1]
        try:
            if config.logger:
                self.logger = config.logger
            else:
                self.logger = logger
        except KeyError:
            self.logger = logger
        try:
            if config.benchmark:
                self.save = benchmark(self.save)
        except:
            pass
        self.exceptionsEligibleForRetry = []
    #---------------------------------------------------------------------------
    def close (self):
        pass
    #---------------------------------------------------------------------------
    def makeJsonDictFromForm (self, form, tm=tm):
        names = [name for name in form.keys() if name != self.config.dumpField]
        jsonDict = sutil.DotDict()
        for name in names:
            if type(form[name]) in (str, unicode):
                jsonDict[name] = form[name]
            else:
                jsonDict[name] = form[name].value
        jsonDict.timestamp = tm.time()
        return jsonDict
    #---------------------------------------------------------------------------
    NO_ACTION = 0
    OK = 1
    DISCARDED = 2
    ERROR = 3
    RETRY = 4
    FAILURES = (ERROR, RETRY)
    SUCCESSES = (NO_ACTION, OK, DISCARDED)
    #---------------------------------------------------------------------------
    def terminated (self, jsonData):
        return False
    #---------------------------------------------------------------------------
    def save_raw (self, ooid, jsonData, dump):
        return CrashStorageBase.NO_ACTION
    #---------------------------------------------------------------------------
    def save_processed (self, ooid, jsonData):
        return CrashStorageBase.NO_ACTION
    #---------------------------------------------------------------------------
    def get_meta (self, ooid):
        raise NotImplementedException("get_meta is not implemented")
    #---------------------------------------------------------------------------
    def get_raw_dump (self, ooid):
        raise NotImplementedException("get_raw_crash is not implemented")
    #---------------------------------------------------------------------------
    def get_raw_dump_base64(self,ooid):
        raise NotImplementedException("get_raw_dump_base64 is not implemented")
    #---------------------------------------------------------------------------
    def get_processed (self, ooid):
        raise NotImplementedException("get_processed is not implemented")
    #---------------------------------------------------------------------------
    def remove (self, ooid):
        raise NotImplementedException("remove is not implemented")
    #---------------------------------------------------------------------------
    def quickDelete (self, ooid):
        return self.remove(ooid)
    #---------------------------------------------------------------------------
    def ooidInStorage (self, ooid):
        return False
    #---------------------------------------------------------------------------
    def newOoids(self):
        raise StopIteration

#===============================================================================
class RawCrashStorageWithFallback(CrashStorageBase):
    required_config = _rc = cm.Namespace()
    _rc.namespace('primary',
                  doc='namespace for primary storage')
    _rc.primary.option('storageClass',
        doc='the class of the primary storage',
        default='',
        from_string_converter=cm.class_converter)
    _rc.namespace('fallback',
                  doc='namespace for fallback storage')
    _rc.fallback.option('storageClass',
        doc='the class of the fallback storage',
        default='',
        from_string_converter=cm.class_converter)
    #---------------------------------------------------------------------------
    def __init__ (self, config, hbaseClient=hbc, jsonDumpStorage=jds):
        super(RawCrashStorageWithFallback, self).__init__(config)
        self.config_assert(config)
        self.primaryStorage = config.primary.storageClass(config)
        self.fallbackStorage = config.fallback.storageClass(config)

    #---------------------------------------------------------------------------
    def save_raw (self, ooid, jsonData, dump, currentTimestamp):
        try:
            result = self.primaryStorage.save_raw(ooid,
                                                  jsonData,
                                                  dump,
                                                  currentTimestamp)
            if result in SUCCESSES:
                return result
        except Exception, x:
            sutil.reportExceptionAndContinue(self.logger)
        return self.fallbackStorage.save_raw(ooid,
                                             jsonData,
                                             dump,
                                             currentTimestamp)

#===============================================================================
class DualCrashStorage(CrashStorageBase):
    required_config = _rc = cm.Namespace()
    _rc.namespace('primary',
                  doc='namespace for primary storage')
    _rc.primary.option('storageClass',
        doc='the class of the primary storage',
        default='',
        from_string_converter=cm.class_converter)
    _rc.namespace('secondary',
                  doc='namespace for secondary storage')
    _rc.secondary.option('storageClass',
        doc='the class of the secondary storage',
        default='',
        from_string_converter=cm.class_converter)
    #---------------------------------------------------------------------------
    def __init__ (self, config, hbaseClient=hbc, jsonDumpStorage=jds):
        super(RawCrashStorageWithFallback, self).__init__(config)
        self.config_assert(config)
        self.primaryStorage = config.primary.storageClass(config)
        self.secondaryStorage = config.fallback.storageClass(config)

    #---------------------------------------------------------------------------
    def save_raw (self, ooid, jsonData, dump, currentTimestamp):
        try:
            primary_result = self.primaryStorage.save_raw(ooid,
                                                          jsonData,
                                                          dump,
                                                          currentTimestamp)
            secondary_result = self.secondaryStorage.save_raw(ooid,
                                                              jsonData,
                                                              dump,
                                                              currentTimestamp)
            if primary_result in FAILURES:
                return primary_result
            if secondary_result in FAILURES:
                return secondary_result
            return primary_result
        except Exception, x:
            sutil.reportExceptionAndContinue(self.logger)
        return CrashStorageBase.ERROR
    #---------------------------------------------------------------------------
    def save_processed (self, ooid, jsonData):
        try:
            primary_result = self.primaryStorage.save_processed(ooid,
                                                                jsonData)
            secondary_result = self.secondaryStorage.save_processed(ooid,
                                                                    jsonData)
            if primary_result in FAILURES:
                return primary_result
            if secondary_result in FAILURES:
                return secondary_result
            return primary_result
        except Exception, x:
            sutil.reportExceptionAndContinue(self.logger)
        return CrashStorageBase.ERROR
    #---------------------------------------------------------------------------
    def get_meta (self, ooid):
        return self.primaryStorage.get_meta(ooid)
    #---------------------------------------------------------------------------
    def get_raw_dump (self, ooid):
        return self.primaryStorage.get_raw_dump(ooid)
    #---------------------------------------------------------------------------
    def get_processed (self, ooid):
        return self.primaryStorage.get_processed(ooid)
    #---------------------------------------------------------------------------
    def remove (self, ooid):
        try:
            primary_result = self.primaryStorage.remove(ooid)
            secondary_result = self.secondaryStorage.remove(ooid)
            if primary_result in FAILURES:
                return primary_result
            if secondary_result in FAILURES:
                return secondary_result
            return primary_result
        except Exception, x:
            sutil.reportExceptionAndContinue(self.logger)
        return CrashStorageBase.ERROR
    #---------------------------------------------------------------------------
    def ooidInStorage (self, ooid):
        return (self.primaryStorage.ooidInStorage(ooid) and
                self.secondaryStorage.ooidInStorage(ooid))
    #---------------------------------------------------------------------------
    def newOoids(self):
        for x in self.primaryStorage.newOoids():
            yield x

#===============================================================================
class HBaseCrashStorage(CrashStorageBase):
    #---------------------------------------------------------------------------
    required_config = _rc = cm.Namespace()
    _rc.option(name='hbaseHost',
               doc='Hostname for HBase/Hadoop cluster. May be a VIP or '
                   'load balancer',
               default='localhost')
    _rc.option(name='hbasePort',
               doc='HBase port number',
               default=9090)
    _rc.option(name='hbaseTimeout',
               doc='timeout in milliseconds for an HBase connection',
               default=5000)

    #---------------------------------------------------------------------------
    def __init__ (self, config, hbaseClient=hbc, jsonDumpStorage=jds):
        super(HBaseCrashStorage, self).__init__(config)
        self.config_assert(config)
        self.logger.info('connecting to hbase')
        self.hbaseConnection = \
            hbaseClient.HBaseConnectionForCrashReports(config.hbaseHost,
                                                       config.hbasePort,
                                                       config.hbaseTimeout,
                                                       logger=self.logger)
        self.exceptionsEligibleForRetry = \
            self.hbaseConnection.hbaseThriftExceptions

    #---------------------------------------------------------------------------
    def close (self):
        self.hbaseConnection.close()

    #---------------------------------------------------------------------------
    def save_raw (self, ooid, jsonData, dump, currentTimestamp=None):
        try:
            jsonDataAsString = json.dumps(jsonData)
            self.hbaseConnection.put_json_dump(ooid, jsonData, dump,
                                               number_of_retries=2)
            self.logger.info('saved - %s', ooid)
            return CrashStorageBase.OK
        except self.exceptionsEligibleForRetry:
            sutil.reportExceptionAndContinue(self.logger)
            return CrashStorageBase.RETRY
        except Exception, x:
            sutil.reportExceptionAndContinue(self.logger)
            return CrashStorageBase.ERROR

    #---------------------------------------------------------------------------
    def save_processed (self, ooid, jsonData):
        self.hbaseConnection.put_processed_json(ooid, jsonData,
                                                number_of_retries=2)

    #---------------------------------------------------------------------------
    def get_meta (self, ooid):
        return self.hbaseConnection.get_json(ooid, number_of_retries=2)

    #---------------------------------------------------------------------------
    def get_raw_dump (self, ooid):
        return self.hbaseConnection.get_dump(ooid, number_of_retries=2)

    #---------------------------------------------------------------------------
    def get_raw_dump_base64 (self, ooid):
        dump = self.get_raw_dump(ooid, number_of_retries=2)
        return base64.b64encode(dump)

    #---------------------------------------------------------------------------
    def get_processed (self, ooid):
        return self.hbaseConnection.get_processed_json(ooid,
                                                       number_of_retries=2)

    #---------------------------------------------------------------------------
    def ooidInStorage (self, ooid):
        return \
            self.hbaseConnection.acknowledge_ooid_as_legacy_priority_job(ooid,
                                                            number_of_retries=2)

    #---------------------------------------------------------------------------
    def get_raw_dump_path(self, ooid, basePath):
        dumpPath = ("%s/%s.dump" % (basePath, ooid)).replace('//', '/')
        f = open(dumpPath, "w")
        try:
            dump = self.hbaseConnection.get_dump(ooid, number_of_retries=2)
            f.write(dump)
        finally:
            f.close()
        return dumpPath

    #---------------------------------------------------------------------------
    def cleanUpTempDumpStorage(self, ooid, basePath):
        dumpPath = ("%s/%s.dump" % (basePath, ooid)).replace('//', '/')
        os.unlink(dumpPath)

    #---------------------------------------------------------------------------
    def newOoids(self):
        return self.hbaseConnection.iterator_for_all_legacy_to_be_processed()

#===============================================================================
class RawFSCrashStorage(CrashStorageBase):
    #---------------------------------------------------------------------------
    required_config = _rc = cm.Namespace()
    _rc.option(name='localFS',
               doc='a file system root for crash storage',
               default='./')
    _rc.option(name='localFSDumpDirCount',
               doc='the max number of crashes that can be stored in any single '
               'directory',
               default=1000)
    _rc.option(name='localFSDumpGID',
               doc='the GID to use when storing crashes (leave blank for file '
               'system default)',
               default=None)
    _rc.option(name='localFSDumpPermissions',
               doc='the permissions to use in storing crashes (decimal)',
               default=(stat.S_IRGRP | stat.S_IWGRP | stat.S_IRUSR |
                       stat.S_IWUSR))
    _rc.option(name='localFSDirPermissions',
               doc='the permissions to use in creating directories (decimal)',
               default=(stat.S_IRGRP | stat.S_IXGRP | stat.S_IWGRP |
                        stat.S_IRUSR | stat.S_IXUSR | stat.S_IWUSR))

    #---------------------------------------------------------------------------
    def __init__ (self, config):
        super(RawFSCrashStorage, self).__init__(config)
        self.config_assert(config)
        self.localFS = jds.JsonDumpStorage(root = config.localFS,
                            maxDirectoryEntries = config.localFSDumpDirCount,
                            jsonSuffix = config.jsonFileSuffix,
                            dumpSuffix = config.dumpFileSuffix,
                            dumpGID = config.localFSDumpGID,
                            dumpPermissions = config.localFSDumpPermissions,
                            dirPermissions = config.localFSDirPermissions,
                            logger = config.logger
                            )

    #---------------------------------------------------------------------------
    def save_raw (self, ooid, jsonData, dump, currentTimestamp):
        try:
            if jsonData.legacy_processing == throt.LegacyThrottler.DISCARD:
                return CrashStorageBase.DISCARDED
        except KeyError:
            pass
        try:
            #jsonDataAsString = json.dumps(jsonData)
            jsonFileHandle, dumpFileHandle = \
                          self.localFS.newEntry(ooid,
                                                self.hostname,
                                                currentTimestamp)
            try:
                dumpFileHandle.write(dump)
                json.dump(jsonData, jsonFileHandle)
            finally:
                dumpFileHandle.close()
                jsonFileHandle.close()
            self.logger.info('saved - %s', ooid)
            return CrashStorageBase.OK
        except Exception, x:
            sutil.reportExceptionAndContinue(self.logger)
        return CrashStorageBase.ERROR

    #---------------------------------------------------------------------------
    def get_meta (self, ooid):
        jobPathname = self.localFS.getJson(ooid)
        jsonFile = open(jobPathname)
        try:
            jsonDocument = json.load(jsonFile)
        finally:
            jsonFile.close()
        return jsonDocument

    #---------------------------------------------------------------------------
    def get_raw_dump (self, ooid):
        jobPathname = self.localFS.getDump(ooid)
        dumpFile = open(jobPathname)
        try:
            dumpBinary = dumpFile.read()
        finally:
            dumpFile.close()
        return dumpBinary

    #---------------------------------------------------------------------------
    def newOoids(self):
        return self.localFS.destructiveDateWalk()

    #---------------------------------------------------------------------------
    def remove (self, ooid):
        self.localFS.remove(ooid)

    #---------------------------------------------------------------------------
    def quickDelete (self, ooid):
        self.localFS.quickDelete(ooid)

#===============================================================================
class LegacyCrashStorage(CrashStorageBase):
    #---------------------------------------------------------------------------
    required_config = _rc = cm.Namespace()
    _rc.option(name='storageRoot',
               doc='a file system root for crash storage',
               default='./std/')
    _rc.option(name='deferredStorageRoot',
               doc='a file system root for crash storage',
               default='./def/')
    _rc.option(name='processedStorageRoot',
               doc='a file system root for crash storage',
               default='./pro/')
    _rc.option(name='dumpDirCount',
               doc='the max number of crashes that can be stored in any single '
               'directory',
               default=1000)
    _rc.option(name='dumpGID',
               doc='the GID to use when storing crashes (leave blank for file '
               'system default)',
               default=None)
    _rc.option(name='dumpPermissions',
               doc='the permissions to use in storing crashes (decimal)',
               default=(stat.S_IRGRP | stat.S_IWGRP | stat.S_IRUSR |
                        stat.S_IWUSR))
    _rc.option(name='dirPermissions',
               doc='the permissions to use in creating directories (decimal)',
               default=(stat.S_IRGRP | stat.S_IXGRP | stat.S_IWGRP |
                        stat.S_IRUSR | stat.S_IXUSR | stat.S_IWUSR))
    _rc.option(name='jsonFileSuffix',
               doc='the file extention for json files',
               default='json')
    _rc.option(name='dumpFileSuffix',
               doc='the file extention for dump files',
               default='dump')

    #---------------------------------------------------------------------------
    def __init__ (self, config):
        super(LegacyCrashStorage, self).__init__(config)
        self.config_assert(config)
        #self.throttler = throt.LegacyThrottler(config)
        self.standard_storage = \
            jds.JsonDumpStorage(root = config.storageRoot,
                                maxDirectoryEntries = config.dumpDirCount,
                                jsonSuffix = config.jsonFileSuffix,
                                dumpSuffix = config.dumpFileSuffix,
                                dumpGID = config.dumpGID,
                                dumpPermissions = config.dumpPermissions,
                                dirPermissions = config.dirPermissions,
                                )
        self.deferred_storage = \
            jds.JsonDumpStorage(root = config.deferredStorageRoot,
                                maxDirectoryEntries = config.dumpDirCount,
                                jsonSuffix = config.jsonFileSuffix,
                                dumpSuffix = config.dumpFileSuffix,
                                dumpGID = config.dumpGID,
                                dumpPermissions = config.dumpPermissions,
                                dirPermissions = config.dirPermissions,
                                )
        self.processed_storage = \
            pds.ProcessedDumpStorage(root = config.processedStorageRoot,
                                maxDirectoryEntries = config.dumpDirCount,
                                jsonSuffix = config.jsonFileSuffix,
                                dumpSuffix = config.dumpFileSuffix,
                                dumpGID = config.dumpGID,
                                dumpPermissions = config.dumpPermissions,
                                dirPermissions = config.dirPermissions,
                                )
        self.hostname = os.uname()[1]

    #---------------------------------------------------------------------------
    def save_raw (self, ooid, jsonData, dump, currentTimestamp):
        try:
            try:
                throttleAction = jsonData.legacy_processing
            except KeyError:
                throttleAction = throt.LegacyThrottler.ACCEPT
            if throttleAction == throt.LegacyThrottler.DISCARD:
                self.logger.debug("discarding %s %s", jsonData.ProductName,
                                  jsonData.Version)
                return CrashStorageBase.DISCARDED
            elif throttleAction == throt.LegacyThrottler.DEFER:
                try:
                    self.logger.debug("deferring %s: %s %s",
                                      ooid,
                                      jsonData.ProductName,
                                      jsonData.Version)
                except KeyError:
                    self.logger.debug("deferring %s: product or version "
                                      "missing", ooid)
                fileSystemStorage = self.deferred_storage
            else:
                try:
                    self.logger.debug("not throttled %s: %s %s",
                                      ooid,
                                      jsonData.ProductName,
                                      jsonData.Version)
                except KeyError:
                    self.logger.debug("not throttled %s: product or version "
                                      "missing", ooid)
                fileSystemStorage = self.standard_storage

            date_processed = sdt.datetimeFromISOdateString(
                                                   jsonData.submitted_timestamp)
            jsonFileHandle, dumpFileHandle = \
                          fileSystemStorage.newEntry(ooid, self.hostname,
                                                     date_processed)
            try:
                dumpFileHandle.write(dump)
                json.dump(jsonData, jsonFileHandle)
            finally:
                dumpFileHandle.close()
                jsonFileHandle.close()

            return CrashStorageBase.OK
        except:
            sutil.reportExceptionAndContinue(self.logger)
            return CrashStorageBase.ERROR

    #---------------------------------------------------------------------------
    def get_meta(self, ooid):
        raw_json_pathname = self.get_raw_json_path(ooid)
        with open(raw_json_pathname) as j:
            raw_json = json.load(j)
        return raw_json

    #---------------------------------------------------------------------------
    def get_raw_json_path(self, ooid):
        try:
            raw_json_pathname = self.standard_storage.getJson(ooid)
        except (OSError, IOError):
            try:
                raw_json_pathname = self.deferred_storage.getJson(ooid)
            except (OSError, IOError):
                raise OoidNotFoundException("%s cannot be found in standard or "
                                            "deferred storage" % ooid)
        return raw_json_pathname

    #---------------------------------------------------------------------------
    def get_raw_dump (self, ooid):
        dump_pathname = self.get_raw_dump_path(ooid)
        with open(dump_pathname) as d:
            dump = d.read()
        return dump

    #---------------------------------------------------------------------------
    def get_raw_dump_path(self, ooid, ignoredBasePath):
        try:
            dump_pathname = self.standard_storage.getDump(ooid)
        except (OSError, IOError):
            try:
                dump_pathname = self.deferred_storage.getDump(ooid)
            except (OSError, IOError):
                raise OoidNotFoundException("%s cannot be found in standard or "
                                            "deferred storage" % ooid)
        return dump_pathname

    #---------------------------------------------------------------------------
    def cleanUpTempDumpStorage(self, ooid, ignoredBasePath):
        """not necessary in this case, we didn't have to write the
        dump to a tempfile"""
        pass

    #---------------------------------------------------------------------------
    def save_processed (self, ooid, jsonData):
        try:
            self.processed_storage.putDumpToFile(ooid, jsonData)
        except Exception:
            self.logger.error('Error saving %s', ooid)
            sutil.reportExceptionAndContinue(self.logger)
            return CrashStorageBase.ERROR
        return CrashStorageBase.OK

    #---------------------------------------------------------------------------
    def get_processed (self, ooid):
        try:
            return self.processed_storage.getDumpFromFile(ooid)
        except Exception:
            self.logger.error('Error fetching %s', ooid)
            sutil.reportExceptionAndContinue(self.logger)
            raise

    #---------------------------------------------------------------------------
    def ooidInStorage(self, ooid):
        try:
            ooidPath = self.standard_storage.getJson(ooid)
            self.standard_storage.markAsSeen(ooid)
        except (OSError, IOError):
            try:
                ooidPath = self.deferred_storage.getJson(ooid)
                self.deferred_storage.markAsSeen(ooid)
            except (OSError, IOError):
                return False
        return True

    #---------------------------------------------------------------------------
    def newOoids(self):
        return self.standard_storage.destructiveDateWalk()


#===============================================================================
class CrashStoragePool(dict):
    #---------------------------------------------------------------------------
    def __init__(self, config, storageClass=HBaseCrashStorage):
        super(CrashStoragePool, self).__init__()
        self.config = config
        self.logger = config.logger
        self.storageClass = storageClass
        self.logger.debug("creating crashStorePool")

    #---------------------------------------------------------------------------
    def crashStorage(self, name=None):
        """Like connecionCursorPairNoTest, but test that the specified
        connection actually works"""
        if name is None:
            name = threading.currentThread().getName()
        if name not in self:
            self.logger.debug("creating crashStore for %s", name)
            self[name] = c = self.storageClass(self.config)
            return c
        return self[name]

    #---------------------------------------------------------------------------
    def cleanup (self):
        for name, crashStore in self.iteritems():
            try:
                crashStore.close()
                self.logger.debug("crashStore for %s closed", name)
            except:
                sutil.reportExceptionAndContinue(self.logger)

    #---------------------------------------------------------------------------
    def remove (self, name):
        crashStorage = self[name]
        crashStorage.close()
        del self[name]