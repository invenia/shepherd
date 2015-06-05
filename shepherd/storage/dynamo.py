"""
This file contains code for storing and accessing serialized
stacks on Amazon's DynamoDB.

TODO:
1) Improve documentation
3) some unit tests
"""
from __future__ import print_function

import time
import boto
import json

from attrdict import AttrDict
from boto.dynamodb.condition import EQ
from boto.dynamodb.exceptions import DynamoDBResponseError, DynamoDBKeyNotFoundError

from shepherd.common.utils import get_logger
from shepherd.common.plugins import Storage


DEFAULT_SETTINGS = AttrDict({
    'table_name': 'stacks',
    'hash_key_name': 'global_name',
    'hash_key_proto_value': str,
    'read_units': 10,
    'write_units': 5,
})


def dynamize(stack):
    if 'tags' in stack:
        for key in stack['tags']:
            stack['tag_{}'.format(key)] = stack['tags'][key]

        del stack['tags']

    for key in stack:
        if isinstance(stack[key], dict) or isinstance(stack[key], AttrDict):
            stack[key] = json.dumps(dict(stack[key]))
            get_logger(stack).debug('dynamize - key=%s, value=%s\n', key, stack[key])

        elif isinstance(stack[key], list):
            stack[key] = json.dumps(list(stack[key]))


def dedynamize(stack):
    if 'tags' not in stack:
        stack['tags'] = {}

    to_delete = []
    for key in stack:
        if key.startswith('tag_'):
            tag_name = key[4:]
            stack['tags'][tag_name] = stack[key]
            to_delete.append(key)   # Mark tag key to be deleted

    # Cleanup all the tag keys marked for deletion
    for key in to_delete:
        del stack[key]

    for key in stack:
        try:
            stack[key] = json.loads(stack[key])
        except(TypeError, ValueError):
            pass


class DynamoStorage(Storage):
    def __init__(self):
        super(DynamoStorage, self).__init__()
        self._table = None
        self._settings = DEFAULT_SETTINGS

    def configure(self, settings):
        self._settings.update(settings)

    def create_table(self):
        """
        Creates the dynamodb table and waits for it to become active.

        TODO: Accept a configuration object for the table schema.
        """
        self._logger.info('Creating dynamodb table %s', self._settings.table_name)
        conn = boto.connect_dynamodb()

        schema = conn.create_schema(
            hash_key_name=self._settings.hash_key_name,
            hash_key_proto_value=self._settings.hash_key_proto_value
        )

        table = conn.create_table(
            name=self._settings.table_name,
            schema=schema,
            read_units=self._settings.read_units,
            write_units=self._settings.write_units
        )

        # Could probably use a retry decorator
        while table.status != 'ACTIVE':
            self._logger.debug(
                'Waiting for table %s to become active',
                self._settings.table_name
            )
            table = conn.get_table(self._settings.table_name)
            time.sleep(5)

        self._table = table

    def get_table(self):
        """
        Handles getting or creating the Dynamodb
        table.
        """
        conn = boto.connect_dynamodb()

        if self._table is not None:
            return self._table

        try:
            self._table = conn.get_table(self._settings.table_name)
        except DynamoDBResponseError:
            self.create_table()

        return self._table

    def search(self, tags):
        """
        Given a dict of tags.

        Search the store for serialized stacks
        that match to those tags. Returning a list of
        the stack names that match.

        NOTE: Run O(n) time, so you should try and
        archive old/unused stacks whenever possible.
        """
        stacks = []

        table = self.get_table()
        scan_filter = {}
        for key, value in tags.items():
            scan_filter['tag_{}'.format(key)] = EQ(value)

        results = table.scan(scan_filter=scan_filter)

        for result in results:
            stack = result
            dedynamize(stack)
            stacks.append(stack)

        return stacks

    def load(self, name):
        """
        Given a unique name.

        Search the store for the serialized stack with
        that name.  Returns a single stack dict.
        """
        stack = None
        table = self.get_table()

        try:
            stack = table.get_item(name)
            dedynamize(stack)
        except DynamoDBKeyNotFoundError:
            self._logger.warn('Could not find stack %s', name)

        return stack

    def dump(self, stack):
        """
        Takes a stack dict and stores it
        in the datastore of your choice.
        """
        # Copy the stack dict cause we are going to mutate it
        # before inserting into dynamo
        entry = stack.copy()
        item = None
        conn = boto.connect_dynamodb()
        table = self.get_table()
        dynamize(entry)

        try:
            item = conn.get_item(table, entry[self._settings.hash_key_name])

            for key in entry:
                item[key] = entry[key]
        except DynamoDBKeyNotFoundError:
            self._logger.info(
                'Stack %s not found. Creating new stack entry.',
                entry[self._settings.hash_key_name]
            )
            item = table.new_item(
                hash_key=entry[self._settings.hash_key_name],
                attrs=entry
            )

        if item is not None:
            self._logger.debug('Inserting new entry %s', entry[self._settings.hash_key_name])
            conn.put_item(item)

    def delete(self, name):
        item = None
        table = self.get_table()

        try:
            # attempt an update
            item = table.get_item(name)
            table.delete_item(item)

        except DynamoDBKeyNotFoundError:
            self._logger.warn('No stack named %s exists to delete.', name)
