#! /usr/bin/env python

import datetime as dt

import socorro.database.schema as sch
import socorro.database.database as sdb
import socorro.lib.util as sutil

#-------------------------------------------------------------------------------
def createPartitions(config, logger):
    """
    Create a set of partitions for all the tables known to be efficient when
    they are created prior to being needed.  see the list
    databaseObjectClassListForWeeklyParitions in the module
    socorro.database.schema
    """
    endDate = config.startDate + dt.timedelta(config.weeksIntoFuture * 7)
    database_connection_pool = sdb.DatabaseConnectionPool(config)
    db_connection = database_connection_pool.connection()
    db_cursor = db_connection.cursor()
    try:
        for db_obj_class in sch.databaseObjectClassListForWeeklyPartitions:
            week_iterator = sch.mondayPairsIteratorFactory(config.startDate,
                                                           endDate)
            db_object = db_obj_class(logger=logger)
            db_object.createPartitions(db_cursor, week_iterator)
            db_connection.commit()
    except:
        db_connection.rollback()
        sutil.reportExceptionAndAbort(logger)
    finally:
        database_connection_pool.cleanup()

#-------------------------------------------------------------------------------
def main(config):
    createPartitions(config, config.logger)

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'create_partitions_app'
version = '1.1'
doc = """This app will create four weeks of future partitions within
the database.  If partitions already exist, that's ok."""
#-------------------------------------------------------------------------------
startDate = cm.Option('startDate',
                      'create partitions beginning with this date (leave blank '
                      'for now)',
                      default='',
                      from_string_converter=cm.datetime_converter)
weeksIntoFuture = cm.Option('weeksIntoFuture',
                            'create partitions this many weeks into the future',
                            default=4)
#-------------------------------------------------------------------------------
def get_required_config():
    rc = cm.Namespace()
    rc.startDate = startDate
    rc.weeksIntoFuture = weeksIntoFuture
    rc.update(sdb.get_required_config())
    return rc
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])