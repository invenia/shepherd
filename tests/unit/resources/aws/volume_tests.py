import boto

from unittest import TestCase
from datetime import datetime
from mock import MagicMock
from moto import mock_ec2

from shepherd.resources.aws.volume import Volume
from tests.unit import validate_empty_resource
from tests.unit import validate_deserialized_resource
from tests.unit import validate_serialized_resource


class TestVolume(TestCase):
    def setUp(self):
        self.test_volume = {
            'local_name': 'TestVolume',
            'availability_zone': 'a',
            'iops': 5000,
            'size': 10,
        }

        self.mack = MagicMock()
        self.mack.settings = {'retries': 0, 'delay': 0}
        self.mack.tags = {
            'stack_name': 'TestStack',
            'stack_creation': datetime.strftime(
                datetime.utcnow(),
                "%Y-%m-%d-%H-%M-%S"
            ),
        }

    def tearDown(self):
        pass

    def test_init(self):
        volume = Volume()

        validate_empty_resource(volume)
        self.assertEquals(volume._type, 'Volume')
        self.assertIsNone(volume._snapshot_id)
        self.assertIsNone(volume._volume_id)
        self.assertIsNone(volume._availability_zone)
        self.assertIsNone(volume._iops)
        self.assertIsNone(volume._size)
        self.assertEquals(volume._volume_type, 'io1')
        self.assertFalse(volume._encrypted)

    def test_deserialize(self):
        volume = Volume()
        volume.deserialize(self.test_volume)

        validate_deserialized_resource(volume, self.test_volume)

    def test_serialize(self):
        volume = Volume()
        volume.deserialize(self.test_volume)
        mydict = volume.serialize()

        self.assertTrue(isinstance(mydict, dict))
        validate_serialized_resource(mydict, self.test_volume)

    @mock_ec2
    def test_create(self):
        volume = Volume()
        volume.deserialize(self.test_volume)
        volume.stack = self.mack
        volume.create()

    @mock_ec2
    def test_create_available(self):
        volume = Volume()
        volume.deserialize(self.test_volume)
        volume.stack = self.mack
        volume.create()
        volume.create()

    @mock_ec2
    def test_destroy(self):
        volume = Volume()
        volume.deserialize(self.test_volume)
        volume.stack = self.mack
        volume.create()
        volume.destroy()

    @mock_ec2
    def test_destroy_available(self):
        volume = Volume()
        volume.deserialize(self.test_volume)
        volume.stack = self.mack
        volume.destroy()

    @mock_ec2
    def test_with_snapshot(self):
        conn = boto.connect_ec2()
        boto_volume = conn.create_volume(80, "us-east-1a")
        snapshot = boto_volume.create_snapshot('a test snapshot')

        volume = Volume()
        self.test_volume['snapshot_id'] = snapshot.id
        volume.deserialize(self.test_volume)
        volume.stack = self.mack
        volume.create()
        volume.destroy()
