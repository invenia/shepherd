.. _resources:

Resources
============

Like :ref:`Stacks`, Resources are core to the shepherd framework. While the list of available resources will be updating regularly, all resources will support the following API.


Resource Properties:
----------------------

- ``local_name``: name provided in the manifest, local to the stack it was created with.
- ``global_name``: the unique name of the resource on the desired cloud provider. By default this is ``{{local_name}}_{{stack_name}}``.
- ``provider``: the provider of the resource (ie: 'aws' ro 'digitalocean'.
- ``type``: the resouce type name (ie: 'Instance', 'Volume', etc)
- ``available``: a bool as to whether the resource has been provisioned.
- ``tags``: a dictionary of tags for easier querying of resources.
- ``stack``: a reference to the stack the resource belongs to.


Resource Methods:
---------------------

All 3 of the methods below must be implemented in the concrete subclass of Resource.

- ``create(self)``: the method that handles creating the resources.
- ``destroy(self)``: handle destruction and cleanup of the resources.
- ``get_dependencies(self)``: provides a list of other resources that this resource depends on for creation (the inverse dependency is assumed for destruction).


*** NOTE: Resource also provides 2 decorators ``@Resource.validate_create(cls, logger)`` and ``@Resource.validate_destroy(cls, logger)`` which provide some handy checks and logging info for subclassed Resource ``create`` and ``destroy`` methods. ***
