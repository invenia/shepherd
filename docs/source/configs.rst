.. _configs:

Configs
===========

The shepherd framework is bootstrapped and configured using a Config object. A Config can either be created from a yaml or json file with the `Config.make_from_file` class method or from a dict with the `Config.make` class method. The dict or file should contain the following components


Manifest Path
--------------
(Required)

The ``manifest_path`` is the path to the root manifest file (see manifests for more details).


Verbosity
----------
(Optional: default=1)

The ``verbosity`` defines the verbosity of logging output. The Config will by default enable logging with a verbosity level of 1. This value can be increased up to 5 for more information.

** IMPORTANT: Set this to 0 if you don't want shepherd to setup logging for you **


Retries & Delay
----------------
(Optional: defaults are retries=120 and delay=5)

The ``retries`` and ``delay`` values specifying number of times resources should poll and the time to wait between polls respectively. An example of how this is used is waiting for instances to come online. Shepherd uses 120 retries with a delay of 5 by default.


Storage
--------
(Optional: default=``{'name': 'DynamoStorage'}``)

The ``storage`` value is a dictionary which specifies which storage plugin to use for saving stack state and any setting that should be passed to that plugin. By default shepherd uses the builtin DynamoDB plugin.


Vars
-----
(Optional)

The ``vars`` dictionary contains a list of values to pass into the manifest templates.

** NOTE: these values will have the highest precedence when parsing the manifest**


Extension Paths
----------------
(Optional)

The ``extension_paths`` provide an alternative search path to look for additional plugins such as Resources or Storage types. By default shepherd will just use the builtin resources and storage directories.


Summary
------------

A sample config may look something like


.. literalinclude:: ../../samples/manifests/simple/lamp-config.yml
