from __future__ import print_function

import boto

from boto.ec2.blockdevicemapping import BlockDeviceMapping
from boto.ec2.blockdevicemapping import BlockDeviceType
from boto.exception import EC2ResponseError
from functools import partial

from arbiter import create_task
from arbiter.sync import run_tasks

from shepherd.common.plugins import Resource
from shepherd.common.utils import tasks_passed, get, dict_contains
from shepherd.resources.aws import (
    get_security_group,
    catch_response_errors,
    ALLOWED_ERRORS,
    create_tags,
    sync_tags
)

SPOT_REQUEST_ACTIVE = 'active'
SPOT_REQUEST_FULFILLED = 'fulfilled'
INST_RUNNING_STATE = 'running'
INST_REACHABLE_STATE = 'passed'


def get_block_device_mapping():
    mapping = BlockDeviceMapping()

    eph0 = BlockDeviceType()
    eph1 = BlockDeviceType()
    eph2 = BlockDeviceType()
    eph3 = BlockDeviceType()
    eph0.ephemeral_name = 'ephemeral0'
    eph1.ephemeral_name = 'ephemeral1'
    eph2.ephemeral_name = 'ephemeral2'
    eph3.ephemeral_name = 'ephemeral3'

    mapping['/dev/sdb'] = eph0
    mapping['/dev/sdc'] = eph1
    mapping['/dev/sdd'] = eph1
    mapping['/dev/sde'] = eph1

    return mapping


class Instance(Resource):
    def __init__(self):
        super(Instance, self).__init__('aws')
        self._availability_zone = None
        self._image_id = None
        self._instance_type = None
        self._security_groups = None
        self._key_name = None
        self._spot_price = None
        self._volumes = []
        self._user_data = None

        self._instance_id = None
        self._security_group_ids = []
        self._spot_instance_request = None
        self._ip = None
        self._reservation = None
        self._block_device_map = get_block_device_mapping()
        self._terminated = True
        self._attached_volumes = []

        self._attributes_map.update({
            'availability_zone': '_availability_zone',
            'image_id': '_image_id',
            'instance_type': '_instance_type',
            'security_groups': '_security_groups',
            'key_name': '_key_name',
            'spot_price': '_spot_price',
            'volumes': '_volumes',
            'user_data': '_user_data',
            'instance_id': '_instance_id',
            'spot_instance_request': '_spot_instance_request',
            'terminated': '_terminated',
        })

    def get_dependencies(self):
        deps = []

        for volume_dict in self._volumes:
            volume = self.stack.get_resource_by_name(
                get(volume_dict, ['VolumeId', 'volume_id'])
            )

            if volume:
                deps.append(volume)

        for group_name in self._security_groups:
            security_group = self.stack.get_resource_by_name(group_name)

            if security_group:
                deps.append(security_group)

        return deps

    @property
    def ip(self):
        return self._ip

    @property
    def resource_id(self):
        return self._instance_id

    def sync(self):
        if self._instance_id:
            self._tags = sync_tags(self._instanced_id, self._tags)
            if not self._check_terminated():
                self._check_running()
                self._check_reachable()
        else:
            self._available = False

    @Resource.validate_create()
    def create(self):
        """
        Handles creating spot or on demand instances.

        Info: task order is:
            1. get_security_group_ids
            2. type_specific_tasks: request_demand or request_spot and check_spot
                (last task should labelled 'get_instance_id')
            3. check_running
            4. create_tags
            5. attach_volumes
            6. check_initialized
            7. ssh_accessible
        """
        common_tasks = (
            create_task('get_security_group_ids', self._get_security_group_ids),
            create_task(
                'check_running', self._check_running, ('get_instance_id',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
            create_task(
                'create_tags', partial(create_tags, self), ('check_running',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
            create_task(
                'attach_volumes', self.attach_volumes, ('create_tags',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
            create_task(
                'check_initialized', self._check_reachable, ('create_tags',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
            # Test ssh accessibility
        )

        type_specific_tasks = ()
        if self._spot_price:
            type_specific_tasks = (
                create_task('request_spot', self._request_spot, ('get_security_group_ids',)),
                create_task(
                    'get_instance_id', self._check_spot, ('request_spot',),
                    retries=self.stack.settings['retries'],
                    delay=self.stack.settings['delay']
                ),
            )
        else:
            type_specific_tasks = (
                create_task('get_instance_id', self._request_demand, ('get_security_group_ids',)),
            )

        tasks = common_tasks + type_specific_tasks
        results = run_tasks(tasks)

        self._available = tasks_passed(
            results, self._logger,
            msg='Failed to provision instance {}'.format(self._local_name)
        )

    @Resource.validate_destroy()
    def destroy(self):
        conn = boto.connect_ec2()
        if self._spot_instance_request:
            conn.cancel_spot_instance_requests(self._spot_instance_request)
            self._spot_instance_request = None

        tasks = (
            create_task('terminate', self._terminate_instance),
            create_task(
                'check', self._check_terminated, ('terminate',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
        )
        results = run_tasks(tasks)

        return tasks_passed(
            results, self._logger,
            msg='Failed to deprovision instance {}'.format(self._local_name)
        )

    # Might want to organize this and create tags better
    def attach_volumes(self):
        resp = False

        if self._instance_id:
            conn = boto.connect_ec2()

            for volume_dict in self._volumes:
                volume_id = self._get_volume_id(
                    get(volume_dict, ['VolumeId', 'volume_id'])
                )
                if volume_id not in self._attached_volumes:
                    # volume = get_volume(volume_id)
                    mountpoint = get(volume_dict, ['Device', 'device'])

                    self._logger.debug(
                        'Attaching volume %s to %s an %s',
                        volume_id, self._instance_id, mountpoint
                    )

                    try:
                        conn.attach_volume(
                            volume_id=volume_id,
                            instance_id=self._instance_id,
                            device=mountpoint
                        )
                        self._attached_volumes.append(volume_id)
                    except EC2ResponseError:
                        return resp

            resp = True

        return resp

    def _request_demand(self):
        self._logger.debug('Requesting demand instance %s', self._local_name)
        conn = boto.connect_ec2()
        reservation = conn.run_instances(
            image_id=self._image_id,
            instance_type=self._instance_type,
            key_name=self._key_name,
            user_data=self._user_data,
            security_group_ids=self._security_group_ids,
            placement=self._availability_zone,
            block_device_map=self._block_device_map
        )

        assert len(reservation.instances) == 1

        self._instance_id = reservation.instances[0].id
        return True

    def _request_spot(self):
        self._logger.debug('Requesting spot instance %s', self._local_name)
        conn = boto.connect_ec2()
        self._spot_instance_request = conn.request_spot_instances(
            image_id=self._image_id,
            price=self._spot_price,
            type='one-time',
            instance_type=self._instance_type,
            key_name=self._key_name,
            user_data=self._user_data,
            security_group_ids=self._security_group_ids,
            placement=self._availability_zone,
            block_device_map=self._block_device_map
        )[0]
        return True

    def _terminate_instance(self):
        conn = boto.connect_ec2()
        if self._instance_id:
            if not self._terminated:
                self._logger.debug('Terminating instance %s', self._local_name)

                resp = catch_response_errors(
                    conn.terminate_instances,
                    kwargs={'instance_ids': [self._instance_id]},
                    allowed=ALLOWED_ERRORS['instance_not_found'].format(self._instance_id),
                    msg='{} ({}) no longer exists. Skipping.'.format(
                        self._local_name, self._instance_id
                    )
                )
                if resp:
                    self._instance_id = None

        self._terminated = True
        return self._terminated

    def _check_running(self):
        self._logger.debug('Checking if instance %s is running', self._local_name)
        resp = False
        if self._instance_id:
            conn = boto.connect_ec2()
            instances = catch_response_errors(
                conn.get_only_instances,
                kwargs={'instance_ids': [self._instance_id]},
                allowed=ALLOWED_ERRORS['instance_not_found'].format(self._instance_id),
            )

            if instances and isinstance(instances, list) and len(instances) == 1:
                instance = instances[0]
                if instance.state == INST_RUNNING_STATE:
                    self._terminated = False
                    self._ip = instance.ip_address
                    resp = True

        return resp

    def _check_reachable(self):
        self._logger.debug('Checking if instance %s is reachable', self._local_name)
        resp = False
        if self._instance_id:
            conn = boto.connect_ec2()
            status = catch_response_errors(
                conn.get_all_instance_status,
                kwargs={'instance_ids': [self._instance_id]},
                allowed=ALLOWED_ERRORS['instance_not_found'].format(self._instance_id),
            )

            if status and isinstance(status, list) and len(status) > 0:
                if status[0].system_status.details['reachability'] == INST_REACHABLE_STATE:
                    resp = True
                else:
                    self._logger.debug(
                        'Reachability Status = %s',
                        status[0].system_status.details['reachability']
                    )

        return resp

    def _check_terminated(self):
        conn = boto.connect_ec2()
        if self._instance_id:
            reservation = catch_response_errors(
                conn.get_all_instances,
                kwargs={'instance_ids': [self._instance_id]},
                allowed=ALLOWED_ERRORS['instance_not_found'].format(self._instance_id),
            )[0]
            instance = reservation.instances[0]

            if instance.state == 'terminated':
                self._available = False
                self._instance_id = None
        else:
            self._available = False

        return not self._available

    def _check_spot(self):
        self._logger.debug(
            'Checking if spot request %s is fulfilled',
            self._spot_instance_request.id
        )
        resp = False
        conn = boto.connect_ec2()

        requests = conn.get_all_spot_instance_requests(
            request_ids=[self._spot_instance_request.id]
        )
        assert len(requests) == 1
        request = requests[0]
        if (request.state == SPOT_REQUEST_ACTIVE and
                request.status.code == SPOT_REQUEST_FULFILLED and
                request.instance_id):
            self._instance_id = request.instance_id
            resp = True

        return resp

    def _create_tags(self):
        conn = boto.connect_ec2()
        self._logger.debug('Creating tags for instance %s', self._local_name)
        if not dict_contains(self._tags, self.stack.tags):
            self._tags.update(self.stack.tags)

        self._tags['Name'] = self._global_name

        try:
            conn.create_tags([self._instance_id], self._tags)
            return True
        except EC2ResponseError:
            return False

    def _get_security_group_ids(self):
        if not self._security_group_ids:
            for sg in self._security_groups:
                self._security_group_ids.append(
                    get_security_group(group_name=sg, stack=self.stack)
                )
        return True

    def _get_volume_id(self, volume_name):
        volume_id = None

        vol = self.stack.get_resource_by_name(volume_name)
        if vol:
            volume_id = vol.volume_id

        return volume_id
