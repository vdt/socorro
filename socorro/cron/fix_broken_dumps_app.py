#!/usr/bin/python

import time
import sys
import subprocess
import os
import cPickle

import psycopg2
import psycopg2.extras

import socorro.lib.util
import socorro.storage.hbase_client as hbaseClient
import socorro.database.database as sdb

from datetime import datetime, timedelta

def fetchOoids(configContext, logger, query):
  try:
    databaseDSN = "host=%(databaseHost)s dbname=%(databaseName)s user=%(databaseUserName)s password=%(databasePassword)s" % configContext
    conn = psycopg2.connect(databaseDSN)
    cur = conn.cursor()
  except:
    socorro.lib.util.reportExceptionAndAbort(logger)

  last_date_processed = get_last_run_date(configContext)

  rows = []
  try:
    before = time.time()
    logger.debug('last_date_processed used for query: %s' % last_date_processed)
    cur.execute(query % last_date_processed)
    rows = cur.fetchall()
    conn.commit()
  except:
    socorro.lib.util.reportExceptionAndAbort(logger)

  return rows, last_date_processed

def fix(configContext, logger, query, fixer):
  rows, last_date_processed = fetchOoids(configContext, logger, query)
  hbc = hbaseClient.HBaseConnectionForCrashReports(configContext.hbaseHost, configContext.hbasePort, configContext.hbaseTimeout, logger=logger)
  for row in rows:
    try:
      ooid, last_date_processed = row
      logger.info('fixing ooid: %s' % ooid)
      dump = hbc.get_dump(ooid)
      fname = '/dev/shm/%s.dump' % ooid
      with open(fname, 'wb') as orig_dump_file:
        orig_dump_file.write(dump)
      logger.debug('wrote dump file: %s' % fname)
      logger.debug('fixed dump file: %s' % fname)
      subprocess.check_call([fixer, fname])
      logger.debug('fixer: %s' % fixer)
      with open(fname, 'rb') as fixed_dump_file:
        fixed_dump = fixed_dump_file.read()
        hbc.put_fixed_dump(ooid, fixed_dump, add_to_unprocessed_queue = True, submitted_timestamp = datetime.now())
      logger.debug('put fixed dump file into hbase: %s' % fname)
      os.unlink(fname)
      logger.debug('removed dump file: %s' % fname)
    except:
      socorro.lib.util.reportExceptionAndContinue(logger)

  return last_date_processed

def get_last_run_date(config):
  try:
    with open(config.persistentBrokenDumpPathname, 'r') as f:
      return cPickle.load(f)
  except IOError:
    return datetime.now() - timedelta(days=config.daysIntoPast)

def save_last_run_date(config, date):
  with open(config.persistentBrokenDumpPathname, 'w') as f:
    return cPickle.dump(date, f)

#-------------------------------------------------------------------------------
def main(config):
  last_date_processed = fix(config,
                            config.logger,
                            config.brokenFirefoxLinuxQuery,
                            config.brokenFirefoxLinuxFixer)
  last_date_processed = fix(config,
                            config.logger,
                            config.brokenFennecQuery,
                            config.brokenFennecFixer)

  save_last_run_date(config, last_date_processed)
  config.logger.debug('stored last_date_processed: %s' % last_date_processed)

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'fix_broken_dumps'
version = '1.1'
doc = """This app is a cron that fetches build info from the ftp site."""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('brokenFirefoxLinuxQuery',
          doc='sql query that finds the broken dumps',
          default="""
    SELECT uuid,date_processed FROM reports WHERE product = 'Firefox'
      AND (version = '4.0b11' OR version = '4.0b12')
      AND os_name = 'Linux'
      AND date_processed > '%s'
      AND date_processed < (now() - INTERVAL '30 minutes')
      ORDER BY date_processed
""",)
rc.option('brokenFirefoxLinuxFixer',
          doc='pathname of a dump healing program',
          default='./minidump_hack-firefox_linux')
rc.option('brokenFennecQuery',
          doc='sql query that finds ill Fennecs',
          default="""
    SELECT uuid,date_processed FROM reports WHERE product = 'Fennec'
      AND version = '4.0b5'
      AND date_processed > '%s'
      AND date_processed < (now() - INTERVAL '30 minutes')
      ORDER BY date_processed
""")
rc.option('brokenFennecFixer',
          doc='pathname of a fennec healing program',
          default='./minidump_hack-fennec')
rc.option('persistentBrokenDumpPathname',
          doc='a pathname to a file system location where this script can '
              'store persistent data',
          default='./fixbrokendumps.pickle')
rc.option('daysIntoPast',
          doc='number of days to look into the past for broken crashes '
              '(0 - use last run time)',
          default=30)
rc.option(name='hbaseHost',
          doc='Hostname for HBase/Hadoop cluster. May be a VIP or '
              'load balancer',
          default='localhost')
rc.option(name='hbasePort',
          doc='HBase port number',
          default=9090)
rc.option(name='hbaseTimeout',
          doc='timeout in milliseconds for an HBase connection',
          default=5000)
#-------------------------------------------------------------------------------
def get_required_config():
    n = cm.Namespace()
    n.update(rc)
    n.update(sdb.get_required_config())
    return n
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])