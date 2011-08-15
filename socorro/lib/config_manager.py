#!/usr/bin/env python

import sys
import os
import getopt
import collections as coll
import datetime
import json
import ConfigParser
import types
import inspect
import os.path
import re

import socorro.lib.util as sutil
from socorro.lib import datetimeutil


#==============================================================================
class ConfigFileMissingError (IOError):
    pass


#==============================================================================
class ConfigFileOptionNameMissingError(Exception):
    pass


#==============================================================================
class NotAnOptionError(Exception):
    pass


#==============================================================================
class OptionError(Exception):
    pass


#==============================================================================
class CannotConvertError(ValueError):
    pass

#==============================================================================


#------------------------------------------------------------------------------
def boolean_converter(input_str):
    """ a conversion function for boolean
    """
    return input_str.lower() in ("true", "t", "1", "y", "yes")


#------------------------------------------------------------------------------
def timedelta_converter(input_str):
    """a conversion function for time deltas"""
    if isinstance(input_str, basestring):
        days, hours, minutes, seconds = 0, 0, 0, 0
        details = input_str.split(':')
        if len(details) >= 4:
            days = int(details[-4])
        if len(details) >= 3:
            hours = int(details[-3])
        if len(details) >= 2:
            minutes = int(details[-2])
        if len(details) >= 1:
            seconds = int(details[-1])
        return datetime.timedelta(days=days,
                                      hours=hours,
                                      minutes=minutes,
                                      seconds=seconds)
    raise ValueError(input_str)

#------------------------------------------------------------------------------
import __builtin__
_all_named_builtins = dir(__builtin__)
def class_converter(input_str):
    """ a conversion that will import a module and class name
    """
    if not input_str:
        return None
    if '.' not in input_str and input_str in _all_named_builtins:
        return eval(input_str)
    parts = input_str.split('.')
    try:
        # first try as a complete module
        package = __import__(input_str)
    except ImportError:
        # it must be a class from a module
        package = __import__('.'.join(parts[:-1]), globals(), locals(), [])
    obj = package
    for name in parts[1:]:
        obj = getattr(obj, name)
    return obj

#------------------------------------------------------------------------------
def regex_converter(input_str):
    return re.compile(input_str)

compiled_regexp_type = type(re.compile(r'x'))


#==============================================================================
class Option(object):

    #------------------------------------------------------------------------------
    from_string_converters = {
        bool: boolean_converter,
        datetime.datetime: datetimeutil.datetimeFromISOdateString,
        datetime.date: datetimeutil.dateFromISOdateString,
        datetime.timedelta: timedelta_converter,
        type: class_converter,
        types.FunctionType: class_converter,
        compiled_regexp_type: regex_converter,
    }

    #--------------------------------------------------------------------------
    def __init__(self,
                 name=None,
                 doc=None,
                 default=None,
                 from_string_converter=None,
                 value=None,
                 short_form=None,
                 *args,
                 **kwargs):
        self.name = name
        self.short_form = short_form
        self.default = default
        self.doc = doc
        if from_string_converter is None:
            if default is not None:
                # take a qualified guess from the default value
                from_string_converter = self._deduce_converter(default)
        if isinstance(from_string_converter, basestring):
            from_string_converter = class_converter(from_string_converter)
        self.from_string_converter = from_string_converter
        if value is None:
            value = default
        self.set_value(value)

    #--------------------------------------------------------------------------
    def _deduce_converter(self, default):
        default_type = type(default)
        return self.from_string_converters.get(default_type, default_type)


    #--------------------------------------------------------------------------
    def set_value(self, val):
        if isinstance(val, basestring):
            try:
                self.value = self.from_string_converter(val)
            except TypeError:
                self.value = val
            except ValueError:
                raise CannotConvertError(val)
        else:
            self.value = val

    #--------------------------------------------------------------------------
    @staticmethod
    def from_dict(a_dict):
        o = Option()
        for key, val in a_dict.items():
            setattr(o, key, val)
        return o

    #--------------------------------------------------------------------------
    def to_dict(self):
        return self.__dict__


#==============================================================================
class Namespace(sutil.DotDict):
    #--------------------------------------------------------------------------
    def __init__(self, doc=''):
        super(Namespace, self).__init__()
        object.__setattr__(self, '_doc', doc)  # force into attributes

    #--------------------------------------------------------------------------
    def __setattr__(self, name, value):
        if isinstance(value, (Option, Namespace)):
            # then they know what they're doing already
            o = value
        else:
            o = Option(name=name, default=value, value=value)
        self.__setitem__(name, o)

    #--------------------------------------------------------------------------
    def option(self,
               name,
               doc=None,
               default=None,
               from_string_converter=None,
               short_form=None,):
        an_option = Option(name=name,
                           doc=doc,
                           default=default,
                           from_string_converter=from_string_converter,
                           short_form=short_form)
        self[name] = an_option

    #--------------------------------------------------------------------------
    def namespace(self, name, doc=''):
        self[name] = Namespace(doc=doc)

    #--------------------------------------------------------------------------
    def set_value(self, name, value, strict=True):
        
        name_parts = name.split('.', 1)
        prefix = name_parts[0]
        try:
            candidate = self[prefix]
        except KeyError:
            if strict:
                raise
            self[prefix] = candidate = Option()
            candidate.name = prefix
        candidate_type = type(candidate)
        if candidate_type == Namespace:
            candidate.set_value(name_parts[1], value, strict)
        else:
            candidate.set_value(value)


#==============================================================================
class OptionsByGetopt(object):
    #--------------------------------------------------------------------------
    def __init__(self, argv_source=None):
        if argv_source is None:
            argv_source = sys.argv
        self.argv_source = argv_source

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches):
        short_options_str, \
        long_options_list = self.getopt_create_opts(
                             config_manager.option_definitions)
        try:
            if ignore_mismatches:
                fn = OptionsByGetopt.getopt_with_ignore
            else:
                fn = getopt.gnu_getopt
            getopt_options, self.args = fn(self.argv_source,
                                           short_options_str,
                                           long_options_list)
        except getopt.GetoptError, x:
            raise NotAnOptionError(str(x))
        command_line_values = sutil.DotDict()
        for opt_name, opt_val in getopt_options:
            if opt_name.startswith('--'):
                name = opt_name[2:]
            else:
                name = self.find_name_with_short_form(opt_name[1:],
                                            config_manager.option_definitions,
                                            '')
                if not name:
                    raise NotAnOptionError('%s is not a valid short '
                                           'form option' % opt_name[1:])
            option = config_manager.get_option_by_name(name)
            if option.from_string_converter == boolean_converter:
                command_line_values[name] = not option.default
            else:
                command_line_values[name] = opt_val
        return command_line_values

    #--------------------------------------------------------------------------
    def getopt_create_opts(self, option_definitions):
        short_options_list = []
        long_options_list = []
        self.getopt_create_opts_recursive(option_definitions,
                                          "",
                                          short_options_list,
                                          long_options_list)
        short_options_str = ''.join(short_options_list)
        return short_options_str, long_options_list

    #--------------------------------------------------------------------------
    def getopt_create_opts_recursive(self, source,
                                     prefix,
                                     short_options_list,
                                     long_options_list):
        for key, val in source.items():
            if type(val) == Option:
                boolean_option = type(val.default) == bool
                if val.short_form:
                    try:
                        if boolean_option:
                            if val.short_form not in short_options_list:
                                short_options_list.append(val.short_form)
                        else:
                            short_with_parameter = "%s:" % val.short_form
                            if short_with_parameter not in short_options_list:
                                short_options_list.append(short_with_parameter)
                    except AttributeError:
                        pass
                if boolean_option:
                    long_options_list.append('%s%s' % (prefix, val.name))
                else:
                    long_options_list.append('%s%s=' % (prefix, val.name))
            else:  # Namespace case
                new_prefix = '%s%s.' % (prefix, key)
                self.getopt_create_opts_recursive(val,
                                                  new_prefix,
                                                  short_options_list,
                                                  long_options_list)

    #--------------------------------------------------------------------------
    @staticmethod
    def getopt_with_ignore(args, shortopts, longopts=[]):
        """my_getopt(args, options[, long_options]) -> opts, args

        This function works like gnu_getopt(), except that unknown parameters
        are ignored rather than raising an error.
        """
        opts = []
        prog_args = []
        if isinstance(longopts, str):
            longopts = [longopts]
        else:
            longopts = list(longopts)
        while args:
            if args[0] == '--':
                prog_args += args[1:]
                break
            if args[0][:2] == '--':
                try:
                    opts, args = getopt.do_longs(opts, args[0][2:],
                                                 longopts, args[1:])
                except getopt.GetoptError:
                    prog_args.append(args[0])
                    args = args[1:]
            elif args[0][:1] == '-':
                try:
                    opts, args = getopt.do_shorts(opts, args[0][1:], shortopts,
                                                  args[1:])
                except getopt.GetoptError:
                    prog_args.append(args[0])
                    args = args[1:]
            else:
                prog_args.append(args[0])
                args = args[1:]
        return opts, prog_args

    #--------------------------------------------------------------------------
    def find_name_with_short_form(self, short_name, source, prefix):
        for key, val in source.items():
            type_of_val = type(val)
            if type_of_val == Namespace:
                prefix = '%s.' % key
                name = self.find_name_with_short_form(short_name, val, prefix)
                if name:
                    return name
            else:
                try:
                    if short_name == val.short_form:
                        return '%s%s' % (prefix, val.name)
                except KeyError:
                    continue
        return None


#==============================================================================
class OptionsByConfFile(object):
    #--------------------------------------------------------------------------
    def __init__(self, filename, opener=open):
        self.values = {}
        with opener(filename) as f:
            previous_key = None
            for line in f:
                if line.strip().startswith('#') or not line.strip():
                    continue
                if line[0] in ' \t' and previous_key:
                    line = line[1:]
                    self.values[previous_key] = '%s%s' % \
                                        (self.values[previous_key], line.rstrip())
                    continue
                try:
                    key, value = line.split("=", 1)
                    self.values[key.strip()] = value.strip()
                    previous_key = key
                except ValueError:
                    self.values[line] = ''

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches):
        return self.values


#==============================================================================
class OptionsByIniFile(object):
    #--------------------------------------------------------------------------
    def __init__(self, source,
                 top_level_section_name='top_level'):
        if isinstance(source, basestring):
            parser = ConfigParser.RawConfigParser()
            parser.optionxform = str
            parser.read(source)
            self.configparser = parser
        else:  # a real config parser was loaded
            self.configparser = source
        self.top_level_section_name = top_level_section_name

    #--------------------------------------------------------------------------
    def get_values(self, config_manager, ignore_mismatches):
        sections_list = self.configparser.sections()
        options = {}
        for a_section in sections_list:
            if a_section == self.top_level_section_name:
                prefix = ''
            else:
                prefix = "%s." % a_section
            for an_option in self.configparser.options(a_section):
                name = '%s%s' % (prefix, an_option)
                options[name] = self.configparser.get(a_section, an_option)
                
                # XXX (peterbe): why these two lines? How can they ever happen?
                if options[name] == None:
                    options[name] = True
                    
        return options


#==============================================================================
class RequiredConfig(object):
    #--------------------------------------------------------------------------
    @classmethod
    def get_required_config(cls):
        result = {}
        for a_class in cls.__mro__:
            try:
                result.update(a_class.required_config)
            except AttributeError:
                pass
        return result

    #--------------------------------------------------------------------------
    def config_assert(self, config):
        for a_parameter in self.required_config.keys():
            assert a_parameter in config, \
                   '%s missing from config' % a_parameter


#==============================================================================
class ConfigurationManager(object):

    #--------------------------------------------------------------------------
    def __init__(self,
                 definition_source_list=None,
                 settings_source_list=None,
                 argv_source=None,
                 use_config_files=True,
                 auto_help=True,
                 manager_controls=True,
                 quit_after_admin=True,
                 options_banned_from_help=None,
                 ):
        # instead of allowing mutables as default keyword argument values...
        if definition_source_list is None:
            definition_source_list = []
        if settings_source_list is None:
            settings_source_list = []
        if argv_source is None:
            argv_source = sys.argv[1:]
        if options_banned_from_help is None:
            options_banned_from_help = ['_application']

        self.option_definitions = Namespace()
        self.definition_source_list = definition_source_list
        if settings_source_list:
            self.custom_settings_source = True
            self.settings_source_list = settings_source_list
        else:
            self.custom_settings_source = False
            command_line_options = OptionsByGetopt(argv_source=argv_source)
            self.settings_source_list = [os.environ,
                                         command_line_options,
                                        ]
        self.auto_help = auto_help
        self.help = False
        self.admin_tasks_done = False
        self.manager_controls = manager_controls
        self.manager_controls_list = ['help', '_write', 'config_path',
                                      '_application']
        self.options_banned_from_help = options_banned_from_help

        if self.auto_help:
            self.setup_auto_help()
        if self.manager_controls:
            self.setup_manager_controls()

        for a_definition_source in self.definition_source_list:
            self.setup_definitions(a_definition_source)

        # first pass to get classes & config path - ignore bad options
        self.overlay_settings(ignore_mismatches=True)

        # read config files
        if use_config_files and not self.custom_settings_source:
            self.read_config_files()
            # second pass to include config file values - ignore bad options
            self.settings_source_list = [self.ini_source,
                                         self.conf_source,
                                         self.json_source,
                                         os.environ,
                                         command_line_options]
            self.overlay_settings(ignore_mismatches=True)

        # walk tree expanding class options
        self.walk_expanding_class_options()

        # third pass to get values - complain about bad options
        self.overlay_settings(ignore_mismatches=False)

        if self.auto_help and self.get_option_by_name('help').value:
            self.output_summary()
            self.help = True
            self.admin_tasks_done = True

        if self.manager_controls and self.get_option_by_name('_write').value:
            self.write_config()
            self.admin_tasks_done = True

        if quit_after_admin and self.admin_tasks_done:
            exit()

    #--------------------------------------------------------------------------
    def read_config_files(self):
	# try ini file
        app = self.get_option_by_name('_application')
        try:
            application_name = app.value.app_name
        except AttributeError:
            self.ini_source = None
            self.conf_source = None
            self.json_source = None
            return
        path = self.get_option_by_name('config_path').value
        file_name = os.path.join(path, '%s.ini' % application_name)
        self.ini_source = OptionsByIniFile(file_name)
        # try conf file
        file_name = os.path.join(path, '%s.conf' % application_name)
        self.conf_source = OptionsByConfFile(file_name)
        # try json file
        file_name = os.path.join(path, '%s.json' % application_name)
        try:
            with open(file_name) as j_file:
                self.json_source = json.load(j_file)
        except IOError:
            self.json_source = {}

    #--------------------------------------------------------------------------
    def walk_expanding_class_options(self, source=None):
        if source is None:
            source = self.option_definitions
        expanded_keys = []
        expansions_were_done = True
        while expansions_were_done:
            expansions_were_done = False
            # can't use iteritems in loop, we're changing the dict
            for key, val in source.items():
                if isinstance(val, Namespace):
                    self.walk_expanding_class_options(val)
                elif (key not in expanded_keys and
                        (inspect.isclass(val.value) or
                         inspect.ismodule(val.value))):
                    expanded_keys.append(key)
                    expansions_were_done = True
                    try:
                        for o_key, o_val in \
                                val.value.get_required_config().iteritems():
                            source.__setattr__(o_key, o_val)
                    except AttributeError:
                        pass  # there are no required_options for this class
                else:
                    pass  # don't need to touch other types of Options
            self.overlay_settings(ignore_mismatches=True)

    #--------------------------------------------------------------------------
    def setup_auto_help(self):
        help_option = Option(name='help', doc='print this', default=False)
        self.definition_source_list.append({'help': help_option})

    #--------------------------------------------------------------------------
    def setup_manager_controls(self):
        manager_options = Namespace()
        manager_options._write = Option(name='_write',
                                        doc='write config file to stdout '
                                            '(conf, ini, json)',
                                        default=None,
                                        )
        #manager_options._quit = Option(name='_quit',
                                       #doc='quit after doing admin commands',
                                       #default=False)
        manager_options.config_path = Option(name='config_path',
                                                 doc='path for config file '
                                                     '(not the filename)',
                                                 default='./')
        self.definition_source_list.append(manager_options)

    #--------------------------------------------------------------------------
    def setup_definitions(self, source):
        if isinstance(source, coll.Mapping):
            self.setup_definitions_for_mappings(source,
                                                self.option_definitions)
            return
        source_type = type(source)
        if source_type == type(coll):  # how do you get the Module type?
            module_dict = source.__dict__.copy()
            del module_dict['__builtins__']
            self.setup_definitions_for_mappings(module_dict,
                                                self.option_definitions)
        elif source_type == list:
            self.setup_definitions_for_tuple_list(source,
                                                  self.option_definitions)
        elif source_type == str:  # it must be json
            import json
            self.setup_definitions_for_mappings(json.loads(source),
                                                self.option_definitions)
        else:
            pass

    #--------------------------------------------------------------------------
    def setup_definitions_for_mappings(self, source, destination):
        if 1:#try:
            for key, val in source.items():
                if key.startswith('__'):
                    continue  # ignore these
                val_type = type(val)
                if val_type == Option:
                    destination[key] = val
                    if not val.name:
                        val.name = key
                    val.set_value(val.default)
                elif isinstance(val, coll.Mapping):
                    if 'name' in val and 'default' in val:
                        # this is an option, not a namespace
                        destination[key] = d = Option(**val)
                    else:
                        # this is a namespace
                        try:
                            destination[key] = d = Namespace(doc=val._doc)
                        except AttributeError:
                            destination[key] = d = Namespace()
                        # recurse!
                        self.setup_definitions_for_mappings(val, d)
                elif val_type in [int, float, str, unicode]:
                    destination[key] = Option(name=key,
                                              doc=key,
                                              default=val)
                else:
                    pass
        else:#except AttributeError:
            pass

    #--------------------------------------------------------------------------
    def setup_definitions_for_tuple_list(self, source, destination):
        for option in source:
            short_form,  long_form, parameters, default, doc = option[:5]
            converter = None
            combo = None
            converter = None
            number_of_entries = len(option)
            if number_of_entries == 6:
                option5 = option[5]
                if isinstance(option5, coll.Iterable):
                    combo = option5
                elif isinstance(option5, coll.Callable):
                    converter = option5
                else:
                    converter = None
            elif number_of_entries < 5 or number_of_entries > 6:
                raise OptionError('option tuple %s has incorrect number of '
                                  'parameters' % str(option))
            if not parameters:
                converter = boolean_converter
                default = bool(default)

            # TODO: This needs review
            namespaces = long_form.split('.')
            a_namespace = destination
            for a_namespace_name in namespaces[:-1]:
                a_namespace = a_namespace.setdefault(a_namespace_name,
                                                     Namespace())
            name = namespaces[-1]
            o = Option(name=name,
                       doc=doc,
                       default=default,
                       short_form=short_form,
                       from_string_coverter=converter,

                       )
            if combo:  # this is rather unimplemented
                o.combo = combo
            a_namespace[o.name] = o

    #--------------------------------------------------------------------------
    def overlay_settings(self, ignore_mismatches=True):
        for a_settings_source in self.settings_source_list:
            if isinstance(a_settings_source, coll.Mapping):
                self.overlay_config_recurse(a_settings_source,
                                            ignore_mismatches=True)
            elif a_settings_source:
                options = a_settings_source.get_values(self,
                                        ignore_mismatches=ignore_mismatches)
                self.overlay_config_recurse(options,
                                        ignore_mismatches=ignore_mismatches)

    #--------------------------------------------------------------------------
    def overlay_config_recurse(self, source, destination=None, prefix='',
                                ignore_mismatches=True):
        if destination is None:
            destination = self.option_definitions
        for key, val in source.items():
            try:
                sub_destination = destination
                for subkey in key.split('.'):
                    sub_destination = sub_destination[subkey]
            except KeyError:
                if ignore_mismatches:
                    continue
                if key == subkey:
                    raise NotAnOptionError('%s is not an option' % key)
                raise NotAnOptionError('%s subpart %s is not an option' %
                                       (key, subkey))
            except TypeError:
                pass
            if isinstance(sub_destination, Namespace):
                self.overlay_config_recurse(val, sub_destination,
                                            prefix=('%s.%s' % (prefix, key)))
            else:
                sub_destination.set_value(val)

    #--------------------------------------------------------------------------
    def walk_config_copy_values(self, source, destination):
        for key, val in source.items():
            value_type = type(val)
            if value_type == Option:
                destination[key] = val.value
            elif value_type == Namespace:
                destination[key] = d = sutil.DotDict()
                self.walk_config_copy_values(val, d)

    #--------------------------------------------------------------------------
    @staticmethod
    def option_sort(x_tuple):
        key, val = x_tuple
        if isinstance(val, Namespace):
            return 'zzzzzzzzzzz%s' % key
        else:
            return key

    #--------------------------------------------------------------------------
    def walk_config(self, source=None, prefix=''):
        if source == None:
            source = self.option_definitions
        options_list = source.items()
        options_list.sort(key=ConfigurationManager.option_sort)
        for key, val in options_list:
            qualified_key = '%s%s' % (prefix, key)
            value_type = type(val)
            if value_type == Option:
                yield qualified_key, key, val
            elif value_type == Namespace:
                yield qualified_key, key, val
                new_prefix = '%s%s.' % (prefix, key)
                for xqkey, xkey, xval in self.walk_config(val, new_prefix):
                    yield xqkey, xkey, xval

    #--------------------------------------------------------------------------
    def get_config(self):
        config = sutil.DotDict()
        self.walk_config_copy_values(self.option_definitions, config)
        return config

    #get definition from classes in defaults

    #--------------------------------------------------------------------------
    def get_option_by_name(self, name):
        source = self.option_definitions
        for sub_name in name.split('.'):
            candidate = source[sub_name]
            if isinstance(candidate, Option):
                return candidate
            else:
                source = candidate
        raise NotAnOptionError('%s is not a known option name' % name)

    #--------------------------------------------------------------------------
    def get_option_names(self, source=None, names=None, prefix=''):
        if not source:
            source = self.option_definitions
        if names is None:
            names = []
        for key, val in source.items():
            if isinstance(val, Namespace):
                new_prefix = '%s%s.' % (prefix, key)
                self.get_option_names(val, names, new_prefix)
            else:
                names.append("%s%s" % (prefix, key))
        return names

    #--------------------------------------------------------------------------
    def get_options(self, source=None, options=None, prefix=''):
        if not source:
            source = self.option_definitions
        if options is None:
            options = []
        for key, val in source.items():
            if isinstance(val, Namespace):
                new_prefix = '%s%s.' % (prefix, key)
                self.get_options(val, options, new_prefix)
            else:
                options.append(("%s%s" % (prefix, key), val))
        return options

    #--------------------------------------------------------------------------
    def output_summary(self,
                       output_stream=sys.stdout,
                       output_template="--{name}\n\t\t{doc} (default: "
                                       "{default})",
                       bool_output_template="--{name}\n\t\t{doc}",
                       short_form_template="\t-{short_form}, ",
                       no_short_form_template="\t    ",
                       block_password=True):
        """outputs the list of acceptable commands.  This is useful as the
        output of the 'help' option or usage.

        Parameters:
          outputStream: where to send the output
          sortOption: 0 - sort by the single character option
                      1 - sort by the long option
          with_parameters_template: a string template for
          outputing options that have parameters from the long form onward
          outputTemplateForOptionsWithoutParameters: a string template for
          outputing options that have no parameters from the long form onward
          short_form_template: a string template for the first
          part of a listing where there is a single letter form of the command
          outputTemplatePrefixForNo: a string template for the first part of a
          listing where there is no single letter form of the command
        """
        try:
            app = self.get_option_by_name('_application')
            try:
                print >> output_stream, "%s %s" % (app.value.app_name,
                                                   app.value.app_version)
            except AttributeError, x:
                pass
            try:
                print >> output_stream, app.value.app_doc
            except AttributeError:
                pass
        except KeyError:
            pass  # there is no _application class
        names_list = self.get_option_names()
        names_list.sort()
        for x in names_list:
            if x in self.options_banned_from_help:
                continue
            option = self.get_option_by_name(x)
            if option.short_form:
                prefix = short_form_template
            else:
                prefix = no_short_form_template
            if isinstance(option.value, bool):
                template = bool_output_template
            else:
                template = output_template
            output_parameters = option.__dict__.copy()
            output_parameters['name'] = x
            if output_parameters['doc'] == None:
                output_parameters['doc'] = 'no documentation available'
            if block_password and 'password' in option.name.lower():
                output_parameters['default'] = '********'
                output_parameters['value'] = '********'
            template = '%s%s' % (prefix, template)
            # in the following line, we want the default to show the values
            # that have been read it from config files.  In other words,
            # we want to show the user what the values will be if they
            # make no further action
            try:
                value = output_parameters['value']
                type_of_value = type(value)
                converter_function = to_string_converters[type_of_value]
                output_parameters['default'] = converter_function(value)
            except KeyError:
                output_parameters['default'] = output_parameters['value']
            print >> output_stream, template.format(**output_parameters)

    #--------------------------------------------------------------------------
    def write_config(self):
        config_file_type = self.get_option_by_name('_write').value
        if config_file_type not in ('conf', 'ini', 'json'):
            raise Exception('unknown config file type')
        app = self.get_option_by_name('_application')
        try:
            app_name = app.value.app_name
        except AttributeError, x:
            app_name = 'unknown-app'
        config_file_name = os.sep.join(
            [self.get_option_by_name('config_path').value,
             '%s.%s' % (app_name, config_file_type)])
        with open(config_file_name, 'w') as f:
            if config_file_type == 'conf':
                self.write_conf(output_stream=f,
                                block_password=False)
            elif config_file_type == 'ini':
                self.write_ini(output_stream=f,
                               block_password=False)
            elif config_file_type == 'json':
                self.write_json(output_stream=f,
                                block_password=False)

    #--------------------------------------------------------------------------
    def option_value_str(self, an_option):
        if an_option.value is None:
            return ''
        try:
            s = to_string_converters[type(an_option.value)](an_option.value)
        except KeyError:
            if type(an_option.value) is not str:
                s = str(an_option.value)
            else:
                s = an_option.value
        return s

    #--------------------------------------------------------------------------
    def write_conf(self,
                   output_stream=sys.stdout,
                   block_password=True,
                   comments=True):
        for qkey, key, val in self.walk_config(self.option_definitions):
            if qkey in self.manager_controls_list:
                continue
            if isinstance(val, Option):
                if comments:
                    print >> output_stream, '# name:', qkey
                    print >> output_stream, '# doc:', val.doc
                    print >> output_stream, '# converter:', \
                        classes_and_functions_to_str(val.from_string_converter)
                if block_password and 'password' in val.name.lower():
                    print >> output_stream, '%s=********\n' % qkey
                else:
                    val_str = self.option_value_str(val)
                    print >> output_stream, '%s=%s\n' % (qkey, val_str)
            else:
                print >> output_stream, '#%s' % ('-' * 79)
                print >> output_stream, '# %s - %s\n' % (key, val._doc)

    #--------------------------------------------------------------------------
    def write_ini(self,
                  output_stream=sys.stdout,
                  block_password=True):
        print >> output_stream, '[top_level]'
        for qkey, key, val in self.walk_config(self.option_definitions):
            if qkey in self.manager_controls_list:
                continue
            if isinstance(val, Namespace):
                print >> output_stream, '[%s]' % key
                print >> output_stream, '# %s\n' % val._doc
            else:
                print >> output_stream, '# name:', qkey
                print >> output_stream, '# doc:', val.doc
                print >> output_stream, '# converter:', \
                      classes_and_functions_to_str(val.from_string_converter)
                if block_password and 'password' in val.name.lower():
                    print >> output_stream, '%s=********\n' % key
                else:
                    val_str = self.option_value_str(val)
                    print >> output_stream, '%s=%s\n' % (key, val_str)

    #--------------------------------------------------------------------------
    def str_safe_option_definitions(self, source=None, destination=None):
        """ creats a string only dictionary of the option definitions"""
        if source is None:
            source = self.option_definitions
        if destination is None:
            destination = sutil.DotDict()
        try:
            for key, val in source.items():
                if key in self.manager_controls_list:
                    continue
                if key.startswith('__'):
                    continue  # ignore these
                val_type = type(val)
                if val_type == Option:
                    destination[key] = d = sutil.DotDict(val.__dict__.copy())
                    for attr in ['default', 'value', 'from_string_converter']:
                        try:
                            attr_type = type(d[attr])
                            f = to_string_converters[attr_type]
                            d[attr] = f(d[attr])
                        except KeyError:
                            pass
                elif isinstance(val, coll.Mapping):
                    # this is a namespace
                    destination[key] = d = sutil.DotDict()
                    self.str_safe_option_definitions(val, d)
                else:
                    pass
        except AttributeError:
            pass
        return destination

    #--------------------------------------------------------------------------
    def write_json(self,
                   output_stream=sys.stdout,
                   block_password=True):
        json_dict = self.str_safe_option_definitions()
        json_str = json.dumps(json_dict)
        print >> output_stream, json_str

    #--------------------------------------------------------------------------
    def log_config(self, logger):
        app = self.get_option_by_name('_application')
        try:
            logger.info("app_name: %s", app.value.app_name)
            logger.info("app_version: %s", app.value.app_version)
        except AttributeError, x:
            pass
        logger.info("current configuration:")
        config = [(qkey, val.value) for qkey, key, val in
                                      self.walk_config(self.option_definitions)
                                    if qkey not in self.manager_controls_list
                                       and not isinstance(val, Namespace)]
        config.sort()
        for key, val in config:
            if 'password' in key.lower():
                logger.info('%s: *********', key)
            else:
                try:
                    logger.info('%s: %s', key,
                                to_string_converters[type(key)](val))
                except KeyError:
                    logger.info('%s: %s', key, val)


#------------------------------------------------------------------------------
def classes_and_functions_to_str(a_thing):
    if a_thing is None:
        return ''
    if inspect.ismodule(a_thing):
        return a_thing.__name__
    if a_thing.__module__ == '__builtin__':
        return a_thing.__name__
    return "%s.%s" % (a_thing.__module__, a_thing.__name__)


#------------------------------------------------------------------------------
to_string_converters = {int: str,
                        float: str,
                        str: str,
                        unicode: unicode,
                        bool: lambda x: 'True' if x else 'False',
                        datetime.datetime: datetimeutil.datetimeToISOdateString,
                        datetime.timedelta: datetimeutil.timedeltaToStr,
                        type: classes_and_functions_to_str,
                        types.FunctionType: classes_and_functions_to_str,
                        compiled_regexp_type: lambda x: x.pattern,
                        }



#------------------------------------------------------------------------------
def new_configuration(configurationModule=None,
                      applicationName=None,
                     ):
    definition_source = []
    if configurationModule:
        definition_source.append(configurationModule)
    config_manager = ConfigurationManager(definition_source,
                                          auto_help=True,
                                          application_name=applicationName)
    return config_manager.get_config()

#==============================================================================
if __name__ == "__main__":
    pass

