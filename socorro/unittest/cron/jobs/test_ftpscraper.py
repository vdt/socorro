import shutil
import os
import json
import unittest
import tempfile
from functools import wraps
from cStringIO import StringIO
import mock
import psycopg2
from socorro.cron import crontabber
from socorro.unittest.config.commonconfig import (
  databaseHost, databaseName, databaseUserName, databasePassword)
from socorro.lib.datetimeutil import utc_now
from configman import ConfigurationManager
from socorro.cron.jobs import ftpscraper

DSN = {
  "database_host": databaseHost.default,
  "database_name": databaseName.default,
  "database_user": databaseUserName.default,
  "database_password": databasePassword.default
}


def stringioify(func):
    @wraps(func)
    def wrapper(*a, **k):
        return StringIO(func(*a, **k))
    return wrapper


class _TestCaseBase(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)

    def _setup_config_manager(self, jobs_string, extra_value_source=None):
        if not extra_value_source:
            extra_value_source = {}
        mock_logging = mock.Mock()
        required_config = crontabber.CronTabber.required_config
        required_config.add_option('logger', default=mock_logging)

        json_file = os.path.join(self.tempdir, 'test.json')
        assert not os.path.isfile(json_file)

        config_manager = ConfigurationManager(
            [required_config,
             #logging_required_config(app_name)
             ],
            app_name='crontabber',
            app_description=__doc__,
            values_source_list=[{
                'logger': mock_logging,
                'jobs': jobs_string,
                'database': json_file,
            }, DSN, extra_value_source]
        )
        return config_manager, json_file


#==============================================================================
class TestFTPScraper(_TestCaseBase):

    def setUp(self):
        super(TestFTPScraper, self).setUp()
        self.psycopg2_patcher = mock.patch('psycopg2.connect')
        self.psycopg2 = self.psycopg2_patcher.start()
        self.urllib2_patcher = mock.patch('urllib2.urlopen')
        self.urllib2 = self.urllib2_patcher.start()

    def tearDown(self):
        super(TestFTPScraper, self).tearDown()
        self.psycopg2_patcher.stop()
        self.urllib2_patcher.stop()

    def test_urljoin(self):
        self.assertEqual(
            ftpscraper.urljoin('http://google.com', '/page.html'),
            'http://google.com/page.html'
        )
        self.assertEqual(
            ftpscraper.urljoin('http://google.com/', '/page.html'),
            'http://google.com/page.html'
        )
        self.assertEqual(
            ftpscraper.urljoin('http://google.com/', 'page.html'),
            'http://google.com/page.html'
        )
        self.assertEqual(
            ftpscraper.urljoin('http://google.com', 'page.html'),
            'http://google.com/page.html'
        )
        self.assertEqual(
            ftpscraper.urljoin('http://google.com', 'dir1', ''),
            'http://google.com/dir1/'
        )

    def test_getLinks(self):
        @stringioify
        def mocked_urlopener(url):
            html_wrap = "<html><body>\n%s\n</body></html>"
            if 'ONE' in url:
                return html_wrap % """
                <a href='One.html'>One.html</a>
                """
            raise NotImplementedError(url)

        self.urllib2.side_effect = mocked_urlopener
        self.assertEqual(
            ftpscraper.getLinks('ONE'),
            []
        )
        self.assertEqual(
            ftpscraper.getLinks('ONE', startswith='One'),
            ['One.html']
        )
        self.assertEqual(
            ftpscraper.getLinks('ONE', endswith='.html'),
            ['One.html']
        )
        self.assertEqual(
            ftpscraper.getLinks('ONE', startswith='Two'),
            []
        )

    def test_parseInfoFile(self):
        @stringioify
        def mocked_urlopener(url):
            if 'ONE' in url:
                return 'BUILDID=123'
            if 'TWO' in url:
                return 'BUILDID=123\nbuildID=456'
            if 'THREE' in url:
                return '123\nhttp://hg.mozilla.org/123'
            if 'FOUR' in url:
                return ('123\nhttp://hg.mozilla.org/123\n'
                        'http://git.mozilla.org/123')
            raise NotImplementedError(url)
        self.urllib2.side_effect = mocked_urlopener

        self.assertEqual(
            ftpscraper.parseInfoFile('ONE'),
            {'BUILDID': '123'}
        )
        self.assertEqual(
            ftpscraper.parseInfoFile('TWO'),
            {'BUILDID': '123',
             'buildID': '456'}
        )
        self.assertEqual(
            ftpscraper.parseInfoFile('THREE', nightly=True),
            {'buildID': '123',
             'rev': 'http://hg.mozilla.org/123'}
        )
        self.assertEqual(
            ftpscraper.parseInfoFile('FOUR', nightly=True),
            {'buildID': '123',
             'rev': 'http://hg.mozilla.org/123',
             'altrev': 'http://git.mozilla.org/123'}
        )

    def test_getRelease(self):
        @stringioify
        def mocked_urlopener(url):
            html_wrap = "<html><body>\n%s\n</body></html>"
            if 'linux_info.txt' in url:
                return 'BUILDID=123'
            if 'build-11' in url:
                return html_wrap % """
                <a href="linux_info.txt">l</a>
                """
            if 'ONE' in url:
                return html_wrap % """
                <a href="build-10/">build-10</a>
                <a href="build-11/">build-11</a>
                """
            if 'TWO' in url:
                return html_wrap % """
                <a href="ignore/">ignore</a>
                """
            raise NotImplementedError(url)

        self.urllib2.side_effect = mocked_urlopener

        self.assertEqual(
            list(ftpscraper.getRelease('TWO', 'http://x')),
            []
        )
        self.assertEqual(
            list(ftpscraper.getRelease('ONE', 'http://x')),
            [('linux', 'ONE', 'build-11', {'BUILDID': '123'})]
        )

    def test_getNightly(self):
        @stringioify
        def mocked_urlopener(url):
            html_wrap = "<html><body>\n%s\n</body></html>"
            if '.linux.txt' in url:
                return '123\nhttp://hg.mozilla.org/123'
            if 'ONE' in url:
                return html_wrap % """
                <a href="firefox.en-US.linux.txt">l</a>
                <a href="firefox.multi.linux.txt">l</a>
                """
            if 'ONE' in url:
                return html_wrap % """
                <a href="build-10/">build-10</a>
                <a href="build-11/">build-11</a>
                """
            if 'TWO' in url:
                return html_wrap % """
                <a href="ignore/">ignore</a>
                """
            raise NotImplementedError(url)

        self.urllib2.side_effect = mocked_urlopener

        self.assertEqual(
            list(ftpscraper.getNightly('TWO', 'http://x')),
            []
        )
        self.assertEqual(
            list(ftpscraper.getNightly('ONE', 'http://x')),
            [('linux', 'ONE', 'firefox',
              {'buildID': '123', 'rev': 'http://hg.mozilla.org/123'}),
             ('linux', 'ONE', 'firefox',
              {'buildID': '123', 'rev': 'http://hg.mozilla.org/123'})]
        )


#==============================================================================
class TestFunctionalFTPScraper(_TestCaseBase):

    def setUp(self):
        super(TestFunctionalFTPScraper, self).setUp()
        # prep a fake table
        assert 'test' in databaseName.default, databaseName.default
        dsn = ('host=%(database_host)s dbname=%(database_name)s '
               'user=%(database_user)s password=%(database_password)s' % DSN)
        self.conn = psycopg2.connect(dsn)
        self.urllib2_patcher = mock.patch('urllib2.urlopen')
        self.urllib2 = self.urllib2_patcher.start()

    def tearDown(self):
        super(TestFunctionalFTPScraper, self).tearDown()
        self.conn.cursor().execute("""
        TRUNCATE TABLE releases_raw CASCADE;
        """)
        self.conn.commit()
        self.urllib2_patcher.stop()

    def _setup_config_manager(self):
        _super = super(TestFunctionalFTPScraper, self)._setup_config_manager
        config_manager, json_file = _super(
          'socorro.cron.jobs.ftpscraper.FTPScraperCronApp|1d',
          extra_value_source={
            'class-FTPScraperCronApp.products': 'firefox',
          }
        )
        return config_manager, json_file

    def test_basic_run(self):

        @stringioify
        def mocked_urlopener(url, today=None):
            if today is None:
                today = utc_now()
            html_wrap = "<html><body>\n%s\n</body></html>"
            if url.endswith('/firefox/'):
                return html_wrap % """
                <a href="candidates/">candidates</a>
                <a href="nightly/">nightly</a>
                """
            if url.endswith('/firefox/nightly/'):
                return html_wrap % """
                <a href="10.0-candidates/">10.0-candidiates</a>
                """
            if url.endswith('/firefox/candidates/'):
                return html_wrap % """
                <a href="10.0b4-candidates/">10.0b4-candidiates</a>
                """
            if (url.endswith('/firefox/nightly/10.0-candidates/') or
                url.endswith('/firefox/candidates/10.0b4-candidates/')):
                return html_wrap % """
                <a href="build1/">build1</a>
                """
            if (url.endswith('/firefox/nightly/10.0-candidates/build1/') or
                url.endswith('/firefox/candidates/10.0b4-candidates/build1/')):
                return html_wrap % """
                <a href="linux_info.txt">linux_info.txt</a>
                """
            if url.endswith(today.strftime('/firefox/nightly/%Y/%m/')):
                return html_wrap % today.strftime("""
                <a href="%Y-%m-%d-trunk/">%Y-%m-%d-trunk</a>
                """)
            if url.endswith(today.strftime(
              '/firefox/nightly/%Y/%m/%Y-%m-%d-trunk/')):
                return html_wrap % """
                <a href="mozilla-nightly-15.0a1.en-US.linux-x86_64.txt">txt</a>
                <a href="mozilla-nightly-15.0a2.en-US.linux-x86_64.txt">txt</a>
                """
            if url.endswith(today.strftime(
              '/firefox/nightly/%Y/%m/%Y-%m-%d-trunk/mozilla-nightly-15.0a1.en'
              '-US.linux-x86_64.txt')):
                return (
                   "20120505030510\n"
                   "http://hg.mozilla.org/mozilla-central/rev/0a48e6561534"
                )
            if url.endswith(today.strftime(
              '/firefox/nightly/%Y/%m/%Y-%m-%d-trunk/mozilla-nightly-15.0a2.en'
              '-US.linux-x86_64.txt')):
                return (
                   "20120505443322\n"
                   "http://hg.mozilla.org/mozilla-central/rev/xxx123"
                )
            if url.endswith(
              '/firefox/nightly/10.0-candidates/build1/linux_info.txt'):
                return "buildID=20120516113045"
            if url.endswith(
              '/firefox/candidates/10.0b4-candidates/build1/linux_info.txt'):
                return "buildID=20120516114455"

            # bad testing boy!
            raise NotImplementedError(url)

        self.urllib2.side_effect = mocked_urlopener

        config_manager, json_file = self._setup_config_manager()
        with config_manager.context() as config:
            tab = crontabber.CronTabber(config)
            tab.run_all()

            information = json.load(open(json_file))
            assert information['ftpscraper']
            assert not information['ftpscraper']['last_error']
            assert information['ftpscraper']['last_success']

        cursor = self.conn.cursor()

        columns = 'product_name', 'build_id', 'build_type'
        cursor.execute("""
        select %s
        from releases_raw
        """ % ','.join(columns)
        )
        builds = [dict(zip(columns, row)) for row in cursor.fetchall()]
        build_ids = dict((str(x['build_id']), x) for x in builds)
        self.assertTrue('20120516114455' in build_ids)
        self.assertTrue('20120516113045' in build_ids)
        self.assertTrue('20120505030510' in build_ids)
        self.assertTrue('20120505443322' in build_ids)
        assert len(build_ids) == 4
        self.assertEqual(build_ids['20120516114455']['build_type'],
                         'Beta')
        self.assertEqual(build_ids['20120516113045']['build_type'],
                         'Release')
        self.assertEqual(build_ids['20120505030510']['build_type'],
                         'Nightly')
        self.assertEqual(build_ids['20120505443322']['build_type'],
                         'Aurora')

        # just one more time, pretend that we run it immediately again
        cursor.execute('select count(*) from releases_raw')
        count_before, = cursor.fetchall()[0]
        assert count_before == 4, count_before

        with config_manager.context() as config:
            tab = crontabber.CronTabber(config)
            tab.run_all()

            information = json.load(open(json_file))
            assert information['ftpscraper']
            assert not information['ftpscraper']['last_error']
            assert information['ftpscraper']['last_success']

        cursor.execute('select count(*) from releases_raw')
        count_after, = cursor.fetchall()[0]
        assert count_after == count_before, count_before
