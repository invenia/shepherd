from __future__ import print_function

import boto
from unittest import TestCase
from mock import MagicMock
from moto import mock_ec2
from datetime import datetime

from shepherd.resources.aws.securityingress import SecurityGroupIngress
from tests.unit import validate_empty_resource
from tests.unit import validate_deserialized_resource
from tests.unit import validate_serialized_resource


class TestSecurityGroup(TestCase):
    def setUp(self):
        self.test_security_group_ingress = {
            'local_name': 'TestSecurityGroupIngress',
            'group_name': 'TestSecurityGroup',
            'src_security_group_name': 'TestSrcSecurityGroup',
            'ip_protocol': 'tcp',
            'from_port': '9005',
            'to_port': '9005',
        }

        self.global_name = '{}_{}_{}'.format(
            self.test_security_group_ingress['local_name'],
            'TestStack',
            datetime.strftime(
                datetime.utcnow(),
                "%Y-%m-%d-%H-%M-%S"
            )
        )

        self.mack = MagicMock()
        self.mack.settings = {'retries': 0, 'delay': 0}
        self.mack.get_resource_by_name.return_value = None

    def tearDown(self):
        pass

    def test_init(self):
        security_group_ingress = SecurityGroupIngress()

        validate_empty_resource(security_group_ingress)
        self.assertEquals(security_group_ingress._type, 'SecurityGroupIngress')
        self.assertIsNone(security_group_ingress._group_name, None)
        self.assertIsNone(security_group_ingress._src_security_group_name, None)
        self.assertIsNone(security_group_ingress._cidr_ip, None)
        self.assertIsNone(security_group_ingress._ip_protocol, None)
        self.assertIsNone(security_group_ingress._from_port, None)
        self.assertIsNone(security_group_ingress._to_port, None)

    def test_deserialize(self):
        security_group_ingress = SecurityGroupIngress()
        security_group_ingress.deserialize(self.test_security_group_ingress)

        validate_deserialized_resource(
            security_group_ingress,
            self.test_security_group_ingress
        )

    def test_serialize(self):
        security_group_ingress = SecurityGroupIngress()
        security_group_ingress.deserialize(self.test_security_group_ingress)
        mydict = security_group_ingress.serialize()

        self.assertTrue(isinstance(mydict, dict))
        validate_serialized_resource(
            mydict,
            self.test_security_group_ingress
        )

    @mock_ec2
    def test_create(self):
        security_group_ingress = SecurityGroupIngress()
        security_group_ingress.deserialize(self.test_security_group_ingress)
        security_group_ingress.stack = self.mack

        conn = boto.connect_ec2()
        conn.create_security_group(
            security_group_ingress._group_name,
            security_group_ingress._group_name
        )
        conn.create_security_group(
            security_group_ingress._src_security_group_name,
            security_group_ingress._src_security_group_name
        )
        security_group_ingress.create()

    @mock_ec2
    def test_create_available(self):
        security_group_ingress = SecurityGroupIngress()
        security_group_ingress.deserialize(self.test_security_group_ingress)
        security_group_ingress.stack = self.mack

        conn = boto.connect_ec2()
        conn.create_security_group(
            security_group_ingress._group_name,
            security_group_ingress._group_name
        )
        conn.create_security_group(
            security_group_ingress._src_security_group_name,
            security_group_ingress._src_security_group_name
        )
        security_group_ingress.create()
        security_group_ingress.create()

    @mock_ec2
    def test_destroy(self):
        security_group_ingress = SecurityGroupIngress()
        security_group_ingress.deserialize(self.test_security_group_ingress)
        security_group_ingress.stack = self.mack

        conn = boto.connect_ec2()
        conn.create_security_group(
            security_group_ingress._group_name,
            security_group_ingress._group_name
        )
        conn.create_security_group(
            security_group_ingress._src_security_group_name,
            security_group_ingress._src_security_group_name
        )
        security_group_ingress.create()
        security_group_ingress.destroy()

    @mock_ec2
    def test_destroy_not_available(self):
        security_group_ingress = SecurityGroupIngress()
        security_group_ingress.deserialize(self.test_security_group_ingress)
        security_group_ingress.stack = self.mack
        security_group_ingress.destroy()
