"""
shepherd.manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This modules contains the Config object itself, which is the
primary outward facing object for the package (kind of like app in Flask).

NOTE: Currently the builtin paths and plugins are hardcoded, we may want to
inspect the plugins module and dirnames to create those variables.
"""
from __future__ import print_function

import os
import sys
import inspect
import fnmatch
import logging
import copy
import anyconfig

from os.path import dirname, join, abspath
from importlib import import_module
from yapsy.PluginManager import PluginManager
from yapsy.PluginFileLocator import PluginFileLocator
from yapsy.PluginFileLocator import IPluginFileAnalyzer
from yapsy.PluginFileLocator import PluginFileAnalyzerWithInfoFile
from attrdict import AttrDict

# from shepherd.common.exceptions import PluginError
from shepherd.common.plugins import Resource
from shepherd.common.plugins import Task
from shepherd.common.plugins import Storage
from shepherd.common.plugins import Parser
from shepherd.common.plugins import is_plugin
from shepherd.common.utils import validate_config

if sys.version > '3':
    from configparser import ConfigParser
else:
    from ConfigParser import ConfigParser

_PACKAGE_PATH = dirname(abspath(__file__))
_BUILTIN_PATHS = [
    join(_PACKAGE_PATH, 'resources'),
    join(_PACKAGE_PATH, 'tasks'),
    join(_PACKAGE_PATH, 'storage'),
]
_DEFAULT_SETTINGS = AttrDict({
    'manifest_path': '',
    'debug': True,
    'retries': 120,
    'delay': 5,
    'vars': {},
    'storage': {
        'name': 'DynamoStorage',
        'settings': {}
    },
})

logger = logging.getLogger(__name__)


class Config(object):
    """
    The :class:`Config <Config>` is responsible for managing the
    plugins and executing given tasks.
    """
    _configs = {}

    def __init__(self, settings):
        self._settings = settings
        self._inspect_analyzer = None
        self._default_analyzer = None
        self._categories = None
        self._paths = _BUILTIN_PATHS
        self._plugins = None
        self._stacks = []

        validate_config(self.settings)
        self._configure_plugins()

    def _configure_plugins(self):
        """
        Handles initialization of the
        :class:`Config <Config>`.  This method shouldn't be called
        outside of this class.

        :param settings: (optional) a settings describing which plugins to load etc.
        """
        logger.debug('Configuring Config')

        # Setup the locators
        # Inspection analyzer, mostly for builtin plugins
        # (resources, tasks, etc)
        self._inspect_analyzer = PluginFileAnalyzerInspection(
            'inspector',
            _BUILTIN_PATHS
        )
        # The default analyzer for any extension paths that we don't trust.
        self._default_analyzer = PluginFileAnalyzerWithInfoFile(
            'default',
            extensions='plugin'
        )
        # The order of the analyzers could matter.
        self._locator = PluginFileLocator(
            analyzers=[
                self._inspect_analyzer,
                self._default_analyzer,
            ]
        )

        # Create the categories filter dict
        self._categories = {
            "Resource": Resource,
            "Task": Task,
            "Storage": Storage,
            "Parser": Parser,
        }

        # Setup the search paths
        if self._settings and "extension_paths" in self._settings:
            self._paths.extend(self._settings["extension_paths"])

        # Actually create the PluginManager
        self._plugins = PluginManager(
            categories_filter=self._categories,
            directories_list=self._paths,
            plugin_locator=self._locator
        )

        # Collect the plugins
        self._plugins.collectPlugins()

    @property
    def settings(self):
        return self._settings

    @classmethod
    def make(cls, settings=None, name=""):
        """
        When first setting up the Config you should call this
        class method.

        :param settings: (optional) a settings describing which plugins to load etc.
        """
        logger.debug('Creating Config named "{}"'.format(name))
        config_settings = _DEFAULT_SETTINGS
        if settings:
            config_settings = config_settings + settings

        if name not in cls._configs:
            logger.info('Creating Config...')
            cls._configs[name] = Config(config_settings)

        return cls._configs[name]

    @classmethod
    def make_from_file(cls, filename, name=""):
        config_settings = _DEFAULT_SETTINGS

        if name in cls._configs:
            logger.warn('Recreating Config object from settings loaded in file')
        else:
            logger.debug('Creating Config from file...')

        settings = anyconfig.load(filename, safe=True)
        if settings:
            config_settings.update(settings)

        cls._configs[name] = Config(config_settings)

        return cls._configs[name]

    @classmethod
    def get(cls, name=""):
        """
        Use this to access your desired Config.
        """
        logger.debug('Retrieving Config named "{}"'.format(name))

        if name in cls._configs:
            return cls._configs[name]
        else:
            raise KeyError('No config with the name {} exists'.format(name))

    # Unclear whether to keep this
    # def run(self, task, **kwargs):
    #     """
    #     Searches for the task to apply to the stack.
    #     Searches both the default paths as well as

    #     :param task: the name of the task you want to run.
    #     :param kwargs: a dictionary of parameters to be passed to the task.
    #     """
    #     tasks = self.get_plugins(category_name='Task', plugin_name=task)

    #     if tasks:
    #         task = tasks[0]
    #         task.run(**kwargs)
    #     else:
    #         raise PluginError('Failed to locate task {}'.format(task))

    def get_plugins(self, category_name=None, plugin_name=None):
        """
        get_plugins returns a deepcopy of all the plugins fitting
        the search criteria.  While this isn't very memory efficient
        our plugins should be small and few between enough that it'll be
        worth getting independent copies of them.  For example we will likely
        want to work with multiple copies of the Same Resource plugin.

        :param category_name: (optional) a category to search for plugins in.
        :param plugin_name: (optional) the name of the plugin to look for.
        """
        results = []

        if category_name and plugin_name:
            plugin_info = self._plugins.getPluginByName(
                plugin_name,
                category=category_name
            )

            if plugin_info:
                results.append(copy.deepcopy(plugin_info.plugin_object))

        elif category_name and not plugin_name:
            plugin_infos = self._plugins.getPluginsOfCategory(category_name)

            for plugin_info in plugin_infos:
                results.append(copy.deepcopy(plugin_info.plugin_object))

        elif plugin_name and not category_name:
            for category in self._plugins.getCategories():
                plugin_info = self._plugins.getPluginByName(
                    plugin_name,
                    category=category
                )

                if plugin_info:
                    results.append(copy.deepcopy(plugin_info.plugin_object))

        elif not category_name and not plugin_name:
            plugin_infos = self._plugins.getAllPlugins()

            for plugin_info in plugin_infos:
                results.append(copy.deepcopy(plugin_info.plugin_object))

        return results


class PluginFileAnalyzerInspection(IPluginFileAnalyzer):
    """
    This PluginFileAnalyzer determines the plugins via inspection.
    If the module contains a class that subclasses
    """
    def __init__(self, name, paths):
        IPluginFileAnalyzer.__init__(self, name)
        self.module_paths = {}
        self.getModulePaths(paths)

    def isValidPlugin(self, filename):
        """
        Checks if the given filename is a valid plugin for this Strategy
        """
        result = False

        if self.getPluginClass(filename):
            result = True

        return result

    def getInfosDictFromPlugin(self, dirpath, filename):
        """
        Returns the extracted plugin informations as a dictionary.
        This function ensures that "name" and "path" are provided.
        """
        infos = {}
        infos["name"] = self.getPluginClass(filename)
        infos["path"] = os.path.join(dirpath, filename)

        logger.debug('Name: {}, Path: {}'.format(infos['name'], infos['path']))

        cf_parser = ConfigParser()
        cf_parser.add_section("Core")
        cf_parser.set("Core", "Name", infos["name"])
        cf_parser.set("Core", "Module", infos["path"])
        return infos, cf_parser

    def getPluginClass(self, filename):
        plugin_class = None

        if filename in self.module_paths:
            sys.path.insert(0, self.module_paths[filename])

            mod_name = os.path.splitext(filename)[0]
            mod = import_module(mod_name)

            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if is_plugin(obj):
                    plugin_class = name
                    break

            sys.path.remove(self.module_paths[filename])

        return plugin_class

    def getModulePaths(self, paths):
        for path in paths:
            for root, dirnames, filenames in os.walk(path):
                for filename in fnmatch.filter(filenames, '*.py'):
                    self.module_paths[filename] = os.path.abspath(root)
