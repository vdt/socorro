import re

import socorro.lib.config_manager as cm

#===============================================================================
class SignatureUtilities (cm.RequiredConfig):
    required_config = _rc = cm.Namespace()
    _rc.option(name='signatureSentinels',
               doc='a list of frame signatures that should always be considered '
                   'top of the stack if present in the stack',
               default="""[
                       '_purecall',
                       ('mozilla::ipc::RPCChannel::Call(IPC::Message*, IPC::Message*)',
                           lambda x: 'CrashReporter::CreatePairedMinidumps(void*, unsigned long, nsAString_internal*, nsILocalFile**, nsILocalFile**)' in x)
                   ]""",
               from_string_converter=eval)
    _rc.option(name='irrelevantSignatureRegEx',
               doc='a regular expression matching frame signatures that should '
                   'be ignored when generating an overall signature',
               default="""'|'.join([
                   '@0x[0-9a-fA-F]{2,}',
                   '@0x[1-9a-fA-F]',
                   'RaiseException',
                   '_CxxThrowException',
                   'mozilla::ipc::RPCChannel::Call\(IPC::Message\*, IPC::Message\*\)',
                   'KiFastSystemCallRet',
                   '(Nt|Zw)WaitForSingleObject(Ex)?',
                   '(Nt|Zw)WaitForMultipleObjects(Ex)?',
                   'WaitForSingleObjectExImplementation',
                   'WaitForMultipleObjectsExImplementation',
                   '___TERMINATING_DUE_TO_UNCAUGHT_EXCEPTION___',
                   '_NSRaiseError',
                   'mozcrt19.dll@0x.*',
                   ])""",
               from_string_converter=cm.eval_to_regex_converter)
    _rc.option('prefixSignatureRegEx',
               doc='a regular expression matching frame signatures that should '
                   'always be coupled with the following frame signature when '
                   'generating an overall signature',
               default="""'|'.join([
                   '@0x0',
                   'strchr',
                   'strstr',
                   'strlen',
                   'PL_strlen',
                   'strcmp',
                   'wcslen',
                   'memcpy',
                   'memmove',
                   'memcmp',
                   'malloc',
                   'realloc',
                   '.*free',
                   'arena_dalloc_small',
                   'arena_alloc',
                   'arena_dalloc',
                   'nsObjCExceptionLogAbort(\(.*?\)){0,1}',
                   'libobjc.A.dylib@0x1568.',
                   'objc_msgSend',
                   '_purecall',
                   'PL_DHashTableOperate',
                   'EtwEventEnabled',
                   'RtlpFreeHandleForAtom',
                   'RtlpDeCommitFreeBlock',
                   'RtlpAllocateAffinityIndex',
                   'RtlAddAccessAllowedAce',
                   'RtlQueryPerformanceFrequency',
                   'RtlpWaitOnCriticalSection',
                   'RtlpWaitForCriticalSection',
                   '_PR_MD_ATOMIC_(INC|DEC)REMENT',
                   'nsCOMPtr.*',
                   'nsRefPtr.*',
                   'operator new\([^,\)]+\)',
                   'CFRelease',
                   'objc_exception_throw',
                   '[-+]\[NSException raise(:format:(arguments:)?)?\]',
                   'mozalloc_handle_oom',
                   'nsTArray_base<.*',
                   'nsTArray<.*',
                   'WaitForSingleObject(Ex)?',
                   'WaitForMultipleObjects(Ex)?',
                   'NtUserWaitMessage',
                   'NtUserMessageCall',
                   'mozalloc_abort.*',
                   'NS_DebugBreak_P.*',
                   'PR_AtomicIncrement',
                   'PR_AtomicDecrement',
                   ])""",
               from_string_converter=cm.eval_to_regex_converter)
    _rc.option('signaturesWithLineNumbersRegEx',
               doc='any signatures that match this list should be combined with '
                   'their associated source code line numbers',
               default="""'|'.join([
                   'js_Interpret',
                   ])""",
               from_string_converter=cm.eval_to_regex_converter)

    #---------------------------------------------------------------------------
    def __init__(self, context):
        self.config = context
        self.irrelevantSignatureRegEx = \
             re.compile(self.config.irrelevantSignatureRegEx)
        self.prefixSignatureRegEx =  \
            re.compile(self.config.prefixSignatureRegEx)
        self.signaturesWithLineNumbersRegEx = \
            re.compile(self.config.signaturesWithLineNumbersRegEx)
        self.fixupSpace = re.compile(r' (?=[\*&,])')
        self.fixupComma = re.compile(r',(?! )')
        self.fixupInteger = re.compile(r'(<|, )(\d+)([uUlL]?)([^\w])')

    #---------------------------------------------------------------------------
    def normalize_signature(self, module_name, function, source, source_line,
                            instruction):
        """ returns a structured conglomeration of the input parameters to serve
        as a signature
        """
        #if function is not None:
        if function:
            if self.signaturesWithLineNumbersRegEx.match(function):
                function = "%s:%s" % (function, source_line)
            # Remove spaces before all stars, ampersands, and commas
            function = self.fixupSpace.sub('',function)
            # Ensure a space after commas
            function = self.fixupComma.sub(', ', function)
            # normalize template signatures with manifest const integers to
            #'int': Bug 481445
            function = self.fixupInteger.sub(r'\1int\4', function)
            return function
        #if source is not None and source_line is not None:
        if source and source_line:
            filename = source.rstrip('/\\')
            if '\\' in filename:
                source = filename.rsplit('\\')[-1]
            else:
                source = filename.rsplit('/')[-1]
            return '%s#%s' % (source, source_line)
        if not module_name:
            module_name = '' # might have been None
        return '%s@%s' % (module_name, instruction)

    #---------------------------------------------------------------------------
    def generate_signature_from_list(self,
                                     signatureList,
                                     isHang=False,
                                     escapeSingleQuote=True,
                                     maxLen=255,
                                     signatureDelimeter=' | '):
        """
        each element of signatureList names a frame in the crash stack; and is:
          - a prefix of a relevant frame: Append this element to the signature
          - a relevant frame: Append this element and stop looking
          - irrelevant: Append this element only after seeing a prefix frame
        The signature is a ' | ' separated string of frame names
        """
        # shorten signatureList to the first signatureSentinel
        sentinelLocations = []
        for aSentinel in self.config.signatureSentinels:
            if type(aSentinel) == tuple:
                aSentinel, conditionFn = aSentinel
                if not conditionFn(signatureList):
                    continue
            try:
                sentinelLocations.append(signatureList.index(aSentinel))
            except ValueError:
                pass
        if sentinelLocations:
            signatureList = signatureList[min(sentinelLocations):]
        newSignatureList = []
        for aSignature in signatureList:
            if self.irrelevantSignatureRegEx.match(aSignature):
                continue
            newSignatureList.append(aSignature)
            if not self.prefixSignatureRegEx.match(aSignature):
                break
        signature = signatureDelimeter.join(newSignatureList)
        if isHang:
            signature = "hang | %s" % signature
        if len(signature) > maxLen:
            signature = "%s..." % signature[:maxLen - 3]
        if escapeSingleQuote:
            signature = signature.replace("'","''")
        return signature