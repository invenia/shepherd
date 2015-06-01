.. _storage:

Storage
========

Shepherd provides a storage mechanism for storing stack state between operations. This is particularly important for debugging inconsistent stack states and auditing changes to stack resources. Currently, only `DynamoDB <http://aws.amazon.com/dynamodb/>`_ is supported as a storage option, but storage in flat files and in database formats will be added in the future. The DynamoDB plugin by default will store stack states in a table called 'stacks'.


*** NOTE: Support for full stack versioning with auditing functionality will be provided before the first major release. ***
