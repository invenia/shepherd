from unittest import TestCase
from mock import MagicMock
from moto import mock_ec2
from datetime import datetime

from shepherd.resources.aws.securitygroup import SecurityGroup
from tests.unit import validate_empty_resource
from tests.unit import validate_deserialized_resource
from tests.unit import validate_serialized_resource


class TestSecurityGroup(TestCase):
    def setUp(self):
        self.test_security_group = {
            'local_name': 'TestSecurityGroup',
            'group_description': 'My test security group',
        }
        self.global_name = '{}_{}_{}'.format(
            self.test_security_group['local_name'],
            'TestStack',
            datetime.strftime(
                datetime.utcnow(),
                "%Y-%m-%d-%H-%M-%S"
            )
        )

        self.mack = MagicMock()
        self.mack.settings = {'retries': 0, 'delay': 0}
        self.mack.get_global_resource_name.return_value = self.global_name

    def tearDown(self):
        pass

    def test_init(self):
        security_group = SecurityGroup()

        validate_empty_resource(security_group)
        self.assertEquals(security_group._type, 'SecurityGroup')
        self.assertIsNone(security_group._group_id, None)
        self.assertIsNone(security_group._group_description, None)

    def test_deserialize(self):
        security_group = SecurityGroup()
        security_group.deserialize(self.test_security_group)

        validate_deserialized_resource(
            security_group,
            self.test_security_group
        )

    def test_serialize(self):
        security_group = SecurityGroup()
        security_group.deserialize(self.test_security_group)
        mydict = security_group.serialize()

        self.assertTrue(isinstance(mydict, dict))
        validate_serialized_resource(
            mydict,
            self.test_security_group
        )

    @mock_ec2
    def test_create(self):
        security_group = SecurityGroup()
        security_group.deserialize(self.test_security_group)
        security_group.stack = self.mack
        security_group.create()

    @mock_ec2
    def test_create_available(self):
        security_group = SecurityGroup()
        security_group.deserialize(self.test_security_group)
        security_group.stack = self.mack
        security_group.create()
        security_group.create()

    @mock_ec2
    def test_destroy(self):
        security_group = SecurityGroup()
        security_group.deserialize(self.test_security_group)
        security_group.stack = self.mack
        security_group.create()
        security_group.destroy()

    @mock_ec2
    def test_destroy_not_available(self):
        security_group = SecurityGroup()
        security_group.deserialize(self.test_security_group)
        security_group.stack = self.mack
        security_group.destroy()
