
class LoggingException(Exception):

    def __init__(self, message, logger):
        Exception.__init__(self, message)
        if logger:
            logger.error(message)


class ConfigError(LoggingException):

    def __init__(self, message, error=None, logger=None):
        LoggingException.__init__(self, message, logger)
        self.error = error


class ManifestError(LoggingException):

    def __init__(self, message, errors=None, logger=None):
        LoggingException.__init__(self, message, logger)
        self.errors = errors


class StackError(LoggingException):

    def __init__(self, message, errors=None, logger=None):
        LoggingException.__init__(self, message, logger)
        self.errors = errors


class PluginError(LoggingException):

    def __init__(self, message, errors=None, logger=None):
        LoggingException.__init__(self, message, logger)
        self.errors = errors
