import sys
import boto

from unittest import TestCase, skipIf
from datetime import datetime
from moto import mock_dynamodb

from shepherd.storage.dynamo import DynamoStorage


@skipIf(sys.version > '3', 'Moto dynamo endpoints fail under python3')
class TestDynamoStorage(TestCase):
    def setUp(self):
        name_fmt = '{stack_name}_{stack_creation}'
        self.test_stack = {
            'local_name': 'MyTestStack',
            'tags': {
                'stack_name': 'MyTestStack',
                'stack_creation': datetime.strftime(
                    datetime.utcnow(),
                    "%Y-%m-%d-%H-%M-%S"
                ),
            },
            'resources': [],
        }

        self.test_stack['global_name'] = name_fmt.format(**self.test_stack['tags'])

    def tearDown(self):
        pass

    @mock_dynamodb
    def test_dump(self):
        store = DynamoStorage()
        conn = boto.connect_dynamodb()
        conn.list_tables()
        store.dump(self.test_stack)

    @mock_dynamodb
    def test_dump_update(self):
        store = DynamoStorage()
        store.dump(self.test_stack)

        self.test_stack['resources'] = ['foo', 'bar']
        store.dump(self.test_stack)

    @mock_dynamodb
    def test_search(self):
        store = DynamoStorage()
        store.dump(self.test_stack)

        self.test_stack['tags']
        stacks = store.search(self.test_stack['tags'])
        self.assertEquals(len(stacks), 1)

        stacks = store.search({
            'stack_creation': self.test_stack['tags']['stack_creation'],
        })
        self.assertEquals(len(stacks), 1)

        stacks = store.search({'foo': 'bar'})
        self.assertEquals(len(stacks), 0)

    @mock_dynamodb
    def test_load(self):
        store = DynamoStorage()
        store.dump(self.test_stack)

        stack = store.load(self.test_stack['global_name'])
        self.assertIsNotNone(stack)

        stack = store.load('foo')
        self.assertIsNone(stack)
