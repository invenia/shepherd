"""
An Environment is a stack that can maintain other stacks.

The idea of an environment is that it maintains a set of resources
that are used by multiple stacks.  For example if we have a set
of stacks that are related to each other we may want them share some
resources.  Be careful not to overuse environments though.  If 2 stacks
are coupled enough to have a lot of shared resources you probably want to
merge them into one stack.

EX)
Assume we are using AWS for our example, if we want to promote a stack
from staging to production the Environment would maintain
the elasticips outside of an individual stack.  Alternatively, we might want
one stack to be able to communicate with another (minimally), so we might
have an Environment that creates a globally accessible security group with which
individual stacks can register to communicate.
"""
import logging

from shepherd.stack import Stack
from shepherd.common.exceptions import StackError

logger = logging.getLogger(__name__)


class Environment(Stack):
    """
    The Environment is a subclass of a Stack object.

    It provides a set useful methods for working with groups
    of stacks at an environment level.
    """
    def __init__(self, name, config_name):
        super(Environment, self).__init__(name, config_name)
        self._stack_names = []
        self._stacks = []

        # This may change, but we probably want a simple
        # environment_name tag by default.
        self._global_name = self._local_name
        del self._tags['stack_name']
        del self._tags['stack_creation']
        self._tags['environment_name'] = self._local_name

    @property
    def stack_names(self):
        return self._stack_names

    def add(self, name, create=False):
        """
        Adds a stack with the given name to the environment.

        If the stack cannot be found and create is true a new stack will
        be created and added to the environment.
        """
        try:
            Stack.restore(name, self._config_name)
        except StackError as exc:
            if create:
                Stack.make(name, self._config_name)
            else:
                raise exc

        self._stack_names.append(name)

    def remove(self, name, delete=False):
        """
        Removes a stack from the environment.

        If delete is set to true the stack will attempt to be deprovisioned.
        """
        if delete:
            stack = Stack.restore(name, self._config_name)
            stack.deprovision_resources()

        self._stack_names.remove(name)

    def restore_stacks(self):
        """
        Restores all stack object identified by our stack_names.
        """
        self._stacks = []

        for name in self._stack_names:
            stack = Stack.restore(name, self._config_name)
            self._stacks.append(stack)

        return self._stacks
