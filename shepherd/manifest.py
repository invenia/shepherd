"""
Handles loading manifest files into a list of valid resource dicts.
Possibly from multiple files.
"""
from __future__ import print_function
from future.builtins import dict

import os
import logging
import json
import anyconfig

from tempfile import mkdtemp
from shutil import rmtree
from within.shell import working_directory
from jinja2 import Template, StrictUndefined

from shepherd.common.exceptions import ManifestError

INCLUDE_KEY = 'include'
INCLUDE_ERROR_MSG = (
    'Include statements in a dict must be the only '
    'entry with a valid filename string as the '
    'value.  For example:\n'
    '{\'include\': \'foo.json\'}'
)
# In the future this could be a list of extension paths stored
# in some kind of settings
EXTENSIONS_PATH = os.path.realpath('shepherd/extensions/')

logger = logging.getLogger(__name__)


class Manifest(object):
    """
    This class is responsible for loading and parsing the stack template
    files. It can then be used for building stack objects.

    In order,

    NOTE: the expected layout of the resources list should look something
    like this.
    ::

        [
            {
                'Name': 'MyInstance',
                'Type': 'Instance',
                'AvailabilityZone' : 'some-availablity-zone',
                'ImageId' :          'i-foo42',
                'InstanceType' :     't1-micro',
                'KeyName' :          'mykey.pem',
                'SpotPrice' :        '2.50',
                'SecurityGroups' :   [
                    'StackWebserverSecurityGroup',
                    'sg-bar24',
                    ...
                ],

                'UserData' : '#!/bin/bash\\necho \"initializing stack\"\\n'
                'Tags' : [
                    {
                        'Key' : 'Name',
                        'Value' : 'Dashboard'
                    },
                    {
                        'Key" : "StackLevel',
                        'Value' : 'Prod'
                    },
                    ...
                ],

            },
            ...
        ]

    VS::

        {
            "MyInstance" :
            {
                "Type" : "AWS::EC2::Instance",
                "Properties": {
                    "Tags" : [
                        {
                            "Key" : "Name",
                            "Value" : "Webserver"
                        },
                        {
                            "Key" : "StackLevel",
                            "Value" : { "Ref" : "StackLevel" }
                        }
                    ],
                    "AvailabilityZone" : { "Ref" : "StackAvailabilityZone" },
                    "ImageId" :          { "Ref" : "WebserverAMI" },
                    "InstanceType" :     { "Ref" : "WebserverInstanceType" },
                    "SecurityGroups" : [
                        { "Ref" : "StackWebserverSecurityGroup" },
                        sg-bar24
                    ],
                    "KeyName" :          { "Ref" : "CloudKeyName" },
                    "SpotPrice" :        { "Ref" : "T1MicroSpotPrice" },

                    "UserData" :
                    { "Fn::Base64" : { "Fn::Join" : [ "", [
                    "#!/bin/bash\\n \"initializing stack\"\\n"
                    ]]}}
                }
            },
            ...
        }

    Notice how only stack resource level variables like
    'StackDashboardSecurityGroup' remain.  Also, how the the name has been
    moved inside the dict and the properties have been moved up a level.
    """
    def __init__(self, config):
        """
        From the provided paths the specs are loaded and parsed.

        NOTE: I'm purposefully not removing the tmp directory on errors,
        because we may want to look at its contents if something fails

        Args:
            config (Config): Description
        """
        self._config = config
        self._template = {}
        self._vars = {}
        self._resources = []
        self._settings = self._config.settings
        self._filename = self._settings.manifest_path

        self._working_dir = mkdtemp(prefix=__name__)
        logger.debug(
            'Storing manifest temp files in %s.',
            self._working_dir
        )
        self._loader = Loader(self._filename)

    @property
    def resources(self):
        return self._resources

    def load(self):
        """
        Loaders are responsible for taking the list of files and building
        a single python dict from them.  The default loader is used if none
        is specified, which simply reads either the json or yaml files
        with the name params or resources.
        """
        logger.debug('Loading %s', self._filename)

        try:
            self._template = self._loader.run()
        except:
            logger.error('Failed to load stack spec')
            raise

        # Write result to file nicely so we can inspect the results later.
        outfile = os.path.join(self._working_dir, "loaded.json")
        logger.debug('Writing loaded template to %s', outfile)
        with open(outfile, 'w+') as fobj:
            fobj.write(json.dumps(dict(self._template), indent=1, sort_keys=True))

    def parse(self):
        """
        Loads the settings(s) into the template and params dicts,
        which can then be validated.
        """
        logger.debug('Parsing Parameters dict.')

        # Simplify the Parameters dict to just key : values
        if 'vars' not in self._template:
            raise ManifestError(
                'Parameters not in template dict',
                logger=logger
            )

        self._vars = self._template['vars']

        if 'vars' in self._settings:
            self._vars.update(dict(self._settings.vars))

        # Run any of the parser plugins on the Parameters dict
        parsers = self._config.get_plugins(category_name='Parser')
        for parser in parsers:
            self._vars = parser.run(self._vars)

        outfile = os.path.join(self._working_dir, "parsed.json")
        logger.debug('Writing parsed vars to %s', outfile)
        with open(outfile, 'w+') as fobj:
            fobj.write(json.dumps(dict(self._vars), indent=1, sort_keys=True))

        # Validate that we don't have any None values in the Parameters dict.
        for val in self._vars.values():
            if val is None:
                raise ManifestError(
                    'Some parameters still equal None after parsing.',
                    logger=logger
                )

    def map(self):
        """
        Maps values in the params dict to the values in the resources dict
        using jinja2 variable referencing syntax
        """
        logger.debug('Mapping Parameters into and simplifying resources list')

        if 'resources' not in self._template:
            raise ManifestError(
                'Resources not in template dict',
                logger=logger
            )

        jinja_template = Template(json.dumps(dict(self._template['resources'])))
        jinja_template.environment.undefined = StrictUndefined()
        resources_dict = json.loads(jinja_template.render(dict(self._vars)))

        # Turn resources into a list where the key ==> local_name
        for key, value in resources_dict.items():
            resource = value
            resource['local_name'] = key
            self._resources.append(resource)

        with open(os.path.join(self._working_dir, "final.json"), "w+") as fobj:
            fobj.write(json.dumps(self._resources, indent=1, sort_keys=True))

    def clear(self):
        """Cleans up the working directory"""
        logger.debug('Removing %s', self._working_dir)
        rmtree(self._working_dir)


class Loader(object):
    """
    The Loader handles packaging multiple template files together.

    Template files can be included in each other like so.  If the value in a
    list or dict is a dict with 1 entry, where the key is include and the
    value is the path to the file.

    List::

        MyList: [
            ...
            {"include" : "../path/to/file"},
            ...
        ]

    Dict::

        MyDict: {
            ...
            "include foo" : "../path/to/foo.json"},
            ...
        }

    NOTE: in the dict case the key value pair will be ignore like the value
    in the list.  Also, the file being imported must be a dict at the top
    level.
    """
    def __init__(self, filename):
        """
        recursively includes references to other template files with the json.
        While good practice will be to include your files to variables
        at the beginning of your files, this provides a generic solution.

        Args:
            filename (str): file to start loading
        """
        self._filename = filename

    def run(self):
        """
        Runs the loader returning the completed

        Returns:
            collection: Returns the fully loaded and unified template.
        """
        return self.load(self._filename)

    def load(self, filename):
        """
        Handles the actual loading and preporcessing of files.

        Args:
            filename (str): the file to load.
        Returns:
            collection: returns load collection and all recusively loaded ones.
        """
        try:
            realname = os.path.realpath(filename)
            working_path = os.path.dirname(realname)

            with working_directory(working_path):
                data = anyconfig.load(realname, safe=True)

                assert isinstance(data, dict)

                if 'includes' in data:
                    include_data = {}

                    # Iterate through the includes in order merging
                    # the dictionaries.  NOTE: Ordering matters here.
                    for include_file in data['includes']:
                        # Dict entries in new include file can override entries
                        # already in include_data.
                        sub = self.load(include_file)

                        if sub:
                            if include_data:
                                include_data.update(sub)
                            else:
                                include_data = sub

                    # Finally, merge the include data with our data
                    # our data will take priority in the merge if
                    # duplicate keys are found.
                    if include_data:
                        include_data.update(data)
                        data = include_data

                return data
        except ValueError as exc:
            # If we get a ValueError while building up
            # the dict, rethrow the error but supply the
            # filename it failed on.
            raise ValueError(
                '{} file {}'.format(
                    exc.message,
                    os.path.realpath(filename)
                )
            )
