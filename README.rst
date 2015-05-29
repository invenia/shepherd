=======
Shepherd
=======

Shepherd is a pluggable resource provisioning framework, similar to Amazon's
cloudformation but faster, more flexibility and cloud provider independent.

Installation
============

Shepherd is not available on PyPI. To install::

    $ pip install git+https://github.com/invenia/Shepherd.git#egg=Shepherd


Features
==========
Shepherd supports multiple useful features for managing resources.

- Stacks: provision, deprovision, tag and audit groups of resources (called stacks)
- Manifests: resource configurations (or manifests) are written in 1 or more human readable yaml files and support jinja2 templating. No more working around JSON configurations!
- Parsers: support for custom parser plugins to handle dynamic Manifest variables.
- Storage: Save stack configuration states for auditing purposes in various storage media.


Usage
=====

To provision and deprovision a stack::

    import os
    import fnmatch
    import logging

    from shepherd.config import Config
    from shepherd.stack import Stack

    FORMAT = '[%(levelname)s  %(asctime)s  %(name)s] - "%(message)s"'
    logging.basicConfig(format=FORMAT)
    logging.getLogger().setLevel(logging.INFO)

    MANIFEST_PATH = os.path.join(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '../',
        ),
        'manifests/simple'
    )

    config = None

    for filename in os.listdir(MANIFEST_PATH):
        if fnmatch.fnmatch(filename, '*config.yml'):
            config = Config.make_from_file(
                os.path.join(MANIFEST_PATH, filename),
                name=MANIFEST_PATH
            )

    stack = Stack.make('TestStack', config_name=MANIFEST_PATH)
    stack.provision_resources()
    stack.deprovision_resources()



License
=======
Shepherd is provided under an MPL License.
