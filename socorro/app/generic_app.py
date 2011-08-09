#! /usr/bin/env python

import logging
import logging.handlers

import socorro.lib.config_manager as cm
import socorro.lib.logging_config as lc


#------------------------------------------------------------------------------
def main(application_class=None):
    if isinstance(application_class, str):
        application_class = cm.class_converter(application_class)
    try:
        application_name = application_class.app_name
    except AttributeError:
        application_name = 'socorro_unknown_app'
    try:
        application_version = application_class.version
    except AttributeError:
        application_version = ''
    try:
        application_doc = application_class.doc
    except AttributeError:
        application_doc = ''

    app_definition = cm.Namespace()
    app_definition.option('_application',
                          doc='the fully qualified module or '
                              'class of the application',
                          default=application_class,
                          from_string_converter=cm.class_converter
                         )
    definition_list = [app_definition,
                       lc.required_config(application_name),
                      ]

    config_manager = cm.ConfigurationManager(definition_list,
                                             options_banned_from_help=[])
    config = config_manager.get_config()

    try:
        app_name = config._application.app_name
    except AttributeError:
        app_name = 'unknown_app'

    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    lc.setupLoggingHandlers(logger, config)
    config.logger = logger

    config_manager.log_config(logger)

    try:
        application_main = application_class.main
    except AttributeError:
        logger.critical("the application class has no main function")
    else:
        application_main(config)
    finally:
        logger.info("done.")

#==============================================================================
if __name__ == '__main__':
    main()
