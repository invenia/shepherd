.. _manifests:

Manifests
=============

Manifests are declarative YAML files describing the configuration of a collection of resources. If you're familiar with Amazon's `cloudformation <http://aws.amazon.com/cloudformation/>`_, these are like cloudformation `templates <http://aws.amazon.com/cloudformation/aws-cloudformation-templates/>`_ with a cleaner and more flexible syntax. Shepherd uses Jinja2 templating for handling variables, which results in a very familiar syntax for developers and system administrators comfortable with `Ansible <http://docs.ansible.com>`_.

Basic Structure
----------------

A standard valid manifest file consists of 3 root keys:

1) ``resources``
2) ``vars``
3) ``includes``

Along with the above 3 root keys, manifest are parsed utilizing `Jinja2 <http://jinja.pocoo.org/docs/dev/>`_ templating. Which allows variables in ``vars`` to used in


Resources
----------
(Required)

The resources value is a dict where each key is the name of different resource (local to the manifest namespace). Each resource is also a dict providing the required parameters needed to build the required `Resources`_ Object, as such validation of each resource dict is limited to whether it is valid YAML and further validation occurs at Resource initialization.


Vars
-----
(Optional)

The vars value is also a dict where each key is a variable name and the value is the value to be inserted. This dictionary is used by the Jinja2 templating to replace variables in the resource dict.


Includes
---------
(Optional)

In order to break up potentially large manifests the include value is a list of files to include in the current manifest. The included files must still have the same valid format as the root manifest and are merged in where duplicates give priority to the current manifest over the included one.


Summary
--------------

A sample main file might look like

.. literalinclude:: ../../samples/manifests/simple/lamp-manifest.yml

and the supporting ``common-vars.yml`` could look like

.. literalinclude:: ../../samples/manifests/simple/common-vars.yml


YAML
------

While shepherd may support other formats in the future, we formally support YAML format for manifests. We believe YAML to be more readable than JSON and more flexible that INI config files. With that said there are a few gotchas and awkward features. For the most part the Ansible documentation has a very good summary of the most common YAML gotchas `here <http://docs.ansible.com/YAMLSyntax.html>`_. In addition a very useful feature in YAML is multiline strings, which are demonstrated in the ``WebServer['user_data']`` in the sample manifest above.
