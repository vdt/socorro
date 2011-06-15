#! /usr/bin/env python

import logging
from datetime import datetime
from datetime import timedelta

logger = logging.getLogger("duplicates")

import socorro.database.database as sdb
import socorro.lib.util as util

#-------------------------------------------------------------------------------
def find_duplicates(config):
    config.logger = logger
    databaseConnectionPool = sdb.DatabaseConnectionPool(config, logger)
    sql = "SELECT update_reports_duplicates('%s', '%s')"
    try:
        connection, cursor= databaseConnectionPool.connectionCursorPair()

        startTime = datetime.now() - timedelta(hours=3)
        endTime = startTime + timedelta(hours=1)
        cursor.execute(sql % (startTime, endTime))
        connection.commit()

        startTime += timedelta(minutes=30)
        endTime = startTime + timedelta(hours=1)
        cursor.execute(sql % (startTime, endTime))
        connection.commit()
    finally:
        databaseConnectionPool.cleanup()

main = find_duplicates

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'duplicates'
version = '0.1'
doc = """This app runs the 'update_reports_duplicates' stored procedure"""
#-------------------------------------------------------------------------------
def get_required_config():
    n = cm.Namespace()
    n.update(sdb.get_required_config())
    return n
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])