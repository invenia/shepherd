from __future__ import print_function

import boto
import logging

from boto.ec2.blockdevicemapping import BlockDeviceMapping
from boto.ec2.blockdevicemapping import BlockDeviceType

from arbiter import create_task
from arbiter.sync import run_tasks

from shepherd.common.plugins import Resource
from shepherd.common.utils import pascal_to_underscore
from shepherd.resources.aws import get_security_group

SPOT_REQUEST_ACTIVE = 'active'
SPOT_REQUEST_FULFILLED = 'fulfilled'
INST_RUNNING_STATE = 'running'
INST_REACHABLE_STATE = 'passed'

logger = logging.getLogger(__name__)


class Instance(Resource):
    def __init__(self):
        super(Instance, self).__init__()
        self._type = 'Instance'
        self._provider = 'aws'
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
        self._reservation = None
        self._block_device_map = BlockDeviceMapping()
        self._terminated = True

        eph0 = BlockDeviceType()
        eph1 = BlockDeviceType()
        eph2 = BlockDeviceType()
        eph3 = BlockDeviceType()
        eph0.ephemeral_name = 'ephemeral0'
        eph1.ephemeral_name = 'ephemeral1'
        eph2.ephemeral_name = 'ephemeral2'
        eph3.ephemeral_name = 'ephemeral3'

        self._block_device_map['/dev/sdb'] = eph0
        self._block_device_map['/dev/sdc'] = eph1
        self._block_device_map['/dev/sdd'] = eph1
        self._block_device_map['/dev/sde'] = eph1

    def deserialize(self, data):
        super(Instance, self).deserialize(data)

        for key in data:
            attr = pascal_to_underscore(key)

            if attr == 'availability_zone':
                self._availability_zone = data[key]
            elif attr == 'image_id':
                self._image_id = data[key]
            elif attr == 'instance_type':
                self._instance_type = data[key]
            elif attr == 'security_groups':
                self._security_groups = data[key]
            elif attr == 'key_name':
                self._key_name = data[key]
            elif attr == 'spot_price':
                self._spot_price = data[key]
            elif attr == 'volumes':
                self._volumes = data[key]
            elif attr == 'user_data':
                self._user_data = data[key]
            elif attr == 'instance_id':
                self._instance_id = data[key]
            elif attr == 'spot_instance_request':
                self._spot_instance_request = data[key]
            elif attr == 'terminated':
                self._terminated = data[key]

        logger.info('Deserialized Instance {}'.format(self._local_name))
        logger.debug(
            'name={} | available={}'.format(
                self._local_name, self._available)
        )

    def serialize(self):
        logger.info('Serializing Instance {}'.format(self._local_name))
        result = super(Instance, self).serialize()

        result.update({
            'availability_zone': self._availability_zone,
            'image_id': self._image_id,
            'instance_type': self._instance_type,
            'security_groups': self._security_groups,
            'key_name': self._key_name,
            'spot_price': self._spot_price,
            'volumes': self._volumes,
            'user_data': self._user_data,
            'instance_id': self._instance_id,
            'spot_instance_request': self._spot_instance_request,
            'terminated': self._terminated
        })

        return result

    def get_dependencies(self):
        deps = []

        for volume_dict in self._volumes:
            volume = self.stack.get_resource_by_name(
                volume_dict['VolumeID']
            )

            if volume:
                deps.append(volume)

        for group_name in self._security_groups:
            security_group = self.stack.get_resource_by_name(group_name)

            if security_group:
                deps.append(security_group)

        return deps

    @Resource.validate_create(logging)
    def create(self):
        """
        Handles creating spot or on demand instances.

        INFO - task order is:
            1) get_security_group_ids
            2) type_specific_tasks: request_demand or request_spot and check_spot
                (last task should labelled 'get_instance_id')
            3) check_running
            4) create_tags
            5) attach_volumes
            6) check_initialized
            7) ssh_accessible
        """
        common_tasks = (
            create_task('get_security_group_ids', self._get_security_group_ids),
            create_task(
                'check_running', self._check_running, ('get_instance_id',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
            create_task('create_tags', self._create_tags, ('check_running',)),
            create_task('attach_volumes', self.attach_volumes, ('check_running',)),
            create_task(
                'check_initialized', self._check_reachable, ('check_running',),
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
                    delay=self.stack.setting['delay']
                ),
            )
        else:
            type_specific_tasks = (
                create_task('get_instance_id', self._request_demand, ('get_security_group_ids',)),
            )

        tasks = common_tasks + type_specific_tasks
        results = run_tasks(tasks)

        if len(results.failed) > 0:
            logger.warn(
                'Failed to provision instance {}\nCompleted={}\nFailed={}'
                .format(self._local_name, results.completed, results.failed)
            )
            return False

        self._available = True

    @Resource.validate_destroy(logging)
    def destroy(self):
        conn = boto.connect_ec2()
        if self._spot_instance_request:
            conn.cancel_spot_instance_requests(self.sir)
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

        if len(results.failed) > 0:
            logger.warn(
                'Failed to deprovision instance {}\nCompleted={}\nFailed={}'
                .format(self._local_name, results.completed, results.failed)
            )
            return False

    # Might want to organize this and create tags better
    def attach_volumes(self):
        if self._instance_id:
            conn = boto.connect_ec2()

            for volume_dict in self._volumes:
                volume_id = self._get_volume_id(
                    volume_dict['VolumeId']
                )
                # volume = get_volume(volume_id)
                mountpoint = volume_dict['Device']

                logger.debug(
                    'Attaching volume {} to {} an {}'.
                    format(volume_id, self._instance_id, mountpoint)
                )

                conn.attach_volume(
                    volume_id=volume_id,
                    instance_id=self._instance_id,
                    device=mountpoint
                )
        return True

    def _request_demand(self):
        logger.debug('Requesting demand instance {}'.format(self._local_name))
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
        logger.debug('Requesting spot instance {}'.format(self._local_name))
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
        )
        return True

    def _terminate_instance(self):
        conn = boto.connect_ec2()
        if self._instance_id:
            if not self._terminated:
                logger.debug('Terminating instance {}'.format(self._local_name))
                conn.terminate_instances(
                    instance_ids=[self._instance_id]
                )
                self._terminated = True

        return self._terminated

    def _check_running(self):
        logger.debug('Checking if instance {} is running'.format(self._local_name))
        resp = False
        assert self._instance_id
        conn = boto.connect_ec2()
        instances = conn.get_only_instances(
            instance_ids=[self._instance_id]
        )
        assert len(instances) == 1
        instance = instances[0]
        if instance.state == INST_RUNNING_STATE:
            self._terminated = False
            resp = True

        return resp

    def _check_reachable(self):
        logger.debug('Checking if instance {} is reachable'.format(self._local_name))
        resp = False
        assert self._instance_id
        conn = boto.connect_ec2()
        status = conn.get_all_instance_status(
            instance_ids=[self._instance_id]
        )

        if len(status) > 0:
            if status[0].system_status.details['reachability'] == INST_REACHABLE_STATE:
                resp = True
            else:
                logger.debug(
                    'Reachability Status = {}'
                    .format(status[0].system_status.details['reachability'])
                )

        return resp

    def _check_terminated(self):
        conn = boto.connect_ec2()
        if self._instance_id:
            reservation = conn.get_all_instances(
                instance_ids=[self._instance_id]
            )[0]
            instance = reservation.instances[0]

            if instance.state == 'terminated':
                self._available = False
                self._instance_id = None

        return not self._available

    def _check_spot(self):
        logger.debug(
            'Checking if spot request {} is filfilled'
            .format(self._spot_instance_request.id)
        )
        resp = False
        conn = boto.connect_ec2()
        requests = conn.get_all_spot_instance_requests(
            request_ids=self._spot_instance_request.id
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
        logger.debug('Creating tags for instance {}'.format(self._local_name))
        self._tags.update(self.stack.tags)
        conn.create_tags([self._instance_id], self._tags)
        return True

    def _get_security_group_ids(self):
        if not self._security_group_ids:
            for sg in self._security_groups:
                    self._security_group_ids.append(
                        self._get_group_id(sg)
                    )
        return True

    def _get_group_id(self, group_name):
        global_group_name = group_name
        group_id = None

        if self.stack.get_resource_by_name(group_name):
            global_group_name = self.stack.get_global_resource_name(
                group_name
            )

        group = get_security_group(group_name=global_group_name)
        if group:
            group_id = group.id

        return group_id

    def _get_volume_id(self, volume_name):
        volume_id = None

        vol = self.stack.get_resource_by_name(volume_name)
        if vol:
            volume_id = vol.volume_id

        return volume_id
