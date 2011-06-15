import socorro.lib.config_manager as cm
import socorro.lib.ver_tools as vtl

import re
import random

compiledRegularExpressionType = type(re.compile(''))
functionType = type(lambda x: x)

#===============================================================================
class LegacyThrottler(cm.RequiredConfig):
    required_config = _rc = cm.Namespace()
    _rc.option('throttleConditions',
               doc='the list of throttle conditions',
               default="""[
    ("Comments", lambda x: x, 100), # 100% of crashes with comments
    ("ReleaseChannel", lambda x: x in ("nightly", "aurora", "beta"), 100),
    ("ProductName", 'Firefox', 10), # 10% of Firefox
    ("Version", re.compile(r'\..*?[a-zA-Z]+'), 100), # 100% of all alpha, beta or special
    ("ProductName", lambda x: x[0] in 'TSC', 100), # 100% of Thunderbird, SeaMonkey & Camino
    (None, True, 0) # reject everything else
]""",
               from_string_converter=eval)
    #---------------------------------------------------------------------------
    def __init__(self, config):
        self.config = config
        self.processedThrottleConditions = self.preprocessThrottleConditions(
                                                      config.throttleConditions)
    #---------------------------------------------------------------------------
    ACCEPT = 0
    DEFER = 1
    DISCARD = 2
    #---------------------------------------------------------------------------
    @staticmethod
    def regexpHandlerFactory(regexp):
        def regexpHandler(x):
            return regexp.search(x)
        return regexpHandler

    #---------------------------------------------------------------------------
    @staticmethod
    def boolHandlerFactory(aBool):
        def boolHandler(dummy):
            return aBool
        return boolHandler

    #---------------------------------------------------------------------------
    @staticmethod
    def genericHandlerFactory(anObject):
        def genericHandler(x):
            return anObject == x
        return genericHandler

    #---------------------------------------------------------------------------
    def preprocessThrottleConditions(self, originalThrottleConditions):
        newThrottleConditions = []
        for key, condition, percentage in originalThrottleConditions:
            #print "preprocessing %s %s %d" % (key, condition, percentage)
            conditionType = type(condition)
            if conditionType == compiledRegularExpressionType:
                #print "reg exp"
                newCondition = LegacyThrottler.regexpHandlerFactory(condition)
                #print newCondition
            elif conditionType == bool:
                #print "bool"
                newCondition = LegacyThrottler.boolHandlerFactory(condition)
                #print newCondition
            elif conditionType == functionType:
                newCondition = condition
            else:
                newCondition = LegacyThrottler.genericHandlerFactory(condition)
            newThrottleConditions.append((key, newCondition, percentage))
        return newThrottleConditions

    #---------------------------------------------------------------------------
    def understandsRefusal (self, jsonData):
        try:
            product = jsonData['ProductName']
            refusalVersion = self.config.minimalVersionForUnderstandingRefusal[product]
            return vtl.normalize(jsonData['Version']) >= vtl.normalize(refusalVersion)
        except KeyError:
            return False

    #---------------------------------------------------------------------------
    def applyThrottleConditions (self, jsonData):
        """cycle through the throttle conditions until one matches or we fall
        off the end of the list.
        returns:
          True - reject
          False - accept
        """
        #print processedThrottleConditions
        for key, condition, percentage in self.processedThrottleConditions:
            #logger.debug("throttle testing  %s %s %d", key, condition,
            #             percentage)
            throttleMatch = False
            try:
                throttleMatch = condition(jsonData[key])
            except KeyError:
                if key == None:
                    throttleMatch = condition(None)
                else:
                    #this key is not present in the jsonData - skip
                    continue
            except IndexError:
                pass
            if throttleMatch: #condition match - apply the throttle percentage
                randomRealPercent = random.random() * 100.0
                #logger.debug("throttle: %f %f %s", randomRealPercent,
                #             percentage, randomRealPercent > percentage)
                return randomRealPercent > percentage
        # nothing matched, reject
        return True

    #---------------------------------------------------------------------------
    def throttle (self, jsonData):
        if self.applyThrottleConditions(jsonData):
            #logger.debug('yes, throttle this one')
            if self.understandsRefusal(jsonData) and not self.config.neverDiscard:
                self.config.logger.debug("discarding %s %s", jsonData.ProductName,
                                         jsonData.Version)
                return LegacyThrottler.DISCARD
            else:
                self.config.logger.debug("deferring %s %s", jsonData.ProductName,
                                         jsonData.Version)
                return LegacyThrottler.DEFER
        else:
            self.config.logger.debug("not throttled %s %s", jsonData.ProductName,
                                     jsonData.Version)
            return LegacyThrottler.ACCEPT
