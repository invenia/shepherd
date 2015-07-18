"""
Provides various utility functions for shepherd ranging from
validating configs to mapping object attributes to and from
dictionaries.
"""
from __future__ import print_function

import os
import re
import jsonschema
import anyconfig
import logging

from shepherd.common.exceptions import ConfigError, LoggingException, PluginError

LOCALREF = 'Fn::LocalRef'
IMPORTREF = 'Fn::ImportRef'
LOGFORMAT = '[%(levelname)s  %(asctime)s  %(name)s] - "%(message)s"'


def run(action_name, config, **kwargs):
    """
    Searches for the action plugin to run.
    Searches both the default paths as well as

    Args:
        action_name (TYPE): the name of the action you want to run.
        config (TYPE): the config object used for creating or location a stack to work on.
        **kwargs: a dictionary of parameters to be passed to the task.

    Returns:
        the action output
    """
    actions = config.get_plugins(category_name='Action', plugin_name=action_name)

    if actions:
        action = actions[0]
        return action.run(config, **kwargs)
    else:
        raise PluginError('Failed to locate task {}'.format(action_name))


def pascal_to_underscore(pascal_str):
    """
    Converts pascal format strings to underscore format.

    http://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-camel-case

    Args:
        pascal_str (TYPE): the pascal case string we want to convert to underscore format.
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', pascal_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def validate_config(config):
    """
    Validates the config format with the schema file.

    Args:
        config (dict): a dictionary of the config settings.
    """
    try:
        path = os.path.dirname(os.path.realpath(__file__))
        schema_file = os.path.join(path, 'config.schema')
        schema = anyconfig.load(schema_file, 'json')

        jsonschema.validate(config, schema)
    except jsonschema.ValidationError as exc:
        ConfigError(exc.message)


def setattrs(obj, attrmap, values):
    """
    Handles setting object attributes from dict.

    Args:
        obj (object): the object with the attributes being set.
        attrmap (dict): a dict mapping dict keys to attribute names, where the
            keys match the expected keys in values (underscore case) and the
            values are the attribute names.
        values (dict): the dict whose values are mapping to the object.
    Returns:
        obj (object): the updated object
    """
    for key in values:
        attr = pascal_to_underscore(key)
        if attr in attrmap:
            setattr(obj, attrmap[attr], values[key])

    return obj


def getattrs(obj, attrmap):
    """
    Handles extracting object attributes into a dict.

    :param attrmap:
    :return: the result dict.

    Args:
        obj (object): the object to extract the attributes from.
        attrmap (dict): a dict mapping dict keys to attribute names, where the
            keys match the keys of the resulting dict and the values match their
            corresponding attributes.
    Returns:
        result (dict): dictionary of the mapped attributes from obj
    """
    result = {}

    for key in attrmap:
        if attrmap[key] in obj.__dict__:
            result[key] = getattr(obj, attrmap[key])

    return result


def dict_contains(superdict, subdict):
    """
    Returns a boolean as to whether the
    superdict contains the same key value pairs
    of the subdict.

    Args:
        superdict (dict): dict with superset of keys in subdict
        subdict (dict): dict with subset of keys from superdict

    Returns:
        result (bool):
    """
    unmatchable = object()
    for key, value in subdict.items():
        superval = superdict.get(key, unmatchable)
        if superval != value:
            return False

    return True


def tasks_passed(results, logger, msg=None, exception=None):
    """
    Logs a warning msg and returns a bool if results contains
    any failures.

    Args:
        results (namedtuple): namedtuple containing the sets of failed
            and completed tasks returned by Arbiter
        logger (Logger): The logger to log to if any tasks failed
        msg (str, optional): A msg to log if any tasks failed.
        exception (Exception, optional): An Exception object to throw if
            supplied.
    Returns:
        resp (bool): Whether all tasks in results completed.
    """
    resp = True
    if len(results.failed) > 0:
        full_msg = '{}.\nCompleted={}\nFailed={}'.format(
            msg, results.completed, results.failed
        )

        if exception:
            logger.error(full_msg)
            if issubclass(type(exception), LoggingException):
                raise exception(full_msg, logger)
            else:
                raise exception(full_msg)
        else:
            logger.warn(full_msg)
            resp = False

    return resp


def get_logger(obj):
    """
    Provides an alternative method of getting a useful logger name
    for an object because yapsy tends to mess up how `__name__` works.

    Args:
        obj (object): the object to build a custom logger name for.

    Returns:
        logger (Logger) - where the name is the __module__.__name__ of type(obj).
    """
    return logging.getLogger('{}.{}'.format(
        type(obj).__module__,
        type(obj).__name__
    ))


def configure_logging(verbosity, logformat=LOGFORMAT):
    """
    Sets up logging for the framework.

    All default logging uses logging.basicConfig with the format string
    `'[%(levelname)s  %(asctime)s  %(name)s] - "%(message)s"'`

    Args:
        verbosity (int): a verbosity level between 0 and 5.
            0. No Logging Configured
            1. Root & shepherd logger = WARNING
            2. Root logger = WARNING; shepherd logger = INFO
            3. Root logger = WARNING; shepherd logger = DEBUG
            4. Root logger = INFO; shepherd logger = DEBUG
            5. Root logger = DEBUG; shepherd logger = DEBUG

        logformat (str, optional): an alternative format string.

    NOTE: for verbosity level lower than 4 the boto logger is set to
        CRITICAl as it tends to be noisy when shepherd is catching
        a lot of exceptions for you.
    """
    if verbosity > 0:
        logging.basicConfig(format=logformat)
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger('shepherd').setLevel(logging.WARNING)
        logging.getLogger('boto').setLevel(logging.CRITICAL)

        if verbosity == 2:
            logging.getLogger('shepherd').setLevel(logging.INFO)
        elif verbosity >= 3:
            if verbosity == 4:
                logging.getLogger().setLevel(logging.INFO)
            elif verbosity >= 5:
                logging.getLogger().setLevel(logging.DEBUG)

            logging.getLogger('shepherd').setLevel(logging.DEBUG)


def get(dictionary, keys, mutually_exclusive=True):
    """
    Allows getting a value from a dict using multiple possible keys.

    Args:
        dict (dict): the dict to get the return value from.
        keys (list): a list of keys to search for.
        mutually_exclusive (bool): whether or not to assert that the keys are mutually exclusive.
    """
    result = None
    for key in keys:
        if not result and key in dictionary:
            result = dictionary[key]
        elif result and key in dictionary and mutually_exclusive:
            raise KeyError(
                "Key {} and {} are not mutually exclusive \
                in the provided dict.".format(result, key)
            )

    if not result:
        raise KeyError('None of the keys {} matched'.format(keys))

    return result
