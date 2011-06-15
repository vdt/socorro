#!/usr/bin/python

import sys
import os.path
import os
import itertools
import web

import socorro.lib.config_manager as cm
import socorro.database.database as sdb
import socorro.webapi.service_discovery as wsd

#-------------------------------------------------------------------------------
def main(config):
    logger = config.logger
    web.webapi.internalerror = web.debugerror

    urls = wsd.get_services(config, 'socorro/services')
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
        app.run()

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'middleware'
version = '2.0'
doc = """provides a REST api for getting data from Socorro."""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('mod_wsgiInstallation',
          doc='True or False, this app is installed under Apache mod_wsgi',
          default=False,
          from_string_converter=cm.boolean_converter)
rc.option('serverIPAddress',
    doc='the IP address from which to accept submissions if not installed '
        'under mod_wsgi',
    default='127.0.0.1',
    short_form='h')
rc.option('serverPort',
    doc='the port to listen to for submissions if not installed under mod_wsgi',
    default=8880,
    short_form='p')
#-------------------------------------------------------------------------------
def get_required_config():
    n = cm.Namespace()
    n.update(rc)
    service_classes = wsd.discover_services('socorro/services')
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