"""
shepherd.resources.aws.iamkeys
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles creation of IAM access key resources on aws.
"""


from __future__ import print_function

import boto

from arbiter import create_task
from arbiter.sync import run_tasks

from shepherd.common.plugins import Resource
from shepherd.common.utils import pascal_to_underscore, tasks_passed
from shepherd.resources.aws import get_access_key


class AccessKey(Resource):
    """
    Subclasses :class:`Resource <Resource>` plugin
    to create and destroy AWS IAM access keys for IAM users.
    """
    def __init__(self):
        super(AccessKey, self).__init__('aws')
        self._user_name = None
        self._access_key_id = None
        self._attributes_map.update({
            'user_name': '_user_name',
            'access_key_id': '_access_key_id',
        })

    def deserialize(self, data):
        super(AccessKey, self).deserialize(data)

        for key in data:
            attr = pascal_to_underscore(key)
            if attr == 'access_key':
                self._access_key_id = data[key]['AccessKeyId']

    def get_dependencies(self):
        deps = []

        user = self.stack.get_resource_by_name(self._user_name)
        if user:
            deps.append(user)

        self._logger.debug(
            'Generating a dependency list for IAM key creation: {}'
            .format(', '.join((dep.local_name for dep in deps)))
        )

        return deps

    @Resource.validate_create()
    def create(self):
        # Only try and create the accesskey if we haven't tried to
        # create one before.
        # Reminder: self._user_name and iamuser.local_name are the same.
        tasks = (
            create_task('create', self._create_key),
            create_task(
                'check', self._check_created, ('create',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            )
        )
        results = run_tasks(tasks)
        return tasks_passed(
            results, self._logger,
            msg='Failed to provision key {}'.format(self._local_name)
        )

    @Resource.validate_destroy()
    def destroy(self):
        tasks = (
            create_task('delete', self._delete_key),
            create_task(
                'check', self._check_deleted, ('delete',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            )
        )
        results = run_tasks(tasks)

        return tasks_passed(
            results, self._logger,
            msg='Failed to deprovision key {}'.format(self._local_name)
        )

    def _create_key(self):
        """ Handles the creation request """
        if self._access_key_id is None:
            self._logger.debug(
                'Requesting IAM Access Key for user {}...'
                .format(self._user_name)
            )

            # Set our global_name which will be the same as the iamuser
            self._global_name = self.stack.get_global_resource_name(
                self._user_name
            )

            # Create the key
            conn = boto.connect_iam()
            resp = conn.create_access_key(self._global_name)
            result = resp.create_access_key_response.create_access_key_result
            self._access_key_id = result.access_key.access_key_id

        return True

    def _delete_key(self):
        """ Handles the deletion request """
        self._logger.debug(
            'Requesting deletion of IAM Access Key ({})...'
            .format(self._access_key_id)
        )
        conn = boto.connect_iam()

        conn.delete_access_key(
            self._access_key_id,
            self._global_name
        )

        return True

    def _check_created(self):
        """ Performs a check that the access key is available """
        if get_access_key(self._global_name, self._access_key_id):
            self._logger.debug(
                'AccessKey {} is now available.'
                .format(self._local_name)
            )
            self._available = True

        return self._available

    def _check_deleted(self):
        """ Performs a check to ensure that the key was successfully deleted """
        if not get_access_key(self._global_name, self._access_key_id):
            self._logger.debug('AccessKey {} deleted'.format(self._local_name))
            self._access_key_id = None
            self._available = False

        return not self._available
