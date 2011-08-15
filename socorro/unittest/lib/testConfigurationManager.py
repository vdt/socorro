import os
import datetime
import tempfile
from contextlib import contextmanager
import ConfigParser
import io
from cStringIO import StringIO
import json
import functools

from socorro.lib import config_manager, datetimeutil
from socorro.lib.util import DotDict

import unittest
class TestCase(unittest.TestCase):
    
    def test_option_constructor_basics(self):
        o = config_manager.Option()
        self.assertEqual(o.name, None)
        self.assertEqual(o.default, None)
        self.assertEqual(o.doc, None)
        self.assertEqual(o.from_string_converter, None)
        self.assertEqual(o.value, None)
        
        o = config_manager.Option('lucy')
        self.assertEqual(o.name, 'lucy')
        self.assertEqual(o.default, None)
        self.assertEqual(o.doc, None)
        self.assertEqual(o.from_string_converter, None)
        self.assertEqual(o.value, None)

        o = config_manager.Option(u'spa\xa0e')
        self.assertEqual(o.name, u'spa\xa0e')
        self.assertEqual(o.default, None)
        self.assertEqual(o.doc, None)
        self.assertEqual(o.from_string_converter, None)
        self.assertEqual(o.value, None)
        
        data = {
          'name': 'lucy',
          'default': 1,
          'doc': "lucy's integer"
        }
        o = config_manager.Option(**data)
        self.assertEqual(o.name, 'lucy')
        self.assertEqual(o.default, 1)
        self.assertEqual(o.doc, "lucy's integer")
        self.assertEqual(o.from_string_converter, int)
        self.assertEqual(o.value, 1)
    
        data = { 
          'name': 'lucy',
          'default': 1,
          'doc': "lucy's integer",
          'value': '1'
        }
        o = config_manager.Option(**data)
        self.assertEqual(o.name, 'lucy')
        self.assertEqual(o.default, 1)
        self.assertEqual(o.doc, "lucy's integer")
        self.assertEqual(o.from_string_converter, int)
        self.assertEqual(o.value, 1)
    
        data = { 
          'name': 'lucy',
          'default': '1',
          'doc': "lucy's integer",
          'from_string_converter': int
        }
        o = config_manager.Option(**data)
        self.assertEqual(o.name, 'lucy')
        self.assertEqual(o.default, '1')
        self.assertEqual(o.doc, "lucy's integer")
        self.assertEqual(o.from_string_converter, int)
        self.assertEqual(o.value, 1)
    
        data = { 
          'name': 'lucy',
          'default': '1',
          'doc': "lucy's integer",
          'from_string_converter': int,
          'other': 'no way'
        }
        o = config_manager.Option(**data)
        self.assertEqual(o.name, 'lucy')
        self.assertEqual(o.default, '1')
        self.assertEqual(o.doc, "lucy's integer")
        self.assertEqual(o.from_string_converter, int)
        self.assertEqual(o.value, 1)
    
        data = { 
          'default': '1',
          'doc': "lucy's integer",
          'from_string_converter': int,
          'other': 'no way'
        }
        o = config_manager.Option(**data)
        self.assertEqual(o.name, None)
        self.assertEqual(o.default, '1')
        self.assertEqual(o.doc, "lucy's integer")
        self.assertEqual(o.from_string_converter, int)
        self.assertEqual(o.value, 1)
    
        d = datetime.datetime.now()
        o = config_manager.Option(name='now', default=d)
        self.assertEqual(o.name, 'now')
        self.assertEqual(o.default, d)
        self.assertEqual(o.doc, None)
        self.assertEqual(o.from_string_converter, 
                         datetimeutil.datetimeFromISOdateString)
        self.assertEqual(o.value, d)
        
    def test_OptionsByGetOpt_basics(self):
        source = ['a', 'b', 'c']
        o = config_manager.OptionsByGetopt(source)
        self.assertEqual(o.argv_source, source)
        o = config_manager.OptionsByGetopt(argv_source=source)
        self.assertEqual(o.argv_source, source)
        
    def test_OptionsByGetOpt_get_values(self):
        c = config_manager.ConfigurationManager(
          manager_controls=False,
          use_config_files=False,
          auto_help=False,
          argv_source=[]
        )
        
        source = ['--limit', '10']
        o = config_manager.OptionsByGetopt(source)
        self.assertEqual(o.get_values(c, True), {})
        self.assertRaises(config_manager.NotAnOptionError,
                          o.get_values, c, False)
        
        c.option_definitions.option('limit', default=0)
        self.assertEqual(o.get_values(c, False), {'limit': '10'})
        self.assertEqual(o.get_values(c, True), {'limit': '10'})

        
    def test_OptionsByGetOpt_getopt_with_ignore(self):
        function = config_manager.OptionsByGetopt.getopt_with_ignore
        args = ['a', 'b', 'c']
        o, a = function(args, '', [])
        self.assertEqual(o, [])
        self.assertEqual(a, args)
        args = ['-a', '14', '--fred', 'sally', 'ethel', 'dwight']
        o, a = function(args, '', [])
        self.assertEqual([], o)
        self.assertEqual(a, args)
        args = ['-a', '14', '--fred', 'sally', 'ethel', 'dwight']
        o, a = function(args, 'a:', [])
        self.assertEqual(o, [('-a', '14')])
        self.assertEqual(a, ['--fred', 'sally', 'ethel', 'dwight'])
        args = ['-a', '14', '--fred', 'sally', 'ethel', 'dwight']
        o, a = function(args, 'a', ['fred='])
        self.assertEqual(o, [('-a', ''), ('--fred', 'sally')])
        self.assertEqual(a, ['14', 'ethel', 'dwight'])
        
    def test_empty_ConfigurationManager_constructor(self):
        # because the default option argument defaults to using sys.argv we 
        # have to mock that
        c = config_manager.ConfigurationManager(
          manager_controls=False,
          use_config_files=False,
          auto_help=False,
          argv_source=[]
        )
        self.assertEqual(c.option_definitions, config_manager.Namespace())
        
    def test_Namespace_basics(self):
        namespace = config_manager.Namespace('doc string')
        namespace.alpha = 1
        my_birthday = datetime.datetime(1960, 5, 4, 15, 10)
        namespace.beta = my_birthday
        self.assertEqual(namespace.alpha.name, 'alpha')
        self.assertEqual(namespace.alpha.doc, None)
        self.assertEqual(namespace.alpha.default, 1)
        self.assertEqual(namespace.alpha.from_string_converter, int)
        self.assertEqual(namespace.alpha.value, 1)
        self.assertEqual(namespace.beta.name, 'beta')
        self.assertEqual(namespace.beta.doc, None)
        self.assertEqual(namespace.beta.default, my_birthday)
        self.assertEqual(namespace.beta.from_string_converter, 
                         datetimeutil.datetimeFromISOdateString)
        self.assertEqual(namespace.beta.value, my_birthday)

    def test_configuration_with_namespace(self):
        namespace = config_manager.Namespace()
        namespace.a = config_manager.Option()
        namespace.a.name = 'a'
        namespace.a.default = 1
        namespace.a.doc = 'the a'
        namespace.b = 17
        config = config_manager.ConfigurationManager(
          [namespace],
          use_config_files=False,
          argv_source=[]
        )
        self.assertEqual(config.option_definitions.a, namespace.a)
        self.assertTrue(isinstance(config.option_definitions.b,
                                   config_manager.Option))
        self.assertEqual(config.option_definitions.b.value, 17)
        self.assertEqual(config.option_definitions.b.default, 17)
        self.assertEqual(config.option_definitions.b.name, 'b')
        
    def test_namespace_constructor_3(self):
        """test json definition"""
    
        j = '{ "a": {"name": "a", "default": 1, "doc": "the a"}, "b": 17}'
        config = config_manager.ConfigurationManager(
          [j],
          use_config_files=False,
          argv_source=[]
        )
        self.assertTrue(isinstance(config.option_definitions.a,
                                   config_manager.Option))
        self.assertEqual(config.option_definitions.a.value, 1)
        self.assertEqual(config.option_definitions.a.default, 1)
        self.assertEqual(config.option_definitions.a.name, 'a')
        self.assertTrue(isinstance(config.option_definitions.b,
                                   config_manager.Option))
        self.assertEqual(config.option_definitions.b.value, 17)
        self.assertEqual(config.option_definitions.b.default, 17)
        self.assertEqual(config.option_definitions.b.name, 'b')

    def test_get_config_1(self):
        n = config_manager.Namespace()
        n.a = config_manager.Option('a', 'the a', 1)
        n.b = 17
        c = config_manager.ConfigurationManager(
          [n],
          manager_controls=False,
          use_config_files=False,
          auto_help=False,
          argv_source=[]
        )
        d = c.get_config()
        e = DotDict()
        e.a = 1
        e.b = 17
        self.assertEqual(d, e)
    
    def test_get_config_2(self):
        n = config_manager.Namespace()
        n.a = config_manager.Option(name='a', default=1, doc='the a')
        n.b = 17
        n.c = c = config_manager.Namespace()
        c.x = 'fred'
        c.y = 3.14159
        c.z = config_manager.Option('z', 'the 99', 99)
        c = config_manager.ConfigurationManager(
          [n],
          manager_controls=False,
          use_config_files=False,
          auto_help=False,
          argv_source=[]
        )
        d = c.get_config()
        e = DotDict()
        e.a = 1
        e.b = 17
        e.c = DotDict()
        e.c.x = 'fred'
        e.c.y = 3.14159
        e.c.z = 99
        self.assertEqual(d, e)
    
    def test_walk_config(self):
        """step through them all"""
        n = config_manager.Namespace(doc='top')
        n.aaa = config_manager.Option('aaa', 'the a', False, short_form='a')
        n.c = config_manager.Namespace(doc='c space')
        n.c.fred = config_manager.Option('fred', 'husband from Flintstones')
        n.c.wilma = config_manager.Option('wilma', 'wife from Flintstones')
        n.d = config_manager.Namespace(doc='d space')
        n.d.fred = config_manager.Option('fred', 'male neighbor from I Love Lucy')
        n.d.ethel = config_manager.Option('ethel', 'female neighbor from I Love Lucy')
        n.d.x = config_manager.Namespace(doc='x space')
        n.d.x.size = config_manager.Option('size', 'how big in tons', 100, short_form='s')
        n.d.x.password = config_manager.Option('password', 'the password', 'secrets')
        c = config_manager.ConfigurationManager(
          [n],
          manager_controls=False,
          use_config_files=False,
          auto_help=False,
          argv_source=[]
        )
        e = [('aaa', 'aaa', n.aaa.name),
             ('c', 'c', n.c._doc),
             ('c.wilma', 'wilma', n.c.wilma.name),
             ('c.fred', 'fred', n.c.fred.name),
             ('d', 'd', n.d._doc),
             ('d.ethel', 'ethel', n.d.ethel.name),
             ('d.fred', 'fred', n.d.fred.name),
             ('d.x', 'x', n.d.x._doc),
             ('d.x.size', 'size', n.d.x.size.name),
             ('d.x.password', 'password', n.d.x.password.name),
            ]
        e.sort()
        r = [(q, k, v.name if isinstance(v, config_manager.Option) else v._doc)
              for q, k, v in c.walk_config()]
        r.sort()
        for expected, received in zip(e, r):
            self.assertEqual(received, expected)

    def _some_namespaces(self):
        """set up some namespaces"""
        n = config_manager.Namespace(doc='top')
        n.aaa = config_manager.Option('aaa', 'the a', '2011-05-04T15:10:00', 
          short_form='a',
          from_string_converter=datetimeutil.datetimeFromISOdateString
        )
        n.c = config_manager.Namespace(doc='c space')
        n.c.fred = config_manager.Option('fred', 'husband from Flintstones', default='stupid')
        n.c.wilma = config_manager.Option('wilma', 'wife from Flintstones', default='waspish')
        n.d = config_manager.Namespace(doc='d space')
        n.d.fred = config_manager.Option('fred', 'male neighbor from I Love Lucy', default='crabby')
        n.d.ethel = config_manager.Option('ethel', 'female neighbor from I Love Lucy', default='silly')
        n.x = config_manager.Namespace(doc='x space')
        n.x.size = config_manager.Option('size', 'how big in tons', 100, short_form='s')
        n.x.password = config_manager.Option('password', 'the password', 'secrets')
        return n
    
    def test_write_flat(self):
        n = self._some_namespaces()
        config = config_manager.ConfigurationManager(
          [n],
          manager_controls=False,
          use_config_files=False,
          auto_help=False,
          argv_source=[]
        )
        expected = """# name: aaa
# doc: the a
# converter: socorro.lib.datetimeutil.datetimeFromISOdateString
aaa=2011-05-04T15:10:00

#-------------------------------------------------------------------------------
# c - c space

# name: c.fred
# doc: husband from Flintstones
# converter: str
c.fred=stupid

# name: c.wilma
# doc: wife from Flintstones
# converter: str
c.wilma=waspish

#-------------------------------------------------------------------------------
# d - d space

# name: d.ethel
# doc: female neighbor from I Love Lucy
# converter: str
d.ethel=silly

# name: d.fred
# doc: male neighbor from I Love Lucy
# converter: str
d.fred=crabby

#-------------------------------------------------------------------------------
# x - x space

# name: x.password
# doc: the password
# converter: str
x.password=********

# name: x.size
# doc: how big in tons
# converter: int
x.size=100
"""
        out = StringIO()
        config.write_conf(output_stream=out)
        received = out.getvalue()
        self.assertEqual(expected.strip(), received.strip())

    def test_write_ini(self):
        n = self._some_namespaces()
        c = config_manager.ConfigurationManager(
          [n],
          manager_controls=False,
          use_config_files=False,
          auto_help=False,
          argv_source=[]
        )
        expected = """[top_level]
# name: aaa
# doc: the a
# converter: socorro.lib.datetimeutil.datetimeFromISOdateString
aaa=2011-05-04T15:10:00

[c]
# c space

# name: c.fred
# doc: husband from Flintstones
# converter: str
fred=stupid

# name: c.wilma
# doc: wife from Flintstones
# converter: str
wilma=waspish

[d]
# d space

# name: d.ethel
# doc: female neighbor from I Love Lucy
# converter: str
ethel=silly

# name: d.fred
# doc: male neighbor from I Love Lucy
# converter: str
fred=crabby

[x]
# x space

# name: x.password
# doc: the password
# converter: str
password=********

# name: x.size
# doc: how big in tons
# converter: int
size=100
"""
        out = StringIO()
        c.write_ini(output_stream=out)
        received = out.getvalue()
        out.close()
        self.assertEqual(expected.strip(), received.strip())

    def test_write_json(self):
        n = self._some_namespaces()
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        
        s = StringIO()
        c.write_json(output_stream=s)
        received = s.getvalue()
        s.close()
        jrec = json.loads(received)

        expect_to_find = {
          "short_form": "a", 
          "default": "2011-05-04T15:10:00", 
          "doc": "the a", 
          "value": "2011-05-04T15:10:00", 
          "from_string_converter": 
              "socorro.lib.datetimeutil.datetimeFromISOdateString",
          "name": "aaa"
        }
        self.assertEqual(jrec['aaa'], expect_to_find)
        
        # let's make sure that we can do a complete round trip
        c2 = config_manager.ConfigurationManager([jrec],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        s = StringIO()
        c2.write_json(output_stream=s)
        received2 = s.getvalue()
        s.close()
        jrec2 = json.loads(received2)
        self.assertEqual(jrec2['aaa'], expect_to_find)
    
    def test_overlay_config_1(self):
        n = config_manager.Namespace()
        n.a = config_manager.Option()
        n.a.name = 'a'
        n.a.default = 1
        n.a.doc = 'the a'
        n.b = 17
        n.c = c = config_manager.Namespace()
        c.x = 'fred'
        c.y = 3.14159
        c.z = config_manager.Option()
        c.z.default = 99
        c.z.doc = 'the 99'
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        o = { "a": 2, "c.z": 22, "c.x": 'noob', "c.y": "2.89" }
        c.overlay_config_recurse(o)
        d = c.get_config()
        e = DotDict()
        e.a = 2
        e.b = 17
        e.c = DotDict()
        e.c.x = 'noob'
        e.c.y = 2.89
        e.c.z = 22
        self.assertEqual(d, e)
    
    def test_overlay_config_2(self):
        n = config_manager.Namespace()
        n.a = config_manager.Option()
        n.a.name = 'a'
        n.a.default = 1
        n.a.doc = 'the a'
        n.b = 17
        n.c = c = config_manager.Namespace()
        c.x = 'fred'
        c.y = 3.14159
        c.z = config_manager.Option()
        c.z.default = 99
        c.z.doc = 'the 99'
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        o = { "a": 2, "c.z": 22, "c.x": 'noob', "c.y": "2.89", "n": "not here" }
        c.overlay_config_recurse(o, ignore_mismatches=True)
        d = c.get_config()
        e = DotDict()
        e.a = 2
        e.b = 17
        e.c = DotDict()
        e.c.x = 'noob'
        e.c.y = 2.89
        e.c.z = 22
        self.assertEqual(d, e)
    
    def test_overlay_config_3(self):
        n = config_manager.Namespace()
        n.a = config_manager.Option()
        n.a.name = 'a'
        n.a.default = 1
        n.a.doc = 'the a'
        n.b = 17
        n.c = c = config_manager.Namespace()
        c.x = 'fred'
        c.y = 3.14159
        c.z = config_manager.Option()
        c.z.default = 99
        c.z.doc = 'the 99'
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        output = {
          "a": 2, 
          "c.z": 22, 
          "c.x": 'noob', 
          "c.y": "2.89", 
          "c.n": "not here"
        }
        self.assertRaises(config_manager.NotAnOptionError,
                          c.overlay_config_recurse, output, 
                          ignore_mismatches=False)
    
    def test_overlay_config_4(self):
        """test overlay dict w/flat source dict"""
        n = config_manager.Namespace()
        n.a = config_manager.Option(name='a', doc='the a', default=1)
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(name='extra', 
                                          doc='the x', 
                                          default=3.14159)
        g = { 'a': 2, 'c.extra': 2.89 }
        c = config_manager.ConfigurationManager([n], [g],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        self.assertEqual(c.option_definitions.a, n.a)
        self.assertTrue(isinstance(c.option_definitions.b,
                                   config_manager.Option))
        self.assertEqual(c.option_definitions.a.value, 2)
        self.assertEqual(c.option_definitions.b.value, 17)
        self.assertEqual(c.option_definitions.b.default, 17)
        self.assertEqual(c.option_definitions.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 2.89)
    
    def test_overlay_config_4a(self):
        """test overlay dict w/deep source dict"""
        n = config_manager.Namespace()
        n.a = config_manager.Option(name='a', doc='the a', default=1)
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(name='extra', doc='the x', default=3.14159)
        g = { 'a': 2, 'c': {'extra': 2.89 }}
        c = config_manager.ConfigurationManager([n], [g],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        self.assertEqual(c.option_definitions.a, n.a)
        self.assertTrue(isinstance(c.option_definitions.b,
                                   config_manager.Option))
        self.assertEqual(c.option_definitions.a.value, 2)
        self.assertEqual(c.option_definitions.b.value, 17)
        self.assertEqual(c.option_definitions.b.default, 17)
        self.assertEqual(c.option_definitions.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 2.89)
    
    def test_overlay_config_5(self):
        """test namespace definition w/getopt"""
        n = config_manager.Namespace()
        n.a = config_manager.Option(name='a', doc='the a', default=1)
        n.b = 17
        n.c = config_manager.Option(name='c', doc='the c', default=False)
        g = config_manager.OptionsByGetopt(argv_source=['--a', '2', '--c'])
        c = config_manager.ConfigurationManager([n], [g],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        self.assertEqual(c.option_definitions.a, n.a)
        self.assertTrue(isinstance(c.option_definitions.b,
                                   config_manager.Option))
        self.assertEqual(c.option_definitions.a.value, 2)
        self.assertEqual(c.option_definitions.b.value, 17)
        self.assertEqual(c.option_definitions.b.default, 17)
        self.assertEqual(c.option_definitions.b.name, 'b')
        self.assertEqual(c.option_definitions.c.name, 'c')
        self.assertEqual(c.option_definitions.c.value, True)
    
    def test_overlay_config_6(self):
        """test namespace definition w/getopt"""
        n = config_manager.Namespace()
        n.a = config_manager.Option(name='a', doc='the a', default=1)
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(name='extra', short_form='e', doc='the x',
                              default=3.14159)
        g = config_manager.OptionsByGetopt(
          argv_source=['--a', '2', '--c.extra', '11.0']
        )
        c = config_manager.ConfigurationManager([n], [g],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False)
        self.assertEqual(c.option_definitions.a, n.a)
        self.assertEqual(type(c.option_definitions.b), config_manager.Option)
        self.assertEqual(c.option_definitions.a.value, 2)
        self.assertEqual(c.option_definitions.b.value, 17)
        self.assertEqual(c.option_definitions.b.default, 17)
        self.assertEqual(c.option_definitions.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 11.0)
    
    def test_overlay_config_6a(self):
        """test namespace w/getopt w/short form"""
        n = config_manager.Namespace()
        n.a = config_manager.Option(name='a', doc='the a', default=1)
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(
          name='extra',
          short_form='e', 
          doc='the x',
          default=3.14159
        )
        g = config_manager.OptionsByGetopt(
          argv_source=['--a', '2', '-e', '11.0']
        )
        c = config_manager.ConfigurationManager([n], [g],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False)
        self.assertEqual(c.option_definitions.a, n.a)
        self.assertEqual(type(c.option_definitions.b), config_manager.Option)
        self.assertEqual(c.option_definitions.a.value, 2)
        self.assertEqual(c.option_definitions.b.value, 17)
        self.assertEqual(c.option_definitions.b.default, 17)
        self.assertEqual(c.option_definitions.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 11.0)
    
    def test_overlay_config_7(self):
        """test namespace definition flat file"""
        n = config_manager.Namespace()
        n.a = config_manager.Option(name='a', doc='the a', default=1)
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(name='extra', doc='the x', 
                                          default=3.14159)
        n.c.string = config_manager.Option(name='string', doc='str', 
                                           default='fred')
        @contextmanager
        def dummy_open(filename):
            yield ['# comment line to be ignored\n',
                   '\n', # blank line to be ignored
                   'a=22\n',
                   'b = 33\n',
                   'c.extra = 2.0\n',
                   'c.string =   wilma\n'
                  ]
        g = config_manager.OptionsByConfFile('dummy-filename', dummy_open)
        c = config_manager.ConfigurationManager([n], [g],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False)
        self.assertEqual(c.option_definitions.a, n.a)
        self.assertEqual(type(c.option_definitions.b), config_manager.Option)
        self.assertEqual(c.option_definitions.a.value, 22)
        self.assertEqual(c.option_definitions.b.value, 33)
        self.assertEqual(c.option_definitions.b.default, 17)
        self.assertEqual(c.option_definitions.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 2.0)
        self.assertEqual(c.option_definitions.c.string.name, 'string')
        self.assertEqual(c.option_definitions.c.string.doc, 'str')
        self.assertEqual(c.option_definitions.c.string.default, 'fred')
        self.assertEqual(c.option_definitions.c.string.value, 'wilma')

    def test_overlay_config_8(self):
        """test namespace definition ini file"""
        n = config_manager.Namespace()
        n.other = config_manager.Namespace()
        n.other.t = config_manager.Option('t', 'the t', 'tee')
        n.d = config_manager.Namespace()
        n.d.a = config_manager.Option(name='a', doc='the a', default=1)
        n.d.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(
          name='extra', doc='the x', default=3.14159
        )
        n.c.string = config_manager.Option(
          name='string', doc='str', default='fred'
        )
        ini_data = """
[other]
t=tea
[d]
# blank line to be ignored
a=22
b = 33
[c]
extra = 2.0
string =   wilma
"""
        config = ConfigParser.RawConfigParser()
        config.readfp(io.BytesIO(ini_data))
        g = config_manager.OptionsByIniFile(config)
        c = config_manager.ConfigurationManager([n], [g],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False)
        self.assertEqual(c.option_definitions.other.t.name, 't')
        self.assertEqual(c.option_definitions.other.t.value, 'tea')
        self.assertEqual(c.option_definitions.d.a, n.d.a)
        self.assertEqual(type(c.option_definitions.d.b), config_manager.Option)
        self.assertEqual(c.option_definitions.d.a.value, 22)
        self.assertEqual(c.option_definitions.d.b.value, 33)
        self.assertEqual(c.option_definitions.d.b.default, 17)
        self.assertEqual(c.option_definitions.d.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 2.0)
        self.assertEqual(c.option_definitions.c.string.name, 'string')
        self.assertEqual(c.option_definitions.c.string.doc, 'str')
        self.assertEqual(c.option_definitions.c.string.default, 'fred')
        self.assertEqual(c.option_definitions.c.string.value, 'wilma')

    def test_overlay_config_9(self):
        """test namespace definition ini file"""
        n = config_manager.Namespace()
        n.other = config_manager.Namespace()
        n.other.t = config_manager.Option('t', 'the t', 'tee')
        n.d = config_manager.Namespace()
        n.d.a = config_manager.Option(name='a', doc='the a', default=1)
        n.d.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(name='extra', doc='the x', default=3.14159)
        n.c.string = config_manager.Option(name='string', doc='str', default='fred')
        ini_data = """
[other]
t=tea
[d]
# blank line to be ignored
a=22
[c]
extra = 2.0
string =   from ini
"""
        config = ConfigParser.RawConfigParser()
        config.readfp(io.BytesIO(ini_data))
        g = config_manager.OptionsByIniFile(config)
        e = DotDict()
        e.fred = DotDict()  # should be ignored
        e.fred.t = 'T'  # should be ignored
        e.d = DotDict()
        e.d.a = 16
        e.c = DotDict()
        e.c.extra = 18.6
        e.c.string = 'from environment'
        v = config_manager.OptionsByGetopt(
          argv_source=['--other.t', 'TTT', '--c.extra', '11.0']
        )
        c = config_manager.ConfigurationManager([n], [e, g, v],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False)
        self.assertEqual(c.option_definitions.other.t.name, 't')
        self.assertEqual(c.option_definitions.other.t.value, 'TTT')
        self.assertEqual(c.option_definitions.d.a, n.d.a)
        self.assertEqual(type(c.option_definitions.d.b), config_manager.Option)
        self.assertEqual(c.option_definitions.d.a.value, 22)
        self.assertEqual(c.option_definitions.d.b.value, 17)
        self.assertEqual(c.option_definitions.d.b.default, 17)
        self.assertEqual(c.option_definitions.d.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 11.0)
        self.assertEqual(c.option_definitions.c.string.name, 'string')
        self.assertEqual(c.option_definitions.c.string.doc, 'str')
        self.assertEqual(c.option_definitions.c.string.default, 'fred')
        self.assertEqual(c.option_definitions.c.string.value, 'from ini')

    def test_overlay_config_10(self):
        """test namespace definition ini file"""
        n = config_manager.Namespace()
        n.t = config_manager.Option('t', 'the t', 'tee')
        n.d = config_manager.Namespace()
        n.d.a = config_manager.Option(name='a', doc='the a', default=1)
        n.d.b = 17
        n.c = config_manager.Namespace()
        n.c.extra = config_manager.Option(name='extra', doc='the x', default=3.14159)
        n.c.string = config_manager.Option(name='string', doc='str', default='fred')
        ini_data = """
[top_level]
t=tea
[d]
# blank line to be ignored
a=22
[c]
extra = 2.0
string =   from ini
"""
        config = ConfigParser.RawConfigParser()
        config.readfp(io.BytesIO(ini_data))
        g = config_manager.OptionsByIniFile(config)
        e = DotDict()
        e.top_level = DotDict()
        e.top_level.t = 'T'
        e.d = DotDict()
        e.d.a = 16
        e.c = DotDict()
        e.c.extra = 18.6
        e.c.string = 'from environment'
        v = config_manager.OptionsByGetopt(
          argv_source=['--c.extra', '11.0']
        )
        c = config_manager.ConfigurationManager([n], [e, g, v],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False)
        self.assertEqual(c.option_definitions.t.name, 't')
        self.assertEqual(c.option_definitions.t.value, 'tea')
        self.assertEqual(c.option_definitions.d.a, n.d.a)
        self.assertEqual(type(c.option_definitions.d.b), config_manager.Option)
        self.assertEqual(c.option_definitions.d.a.value, 22)
        self.assertEqual(c.option_definitions.d.b.value, 17)
        self.assertEqual(c.option_definitions.d.b.default, 17)
        self.assertEqual(c.option_definitions.d.b.name, 'b')
        self.assertEqual(c.option_definitions.c.extra.name, 'extra')
        self.assertEqual(c.option_definitions.c.extra.doc, 'the x')
        self.assertEqual(c.option_definitions.c.extra.default, 3.14159)
        self.assertEqual(c.option_definitions.c.extra.value, 11.0)
        self.assertEqual(c.option_definitions.c.string.name, 'string')
        self.assertEqual(c.option_definitions.c.string.doc, 'str')
        self.assertEqual(c.option_definitions.c.string.default, 'fred')
        self.assertEqual(c.option_definitions.c.string.value, 'from ini')

    def test_walk_expanding_class_options(self):
        class A(config_manager.RequiredConfig):
            required_config = {
              'a': config_manager.Option('a', 'the a', 1),
              'b': 17,
            }
        n = config_manager.Namespace()
        n.source = config_manager.Namespace()
        n.source.c = config_manager.Option(name='c', default=A, doc='the A class')
        n.dest = config_manager.Namespace()
        n.dest.c = config_manager.Option(name='c', default=A, doc='the A class')
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        e = config_manager.Namespace()
        e.s = config_manager.Namespace()
        e.s.c = config_manager.Option(name='c', default=A, doc='the A class')
        e.s.a = config_manager.Option('a', 'the a', 1)
        e.s.b = config_manager.Option('b', default=17)
        e.d = config_manager.Namespace()
        e.d.c = config_manager.Option(name='c', default=A, doc='the A class')
        e.d.a = config_manager.Option('a', 'the a', 1)
        e.d.b = config_manager.Option('b', default=17)
        def namespace_test(val):
            self.assertEqual(type(val), config_manager.Namespace)
        def option_test(val, expected=None):
            self.assertEqual(val.name, expected.name)
            self.assertEqual(val.default, expected.default)
            self.assertEqual(val.doc, expected.doc)
        e = [ ('dest', 'dest', namespace_test),
              ('dest.a', 'a', functools.partial(option_test, expected=e.d.a)),
              ('dest.b', 'b', functools.partial(option_test, expected=e.d.b)),
              ('dest.c', 'c', functools.partial(option_test, expected=e.d.c)),
              ('source', 'source', namespace_test),
              ('source.a', 'a', functools.partial(option_test, expected=e.s.a)),
              ('source.b', 'b', functools.partial(option_test, expected=e.s.b)),
              ('source.c', 'c', functools.partial(option_test, expected=e.s.c)),
            ]
        c_contents = [(qkey, key, val) for qkey, key, val in c.walk_config()]
        c_contents.sort()
        e.sort()
        for c_tuple, e_tuple in zip(c_contents, e):
            qkey, key, val = c_tuple
            e_qkey, e_key, e_fn = e_tuple
            self.assertEqual(qkey, e_qkey)
            self.assertEqual(key, e_key)
            e_fn(val)
    
    def test_get_option_names(self):
        n = config_manager.Namespace()
        n.a = config_manager.Option('a', 'the a', 1)
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.fred = config_manager.Option('fred')
        n.c.wilma = config_manager.Option('wilma')
        n.d = config_manager.Namespace()
        n.d.fred = config_manager.Option('fred')
        n.d.wilma = config_manager.Option('wilma')
        n.d.x = config_manager.Namespace()
        n.d.x.size = config_manager.Option('size')
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        names = c.get_option_names()
        names.sort()
        e = ['a', 'b', 'c.fred', 'c.wilma', 'd.fred', 'd.wilma', 'd.x.size']
        e.sort()
        self.assertEqual(names, e)
    
    def test_get_option_by_name(self):
        n = config_manager.Namespace()
        n.a = config_manager.Option('a', 'the a', 1)
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.fred = config_manager.Option('fred')
        n.c.wilma = config_manager.Option('wilma')
        n.d = config_manager.Namespace()
        n.d.fred = config_manager.Option('fred')
        n.d.wilma = config_manager.Option('wilma')
        n.d.x = config_manager.Namespace()
        n.d.x.size = config_manager.Option('size')
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        self.assertEqual(c.get_option_by_name('a'), n.a)
        self.assertEqual(c.get_option_by_name('b').name, 'b')
        self.assertEqual(c.get_option_by_name('c.fred'), n.c.fred)
        self.assertEqual(c.get_option_by_name('c.wilma'), n.c.wilma)
        self.assertEqual(c.get_option_by_name('d.fred'), n.d.fred)
        self.assertEqual(c.get_option_by_name('d.wilma'), n.d.wilma)
        self.assertEqual(c.get_option_by_name('d.wilma'), n.d.wilma)
        self.assertEqual(c.get_option_by_name('d.x.size'), n.d.x.size)

    def XXXtest_output_summary():
        """test_output_summary: the output from help"""
        n = config_manager.Namespace()
        n.aaa = config_manager.Option('aaa', 'the a', False, short_form='a')
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.fred = config_manager.Option('fred', 'husband from Flintstones')
        n.c.wilma = config_manager.Option('wilma', 'wife from Flintstones')
        n.d = config_manager.Namespace()
        n.d.fred = config_manager.Option('fred', 'male neighbor from I Love Lucy')
        n.d.ethel = config_manager.Option('ethel', 'female neighbor from I Love Lucy')
        n.d.x = config_manager.Namespace()
        n.d.x.size = config_manager.Option('size', 'how big in tons', 100, short_form='s')
        n.d.x.password = config_manager.Option('password', 'the password', 'secrets')
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        s = StringIO()
        c.output_summary(output_stream=s)
        r = s.getvalue()
        s.close()
        e = """	-a, --aaa
		the a
	    --b
		no documentation available (default: 17)
	    --c.fred
		husband from Flintstones (default: None)
	    --c.wilma
		wife from Flintstones (default: None)
	    --d.ethel
		female neighbor from I Love Lucy (default: None)
	    --d.fred
		male neighbor from I Love Lucy (default: None)
	    --d.x.password
		the password (default: ********)
	-s, --d.x.size
		how big in tons (default: 100)
"""
        self.assertEqual(r, e)
    
    def test_eval_as_converter(self):
        """does eval work as a to string converter on an Option object?"""
        n = config_manager.Namespace()
        n.aaa = config_manager.Option('aaa', 'the a', False, short_form='a')
        n.b = 17
        n.c = config_manager.Namespace()
        n.c.fred = config_manager.Option('rules', 'the doc',
                             default="[ ('version', 'fred', 100), "
                                     "('product', 'sally', 100)]",
                             from_string_converter=eval)
        n.c.wilma = config_manager.Option('wilma', 'wife from Flintstones')
        c = config_manager.ConfigurationManager([n],
                                    manager_controls=False,
                                    use_config_files=False,
                                    auto_help=False,
                                    argv_source=[])
        s = StringIO()
        c.output_summary(output_stream=s)
        r = s.getvalue()
        s.close()
        e = """	-a, --aaa
		the a
	    --b
		no documentation available (default: 17)
	    --c.fred
		the doc (default: [('version', 'fred', 100), ('product', 'sally', 100)])
	    --c.wilma
		wife from Flintstones (default: None)
"""
        self.assertEqual(r, e)
        
    def test_setting_known_from_string_converter_on_Option(self):
        opt = config_manager.Option(default=u'Peter')
        self.assertEqual(opt.default, u'Peter')
        self.assertEqual(opt.from_string_converter, unicode)

        opt = config_manager.Option(default=100)
        self.assertEqual(opt.default, 100)
        self.assertEqual(opt.from_string_converter, int)

        opt = config_manager.Option(default=100L)
        self.assertEqual(opt.default, 100L)
        self.assertEqual(opt.from_string_converter, long)
        
        opt = config_manager.Option(default=100.0)
        self.assertEqual(opt.default, 100.0)
        self.assertEqual(opt.from_string_converter, float)
        
        from decimal import Decimal
        opt = config_manager.Option(default=Decimal('100.0'))
        self.assertEqual(opt.default, Decimal('100.0'))
        self.assertEqual(opt.from_string_converter, Decimal)
        
        opt = config_manager.Option(default=False)
        self.assertEqual(opt.default, False)
        self.assertEqual(opt.from_string_converter, 
                         config_manager.boolean_converter)
                         
        dt = datetime.datetime(2011, 8, 10, 0, 0, 0)
        opt = config_manager.Option(default=dt)
        self.assertEqual(opt.default, dt)
        self.assertEqual(opt.from_string_converter, 
                         datetimeutil.datetimeFromISOdateString)

        dt = datetime.date(2011, 8, 10)
        opt = config_manager.Option(default=dt)
        self.assertEqual(opt.default, dt)
        self.assertEqual(opt.from_string_converter, 
                         datetimeutil.dateFromISOdateString)
                         
    def test_boolean_converter_in_Option(self):
        opt = config_manager.Option(default=False)
        self.assertEqual(opt.default, False)
        self.assertEqual(opt.from_string_converter, 
                         config_manager.boolean_converter)
                         
        opt.set_value('true')
        self.assertEqual(opt.value, True)
        
        opt.set_value('false')
        self.assertEqual(opt.value, False)

        opt.set_value('1')
        self.assertEqual(opt.value, True)
        
        opt.set_value('t')
        self.assertEqual(opt.value, True)

        opt.set_value(True)
        self.assertEqual(opt.value, True)

        opt.set_value(False)
        self.assertEqual(opt.value, False)

        opt.set_value('False')
        self.assertEqual(opt.value, False)

        opt.set_value('True')
        self.assertEqual(opt.value, True)
        
        opt.set_value('None')
        self.assertEqual(opt.value, False)
        
        opt.set_value('YES')
        self.assertEqual(opt.value, True)

        opt.set_value(u'1')
        self.assertEqual(opt.value, True)
        
        opt.set_value(u'y')
        self.assertEqual(opt.value, True)

        opt.set_value(u't')
        self.assertEqual(opt.value, True)
        
    def test_timedelta_converter_in_Option(self):
        one_day = datetime.timedelta(days=1)
        opt = config_manager.Option(default=one_day)
        self.assertEqual(opt.default, one_day)
        self.assertEqual(opt.from_string_converter,
                         config_manager.timedelta_converter)
        
        two_days = datetime.timedelta(days=2)
        timedelta_as_string = datetimeutil.timedeltaToStr(two_days)
        assert isinstance(timedelta_as_string, basestring)
        opt.set_value(timedelta_as_string)
        self.assertEqual(opt.value, two_days)

        opt.set_value(unicode(timedelta_as_string))
        self.assertEqual(opt.value, two_days)
        
        opt.set_value(two_days)
        self.assertEqual(opt.value, two_days)

        self.assertRaises(config_manager.CannotConvertError, 
                          opt.set_value, 'JUNK')

        self.assertRaises(config_manager.CannotConvertError,
                          opt.set_value, '0:x:0:0')
                          
    def test_regexp_converter_in_Option(self):
        import re
        regex_str = '\w+'
        sample_regex = re.compile(regex_str)
        opt = config_manager.Option(default=sample_regex)
        self.assertEqual(opt.default, sample_regex)
        self.assertEqual(opt.from_string_converter,
                         config_manager.regex_converter)

        opt.set_value(regex_str)
        self.assertEqual(opt.value.pattern, sample_regex.pattern)

    def test_eval_as_converter(self):
        """does eval work as a to string converter on an Option object?"""
        n = config_manager.Namespace()
        n.option('aaa', doc='the a', default='', short_form='a')
        self.assertEqual(n.aaa.value, '')
        
    def test_setting_nested_namespaces(self):
        n = config_manager.Namespace()
        n.namespace('sub')
        sub_n = n.sub
        sub_n.option('name')
        self.assertTrue(n.sub)
        self.assertTrue(isinstance(n.sub.name, config_manager.Option))
        
    def test_editing_values_on_namespace(self):
        n = config_manager.Namespace()
        self.assertRaises(KeyError, n.set_value, 'name', 'Peter')
        n.option('name', 'Lars')
        n.set_value('name', 'Peter')
        self.assertTrue(n.name)
        self.assertEqual(n.name.value, 'Peter')
        n.namespace('user')
        n.user.option('age', 100)
        n.set_value('user.age', 200)
        self.assertTrue(n.user.age)
        self.assertEqual(n.user.age.value, 200)
        
        # let's not be strict once
        n.set_value('user.gender', u'male', strict=False)
        self.assertEqual(n.user.gender.value, u'male')
    
    def test_OptionsByConfFile_basics(self):
        tmp_filename = os.path.join(tempfile.gettempdir(), 'test.conf')
        with open(tmp_filename, 'w') as f:
            f.write('# comment\n')
            f.write('limit=20\n')
            f.write('\n')
        try:
            o = config_manager.OptionsByConfFile(tmp_filename)
            assert o.values == {'limit': '20'}, o.values
            c = config_manager.ConfigurationManager([],
                                        manager_controls=False,
                                        use_config_files=False,
                                        auto_help=False,
                                        argv_source=[])
                    
            self.assertEqual(o.get_values(c, False), {'limit': '20'})
            self.assertEqual(o.get_values(c, True), {'limit': '20'})
            # XXX (peterbe): commented out because I'm not sure if 
            # OptionsByConfFile get_values() should depend on the configuration
            # manager it is given as first argument or not.
            #self.assertEqual(o.get_values(c, True), {})
            #self.assertRaises(config_manager.NotAnOptionError,
            #                  o.get_values, c, False)
            
            #c.option_definitions.option('limit', default=0)
            #self.assertEqual(o.get_values(c, False), {'limit': '20'})
            #self.assertEqual(o.get_values(c, True), {'limit': '20'})
        finally:
            if os.path.isfile(tmp_filename):
                os.remove(tmp_filename)
    
    def test_OptionsByIniFile_basics(self):
        tmp_filename = os.path.join(tempfile.gettempdir(), 'test.conf')
        open(tmp_filename, 'w').write("""
; comment
[top_level]
name=Peter
awesome:
; comment
[othersection]
foo=bar  ; other comment
        """)
        
        try:
            o = config_manager.OptionsByIniFile(tmp_filename)
            c = config_manager.ConfigurationManager([],
                                        manager_controls=False,
                                        use_config_files=False,
                                        auto_help=False,
                                        argv_source=[])
                    
            self.assertEqual(o.get_values(c, False), 
                             {'othersection.foo': 'bar',
                              'name': 'Peter',
                              'awesome': ''})
            self.assertEqual(o.get_values(c, True), 
                             {'othersection.foo': 'bar',
                              'name': 'Peter',
                              'awesome': ''})
            # XXX (peterbe): commented out because I'm not sure if 
            # OptionsByIniFile get_values() should depend on the configuration
            # manager it is given as first argument or not.
            #self.assertEqual(o.get_values(c, True), {})
            #self.assertRaises(config_manager.NotAnOptionError,
            #                  o.get_values, c, False)
            
            #c.option_definitions.option('limit', default=0)
            #self.assertEqual(o.get_values(c, False), {'limit': '20'})
            #self.assertEqual(o.get_values(c, True), {'limit': '20'})
        finally:
            if os.path.isfile(tmp_filename):
                os.remove(tmp_filename)
                
    def test_RequiredConfig_get_required_config(self):
        class Foo:
            required_config = {'foo': True}
        class Bar:
            required_config = {'bar': False}
        class Poo:
            pass
        
        class Combined(config_manager.RequiredConfig, Foo, Poo, Bar):
            pass
        
        result = Combined.get_required_config()
        self.assertEqual(result, {'foo': True, 'bar': False})
        
    def test_create_ConfigurationManager_with_use_config_files(self):
        # XXX incomplete! (peter, 15 Aug)
        c = config_manager.ConfigurationManager([],
                                    manager_controls=False,
                                    use_config_files=True,
                                    auto_help=False,
                                    argv_source=[])
        
    
