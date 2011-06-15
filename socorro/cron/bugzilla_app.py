#! /usr/bin/env python

import urllib2
import logging
import datetime as dt
import cPickle
import csv
import time

logger = logging.getLogger("bugzilla")

import socorro.database.database as sdb
import socorro.lib.util as util

#-------------------------------------------------------------------------------
def find_signatures(bugReportDict):
    try:
        candidateString = bugReportDict['short_desc']
        bracketNestingCounter = 0 #limit 1
        firstLevelBracketPositions = []
        for i, ch in enumerate(candidateString):
            if ch == '[':
                if bracketNestingCounter == 0:
                    firstLevelBracketPositions.append(i+2) #choose position 2 beyond
                bracketNestingCounter += 1
            elif ch == ']':
                if bracketNestingCounter == 1:
                    firstLevelBracketPositions.append(i)
                if bracketNestingCounter: bracketNestingCounter -= 1
        listOfSignatures = []
        try:
            for beginSignaturePosition, endSignaturePosition in ((firstLevelBracketPositions[x],firstLevelBracketPositions[x+1]) for x in range(0,len(firstLevelBracketPositions),2)):
                if candidateString[beginSignaturePosition-1] == '@':
                    listOfSignatures.append(candidateString[beginSignaturePosition:endSignaturePosition].strip())
        except IndexError:
            pass
        setOfSignatures = set(listOfSignatures)
        return (int(bugReportDict["bug_id"]), bugReportDict["bug_status"], bugReportDict["resolution"], bugReportDict["short_desc"], setOfSignatures)
    except (KeyError, TypeError, ValueError):
        return None

#-------------------------------------------------------------------------------
def bug_id_to_signature_association_iterator(query, querySourceFunction=urllib2.urlopen):
    logger.debug("query: %s", query)
    for x in csv.DictReader(querySourceFunction(query)):
        logger.debug("reading csv: %s", str(x))
        yield find_signatures(x)

#-------------------------------------------------------------------------------
def signature_is_found(signature, databaseCursor):
    try:
        sdb.singleValueSql(databaseCursor, "select id from reports where signature = %s limit 1", (signature,))
        return True
    except sdb.SQLDidNotReturnSingleValue:
        return False

#-------------------------------------------------------------------------------
def insert_or_update_bug_in_database(bugId, statusFromBugzilla, resolutionFromBugzilla, shortDescFromBugzilla, signatureSetFromBugzilla,
                                     databaseCursor, signatureFoundInReportsFunction=signature_is_found):
    try:
        if len(signatureSetFromBugzilla) == 0:
            databaseCursor.execute("delete from bugs where id = %s", (bugId,))
            databaseCursor.connection.commit()
            logger.info("rejecting bug (no signatures): %s - %s, %s", bugId, statusFromBugzilla, resolutionFromBugzilla)
        else:
            useful = False
            insertMade = False
            try:
                statusFromDatabase, resolutionFromDatabase, shortDescFromDatabase = sdb.singleRowSql(databaseCursor, "select status, resolution, short_desc from bugs where id = %s", (bugId,))
                if statusFromDatabase != statusFromBugzilla or resolutionFromDatabase != resolutionFromBugzilla or shortDescFromDatabase != shortDescFromBugzilla:
                    databaseCursor.execute("update bugs set status = %s, resolution = %s, short_desc = %s where id = %s", (statusFromBugzilla, resolutionFromBugzilla, shortDescFromBugzilla, bugId))
                    logger.info("bug status updated: %s - %s, %s", bugId, statusFromBugzilla, resolutionFromBugzilla)
                    useful = True
                listOfSignaturesFromDatabase = [x[0] for x in sdb.execute(databaseCursor, "select signature from bug_associations where bug_id = %s", (bugId,))]
                for aSignature in listOfSignaturesFromDatabase:
                    if aSignature not in signatureSetFromBugzilla:
                        databaseCursor.execute("delete from bug_associations where signature = %s and bug_id = %s", (aSignature, bugId))
                        logger.info ('association removed: %s - "%s"', bugId, aSignature)
                        useful = True
            except sdb.SQLDidNotReturnSingleRow:
                databaseCursor.execute("insert into bugs (id, status, resolution, short_desc) values (%s, %s, %s, %s)", (bugId, statusFromBugzilla, resolutionFromBugzilla, shortDescFromBugzilla))
                insertMade = True
                listOfSignaturesFromDatabase = []
            for aSignature in signatureSetFromBugzilla:
                if aSignature not in listOfSignaturesFromDatabase:
                    if signatureFoundInReportsFunction(aSignature, databaseCursor):
                        databaseCursor.execute("insert into bug_associations (signature, bug_id) values (%s, %s)", (aSignature, bugId))
                        logger.info ('new association: %s - "%s"', bugId, aSignature)
                        useful = True
                    else:
                        logger.info ('rejecting association (no reports with this signature): %s - "%s"', bugId, aSignature)
            if useful:
                databaseCursor.connection.commit()
                if insertMade:
                    logger.info('new bug: %s - %s, %s, "%s"', bugId, statusFromBugzilla, resolutionFromBugzilla, shortDescFromBugzilla)
            else:
                databaseCursor.connection.rollback()
                if insertMade:
                    logger.info('rejecting bug (no useful information): %s - %s, %s, "%s"', bugId, statusFromBugzilla, resolutionFromBugzilla, shortDescFromBugzilla)
                else:
                    logger.info('skipping bug (no new information): %s - %s, %s, "%s"', bugId, statusFromBugzilla, resolutionFromBugzilla, shortDescFromBugzilla)
    except Exception, x:
        databaseCursor.connection.rollback()
        raise

#-------------------------------------------------------------------------------
def get_last_run_date(config, now_function=dt.datetime.now):
    if config.daysIntoPast == 0:
        try:
            f = open(config.persistentDataPathname)
            try:
                return cPickle.load(f)
            finally:
                f.close()
        except IOError:
            return now_function() - dt.timedelta(days=100)
    else:
        return now_function() - dt.timedelta(days=config.daysIntoPast)

#-------------------------------------------------------------------------------
def save_last_run_date(config, now_function=dt.datetime.now):
    try:
        f = open(config.persistentDataPathname, "w")
        try:
            return cPickle.dump(now_function(), f)
        finally:
            f.close()
    except IOError:
        reportExceptionAndContinue(logger)

#-------------------------------------------------------------------------------
def record_associations(config):
    databaseConnectionPool = sdb.DatabaseConnectionPool(config)
    try:
        databaseConnection, databaseCursor = databaseConnectionPool.connectionCursorPair()
        lastRunDate = get_last_run_date(config)
        lastRunDateAsString = lastRunDate.strftime('%Y-%m-%d')
        logger.info("beginning search from this date (YYYY-MM-DD): %s", lastRunDateAsString)
        query = config.bugzillaQuery % lastRunDateAsString
        logger.info("searching using: %s", query)
        for bug, status, resolution, short_desc, signatureSet in bug_id_to_signature_association_iterator(query):
            logger.debug("bug %s (%s, %s) %s: %s", bug, status, resolution, short_desc, str(signatureSet))
            insert_or_update_bug_in_database (bug, status, resolution, short_desc, signatureSet, databaseCursor)
        save_last_run_date(config)
    finally:
        databaseConnectionPool.cleanup()

#-------------------------------------------------------------------------------
def main(config):
    record_associations(config)

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'bugzilla'
version = '1.4'
doc = """This app will query bugzilla and try to associate bug titles with
existing crash signatures within the database."""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('bugzillaQuery',
          'the URL to fetch a csv file from a query',
          default='https://bugzilla.mozilla.org/buglist.cgi?query_format=advanced&short_desc_type=allwordssubstr&short_desc=&long_desc_type=allwordssubstr&long_desc=&bug_file_loc_type=allwordssubstr&bug_file_loc=&status_whiteboard_type=allwordssubstr&status_whiteboard=&keywords_type=allwords&keywords=&deadlinefrom=&deadlineto=&emailassigned_to1=1&emailtype1=substring&email1=&emailassigned_to2=1&emailreporter2=1&emailqa_contact2=1&emailcc2=1&emailtype2=substring&email2=&bugidtype=include&bug_id=&votes=&chfieldfrom=%s&chfieldto=Now&chfield=[Bug+creation]&chfield=resolution&chfield=bug_status&chfield=short_desc&chfieldvalue=&cmdtype=doit&order=Importance&field0-0-0=noop&type0-0-0=noop&value0-0-0=&ctype=csv'
         )
rc.option('persistentDataPathname',
          'a pathname to a file system location where '
          'this script can store persistent data',
          default='./bugzilla.pickle')
rc.option('daysIntoPast',
          'number of days to look into the past for bugs (0 - '
          'use last run time)',
          default=0)
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