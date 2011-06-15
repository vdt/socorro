#! /usr/bin/env python

#-------------------------------------------------------------------------------
def main(config):
  p = config.processorClass(config)
  p.start()

#===============================================================================
# any routine that uses this module and the ConfigurationManager should have
# these options defined:
import socorro.lib.config_manager as cm
#-------------------------------------------------------------------------------
app_name = 'processor'
version = '2.0'
doc = """The processor"""
#-------------------------------------------------------------------------------
rc = cm.Namespace()
rc.option('processorClass',
          doc='the class of the processor',
          default='socorro.processor.external_processor.'
                  'ProcessorWithExternalBreakpad',
          from_string_converter=cm.class_converter)

#-------------------------------------------------------------------------------
def get_required_config():
    n = cm.Namespace()
    n.update(rc)
    return n
#-------------------------------------------------------------------------------
if __name__ == '__main__':
    import socorro.app.genericApp as gapp
    import sys
    gapp.main(sys.modules[__name__])
