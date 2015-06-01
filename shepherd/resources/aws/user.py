from __future__ import print_function

import boto
import json

from boto.exception import BotoServerError
from arbiter import create_task
from arbiter.sync import run_tasks

from shepherd.common.plugins import Resource
from shepherd.common.utils import tasks_passed


class User(Resource):
    def __init__(self):
        super(User, self).__init__('aws')
        self._user_info = None
        self._groups = []
        self._policies = []

        self._attributes_map.update({
            'user_info': '_user_info',
            'groups': '_groups',
            'policies': '_policies',
        })

    def get_dependencies(self):
        deps = []
        self._logger.debug(
            'Generating a dependency list for IAM User creation: []'
        )

        return deps

    @Resource.validate_create()
    def create(self):
        self._global_name = self.stack.get_global_resource_name(self._local_name)

        tasks = (
            create_task('create_user', self._create_user),
            create_task(
                'check_user', self._check_user, ('create_user',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
            create_task('add_to_groups', self._add_to_groups, ('check_user',)),
            create_task('create_policies', self._create_policies, ('check_user',)),
        )
        results = run_tasks(tasks)
        self._available = tasks_passed(
            results, self._logger,
            msg='Failed to provision user {}'.format(self._local_name),
        )

    @Resource.validate_destroy()
    def destroy(self):
        tasks = (
            create_task(
                'check_user', self._check_user,
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
            create_task('remove_from_groups', self._rm_from_groups, ('check_user',)),
            create_task('delete_policies', self._delete_policies, ('check_user',)),
            create_task('delete_user', self._delete_user, ('check_user',)),
        )
        results = run_tasks(tasks)
        self._available = not tasks_passed(
            results, self._logger,
            msg='Failed to deprovision user {}'.format(self._local_name)
        )

    def _create_user(self):
        """ Handles the creation request """
        if not self._user_info:
            self._logger.debug('Creating user {}'.format(self._local_name))
            conn = boto.connect_iam()
            self._user_info = conn.create_user(self._global_name)

        return True

    def _delete_user(self):
        """ Handles the deletion request """
        conn = boto.connect_iam()
        self._logger.debug('Deleting user {}'.format(self._local_name))
        conn.delete_user(self._global_name)
        return True

    def _create_policies(self):
        """ Creates any required user policies """
        conn = boto.connect_iam()
        self._logger.debug('Creating policies for user {}'.format(self._local_name))
        for policy in self._policies:
            self._logger.debug('Creating policiy {}'.format(policy['PolicyName']))
            conn.put_user_policy(
                self._global_name,
                policy['PolicyName'],
                json.dumps(policy['PolicyDocument'])
            )

        return True

    def _delete_policies(self):
        """ Delete any user policies """
        conn = boto.connect_iam()
        self._logger.debug('Deleting policies for user {}'.format(self._local_name))
        for policy in self._policies:
            try:
                conn.get_user_policy(
                    self._global_name,
                    policy['PolicyName']
                )
            except:
                self._logger.warn(
                    'IAM Policy {} not found for user {}'
                    .format(policy['PolicyName'], self._global_name)
                )
            else:
                self._logger.debug('Deleting policy {}'.format(policy['PolicyName']))
                conn.delete_user_policy(
                    self._global_name,
                    policy['PolicyName']
                )

        return True

    def _add_to_groups(self):
        """ Adds the user to the specified groups """
        conn = boto.connect_iam()
        for groupname in self._groups:
            try:
                conn.get_group(groupname)
            except:
                self._logger.warn('IAM group {} not found'.format(groupname))
            else:
                conn.add_user_to_group(groupname, self._global_name)

        return True

    def _rm_from_groups(self):
        """ Removes the user from specified groups """
        conn = boto.connect_iam()
        for groupname in self._groups:
            try:
                conn.get_group(groupname)
            except:
                self._logger.warn('IAM group {} not found')
            else:
                conn.remove_user_from_group(groupname, self._global_name)

        return True

    def _check_user(self):
        """ Checks user exists """
        ret = False
        try:
            conn = boto.connect_iam()
            conn.get_user(self._global_name)
            ret = True
        except BotoServerError:
            self._logger.debug('User {} doesn\'t exist yet'.format(self._local_name))
            pass

        return ret
