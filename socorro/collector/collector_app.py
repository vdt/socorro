#! /usr/bin/env python

import web

import socorro.storage.crashstorage as cstore
import socorro.webapi.class_partial as cpart
import socorro.webapi.service_discovery as wsd

#-------------------------------------------------------------------------------
def main(config):
    logger = config.logger
    web.config.debug = False
    web.webapi.internalerror = web.debugerror

    crashStoragePool = cstore.CrashStoragePool(config,
                                               config.storageClass)
    config.crashStoragePool = crashStoragePool
    config.legacyThrottler = None if not config.throttlerClass else \
                             config.throttlerClass(config)

    urls = wsd.get_services(config, 'socorro/collector')
    logger.info(str(urls))

    if config.mod_wsgiInstallation:
        logger.info('This is an Apache mod_wsgi installation')
        application = web.application(urls, globals()).wsgifunc()
    else:
        logger.info('This is a stand alone installation without mod_wsgi')
        import socorro.webapi.webapp as sweb
        app =  sweb.StandAloneWebApplication(config.serverIPAddress,
                                             config.serverPort,
                                             urls,
                                             globals())
        try:
            app.run()
        finally:
            crashStoragePool.cleanup()

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'collector'
version = '3.0'
doc = """The collector"""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
#rc.option('collectorClass',
    #doc='the class of the collector',
    #default='socorro.collector.wsgicollector.Collector',
    #from_string_converter=cm.class_converter)
rc.option('mod_wsgiInstallation',
    doc='True or False, this app is installed under mod_wsgi',
    default=False,
    from_string_converter=cm.boolean_converter)
rc.option('serverIPAddress',
    doc='the IP address from which to accept submissions if not installed '
        'under mod_wsgi',
    default='127.0.0.1',
    short_form='h')
rc.option('serverPort',
    doc='the port to listen to for submissions if not installed under mod_wsgi',
    default=8882,
    short_form='p')
rc.option('neverDiscard',
    doc='if True, ignore the "throttleable" protocol',
    default=True,
    from_string_converter=cm.boolean_converter)
rc.option('minimalVersionForUnderstandingRefusal',
    doc='dict of product version pairs that indicate the minimal version '
        'number for products that understand refusal',
    default="{ 'Firefox': '3.5.4' }",
    from_string_converter=eval)
rc.option('benchmark',
    doc='collect benchmarking information',
    default=False,
    from_string_converter=cm.boolean_converter)
rc.option('throttlerClass',
          doc='the class of the throttler',
          default='socorro.collector.throttler.LegacyThrottler',
          from_string_converter=cm.class_converter)

#-------------------------------------------------------------------------------
def get_required_config():
    n = cm.Namespace()
    n.update(rc)
    service_classes = wsd.discover_services('socorro/collector')
    for a_service_class in service_classes:
        try:
            n.update(a_service_class.get_required_config())
        except AttributeError:
            pass
    return n

#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])