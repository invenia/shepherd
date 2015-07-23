"""
shepherd.resources.aws.securitygroup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles creation and destruction of security groups
"""
from __future__ import print_function

import boto

from arbiter import create_task
from arbiter.sync import run_tasks

from functools import partial

from shepherd.common.plugins import Resource
from shepherd.common.exceptions import StackError
from shepherd.common.utils import tasks_passed
from shepherd.resources.aws import (
    get_security_group,
    catch_response_errors,
    ALLOWED_ERRORS,
    create_tags,
    sync_tags
)


class SecurityGroup(Resource):
    def __init__(self):
        super(SecurityGroup, self).__init__('aws')
        self._group_id = None
        self._group_description = None

        self._attributes_map.update({
            'group_id': '_group_id',
            'group_description': '_group_description'
        })

    @property
    def resource_id(self):
        return self._group_id

    def get_dependencies(self):
        deps = []
        self._logger.debug(
            'Generating a dependency list for EC2 Security Group creation: []'
        )

        return deps

    def sync(self):
        if self._group_id:
            self._tags = sync_tags(self._group_id, self._tags)
            self._check_created()

    @Resource.validate_create()
    def create(self):
        tasks = (
            create_task('create', self._create_group),
            create_task(
                'tag', partial(create_tags, self), ('create',),
                retries=self.stack.settings["retries"],
                delay=self.stack.settings["delay"]
            ),
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
        if self._group_id and get_security_group(group_id=self._group_id):
            resp = catch_response_errors(
                conn.delete_security_group,
                kwargs={'group_id': self._group_id},
                allowed=ALLOWED_ERRORS['securitygroup_not_found'].format(self._group_id),
                msg='{} ({}) no longer exists. Skipping.'.format(
                    self._local_name, self._group_id
                )
            )

            if resp:
                logger.info(
                    'EC2 Security Group %s successfully destroyed',
                    self._local_name
                )
            else:
                raise StackError(
                    'Failed to destroy EC2 Security Group {}. ID={}'
                    .format(self._local_name, self._group_id),
                    log=False
                )
        else:
            logger.warn(
                'Group does not exist anymore. Setting EC2 Security '
                'Group %s to unavailable', self._local_name
            )

        self._available = False
        self._group_id = None

    def _create_group(self):
        """ Handles the creation request """
        conn = boto.connect_ec2()
        if self._group_id is None:
            self._logger.debug(
                'Requesting EC2 Security Group %s...',
                self._global_name
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
                'EC2 Security Group %s is now available.',
                self._local_name
            )
            self._available = True

        return self._available
