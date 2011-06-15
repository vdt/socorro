#! /usr/bin/env python
"""
signatures.py calls a stored procedure used for updating the first appearance
of signature information, as well as updating signature_productdims.

This script is expected to be run once per hour, and will be called
from scripts/startSignatures.py.
"""

from datetime import datetime
from datetime import timedelta

import socorro.database.database as sdb
import socorro.lib.util as util

hours_back = 3

#-------------------------------------------------------------------------------
def update_signatures(config):
    logger = config.logger
    db = sdb.Database(config)
    databaseConnection = db.connection()
    try:
        databaseCursor = databaseConnection.cursor()
        databaseCursor.execute("""
        SELECT max(first_report) FROM signature_build
        """);
        last_run = databaseCursor.fetchone()[0]
        now = datetime.now()
        if last_run is None:
            last_run = now
        delta = now - last_run
        total_seconds = delta.days * 86400 + delta.seconds
        total_hours = total_seconds / 3600 - hours_back
        logger.info("total_hours: %s" % total_hours)
        for hour in xrange(total_hours):
            hour = int(hour) + 1
            timestamp = now - timedelta(hours=hour)
            databaseCursor.execute("""
                --- time, hours_back, hours_window
                SELECT update_signature_matviews('%s', '%s', 2)
                """ % (timestamp, hours_back))
            databaseConnection.commit()
    finally:
        databaseConnection.close()

#-------------------------------------------------------------------------------
main = update_signatures # alternate name for use by app infrastructure

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'signatures'
version = '1.5'
doc = """This cron app will keep the server status table updated"""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('start_day',
          doc='The number of days before today that should serve as the start '
          'date for the query window.',
          default=1)
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