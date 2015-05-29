import boto

from unittest import TestCase
from datetime import datetime
from mock import MagicMock
from moto import mock_ec2

from shepherd.resources.aws.instance import Instance
from tests.unit import validate_empty_resource
from tests.unit import validate_deserialized_resource
from tests.unit import validate_serialized_resource


class TestInstance(TestCase):
    def setUp(self):
        self.test_instance = {
            'local_name': 'TestInstance',
            'availability_zone': 'a',
            'image_id': 'ami-1234abcd',
            'instance_type': 't1.micro',
            'security_groups': ['TestGroup'],
            'key_name': 'test_keypair',
            'volumes': [{
                'Device': '/dev/sdh',
                'VolumeId': 'TestVolume'
            }]
        }

        self.volumes = {}
        self.security_groups = {}
        self.mack = MagicMock()
        self.mack.settings = {'retries': 0, 'delay': 0}
        self.mack.tags = {
            'stack_name': 'TestStack',
            'stack_creation': datetime.strftime(
                datetime.utcnow(),
                "%Y-%m-%d-%H-%M-%S"
            ),
        }
        self.mack.get_global_resource_name.side_effect = self.mock_get_global_resource_name
        self.mack.get_resource_by_name.side_effect = self.mock_get_resource_by_name

    def tearDown(self):
        pass

    def mock_get_global_resource_name(self, name):
        return name

    def mock_get_resource_by_name(self, name):
        resource = None

        for key in self.volumes:
            if key == name:
                resource = MagicMock()
                resource.volume_id = self.volumes[key]
                return resource

        for key in self.security_groups:
            if key == name:
                resource = MagicMock()
                resource.id = self.security_groups[key]
                return resource

        return resource

    def mock_create_dependencies(self):
        conn = boto.connect_ec2()

        for vol in self.test_instance['volumes']:
            volume = conn.create_volume(
                size=80,
                zone=self.test_instance['availability_zone'],
            )

            self.volumes[vol['VolumeId']] = volume.id

        for groupname in self.test_instance['security_groups']:
            group_id = conn.create_security_group(
                groupname, groupname)

            self.security_groups[groupname] = group_id

    def test_init(self):
        instance = Instance()

        validate_empty_resource(instance)

    def test_deserialize(self):
        instance = Instance()
        instance.deserialize(self.test_instance)

        validate_deserialized_resource(instance, self.test_instance)

    def test_serialize(self):
        instance = Instance()
        instance.deserialize(self.test_instance)
        mydict = instance.serialize()

        self.assertTrue(isinstance(mydict, dict))
        validate_serialized_resource(mydict, self.test_instance)

    @mock_ec2
    def test_create(self):
        instance = Instance()
        instance.deserialize(self.test_instance)
        instance.stack = self.mack
        self.mock_create_dependencies()
        instance.create()

    @mock_ec2
    def test_create_available(self):
        instance = Instance()
        instance.deserialize(self.test_instance)
        instance.stack = self.mack
        self.mock_create_dependencies()
        instance.create()
        instance.create()

    @mock_ec2
    def test_destroy(self):
        instance = Instance()
        instance.deserialize(self.test_instance)
        instance.stack = self.mack
        self.mock_create_dependencies()
        instance.create()
        instance.destroy()

    @mock_ec2
    def test_destroy_available(self):
        instance = Instance()
        instance.deserialize(self.test_instance)
        instance.stack = self.mack
        self.mock_create_dependencies()
        instance.destroy()
