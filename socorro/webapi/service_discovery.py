
import sys
import os.path
import os
import itertools

import socorro.lib.memoize as mem
import socorro.webapi.class_partial as cpart
import socorro.lib.config_manager as cm

#-------------------------------------------------------------------------------
def discover_services_iter(service_path, ospath=os.path, os=os):
    """this generator searches for the socorro.services directory, then on
    finding it, reads the list of modules in that directory.  For each
    module that it finds with a name ending with 'service.py', it finds the
    classes within that have names ending with 'Service'.  This list of
    classes is then yielded by the iterator.

    service_path: a fragment of a path such as 'socorro/services'"""
    socorro_services_dir = None
    for p in sys.path:
        target = os.sep.join((p, service_path))
        if ospath.isdir(target):
            socorro_services_dir = target
            break
    if not socorro_services_dir:
        return
    files = os.listdir(socorro_services_dir)
    service_dotted_path = service_path.replace(os.sep, '.')
    for f in files:
        if f.endswith('service.py'):
            module_name = '%s.%s' % (service_dotted_path, f[:-3])
            module = cm.class_converter(module_name)
            service_class_names = (x for x in dir(module)
                                     if x.endswith('Service'))
            for x in service_class_names:
                yield getattr(module, x)

#-------------------------------------------------------------------------------
@mem.memoize()
def discover_services(service_path, ospath=os.path, os=os):
    r = [x for x in discover_services_iter(service_path,
                                              ospath=os.path,
                                              os=os)]
    return r

#-------------------------------------------------------------------------------
def get_services(config, service_path):
    """returns a tuple of uri/service class pairs compatible with the
    web.py framework.
    service_path: a fragment of a path such as 'socorro/services'"""
    service_classes = discover_services(service_path)
    uri_class_iter = ((x.uri, cpart.classWithPartialInit(x, config))
                         for x in service_classes)
    return tuple(itertools.chain(*uri_class_iter))
