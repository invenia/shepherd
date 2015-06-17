import os
import fnmatch

from within.shell import working_directory

from shepherd.config import Config
from shepherd.stack import Stack

MANIFEST_PATH = 'manifests'


def test_manifest_generator():
    """
    manifests_tests - test_manifest_generator.

    Loops through the samples directory and tests that
    each sample config and manifest file can successfully
    be loaded and validated.
    """
    working_dir = os.path.dirname(os.path.realpath(__file__))

    with working_directory(working_dir):
        for folder in os.listdir(MANIFEST_PATH):
            path = os.path.join(
                os.path.abspath(MANIFEST_PATH),
                folder
            )

            yield validate_manifests, path


def validate_manifests(path):
    """
    manifests_tests - validate_manifests.

    Actually creates the manifest for a given path
    and checks that it can be properly parsed.
    """
    config = None
    for filename in os.listdir(path):
        if fnmatch.fnmatch(filename, '*config.yml'):
            config = Config.make_from_file(
                os.path.join(path, filename),
                name=path
            )

            Stack.make('TestStack', config)
