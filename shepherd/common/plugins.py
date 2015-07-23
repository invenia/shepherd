"""
Uses abstract base classes and IPlugin to create
base plugin classes.  Each defines a particular interface
For example all resources should have a create, destroy and
exists methods.

This combined with the PluginManager in shepherd.manager helps
to creates a common method of building the modular architecture.  Since,
the built in resources, parsers, etc all use the same abstract classes, adding
new features should be seemless.
"""
import sys
import inspect
import logging

from abc import ABCMeta, abstractmethod
from yapsy.IPlugin import IPlugin

from shepherd.common.exceptions import StackError
from shepherd.common.utils import setattrs, getattrs


class Action(IPlugin):
    """
    Defines an action to run.

    WARNING: Actions may be depricated as objects in future versions
        if yapsy is removed as the plugin manager.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self, config, **kwargs):
        """
        Takes an undefined set of name arguments.

        Args:
            config (Config): the config object for locating plugins, settings, etc.
            kwargs (dict): named parameters that should passed to the action
        """
        raise NotImplementedError(
            'The abstractmethod "run" was not '
            'implemented in the Action abstract base class'
        )


class Parser(IPlugin):
    """
    During parsing of manifests Parsers can be used to handles any
    modifications to the params subdict before merging the params
    into the resources.

    This could be used for dynamic variables like getting the latest
    volume snapshots, external resources, etc.

    NOTE: multiple parsers can be run on the paramsdict, so ensure that they
    are independent of each other. For example you may want a parser for
    modifying each dynamic variable.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self, paramsdict, config=None):
        """
        Takes a dict of the parameters and returns the modified version.
        It optionally takes a config which could contain default input values
        to use.

        Args:
            paramsdict (dict): the current params dict.
            config (Config, optional): the config object if the Parser would like to
        """
        raise NotImplementedError(
            'The abstractmethod "run" was not '
            'implemented in the Parser abstract base class'
        )


class Storage(IPlugin):
    """
    Defines an API for storage plugins.

    WARNING: Storage plugins should be thread safe.
    For example, if your storage plugin writes to a file
    make sure you're locking and unlocking the file accordingly.

    FEATURE: should probably support some kind of archiving approach
    for old and unused stacks.
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        """Summary"""
        self._logger = logging.getLogger(
            'shepherd.storage.{}'.format(type(self).__name__)
        )

    @abstractmethod
    def search(self, tags):
        """
        Given a dict of tags.

        Search the store for serialized stacks
        that match to those tags. Returning a list of
        the stack names that match.

        Args:
            tags (dict): tags to use when search for stacks.
        """
        raise NotImplementedError(
            'The abstractmethod "search" was not '
            'implemented in the Storage abstract base class'
        )

    @abstractmethod
    def load(self, name):
        """
        Given a unique name.

        Search the store for the serialized stack with
        that name.  Returns a single stack dict.

        Args:
            name (str): the global_name of the stack to load.
        """
        raise NotImplementedError(
            'The abstractmethod "load" was not '
            'implemented in the Storage abstract base class'
        )

    @abstractmethod
    def dump(self, stack):
        """
        Takes a stack dict and stores it
        in the datastore of your choice.

        Args:
            stack (Stack): dumps the stack into the storage media
        """
        raise NotImplementedError(
            'The abstractmethod "dump" was not '
            'implemented in the Storage abstract base class'
        )


class Resource(IPlugin):
    """
    Defines a simple interface for interacting with
    resource objects.
    """
    __metaclass__ = ABCMeta

    def __init__(self, provider):
        """Summary

        Args:
            provider (str): the name of the provider the resource is designed
                to run on.

        Attributes:
            local_name (str): the name local to the stack.
            global_name (str): the global name that is unique within the storage and provider.
            provider (str): the provider of the resource.
            type (str): the name of the resource type.
            tags (dict): a dictionary of tags used for looking up resources in shepherd
                or on the provider.
            stack (Stack): the stack the resource belongs to.
        """
        self._local_name = None
        self._global_name = None
        self._provider = provider
        self._type = type(self).__name__
        self._stack = None
        self._available = False
        self._tags = {}
        self._logger = logging.getLogger(
            'shepherd.resources.{}.{}'.format(provider, self._type)
        )
        self._attributes_map = {
            'local_name': '_local_name',
            'global_name': '_global_name',
            'provider': '_provider',
            'type': '_type',
            'available': '_available',
            'tags': '_tags',
        }

    @property
    def local_name(self):
        return self._local_name

    @property
    def global_name(self):
        return self._global_name

    @property
    def provider(self):
        return self._provider

    @property
    def type(self):
        return self._type

    @property
    def available(self):
        return self._available

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        self._tags = value

    @property
    def stack(self):
        return self._stack

    @stack.setter
    def stack(self, value):
        self._stack = value

    @classmethod
    def validate_create(cls):
        """
        A default Resource decorator to remove boilerplate validation
        code for create requests.
        """
        def wrap(func):
            def function(self, *args):
                self._logger.info(
                    'Creating %s %s ...', type(self).__name__, self._local_name
                )
                resp = True
                if not self._available:
                    if self._stack is None:
                        raise StackError(
                            'Unknown parent stack. Make sure that the stack '
                            'property is set prior to calling create',
                            logger=self._logger
                        )

                    passed = func(self, *args)
                    if passed is False:
                        resp = False
                    else:
                        resp = self._available
                else:
                    self._logger.debug(
                        '%s %s is already available', type(self).__name__, self._local_name
                    )

                return resp
            return function
        return wrap

    @classmethod
    def validate_destroy(cls):
        """
        A default Resource decorator to remove boilerplate validation
        code for destroy requests.
        """
        def wrap(func):
            def function(self, *args):
                self._logger.info(
                    'Destroying %s %s ...', type(self).__name__, self._local_name
                )
                resp = True
                if self._available:
                    if self._stack is None:
                        raise StackError(
                            'Unknown parent stack. Make sure that the stack '
                            'property is set prior to calling create',
                            logger=self._logger
                        )

                    passed = func(self, *args)
                    if passed is False:
                        resp = False
                    else:
                        resp = not self._available
                else:
                    self._logger.debug(
                        '%s %s is already unavailable', type(self).__name__, self._local_name
                    )
                return resp
            return function
        return wrap

    def deserialize(self, data):
        """
        Deserializes the keys and values in a dictionary into attributes
        for self.

        Notes:
            The mapping of keys to attributes is done using ``self._attributes_map``.

        Args:
            data (dict): a dictionary of the attributes to deserialize.
        """
        setattrs(self, self._attributes_map, data)
        self._logger.debug(
            'Deserialized %s %s', type(self).__name__, self._local_name
        )

    def serialize(self):
        """
        Serializes the attributes to a dict using ``self._attributes_map``.

        Returns:
            dict: the serialized dictionary of the attributes.
        """
        self._logger.debug(
            'Serializing %s %s', type(self).__name__, self._local_name
        )
        return getattrs(self, self._attributes_map)

    @abstractmethod
    def create(self):
        """
        All resources must have a create method.
        """
        raise NotImplementedError(
            'The abstractmethod "create" was not implemented in a subclass'
        )

    @abstractmethod
    def destroy(self):
        """
        All resources must have a destroy method.
        """
        raise NotImplementedError(
            'The abstractmethod "destroy" was not implemented in a subclass'
        )

    @abstractmethod
    def get_dependencies(self):
        """
        Generates a list of dependencies for the resource.

        Returns:
            list: of other resource names this resource depends on.
        """
        raise NotImplementedError(
            'The abstractmethod "get_dependencies" was '
            'not implemented in a subclass'
        )

    @abstractmethod
    def sync(self):
        """
        Tells a resource to try and synchronize its state with
        its provider if necessary.
        """
        raise NotImplementedError(
            'The abstractmethod "sync" was '
            'not implemented in a subclass'
        )


def is_plugin(cls):
    """
    Accepts a class and returns a boolean as to whether the class is a valid
    plugin.

    Kind of a hack, but it dynamically scans the plugins file for all valid
    shepherd plugin abstract base classes.

    Args:
        cls (class): the class that may be a plugin.
    """
    mod = sys.modules[__name__]

    for name, plugin in inspect.getmembers(mod, inspect.isclass):
        # Kind of ugly if statem making sure we don't count IPlugin
        # or the abs plugins before checking if it subclasses them.
        if (plugin.__name__ != 'IPlugin' and
                plugin.__name__ != cls.__name__ and
                issubclass(cls, IPlugin) and
                issubclass(cls, plugin)):
            return True

    return False
