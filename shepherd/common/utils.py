"""
Contains various utility functions for parsing the json and yaml
stack configs.

NOTE: This module is mostly used by the Manifest object.
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


def run(self, action_name, config, **kwargs):
    """
    Searches for the action plugin to run.
    Searches both the default paths as well as

    :param task: the name of the task you want to run.
    :param kwargs: a dictionary of parameters to be passed to the task.
    """
    actions = config.get_plugins(category_name='Action', plugin_name=action_name)

    if actions:
        action = actions[0]
        action.run(config, **kwargs)
    else:
        raise PluginError('Failed to locate task {}'.format(action_name))


def pascal_to_underscore(pascal_str):
    """
    http://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-camel-case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', pascal_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def validate_config(config):
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

    :param obj: the object with the attributes being set.
    :param attrmap: a dict mapping dict keys to attribute names, where the
        keys match the expected keys in values (underscore case) and the
        values are the attribute names.
    :param values: the dict whose values are mapping to the object.
    :return: the updated object
    """
    for key in values:
        attr = pascal_to_underscore(key)
        if attr in attrmap:
            setattr(obj, attrmap[attr], values[key])

    return obj


def getattrs(obj, attrmap):
    """
    Handles extracting object attributes into a dict.

    :param obj: the object to extract the attributes from.
    :param attrmap: a dict mapping dict keys to attribute names, where the
        keys match the keys of the resulting dict and the values match their
        corresponding attributes.
    :return: the result dict.
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
    """
    resp = True
    if len(results.failed) > 0:
        full_msg = '{}.\nCompleted={}\nFailed={}'.format(
            msg, results.completed, results.failed
        )

        if exception:
            logger.error(full_msg)
            if issubclass(type(exception), LoggingException):
                exception(full_msg, logger)
            else:
                exception(full_msg)
        else:
            logger.warn(full_msg)
            resp = False

    return resp


def get_logger(obj):
    """
    Provides an alternative method of getting a useful logger name
    for an object because yapsy tends to mess up how `__name__` works.
    """
    return logging.getLogger('{}.{}'.format(
        type(obj).__module__,
        type(obj).__name__
    ))


def configure_logging(verbosity):
    logformat = '[%(levelname)s  %(asctime)s  %(name)s] - "%(message)s"'
    logging.basicConfig(format=logformat)
    logging.getLogger().setLevel(logging.WARNING)

    if verbosity == 1:
        logging.getLogger('shepherd').setLevel(logging.WARNING)
    elif verbosity == 2:
        logging.getLogger('shepherd').setLevel(logging.INFO)
    elif verbosity >= 3:
        if verbosity == 4:
            logging.getLogger().setLevel(logging.INFO)
        elif verbosity >= 5:
            logging.getLogger().setLevel(logging.DEBUG)

        logging.getLogger('shepherd').setLevel(logging.DEBUG)
