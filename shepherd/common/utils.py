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

from shepherd.common.exceptions import ConfigValidationError

LOCALREF = 'Fn::LocalRef'
IMPORTREF = 'Fn::ImportRef'


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
        ConfigValidationError(exc.message)


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
