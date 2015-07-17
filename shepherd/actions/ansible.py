"""
The ansible action handles generating a custom inventory file
and running the supplied playbook on the stack instances. This also
includes cloning the playbook down from a remote url if supplied instead
of a path and installing the requirements from a requirements.yml file if
one is found in the playbook directory.

The ansible action takes a
1. playbook name
2. a path or url for the playbook location
3. a vault_pass or a vault_key_file if your playbook
    has a vault in it.
4. tags or skip_tags to modify what tasks in the playbook run.
5. extra_vars for variables that need to be passed in and
6. opt_flags to add any extra flags to the ansible command.
7. name of the stack to run on.

TODO:
    - Provide an option to supply a dict for mapping instance tags
      to groups in the inventory file that are used in the playbook.
    - Tests.
    - Provide a sample playbook repo with a requirements.yml file
"""
import os
import anyconfig
import jsonschema
import envoy
import shutil
import logging

from git.repo.base import Repo
from within.shell import working_directory
from tempfile import mkdtemp

from shepherd.stack import Stack
from shepherd.common.plugins import Action

logger = logging.getLogger(__name__)


class Ansible(Action):
    def __init__(self):
        super(Ansible, self).__init__()
        self._working_dir = None
        self.path = None
        self.playbook = None
        self.inventory = None

    def validate(self, **kwargs):
        """
        Validates the kwargs with the schema file.

        Args:
            kwargs (dict): a dictionary of settings.
        """
        logger.debug('Validating settings...')
        path = os.path.dirname(os.path.realpath(__file__))
        schema_file = os.path.join(path, 'ansible.schema')
        assert os.path.isfile(schema_file)
        schema = anyconfig.load(schema_file, 'json')

        jsonschema.validate(kwargs, schema)

    def run(self, config, **kwargs):
        """
        Run the ansible playbook on all hosts in the stack.

        Args:
            kwargs (dict): a dictionary of settings.

        Notes:
            * Default naming for the inventory files use::

                [tag_stack_name_{stack_name}]
                {all instance ips}

                [tag_local_name_{local_name}]
                {instance ip}

                ...

        """
        self._working_dir = mkdtemp(prefix=__name__)
        stack = Stack.restore(kwargs['name'], config)
        try:
            self.path = '{}/playbook'.format(self._working_dir)
            self.playbook = os.path.join(self.path, kwargs["playbook"])
            self.inventory = '{}/inventory'.format(self._working_dir)

            self.validate(**kwargs)
            self.install_playbook(**kwargs)

            # After the playbook has been installed ensure that the playbook
            # in the working directory exists.
            if not os.path.isfile(self.playbook):
                raise ValueError('Playbook %s is not a file', self.playbook)

            self.install_requirements()
            self.build_inventory(stack)

            if 'vault_pass' in kwargs or 'vault_key_file' in kwargs:
                self.passfile = '{}/vaultpass'.format(self._working_dir)
                logger.debug('Setting up vault password file...')
                if 'vault_pass' in kwargs:
                    with open(self.passfile, 'w') as handle:
                        handle.write(kwargs['vault_pass'])
                elif 'vault_key_file' in kwargs:
                    assert os.path.isfile(kwargs['vault_key_file'])
                    os.symlink(
                        os.path.realpath(kwargs['vault_key_file']),
                        self.passfile
                    )

            # There is a slight security issue where if the vault_pass file
            # is moved between the closing of the file above and it getting
            # opened by ansible in the cmd below the password file won't get
            # cleaned up.

            cmd = 'ansible-playbook -i {} {}'.format(self.inventory, self.playbook)
            if 'vault_pass' in kwargs or 'vault_key_file' in kwargs:
                cmd = ('{} --vault-password-file={}'.format(cmd, self.passfile))
            if 'extra_vars' in kwargs:
                cmd = '{} --extra-vars \"{}\"'.format(cmd, kwargs['extra_vars'])
            if 'tags' in kwargs:
                cmd = '{} --tags={}'.format(cmd, kwargs['tags'])
            if 'skip_tags' in kwargs:
                cmd = '{} --skip_tags={}'.format(cmd, kwargs['skip_tags'])
            if 'opt_flags' in kwargs:
                # Should probably do proper validation on these, but
                # I don't think it should be used very often.
                cmd = '{} {}'.format(cmd, kwargs['opt_flags'])

            # Log envoy output
            result = envoy.run(cmd)
            logger.debug(result.std_out)
            logger.warn(result.std_err)
        finally:
            logger.debug('Deleting working directory %s', self._working_dir)
            shutil.rmtree(self._working_dir)

        return stack

    def install_playbook(self, **kwargs):
        """
        Validates that self._playbook is a valid path or url.
        If it is a url git clone to /tmp. If it has a requires file
        install dependencies.
        """
        logger.debug('Installing playbook...')
        if "url" in kwargs:
            # Should probably extract the playbook name from the playbook
            # URL
            Repo.clone_from(
                kwargs["url"],
                self.path
            )
        elif "path" in kwargs:
            if os.path.exists(kwargs["path"]):
                path = None
                if os.path.isfile(kwargs["path"]):
                    path = os.path.dirname(kwargs["path"])
                else:
                    path = kwargs["path"]

                os.symlink(os.path.realpath(path), self.path)
            else:
                raise ValueError(
                    'The path value provided (%s) does not exists',
                    kwargs['path']
                )

        assert os.path.exists(self.path)

    def install_requirements(self):
        logger.debug('Installing requirements...')
        requirements_path = os.path.join(self.path, "requirements.yml")
        if os.path.exists(requirements_path):
            with working_directory(os.path.dirname(self.playbook)):
                envoy.run('ansible-galaxy install -r requirements.yml')

    def build_inventory(self, stack):
        logger.debug('Buidling the inventory file...')
        instances = stack.get_resource_by_type('Instance')
        common_name = 'tag_stack_name_{}'.format(stack.global_name)
        inventory_dict = {
            common_name: [],
        }

        for instance in instances:
            inventory_dict[common_name].append(instance.ip)
            if instance.local_name in inventory_dict:
                inventory_dict[instance.local_name].append(instance.ip)
            else:
                inventory_dict[instance.local_name] = [instance.ip]

        with open(self.inventory, 'w') as handle:
            content = ''
            for key, ips in inventory_dict.items():
                content += '[tag_local_name_{}]\n'.format(key)

                for ip in ips:
                    content += '{}\n'.format(ip)

            logger.debug('Inventory content:\n %s', content)
            handle.write(content)
