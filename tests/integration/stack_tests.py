import os
import fnmatch

from unittest import TestCase
from moto import mock_iam, mock_ec2, mock_dynamodb

from within.shell import working_directory

from shepherd.stack import Stack
from shepherd.config import Config
from shepherd.common.exceptions import PluginError

MANIFEST_PATH = 'manifests/simple'


class TestStack(TestCase):
    def setUp(self):
        self.config = Config.make(
            settings={
                'retries': 0,
                'delay': 0,
            },
            name='test_config'
        )
        self.resources = [
            {
                'local_name': 'TestUser',
                'type': 'User',
                'provider': 'aws',
                'path': '/',
                'policies': [{
                    "PolicyName": "admin",
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": []
                    }
                }]
            },
            {
                'local_name': 'TestKey',
                'type': 'AccessKey',
                'provider': 'aws',
                'user_name': 'TestUser'
            },
            {
                'local_name': 'TestVolume',
                'type': 'Volume',
                'provider': 'aws',
                'availability_zone': 'a',
                'iops': 500,
                'size': 10,
            },
            {
                'local_name': 'TestSecurityGroup',
                'type': 'SecurityGroup',
                'provider': 'aws',
                'group_description': 'My test security group',
            },
            {
                'local_name': 'TestSrcSecurityGroup',
                'type': 'SecurityGroup',
                'provider': 'aws',
                'group_description': 'My test source security group',
            },
            {
                'local_name': 'TestSecurityGroupIngress',
                'type': 'SecurityGroupIngress',
                'provider': 'aws',
                'group_name': 'TestSecurityGroup',
                'src_security_group_name': 'TestSrcSecurityGroup',
                'ip_protocol': 'tcp',
                'from_port': '5000',
                'to_port': '5000',
            }
        ]

    def tearDown(self):
        self.config = Config.make(
            settings={
                'retries': 0,
                'delay': 0,
            },
            name='test_config'
        )

    def test_init(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)

    def test_serialize(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)
        mydict = self.stack.serialize()
        self.assertTrue(isinstance(mydict, dict))

    def test_deserialize(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)
        mydict = self.stack.serialize()
        self.assertTrue(isinstance(mydict, dict))
        self.stack.deserialize(mydict)

    def test_get_global_resource_name(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)

        global_name = self.stack.get_global_resource_name('TestKey')
        self.assertTrue(len(global_name) > len('TestKey'))
        self.assertTrue(global_name.startswith('TestKey'))

    def test_get_resource_by_name(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)

        key = self.stack.get_resource_by_name('TestKey')
        self.assertIsNotNone(key)

        foo = self.stack.get_resource_by_name('Foo')
        self.assertIsNone(foo)

    def test_get_resource_by_type(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)

        keys = self.stack.get_resource_by_type('AccessKey')
        self.assertEquals(len(keys), 1)

        users = self.stack.get_resource_by_type('User')
        self.assertEquals(len(users), 1)

        bars = self.stack.get_resource_by_type('Bar')
        self.assertEquals(len(bars), 0)

    def test_get_resource_by_tags(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)

        resources = self.stack.get_resource_by_tags(
            {'stack_name': 'test_stack'}
        )
        self.assertTrue(len(resources) > 0)

        resources = self.stack.get_resource_by_tags(
            {'stack_name': 'foo'}
        )
        self.assertEquals(len(resources), 0)

        resources = self.stack.get_resource_by_tags(
            {'foo': 'bar'}
        )
        self.assertEquals(len(resources), 0)

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb()
    def test_provision_resources(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)

        self.stack.provision_resources()

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb
    def test_deprovision_resources(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)

        self.stack.provision_resources()
        self.stack.deprovision_resources()

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb()
    def test_save(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)
        self.stack.save()

        self.stack.provision_resources()
        self.stack.save()

        self.stack.deprovision_resources()
        self.stack.save()

        with self.assertRaises(PluginError):
            # Need to access storage name via dict syntax cause otherwise it operates on a deep copy
            # rathern than the same reference.
            self.stack._config._settings['storage']['name'] = 'Foo'
            self.stack.save()

        self.stack._config._settings['storage']['name'] = 'DynamoStorage'

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb()
    def test_restore(self):
        self.stack = Stack('test_stack', self.config)
        self.stack.deserialize_resources(self.resources)
        self.stack.save()
        Stack.restore(self.stack.global_name, self.config)

        with self.assertRaises(PluginError):
            self.stack._config._settings['storage']['name'] = 'Foo'
            Stack.restore('test_stack', self.config)

        self.stack._config._settings['storage']['name'] = 'DynamoStorage'

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb()
    def test_stack_provisioning_with_manifest(self):
        config = None

        working_dir = os.path.dirname(os.path.realpath(__file__))

        with working_directory(working_dir):
            for filename in os.listdir(MANIFEST_PATH):
                if fnmatch.fnmatch(filename, '*config.yml'):
                    config = Config.make_from_file(
                        os.path.join(MANIFEST_PATH, filename),
                        name=MANIFEST_PATH
                    )

            self.assertIsNotNone(config)
            config.settings.retries = 0
            config.settings.delay = 0

            stack = Stack.make('TestStack', config)
            stack.provision_resources()
            stack.deprovision_resources()
