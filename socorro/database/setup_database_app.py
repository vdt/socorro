#! /usr/bin/env python

import socorro.database.schema as sch
import socorro.database.database as sdb
import socorro.lib.util as sutil

#-------------------------------------------------------------------------------
def main(config, sch=sch, sdb=sdb):
    """setup the schema for a new instance of Socorro"""
    logger = config.logger
    database_connection_pool = sdb.DatabaseConnectionPool(config)
    db_connection = database_connection_pool.connection()
    db_cursor = db_connection.cursor()

    try:
        db_cursor.execute("CREATE LANGUAGE plperl")
        db_cursor.execute("CREATE LANGUAGE plpgsql")
    except:
        db_connection.rollback()

    try:
        for db_obj_class in sch.getOrderedSetupList():
            try:
                db_object = db_obj_class(logger=logger)
                db_object._createSelf(db_cursor)
                db_connection.commit()
            except Exception,x:
                db_connection.rollback()
                sutil.reportExceptionAndContinue(logger)
    finally:
        database_connection_pool.cleanup()

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'setup_database_app'
version = '1.1'
doc = """This app configures the database with an initial schema"""
#-------------------------------------------------------------------------------
def get_required_config():
    return sdb.get_required_config()
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])