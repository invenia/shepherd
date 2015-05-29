import sys
import os
import fnmatch
import logging
import argparse

from within.shell import working_directory

from shepherd.config import Config
from shepherd.stack import Stack

FORMAT = '[%(levelname)s  %(asctime)s  %(name)s] - "%(message)s"'
logging.basicConfig(format=FORMAT)
logging.getLogger().setLevel(logging.INFO)

MANIFEST_PATH = 'manifests/simple'


def main(args):
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('boto').setLevel(logging.INFO)
        logging.getLogger('yapsy').setLevel(logging.INFO)
        logging.getLogger('anyconfig').setLevel(logging.INFO)

    working_dir = os.path.dirname(os.path.realpath(__file__))

    with working_directory(working_dir):
        config = None

        for filename in os.listdir(MANIFEST_PATH):
            if fnmatch.fnmatch(filename, '*config.yml'):
                config = Config.make_from_file(
                    os.path.join(MANIFEST_PATH, filename),
                    name=MANIFEST_PATH
                )
        if config:
            if args.action == 'create':
                stack = Stack.make('TestStack', config_name=MANIFEST_PATH)
                stack.provision_resources()
                stack.save()
                print('Stack Created - global name is {}'.format(stack.global_name))
            elif args.action == 'destroy':
                stack = Stack.restore(args.name, config_name=MANIFEST_PATH)
                stack.deprovision_resources()
                stack.save()
                print(
                    'REMINDER: while the stack has been deprovisioned the saved state '
                    'remains stored in dynamodb for auditing purposes'
                )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="As script for manager a simple stack"
    )
    actions = parser.add_subparsers(
        title="action",
        description="Action to perform on the stack",
        help="See '{} <action> -h' for more information on a specific command.".format(
            sys.argv[0]
        )
    )

    create_action = actions.add_parser(
        "create",
        description="Create a simple stack",
        help="Create a new stack"
    )
    create_action.set_defaults(action='create')
    create_action.add_argument(
        "-d", "--debug",
        action='store_true',
        help="Print debugging information to stdout"
    )

    destroy_action = actions.add_parser(
        "destroy",
        description="Destroy a simple stack",
        help="Destroy an existing stack"
    )
    destroy_action.set_defaults(action='destroy')
    destroy_action.add_argument(
        "-d", "--debug",
        action='store_true',
        help="Print debugging information to stdout"
    )
    destroy_action.add_argument(
        "-n", "--name",
        help="The global name of the stack to be destroyed (returned after stack creation"
    )

    args = parser.parse_args()
    main(args)
