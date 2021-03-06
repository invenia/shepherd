"""
shepherd.manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This modules contains the Config object itself, which is the
primary outward facing object for the package (kind of like app in Flask).

Notes:
    * Currently the builtin paths and plugins are hardcoded, we may want to
    inspect the plugins module and dirnames to create those variables.
    * See the common/config.schema for the schema of the settings dict.
    * the default settings dict is::

        {
            'manifest_path': '',
            'verbosity': 2,
            'retries': 120,
            'delay': 5,
            'vars': {},
            'storage': {
                'name': 'DynamoStorage',
                'settings': {}
            },
        }

"""
from __future__ import print_function

import os
import sys
import inspect
import fnmatch
import logging
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
from shepherd.common.plugins import Action
from shepherd.common.plugins import Storage
from shepherd.common.plugins import Parser
from shepherd.common.plugins import is_plugin
from shepherd.common.utils import validate_config, configure_logging

if sys.version > '3':
    from configparser import ConfigParser
else:
    from ConfigParser import ConfigParser

_PACKAGE_PATH = dirname(abspath(__file__))
_BUILTIN_PATHS = [
    join(_PACKAGE_PATH, 'resources'),
    join(_PACKAGE_PATH, 'actions'),
    join(_PACKAGE_PATH, 'storage'),
]
_DEFAULT_SETTINGS = AttrDict({
    'manifest_path': '',
    'verbosity': 2,
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
    _configs = []
    logging_verbosity = 0

    def __init__(self, settings, name):
        """Summary

        Args:
            settings (dict): the dictionary of settings
            name (str): the config name
        """
        assert settings is not None
        assert name is not None

        self._name = name
        self._settings = settings
        self._inspect_analyzer = None
        self._default_analyzer = None
        self._categories = None
        self._paths = _BUILTIN_PATHS
        self._plugins = None
        self._stacks = []

        validate_config(settings)
        if Config.logging_verbosity < settings['verbosity']:
            configure_logging(settings['verbosity'])
            Config.logging_verbosity = settings['verbosity']
            logger.info(
                'Increased logging verbosity from %s to %s with the new config...',
                Config.logging_verbosity,
                settings['verbosity']
            )

        self._configure_plugins()

    def _configure_plugins(self):
        """
        Handles initialization of the
        :class:`Config <Config>`.  This method shouldn't be called
        outside of this class.
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
            "Action": Action,
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
    def name(self):
        return self._name

    @property
    def settings(self):
        return self._settings

    @classmethod
    def make(cls, settings=None, name=""):
        """
        When first setting up the Config you should call this
        class method.

        Args:
            settings (dict, optional): desire settings values overriding the defaults.
            name (str, optional): the name of the config

        Returns: the created config obj
        """
        logger.debug('Creating Config named "%s"', name)
        config_settings = _DEFAULT_SETTINGS
        if settings:
            config_settings.update(settings)

        assert config_settings is not None
        new_config = Config(config_settings, name)
        for index, config in enumerate(cls._configs):
            if config.name == name:
                logger.warn('Recreating Config named %s', name)
                cls._configs[index] = new_config
                break
        else:
            cls._configs.append(new_config)

        return new_config

    @classmethod
    def make_from_file(cls, filename, name=""):
        """
        Loads the settings dict from a file and passes it to Config.make.

        Args:
            filename (str): name of the file to load
            name (str, optional): the name of the config

        Returns:
            Config: the created config obj
        """
        settings = anyconfig.load(filename, safe=True)
        return cls.make(settings=settings, name=name)

    @classmethod
    def get(cls, name=""):
        """
        Use this to access your desired Config.

        Args:
            name (str, optional): the unique name of the config you
                want returned.

        Returns: the config obj

        Raises:
            KeyError: if a config by that name does't exist.
        """
        logger.debug('Retrieving Config named "%s"', name)

        for config in cls._configs:
            if config.name == name:
                return config
        else:
            raise KeyError('No config with the name {} exists'.format(name))

    def get_plugins(self, category_name=None, plugin_name=None):
        """
        get_plugins returns a deepcopy of all the plugins fitting
        the search criteria.  While this isn't very memory efficient
        our plugins should be small and few between enough that it'll be
        worth getting independent copies of them.  For example we will likely
        want to work with multiple copies of the Same Resource plugin.

        Args:
            category_name (str, optional): a category to search for plugins in.
            plugin_name (str, optional): the name of the plugin to look for.

        Returns:
            list: of the plugins that match the criteria.
        """
        results = []

        if category_name and plugin_name:
            plugin_info = self._plugins.getPluginByName(
                plugin_name,
                category=category_name
            )

            if plugin_info:
                results.append(plugin_info.plugin_object.__class__())

        elif category_name and not plugin_name:
            plugin_infos = self._plugins.getPluginsOfCategory(category_name)

            for plugin_info in plugin_infos:
                results.append(plugin_info.plugin_object.__class__())

        elif plugin_name and not category_name:
            for category in self._plugins.getCategories():
                plugin_info = self._plugins.getPluginByName(
                    plugin_name,
                    category=category
                )

                if plugin_info:
                    results.append(plugin_info.plugin_object.__class__())

        elif not category_name and not plugin_name:
            plugin_infos = self._plugins.getAllPlugins()

            for plugin_info in plugin_infos:
                results.append(plugin_info.plugin_object.__class__())

        return results


class PluginFileAnalyzerInspection(IPluginFileAnalyzer):
    """
    This PluginFileAnalyzer determines the plugins via inspection.
    If the module contains a class that subclasses
    """
    def __init__(self, name, paths):
        """Summary

        Args:
            name (str): name of the Analyzer [requirement of yapsy]
            paths (list): the paths search through for loadable plugins
        """
        IPluginFileAnalyzer.__init__(self, name)
        self.module_paths = {}
        self.getModulePaths(paths)

    def isValidPlugin(self, filename):
        """
        Checks if the given filename is a valid plugin for this Strategy

        Args:
            filename (str): name of the file to inspect.
        """
        result = False

        if self.getPluginClass(filename):
            result = True

        return result

    def getInfosDictFromPlugin(self, dirpath, filename):
        """
        Returns the extracted plugin informations as a dictionary.
        This function ensures that "name" and "path" are provided.

        Args:
            dirpath (str): the directory of the file
            filename (str): the filename
        """
        infos = {}
        infos["name"] = self.getPluginClass(filename)
        infos["path"] = os.path.join(dirpath, filename)

        logger.debug('Name: %s, Path: %s', infos['name'], infos['path'])

        cf_parser = ConfigParser()
        cf_parser.add_section("Core")
        cf_parser.set("Core", "Name", infos["name"])
        cf_parser.set("Core", "Module", infos["path"])
        return infos, cf_parser

    def getPluginClass(self, filename):
        """
        Extracts the plugin class from the given file.

        Args:
            filename (str): name of file to inspect

        Returns:
            str: name of the plugin class
        """
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
        """
        Extracts the module_paths from the provided lis of paths.

        Args:
            paths (list): list of paths to walk
        """
        for path in paths:
            for root, _, filenames in os.walk(path):
                for filename in fnmatch.filter(filenames, '*.py'):
                    self.module_paths[filename] = os.path.abspath(root)
