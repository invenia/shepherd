"""
user calls a stack, passing a filepath to the template to parse.
The returned stack object has all params and resources for that stack,
Stacks will support higher level operations like "create","wake","sleep".
"""
from __future__ import print_function
from future.builtins import dict

import logging
from datetime import datetime
from arbiter import create_task
from arbiter.sync import run_tasks

from shepherd.config import Config
from shepherd.manifest import Manifest
from shepherd.common.exceptions import PluginError, StackError
from shepherd.common.utils import dict_contains, tasks_passed

logger = logging.getLogger(__name__)
_DEFAULT_NAME_FMT = '{stack_name}_{stack_creation}'


class Stack(object):
    """
    The Stack object maintains and manipulates the list of cloud
    resources that need to be provisioned.
    """
    def __init__(self, name, config):
        self._name_fmt = _DEFAULT_NAME_FMT
        self._local_name = name
        self._global_name = None
        self._config = config
        self._config_name = config.name
        self._settings = self._config.settings
        self._resources = []
        self._tags = {
            'stack_name': self._local_name,
            'stack_creation': datetime.strftime(
                datetime.utcnow(),
                "%Y-%m-%d-%H-%M-%S"
            ),
        }

        if 'stack_name_fmt' in self._config.settings:
            self._name_fmt = self._config.stack_name_fmt

        if 'tags' in self._settings and isinstance(self._settings.tags, dict):
            self._tags.update(self._settings.tags)

        self._global_name = self._name_fmt.format(**self._tags)

    def __repr__(self):
        return u"Stack({}. {}".format(
            self._tags['stack_name'],
            self._config_name
        )

    def __str__(self):
        return self._local_name

    @property
    def global_name(self):
        return self._global_name

    @property
    def settings(self):
        return self._settings

    @property
    def tags(self):
        return self._tags

    @classmethod
    def make(cls, name, config):
        """
        Handles creating a stack instance.
        """
        # Build the Manifest which handles the
        # parsing, loading, etc of the template files.
        manifest = Manifest(config)
        manifest.load()
        manifest.parse()
        manifest.map()

        # Create our new Stack object.
        stack = Stack(name, config)

        # Finally, we call the stacks deserialize method
        # giving it just the finished resources dict from
        # the Manifest.
        stack.deserialize_resources(manifest.resources)

        manifest.clear()

        return stack

    @classmethod
    def restore(cls, name, config):
        """
        Handles restoring a stack with the given name
        from the storage plugin specified in
        config.settings
        """
        logger.debug('Stack.restore: Storage setting=%s', config.settings.storage)
        store_name = config.settings.storage.name
        # Get storage plugin
        stores = config.get_plugins(
            category_name='Storage',
            plugin_name=store_name
        )
        if stores:
            store = stores[0]
            store.configure(config.settings.storage.settings)
            serialized = store.load(name)

            if not serialized:
                raise StackError(
                    'Could not find stack {} in store {}'
                    .format(name, store_name),
                    logger=logger
                )

            stack = Stack.deserialize(serialized)
        else:
            raise PluginError(
                'Failed to locate storage plugin {}'.format(store_name)
            )

        return stack

    def save(self):
        """
        Saves this stack to the storage plugin specified
        in config.settings.
        """
        logger.debug('Stack.save: Storage settings=%s', self._config.settings.storage)
        store_name = self._config.settings.storage.name
        # Get the storage plugin
        stores = self._config.get_plugins(
            category_name='Storage',
            plugin_name=store_name
        )
        if stores:
            store = stores[0]
            store.configure(self._config.settings.storage.settings)
            store.dump(self.serialize())
        else:
            raise PluginError(
                'Failed to locate storage plugin {}'.format(store_name)
            )

    @classmethod
    def deserialize(cls, data):
        config = Config.make(settings=data['settings'], name=data['config_name'])
        stack = Stack(data['local_name'], config)
        stack._global_name = data['global_name']
        stack._tags = data['tags']
        stack.deserialize_resources(data['resources'])
        return stack

    def serialize(self):
        result = {
            'local_name': self._local_name,
            'global_name': self._global_name,
            'config_name': self._config_name,
            'settings': self._settings,
            'tags': self._tags,
            'resources': [],
        }

        for resource in self._resources:
            result['resources'].append(resource.serialize())

        return result

    def get_global_resource_name(self, name):
        global_name = "{}_{}".format(name, self._global_name)
        global_name = global_name[0:63]  # some things can only be 64 long...

        return global_name

    def get_resource_by_name(self, local_name):
        """
        Takes a string for the unique *local* resource name
        and returns the resource that matches.

        NOTE: if you somehow manage to change the object name
        to no longer be unique this method will only return the first
        one it finds.
        """
        for resource in self._resources:
            if resource.local_name == local_name:
                return resource
        else:
            return None

    def get_resource_by_type(self, resource_type):
        """
        Takes a string representing the resource type you want to retrieve
        and returns a list of all resources that match that type.  The type is
        determined by either the name of the resources class or by the resource
        type attribute if one exists.
        """
        logger.info('Looking up resources of type %s', resource_type)
        resources = []
        for resource in self._resources:
            if type(resource).__name__ == resource_type:
                resources.append(resource)
            elif hasattr(resource, 'type'):
                if resource.type == resource_type:
                    resources.append(resource)

        return resources

    def get_resource_by_tags(self, tags):
        """
        Returns a list of resources where the resource tags contains the same
        key values as the tags provided.
        """
        logger.info('Looking up resources with tags %s', str(tags))
        return [
            resource for resource in self._resources if dict_contains(
                resource.tags, tags
            )
        ]

    def task_function_wrapper(self, function):
        """
        Wraps a resource function with
          - saving the stack
          - logging errors
          - etc
        """
        try:
            function()
            self.save()
        except Exception as exc:
            logger.exception(exc)

    def provision_resources(self, resources=None):
        """
        Handles building a list of create tasks and
        running them with dynamic dependency handling via
        run_tasks.
        """
        logger.debug('Building create tasks list')

        if resources is None:
            logger.debug(
                'No resources list provided. '
                'Provisioning all stack resources.'
            )
            resources = self._resources

        tasks = []
        for resource in resources:
            logger.info(
                'Stack.provision_resources - %s marked for creation',
                resource.local_name
            )
            logger.debug(
                'Stack.provision_resources - Dependencies: %s',
                resource.get_dependencies()
            )

            tasks.append(
                create_task(
                    resource.local_name,
                    resource.create,
                    tuple(dep.local_name for dep in resource.get_dependencies())
                )
            )

        # This should be in a try except cause arbiter won't catch anything
        logger.info("Provisioning Resources ...")
        results = run_tasks(tasks)
        tasks_passed(
            results,
            logger,
            msg='Failed to provision resources',
            exception=StackError
        )

    def deprovision_resources(self, resources=None):
        """
        Handles building a list of destroy tasks and
        running them with dynamic dependency handling via
        run_tasks.

        NOTE: We are also responsible for inverting the
        dependency cases to the standard creation dependencies.
        """
        logger.debug('Building destroy tasks list')

        if resources is None:
            logger.debug(
                'No resources list provided. '
                'Deprovisioning all stack resources.'
            )
            resources = self._resources

        inverse_dependencies = {}
        for resource in resources:
            inverse_dependencies[resource.local_name] = []

            for dep in resource.get_dependencies():
                if dep.local_name not in inverse_dependencies:
                    inverse_dependencies[dep.local_name] = []

                inverse_dependencies[dep.local_name].append(resource.local_name)

        tasks = []
        for resource in resources:
            logger.info(
                'Stack.deprovision_resources - %s marked for deletion',
                resource.local_name
            )
            logger.debug(
                'Stack.deprovision_resources - Dependencies: %s',
                inverse_dependencies[resource.local_name]
            )

            tasks.append(
                create_task(
                    resource.local_name,
                    resource.destroy,
                    tuple(dep for dep in inverse_dependencies[resource.local_name])
                )
            )

        # TODO: Should check for failed tasks and throw an exception and traceback

        # This should be in a try except
        logger.info("Deprovisioning Resources ...")
        results = run_tasks(tasks)
        tasks_passed(
            results,
            logger,
            msg='Failed to deprovision resources',
            exception=StackError
        )

    def deserialize_resources(self, resource_list):
        """
        Given a list or resource dicts we:

        1) loop over them
        2) extract the resource plugin name from the 'Type'
        3) get the plugin and deserialize it from the dict
        4) add the deserialized resource to the list of resources.
        """
        for rsrc_dict in resource_list:
            # Get the resource plugin and deserialize it with the dict
            classname = rsrc_dict['type']

            resources = self._config.get_plugins(
                category_name='Resource',
                plugin_name=classname
            )

            if not resources:
                raise PluginError(
                    'Failed to locate resource plugin named {}'
                    .format(classname)
                )

            for resource in resources:
                if resource.provider.lower() == rsrc_dict['provider'].lower():
                    # Simply deserialize the stack
                    resource.deserialize(rsrc_dict)

                    # Add stack tags to resource if they
                    # aren't already there ie: this will add stack level
                    # tags to resource that are being deserialized from a manifest.
                    newtags = resource.tags
                    newtags.update(self._tags)
                    resource.tags = newtags

                    # Set the stack reference on the resource to our stack.
                    resource.stack = self

                    self._resources.append(resource)
                else:
                    raise PluginError(
                        'Failed to locate resource named {} for provider {}'
                        .format(classname, rsrc_dict['provider'].lower())
                    )
