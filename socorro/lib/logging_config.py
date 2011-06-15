import socorro.lib.config_manager as cm

import logging

#===============================================================================
# logging routines

def required_config (application_name=''):
    lc = cm.Namespace()
    lc.option('syslogHost',
              doc='syslog hostname',
              default='localhost')
    lc.option('syslogPort',
              doc='syslog port',
              default=514)
    lc.option('syslogFacilityString',
              doc='syslog facility string ("user", "local0", etc)',
              default='user')
    lc.option('syslogLineFormatString',
              doc='python logging system format for syslog entries',
              default='%s (pid %%(process)d): '
                      '%%(asctime)s %%(levelname)s - %%(threadName)s - '
                      '%%(message)s' % application_name)
    lc.option('syslogErrorLoggingLevel',
              doc='logging level for the log file (10 - DEBUG, 20 '
                  '- INFO, 30 - WARNING, 40 - ERROR, 50 - CRITICAL)',
              default=40)
    lc.option('stderrLineFormatString',
              doc='python logging system format for logging to stderr',
              default ='%(asctime)s %(levelname)s - %(threadName)s - '
                       '%(message)s')
    lc.option('stderrErrorLoggingLevel',
              doc='logging level for the logging to stderr (10 - '
                  'DEBUG, 20 - INFO, 30 - WARNING, 40 - ERROR, 50 - CRITICAL)',
              default=10)
    return lc

#-------------------------------------------------------------------------------
def setupLoggingHandlers(logger, config):
    stderrLog = logging.StreamHandler()
    stderrLog.setLevel(config.stderrErrorLoggingLevel)
    stderrLogFormatter = logging.Formatter(config.stderrLineFormatString)
    stderrLog.setFormatter(stderrLogFormatter)
    logger.addHandler(stderrLog)

    syslog = logging.handlers.SysLogHandler(facility=
                                            config.syslogFacilityString)
    syslog.setLevel(config.syslogErrorLoggingLevel)
    syslogFormatter = logging.Formatter(config.syslogLineFormatString)
    syslog.setFormatter(syslogFormatter)
    logger.addHandler(syslog)
