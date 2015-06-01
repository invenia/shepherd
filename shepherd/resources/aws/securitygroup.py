"""
shepherd.resources.aws.securitygroup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles creation and destruction of security groups
"""
from __future__ import print_function

import boto

from arbiter import create_task
from arbiter.sync import run_tasks

from shepherd.common.plugins import Resource
from shepherd.common.exceptions import StackError
from shepherd.common.utils import tasks_passed
from shepherd.resources.aws import get_security_group


class SecurityGroup(Resource):
    def __init__(self):
        super(SecurityGroup, self).__init__('aws')
        self._group_id = None
        self._group_description = None

        self._attributes_map.update({
            'group_id': '_group_id',
            'group_description': '_group_description'
        })

    def get_dependencies(self):
        deps = []
        self._logger.debug(
            'Generating a dependency list for EC2 Security Group creation: []'
        )

        return deps

    @Resource.validate_create()
    def create(self):
        tasks = (
            create_task('create', self._create_group),
            create_task(
                'check', self._check_created, ('create',),
                retries=self.stack.settings["retries"],
                delay=self.stack.settings["delay"]
            )
        )
        results = run_tasks(tasks)

        return tasks_passed(
            results, self._logger,
            msg='Failed to provision security group {}'.format(self._local_name)
        )

    @Resource.validate_destroy()
    def destroy(self):
        conn = boto.connect_ec2()
        logger = self._logger
        if self._group_id is not None and get_security_group(group_id=self._group_id):
            resp = conn.delete_security_group(group_id=self._group_id)

            if resp:
                logger.info(
                    'EC2 Security Group {} successfully destroyed'
                    .format(self._local_name)
                )
                self._group_id = None
                self._available = False
            else:
                raise StackError(
                    'Failed to destroy EC2 Security Group {}. ID={}'
                    .format(self._local_name, self._group_id),
                    log=False
                )
        else:
            logger.warn(
                'Group does not exist anymore. Setting EC2 Security '
                'Group {} to unavailable'.format(self._local_name)
            )

    def _create_group(self):
        """ Handles the creation request """
        conn = boto.connect_ec2()
        if self._group_id is None:
            self._logger.debug(
                'Requesting EC2 Security Group {}...'
                .format(self._global_name)
            )

            self._global_name = self.stack.get_global_resource_name(
                self._local_name
            )

            # Create the Security group
            self._group_id = conn.create_security_group(
                self._global_name,
                self._group_description
            ).id

        return True

    def _check_created(self):
        """ Checks that group is available """
        if get_security_group(group_id=self._group_id):
            self._logger.info(
                'EC2 Security Group {} is now available.'
                .format(self._local_name)
            )
            self._available = True

        return self._available
