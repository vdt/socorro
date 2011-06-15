import socorro.collector.throttler as th
import socorro.lib.util as util

import re


def testLegacyThrottler():
  config = util.DotDict()
  config.logger = util.SilentFakeLogger()
  config.throttleConditions = [ ('alpha', re.compile('ALPHA'), 100),
                                ('beta',  'BETA', 100),
                                ('gamma', lambda x: x == 'GAMMA', 100),
                                ('delta', True, 100),
                                (None, True, 0)
                              ]
  config.minimalVersionForUnderstandingRefusal = { 'product1': '3.5', 'product2': '4.0' }
  config.neverDiscard = False
  thr = th.LegacyThrottler(config)
  expected = 5
  actual = len(thr.processedThrottleConditions)
  assert expected == actual, "expected thr.preprocessThrottleConditions to have length %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.0',
                         'alpha':'ALPHA',
                       })
  expected = False
  actual = thr.understandsRefusal(json1)
  assert expected == actual, "understand refusal expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.6',
                         'alpha':'ALPHA',
                       })
  expected = True
  actual = thr.understandsRefusal(json1)
  assert expected == actual, "understand refusal expected %d, but got %d instead" % (expected, actual)

  expected = th.LegacyThrottler.ACCEPT
  actual = thr.throttle(json1)
  assert expected == actual, "regexp throttle expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.4',
                         'alpha':'not correct',
                       })
  expected = th.LegacyThrottler.DEFER
  actual = thr.throttle(json1)
  assert expected == actual, "regexp throttle expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.6',
                         'alpha':'not correct',
                       })
  expected = th.LegacyThrottler.DISCARD
  actual = thr.throttle(json1)
  assert expected == actual, "regexp throttle expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.6',
                         'beta':'BETA',
                       })
  expected = th.LegacyThrottler.ACCEPT
  actual = thr.throttle(json1)
  assert expected == actual, "string equality throttle expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.6',
                         'beta':'not BETA',
                       })
  expected = th.LegacyThrottler.DISCARD
  actual = thr.throttle(json1)
  assert expected == actual, "string equality throttle expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.6',
                         'gamma':'GAMMA',
                       })
  expected = th.LegacyThrottler.ACCEPT
  actual = thr.throttle(json1)
  assert expected == actual, "string equality throttle expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.6',
                         'gamma':'not GAMMA',
                       })
  expected = th.LegacyThrottler.DISCARD
  actual = thr.throttle(json1)
  assert expected == actual, "string equality throttle expected %d, but got %d instead" % (expected, actual)

  json1 = util.DotDict({ 'ProductName':'product1',
                         'Version':'3.6',
                         'delta':"value doesn't matter",
                       })
  expected = th.LegacyThrottler.ACCEPT
  actual = thr.throttle(json1)
  assert expected == actual, "string equality throttle expected %d, but got %d instead" % (expected, actual)

