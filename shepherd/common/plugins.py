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

from abc import ABCMeta, abstractmethod
from yapsy.IPlugin import IPlugin

from shepherd.common.exceptions import StackError


class Task(IPlugin):
    """
    Defines a task to run.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self, **kwargs):
        """
        Takes an undefined set of name arguments.
        """
        return


class Parser(IPlugin):
    """
    Handles any modifications to the params subdict before merging
    the params into the resources.

    This could be used for dynamic variables like getting the latest
    volume snapshots, external resources, etc.

    NOTE: multiple parsers can be run on the paramsdict, so ensure that they
    are independent of each other.  For example you may want a parser for
    modifying each dynamic variable.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def run(self, paramsdict, config=None):
        """
        Takes a dict of the parameters and returns the modified version.
        It optionally takes a config which could contain default input values
        to use.
        """
        return


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

    @abstractmethod
    def search(self, tags):
        """
        Given a dict of tags.

        Search the store for serialized stacks
        that match to those tags. Returning a list of
        the stack names that match.
        """
        return

    @abstractmethod
    def load(self, name):
        """
        Given a unique name.

        Search the store for the serialized stack with
        that name.  Returns a single stack dict.
        """
        return

    @abstractmethod
    def dump(self, stack):
        """
        Takes a stack dict and stores it
        in the datastore of your choice.
        """
        return


class Resource(IPlugin):
    """
    Defines a simple interface for interacting with
    resource objects.
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        self._local_name = None
        self._global_name = None
        self._provider = None
        self._type = None
        self._stack = None
        self._available = False
        self._tags = {}

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
    def validate_create(cls, logger):
        """
        A default Resource decorator to remove boilerplate validation
        code for create requests.
        """
        def wrap(func):
            def function(self, *args):
                logger.info(
                    'Creating {} {} ...'.format(
                        type(self).__name__, self._local_name
                    )
                )
                resp = True
                if not self._available:
                    if self._stack is None:
                        raise StackError(
                            'Unknown parent stack. Make sure that the stack '
                            'property is set prior to calling create',
                            name=__name__
                        )

                    passed = func(self, *args)
                    if passed is False:
                        resp = False
                    else:
                        resp = self._available
                else:
                    logger.debug(
                        '{} {} is already available'
                        .format(type(self).__name__, self._local_name)
                    )

                return resp
            return function
        return wrap

    @classmethod
    def validate_destroy(cls, logger):
        """
        A default Resource decorator to remove boilerplate validation
        code for destroy requests.
        """
        def wrap(func):
            def function(self, *args):
                logger.info(
                    'Destroying {} {} ...'.format(
                        type(self).__name__, self._local_name
                    )
                )
                resp = True
                if self._available:
                    if self._stack is None:
                        raise StackError(
                            'Unknown parent stack. Make sure that the stack '
                            'property is set prior to calling create',
                            name=__name__
                        )

                    passed = func(self, *args)
                    if passed is False:
                        resp = False
                    else:
                        resp = not self._available
                else:
                    logger.debug(
                        '{} {} is already unavailable'
                        .format(type(self).__name__, self._local_name)
                    )
                return resp
            return function
        return wrap

    @abstractmethod
    def serialize(self):
        """
        Returns a dict representing the resources state.

        NOTE: You will always want a super(Resource, self).serialize()
        from your resources serialize methods
        """
        return {
            'local_name': self._local_name,
            'global_name': self._global_name,
            'provider': self._provider,
            'type': self._type,
            'available': self._available,
            'tags': self.tags,
        }

    @abstractmethod
    def deserialize(self, data):
        """
        Sets the object variables based on the given dict.

        NOTE:
        - this is a bit of a hack.  Normally, this would be a factory,
        but we want to be able to use this for both reading resources from the
        manifest and loading stack state.
        - You will always want a super(Resource, self).deserialize()
        from your resources deserialize methods
        """
        for key in data:
            lower_key = key.lower()

            if lower_key == 'local_name':
                self._local_name = data[key]
            elif lower_key == 'global_name':
                self._global_name = data[key]
            elif lower_key == 'provider':
                self._provider = data[key]
            elif lower_key == 'type':
                self._type = data[key]
            elif lower_key == 'available':
                self._available = data[key]
            elif lower_key == 'tags':
                self._tags = data[key]

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
        """
        raise NotImplementedError(
            'The abstractmethod "get_dependencies" was '
            'not implemented in a subclass'
        )


def is_plugin(obj):
    """
    Accepts a class and returns a boolean as to whether the class is a valid
    plugin.

    Kind of a hack, but it dynamically scans the plugins file for all valid
    shepherd plugin abstract base classes.
    """
    mod = sys.modules[__name__]

    for name, plugin in inspect.getmembers(mod, inspect.isclass):
        # Kind of ugly if statem making sure we don't count IPlugin
        # or the abs plugins before checking if it subclasses them.
        if (plugin.__name__ != 'IPlugin' and
                plugin.__name__ != obj.__name__ and
                issubclass(obj, IPlugin) and
                issubclass(obj, plugin)):
            # print(plugin.__name__)
            # print(obj.__name__)
            return True

    return False
