#! /usr/bin/env python

import ConfigParser as cp
import os.path
import json

import sys
import logging
import logging.handlers

import socorro.lib.config_manager as cm
import socorro.lib.logging_config as lc
import socorro.lib.util as sutil

def main(application_class):
    if isinstance(application_class, str):
        application_class = cm.class_converter(application_class)
    try:
        application_name = application_class.app_name
    except AttributeError:
        application_name = 'Socorro Unknown App'
    try:
        application_version = application_class.version
    except AttributeError:
        application_version = ''
    try:
        application_doc = application_class.doc
    except AttributeError:
        application_doc = ''
    application_main = application_class.main

    app_definition = cm.Namespace()
    app_definition.option('_application',
                          doc='the fully qualified module or '
                              'class of the application',
                          default=application_class,
                          from_string_converter=cm.class_converter
                         )
    definition_list = [ app_definition,
                        lc.required_config(application_name),
                      ]

    config_manager = cm.ConfigurationManager(definition_list,
                                        application_name=application_name,
                                        application_version=application_version,
                                        application_doc=application_doc,
                                             )
    config = config_manager.get_config()

    logger = logging.getLogger(config._application.app_name)
    logger.setLevel(logging.DEBUG)
    lc.setupLoggingHandlers(logger, config)
    config.logger = logger

    config_manager.log_config(logger)

    try:
        application_main(config)
    finally:
        logger.info("done.")

if __name__ == '__main__':
    main()
