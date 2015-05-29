import boto

from unittest import TestCase
from mock import MagicMock
from moto import mock_iam
from datetime import datetime
from boto.exception import BotoServerError

from shepherd.common.exceptions import StackError
from shepherd.resources.aws.key import AccessKey
from shepherd.resources.aws.user import User

from tests.unit import validate_empty_resource
from tests.unit import validate_deserialized_resource
from tests.unit import validate_serialized_resource


class TestAccessKey(TestCase):
    def setUp(self):
        self.test_key = {
            'local_name': 'Testkey',
            'user_name': 'TestUser',
        }
        self.global_name = '{}_{}_{}'.format(
            self.test_key['user_name'],
            'TestStack',
            datetime.strftime(
                datetime.utcnow(),
                "%Y-%m-%d-%H-%M-%S"
            )
        )

        self.iamuser = User()
        self.iamuser._global_name = self.global_name
        self.iamuser._available = True

        self.mack = MagicMock()
        self.mack.settings = {'retries': 0, 'delay': 0}
        self.mack.get_resource_by_name.return_value = self.iamuser
        self.mack.get_global_resource_name.return_value = self.global_name

    def tearDown(self):
        pass

    def test_init(self):
        key = AccessKey()

        validate_empty_resource(key)
        self.assertEquals(key._type, 'AccessKey')
        self.assertIsNone(key._user_name)
        self.assertIsNone(key._access_key_id)

    def test_deserialize(self):
        key = AccessKey()
        key.deserialize(self.test_key)

        validate_deserialized_resource(key, self.test_key)

    def test_serialize(self):
        key = AccessKey()
        key.deserialize(self.test_key)
        mydict = key.serialize()

        self.assertTrue(isinstance(mydict, dict))
        validate_serialized_resource(mydict, self.test_key)

    @mock_iam
    def test_create_with_user(self):
        key = AccessKey()
        key.deserialize(self.test_key)
        key.stack = self.mack

        conn = boto.connect_iam()
        conn.create_user(self.global_name)

        key.create()

    @mock_iam
    def test_create_without_user(self):
        key = AccessKey()
        key.deserialize(self.test_key)
        key.stack = self.mack
        self.iamuser._available = False

        self.assertRaises(BotoServerError, key.create)

    @mock_iam
    def test_create_without_stack(self):
        key = AccessKey()
        key.deserialize(self.test_key)

        conn = boto.connect_iam()
        conn.create_user(self.global_name)

        self.assertRaises(StackError, key.create)

    @mock_iam
    def test_create_available(self):
        key = AccessKey()
        key.deserialize(self.test_key)
        key.stack = self.mack
        key._available = True

        conn = boto.connect_iam()
        conn.create_user(self.global_name)

        # create_key(self.global_name)
        key.create()

    @mock_iam
    def test_destroy(self):
        key = AccessKey()
        key.deserialize(self.test_key)
        key.stack = self.mack

        conn = boto.connect_iam()
        conn.create_user(self.global_name)
        key.create()
        key.destroy()

    @mock_iam
    def test_destroy_without_stack(self):
        key = AccessKey()
        key.deserialize(self.test_key)
        key.stack = self.mack

        conn = boto.connect_iam()
        conn.create_user(self.global_name)

        key.create()
        key.stack = None
        self.assertRaises(StackError, key.destroy)

    @mock_iam
    def test_destroy_not_available(self):
        key = AccessKey()
        key.deserialize(self.test_key)
        key.stack = self.mack

        conn = boto.connect_iam()
        conn.create_user(self.global_name)

        key.create()
        key.destroy()
        key.destroy()


def create_key(user_name):
    conn = boto.connect_iam()
    conn.create_access_key(user_name)
