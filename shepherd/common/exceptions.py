import logging


class LoggingException(Exception):

    def __init__(self, message, name, log=True):
        Exception.__init__(self, message)
        if log:
            logger = logging.getLogger(name)
            logger.error(message)


class ConfigValidationError(LoggingException):

    def __init__(self, message, error=None, name=__name__):
        LoggingException.__init__(self, message, name)
        self.error = error


class ManifestParsingError(LoggingException):

    def __init__(self, message, errors=None, name=__name__):
        LoggingException.__init__(self, message, name)
        self.errors = errors


class ManifestValidationError(LoggingException):

    def __init__(self, message, errors=None, name=__name__):
        LoggingException.__init__(self, message, name)
        self.errors = errors


class StackError(LoggingException):

    def __init__(self, message, errors=None, name=__name__, log=True):
        LoggingException.__init__(self, message, name, log=log)
        self.errors = errors


class PluginError(LoggingException):

    def __init__(self, message, errors=None, name=__name__):
        LoggingException.__init__(self, message, name)
        self.errors = errors
