.. index:: installation

.. _installation-chapter:

Installation
============

Socorro VM (built with Vagrant + Puppet)
------------

You can build a standalone Socorro development VM -
see :ref:`setupdevenv-chapter` for more info.

The config files and puppet manifests in ./puppet/ are a useful reference
when setting up Socorro for the first time.

Automated Install using Puppet
------------

It is possible to use puppet to script an install onto an existing environment.
This has been tested in EC2 but should work on any regular Ubuntu Lucid install.

See puppet/ubuntu-bootstrap.sh for an example.

Manual Install
------------

Requirements
````````````

.. sidebar:: Breakpad client and symbols

   Socorro aggregates and reports on Breakpad crashes.
   Read more about `getting started with Breakpad <http://code.google.com/p/google-breakpad/wiki/GettingStartedWithBreakpad>`_.

   You will need to `produce symbols for your application <http://code.google.com/p/google-breakpad/wiki/LinuxStarterGuide#Producing_symbols_for_your_application>`_ and make these files available to Socorro.

* Linux (tested on Ubuntu Lucid and RHEL/CentOS 6)

* HBase (Cloudera CDH3)

* PostgreSQL 9.0

* Python 2.6

Ubuntu
````````````
1) Add PostgreSQL 9.0 PPA from https://launchpad.net/~pitti/+archive/postgresql
2) Add Cloudera apt source from https://ccp.cloudera.com/display/CDHDOC/CDH3+Installation#CDH3Installation-InstallingCDH3onUbuntuSystems
3) Install dependencies using apt-get

As *root*:
::
  apt-get install supervisor rsyslog libcurl4-openssl-dev build-essential sun-java6-jdk ant python-software-properties subversion libpq-dev python-virtualenv python-dev libcrypt-ssleay-perl php5-tidy apache2 libapache2-mod-wsgi memcached php5-pgsql php5-curl php5-dev php-pear php5-common php5-cli php5-memcache php5 php5-gd php5-mysql php5-ldap hadoop-hbase hadoop-hbase-master hadoop-hbase-thrift curl liblzo2-dev postgresql-9.0 postgresql-plperl-9.0 postgresql-contrib-9.0

RHEL/Centos
````````````
Use "text install"
Choose "minimal" as install option.

1) Add Cloudera yum repo from https://ccp.cloudera.com/display/CDHDOC/CDH3+Installation#CDH3Installation-InstallingCDH3onRedHatSystems
2) Add PostgreSQL 9.0 yum repo from http://www.postgresql.org/download/linux#yum
3) Install Sun Java JDK version JDK 6u16 - Download appropriate package from http://www.oracle.com/technetwork/java/javase/downloads/index.html
4) Install dependencies using YUM:

As *root*:
::
  yum install httpd mod_ssl mod_wsgi postgresql-server postgresql-plperl perl-pgsql_perl5 postgresql-contrib subversion make rsync php-pecl-memcache memcached php-pgsql subversion gcc-c++ curl-devel ant python-virtualenv hadoop-0.20 hadoop-hbase daemonize

5) Disable SELinux

As *root*:
  Edit /etc/sysconfig/selinux and set "SELINUX=disabled"

6) Reboot

As *root*:
::
  shutdown -r now

Download and install Socorro
````````````
Determine latest release tag from https://wiki.mozilla.org/Socorro:Releases#Previous_Releases

Clone from github, as the *socorro* user:
::
  git clone https://github.com/mozilla/socorro
  git checkout LATEST_RELEASE_TAG_GOES_HERE
  cd socorro
  cp scripts/config/commonconfig.py.dist scripts/config/commonconfig.py

Edit scripts/config/commonconfig.py

From inside the Socorro checkout, as the *socorro* user, change:
::
  databaseName.default = 'breakpad'
  databaseUserName.default = 'breakpad_rw'
  databasePassword.default = 'aPassword'

If you change the password, make sure to change it in sql/roles.sql as well.

Run unit/functional tests, and generate report
````````````
From inside the Socorro checkout, as the *socorro* user:
::
  # only need install-submodules for pre-9.0 versions of Socorro
  make install-submodules
  make test

Set up directories and permissions
````````````
As *root*:
::
  mkdir /etc/socorro
  mkdir /var/log/socorro
  mkdir -p /data/socorro
  useradd socorro
  chown socorro:socorro /var/log/socorro
  mkdir /home/socorro/primaryCrashStore /home/socorro/fallback /home/socorro/persistent
  chown apache /home/socorro/primaryCrashStore /home/socorro/fallback
  chmod 2775 /home/socorro/primaryCrashStore /home/socorro/fallback

Note - use www-data instead of apache for debian/ubuntu

Compile minidump_stackwalk

From inside the Socorro checkout, as the *socorro* user:
::
  make minidump_stackwalk

Install socorro
````````````
From inside the Socorro checkout, as the *socorro* user:
::
  make install

By default, this installs files to /data/socorro. You can change this by 
specifying the PREFIX:
::
  make install PREFIX=/usr/local/socorro

.. _howsocorroworks-chapter:

How Socorro Works
````````````

There are two main parts to Socorro:

1) collects, processes, and allows real-time searches and results for individual crash reports

  This requires both HBase and PostgreSQL, as well as the Collector, Crashmover,
  Monitor, Processor and Middleware and UI. 

  Individual crash reports are pulled from long-term storage (HBase) using the /report/index/ page, for
  example: http://crash-stats/report/index/YOUR_CRASH_ID_GOES_HERE

  The search feature is at: http://crash-stats/query

2) a set of batch jobs which compiles aggregate reports and graphs, such as "Top Crashes by Signature"

  This requires PostgreSQL, Middleware and UI. It triggered once per day by the "daily_matviews" cron job, 
  covering data processed in the previous UTC day.

  Every other page on http://crash-stats is of this type.


.. _crashflow-chapter:

Crash Flow
````````````

The basic flow of an incoming crash is:

(breakpad client) -> (collector) -> (local file system) -> (newCrashMover.py) -> (hbase)

A single machine will need to run the Monitor service, which watches
hbase for incoming crashes and queues them up for the Processor service
(which can run on one or more servers). Monitor and Processor use PostgreSQL
to coordinate.

Finally, processed jobs are inserted into both hbase and PostgreSQL

Configure Socorro 
````````````

These pages show how to start the services manually, please also see the
next section "Install startup scripts":

* Start configuration with :ref:`commonconfig-chapter`
* On the machine(s) to run collector, setup :ref:`collector-chapter`
* On the machine(s) to run  collector setup :ref:`crashmover-chapter`
* On the machine to run monitor, setup :ref:`monitor-chapter`
* On same machine that runs monitor, setup :ref:`deferredcleanup-chapter`
* On the machine(s) to run processor, setup :ref:`processor-chapter`

Install startup scripts
````````````
RHEL/CentOS only (Ubuntu TODO - see ./puppet/files/etc_supervisor for supervisord example)

As *root*:
::
    ln -s /data/socorro/application/scripts/init.d/socorro-{monitor,processor,crashmover} /etc/init.d/
    chkconfig socorro-monitor on
    chkconfig socorro-processor on
    chkconfig socorro-crashmover on
    service httpd restart
    chkconfig httpd on
    service memcached restart
    chkconfig memcached on

Install Socorro cron jobs
````````````
From inside the Socorro checkout, as the *root* user:
::
  ln -s /data/socorro/application/scripts/crons/socorrorc /etc/socorro/
  cp puppet/files/etc_crond/socorro /etc/cron.d/

Socorro's cron jobs are moving to a new cronjob manager called :ref:`crontabber-chapter`.
:ref:`crontabber-chapter` runs every 5 minutes from the system crontab, and looks inside
the config/ directory for it's configuration.

However some configuration is shared and site-specific, so is expected to
be in the system directory /etc/socorro :

From inside the Socorro checkout, as the *root* user:
::
  cp puppet/files/etc_socorro/postgres.ini /etc/socorro/

PostgreSQL Config
````````````
RHEL/CentOS - Initialize and enable on startup (not needed for Ubuntu)

As *root*:
::
  service postgresql initdb
  service postgresql start
  chkconfig postgresql on

As *root*:

* edit /var/lib/pgsql/data/pg_hba.conf and change IPv4/IPv6 connection from "ident" to "md5"
* edit /var/lib/pgsql/data/postgresql.conf and:
    * uncomment # listen_addresses = 'localhost'
    * change TimeZone to 'UTC'
* edit other postgresql.conf paramters per www.postgresql.org community guides

Populate PostgreSQL Database
````````````
Refer to :ref:`populatepostgres-chapter` for information about
loading the schema and populating the database.

This step is *required* to get basic information about existing product names
and versions into the system.


Configure Apache
````````````
Socorro uses three virtual hosts:

* crash-stats   - the web UI for viewing crash reports
* socorro-api   - the "middleware" used by the web UI 
* crash-reports - receives reports from crashing clients (via HTTP POST)

As *root*:
::
  cp puppet/files/etc_apache2_sites-available/{crash-reports,crash-stats,socorro-api} /etc/httpd/conf.d/

edit /etc/httpd/conf.d/{crash-reports,crash-stats,socorro-api} and customize
as needed for your site

As *root*
::
  mkdir /var/log/httpd/{crash-stats,crash-reports,socorro-api}.example.com
  chown apache /data/socorro/htdocs/application/logs/

Note - use www-data instead of apache for debian/ubuntu

Enable PHP short_open_tag
````````````
As *root*:

edit /etc/php.ini and make the following changes:
::
  short_open_tag = On
  date.timezone = 'America/Los_Angeles'

Configure Kohana (PHP/web UI)
````````````
Refer to :ref:`uiinstallation-chapter` (deprecated as of 2.2, new docs TODO)

Hadoop+HBase install
````````````
Configure Hadoop 0.20 + HBase 0.89
  Refer to https://ccp.cloudera.com/display/CDHDOC/HBase+Installation

You can start with a standalone setup, but read all of the above for info on a real, distributed setup!

NOTE - HBase stores the database in /tmp by default, which many distributions
clear out occasionally. You should change this in /etc/hbase/conf/hbase-site.xml like so:
::
  <configuration>
    <property>
      <name>hbase.rootdir</name>
      <value>file:///var/lib/hbase</value>
    </property>
  </configuration>

Make sure that the above directory exists and is owned by hbase, as *root*:
::
  mkdir -p /var/lib/hbase
  chown hbase:hbase /var/lib/hbase

RHEL/CentOS only (not needed for Ubuntu)
Install startup scripts

As *root*:
::
  service hadoop-hbase-master start
  chkconfig hadoop-hbase-master on
  service hadoop-hbase-thrift start
  chkconfig hadoop-hbase-thrift on

Load Hbase schema
````````````
FIXME this skips LZO suport, remove the "sed" command if you have it installed

From inside the Socorro checkout, as the *socorro* user:
::
  cat analysis/hbase_schema | sed 's/LZO/NONE/g' | hbase shell


.. _systemtest-chapter:

System Test
````````````
Generate a test crash:

1) Install http://code.google.com/p/crashme/ add-on for Firefox
2) Point your Firefox install at http://crash-reports/submit

See: https://developer.mozilla.org/en/Environment_variables_affecting_crash_reporting

If you already have a crash available and wish to submit it, you can
use the standalone submitter tool:

From inside the Socorro checkout, as the *socorro* user:
::
  virtualenv socorro-virtualenv
  . socorro-virtualenv/bin/activate
  pip install poster
  cp scripts/config/submitterconfig.py.dist scripts/config/submitterconfig.py
  export PYTHONPATH=.:thirdparty
  python scripts/submitter.py -u http://crash-reports/submit -j ~/Downloads/crash.json -d ~/Downloads/crash.dump

You should get a "CrashID" returned.
Check syslog logs for user.*, should see the CrashID returned being collected.

Attempt to pull up the newly inserted crash: http://crash-stats/report/index/YOUR_CRASH_ID_GOES_HERE

The (syslog "user" facility) logs should show this new crash being inserted for priority processing, and it should be available shortly thereafter.

