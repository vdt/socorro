try:
    import json
except ImportError:
    import simplejson as json
import logging
import web

import socorro.lib.util as util
import socorro.database.database as db
import socorro.storage.crashstorage as cs
import socorro.lib.config_manager as cm
import socorro.database.database as sdb

logger = logging.getLogger("webapi")

#-------------------------------------------------------------------------------
def typeConversion (listOfTypeConverters, listOfValuesToConvert):
    return (t(v) for t, v in zip(listOfTypeConverters, listOfValuesToConvert))

#===============================================================================
class Unimplemented(Exception):
    pass

#===============================================================================
class JsonServiceBase (cm.RequiredConfig):
    #---------------------------------------------------------------------------
    # static data
    required_config = _rc = cm.Namespace()
    _rc.update(sdb.get_required_config())
    _rc.option(name='storageClass',
               doc='the fully qualified name of the crash '
                   'storage class',
               default='socorro.storage.crashstorage.HBaseCrashStorage',
               from_string_converter = cm.class_converter)
    #---------------------------------------------------------------------------
    def __init__(self, config):
        try:
            self.context = config
            self.database = db.Database(config)
            self.crashStoragePool = cs.CrashStoragePool(config,
                                                        config.storageClass)
        except (AttributeError, KeyError):
            util.reportExceptionAndContinue(logger)

    #---------------------------------------------------------------------------
    def GET(self, *args):
        try:
            result = self.get(*args)
            if type(result) is tuple:
                web.header('Content-Type', result[1])
                return result[0]
            return json.dumps(result)
        except Exception, x:
            stringLogger = util.StringLogger()
            util.reportExceptionAndContinue(stringLogger)
            try:
                util.reportExceptionAndContinue(self.context.logger)
            except (AttributeError, KeyError):
                pass
            raise Exception(stringLogger.getMessages())

    #---------------------------------------------------------------------------
    def get(self, *args):
        raise Unimplemented("the GET function has not been implemented for %s"
                            % args)

    #---------------------------------------------------------------------------
    def POST(self, *args):
        try:
            result = self.post()
            if type(result) is tuple:
                web.header('Content-Type', result[1])
                return result[0]
            return json.dumps(result)
        except web.HTTPError:
            raise
        except Exception:
            util.reportExceptionAndContinue(self.context.logger)
            raise

    #---------------------------------------------------------------------------
    def post(self, *args):
        raise Unimplemented("the POST function has not been implemented.")
