import os
import fnmatch

from unittest import TestCase
from within.shell import working_directory

from shepherd.stack import Stack
from shepherd.config import Config

MANIFEST_PATH = 'manifests/simple'


class TestStack(TestCase):
    def setUp(self):
        self.working_dir = os.path.dirname(os.path.realpath(__file__))

        with working_directory(self.working_dir):
            for filename in os.listdir(MANIFEST_PATH):
                if fnmatch.fnmatch(filename, '*config.yml'):
                    self.config = Config.make_from_file(
                        os.path.join(MANIFEST_PATH, filename),
                        name=MANIFEST_PATH
                    )

    def tearDown(self):
        pass

    def test_stack_provisioning(self):
        with working_directory(self.working_dir):
            stack = Stack.make('TestStack', config_name=MANIFEST_PATH)
            stack.provision_resources()
            stack.deprovision_resources()
