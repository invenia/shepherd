from unittest import TestCase
from mock import MagicMock
from moto import mock_iam
from datetime import datetime

from shepherd.resources.aws.user import User
from tests.unit import validate_empty_resource
from tests.unit import validate_deserialized_resource
from tests.unit import validate_serialized_resource


class Testuser(TestCase):
    def setUp(self):
        self.test_user = {'local_name': 'TestUser'}
        self.global_name = '{}_{}_{}'.format(
            self.test_user['local_name'],
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
        user = User()

        validate_empty_resource(user)
        self.assertEquals(user._type, 'User')
        self.assertIsNone(user._user_info)
        self.assertEquals(user._groups, [])
        self.assertEquals(user._policies, [])

    def test_deserialize(self):
        user = User()
        user.deserialize(self.test_user)

        validate_deserialized_resource(user, self.test_user)

    def test_serialize(self):
        user = User()
        user.deserialize(self.test_user)
        mydict = user.serialize()

        self.assertTrue(isinstance(mydict, dict))
        validate_serialized_resource(mydict, self.test_user)

    @mock_iam
    def test_create(self):
        user = User()
        user.deserialize(self.test_user)
        user.stack = self.mack
        user.create()

    @mock_iam
    def test_create_available(self):
        user = User()
        user.deserialize(self.test_user)
        user.stack = self.mack
        user.create()
        user.create()

    @mock_iam
    def test_destroy(self):
        user = User()
        user.deserialize(self.test_user)
        user.stack = self.mack
        user.create()
        user.destroy()

    @mock_iam
    def test_destroy_not_available(self):
        user = User()
        user.deserialize(self.test_user)
        user.stack = self.mack
        user.destroy()
