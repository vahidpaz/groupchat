import logging
import threading




class ThreadContextLogger(logging.LoggerAdapter):
    '''MDC (Mapped Diagnostic Context) for logging.Logger. Expected use is for the context value to be changed by various threads to distinguish logs in a multi-threaded application.'''

    def __init__(self, logger, extra, contextval):
        super().__init__(logger, extra)
        self.logcontext = _threadlocal
        self.logcontext.val = contextval

    def process(self, msg, kwargs):
        # If a value for the log context has not been set, then don't
        # bother adding any context information to the message.
        if self.logcontext.val is None:
            return msg, kwargs
        return '[{}] {}'.format(self.logcontext.val, msg), kwargs


def getlogger(name, contextval=None):
    '''No handlers/formatters are defined here. Expects user application to define a parent logger that has a handler.'''
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    log = ThreadContextLogger(log, extra=None, contextval=contextval)
    return log


# TODO: How will unused values ever be cleaned up from this object? Is
# there a weakly referenced version to use? Or better yet, when threads
# terminate will the data be auto-deleted?
_threadlocal = threading.local()

