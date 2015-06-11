import os
import fnmatch

from unittest import TestCase
from moto import mock_iam, mock_ec2, mock_dynamodb
from within.shell import working_directory

from shepherd.config import Config
from shepherd.common.utils import run

MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__),
    'manifests/simple'
)
PLAYBOOK_PATH = os.path.join(
    os.path.dirname(__file__),
    'ansible_playbook'
)


class TestActions(TestCase):

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb()
    def test_create(self):
        self.run_action('CreateStack', name='TestStack')

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb()
    def test_destroy(self):
        global_name = self.run_action('CreateStack', name='TestStack')
        self.run_action('DestroyStack', name=global_name)

    @mock_iam()
    @mock_ec2()
    @mock_dynamodb()
    def test_ansible(self):
        global_name = self.run_action('CreateStack', name='TestStack')
        self.run_action(
            'Ansible',
            name=global_name,
            path=PLAYBOOK_PATH,
            playbook='playbook.yml',
            vault_key_file=os.path.join(PLAYBOOK_PATH, 'vault-password'),
            opt_flags='--dry-run'
        )

    def run_action(self, action, **kwargs):
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

            return run(action, config, **kwargs)
