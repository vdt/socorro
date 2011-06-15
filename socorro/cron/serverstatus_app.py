#! /usr/bin/env python

"""
This script is what populates the aggregate server_status table for jobs and processors.

It provides up to date reports on the status of Socorro servers

The following fields are updated in server_status table:
  id - primary key
  date_recently_completed - timestamp for job most recently processed in jobs table
  date_oldest_job_queued - timestamp for the oldest job which is incomplete
  avg_process_sec - Average number of seconds (float) for jobs completed since last run
                    or 0.0 in edge case where no jobs have been processed
  avg_wait_sec- Average number of seconds (float) for jobs completed since last run
                or 0.0 in edge case where no jobs have been processed
  waiting_job_count - Number of jobs incomplete in queue
  processors_count - Number of processors running to process jobs
  date_created - timestamp for this record being udpated
"""
import time
import datetime

import psycopg2
import psycopg2.extras

import socorro.lib.util
import socorro.database.database as sdb

#-------------------------------------------------------------------------------
def update(config, logger):
    serverStatsSql = """INSERT INTO server_status
  (date_recently_completed, date_oldest_job_queued, avg_process_sec,
   avg_wait_sec, waiting_job_count, processors_count, date_created)
 SELECT

  (SELECT MAX(jobs.completeddatetime)
   FROM jobs WHERE jobs.completeddatetime IS NOT NULL) AS date_recently_completed,

  (SELECT jobs.queueddatetime
   FROM jobs WHERE jobs.completeddatetime IS NULL
   ORDER BY jobs.queueddatetime LIMIT 1) AS date_oldest_job_queued,

  (SELECT COALESCE (
     EXTRACT (EPOCH FROM avg(jobs.completeddatetime - jobs.starteddatetime)),
     0) FROM jobs
   WHERE jobs.completeddatetime > %s) AS avg_process_sec ,

  (SELECT COALESCE (
     EXTRACT (EPOCH FROM avg(jobs.completeddatetime - jobs.queueddatetime)),
     0) FROM jobs
   WHERE jobs.completeddatetime > %s) AS avg_wait_sec,

  (SELECT COUNT(jobs.id)
   FROM jobs WHERE jobs.completeddatetime IS NULL) AS waiting_job_count,

  (SELECT count(processors.id)
   FROM processors ) AS processors_count,

  CURRENT_TIMESTAMP AS date_created;"""


    serverStatsLastUpdSql = """ /* serverstatus.lastUpd */
SELECT id, date_recently_completed, date_oldest_job_queued, avg_process_sec,
        avg_wait_sec, waiting_job_count, processors_count, date_created
FROM server_status ORDER BY date_created DESC LIMIT 1;
"""

    try:
        db = sdb.Database(config)
        conn = db.connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    except:
        socorro.lib.util.reportExceptionAndAbort(logger)

    startTime = datetime.datetime.now()
    startTime -= config.processingInterval
    timeInserting = 0
    if config.debug:
        logger.debug("Creating stats from now back until %s" % startTime)
    try:
        before = time.time()
        cur.execute(serverStatsSql, (startTime, startTime))
        timeInserting = time.time() - before;
        cur.execute(serverStatsLastUpdSql)
        row = cur.fetchone()
        conn.commit()
    except:
        socorro.lib.util.reportExceptionAndAbort(logger)

    if row:
        logger.info("Server Status id=%d was updated at %s -- recent=%s, oldest=%s, avg_proc=%s, avg_wait=%s, waiting=%s, procs=%s -- in %s seconds" % (row['id'], row['date_created'], row['date_recently_completed'], row['date_oldest_job_queued'], row['avg_process_sec'], row['avg_wait_sec'], row['waiting_job_count'], row['processors_count'], timeInserting))
    else:
        msg = "Unable to read from server_status table after attempting to insert a new record"
        logger.warn(msg)
        raise Exception(msg)

#-------------------------------------------------------------------------------
def main(config):
    update(config, config.logger)

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'server_status'
version = '1.5'
doc = """This cron app will keep the server status table updated"""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('debug',
          doc='do debug output and routines',
          default=False,
          short_form='D',
          from_string_converter=cm.boolean_converter)
rc.option('initMode',
          doc='Use this the first time you run the script.',
          default=False,
          short_form='I',
          from_string_converter=cm.boolean_converter)
rc.option('processingInterval',
          'how often to process reports (HHH:MM:SS)',
          default='00:05:00',
          from_string_converter=cm.timedelta_converter)
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