from __future__ import print_function

import boto
import logging

from arbiter import create_task
from arbiter.sync import run_tasks

# from shepherd.resource import Resource, TemplateObject
from shepherd.common.plugins import Resource
from shepherd.common.exceptions import StackError
from shepherd.common.utils import pascal_to_underscore
from shepherd.resources.aws import get_volume

DEFAULT_VOL_SIZE = 128
logger = logging.getLogger(__name__)


class Volume(Resource):

    def __init__(self):
        super(Volume, self).__init__()
        self._type = 'Volume'
        self._provider = 'aws'
        self._snapshot_id = None
        self._volume_id = None
        self._availability_zone = None
        self._iops = None
        self._size = None
        self._volume_type = "io1"
        self._encrypted = False

    @property
    def volume_id(self):
        return self._volume_id

    def deserialize(self, data):
        super(Volume, self).deserialize(data)

        for key in data:
            attr = pascal_to_underscore(key)

            if attr == 'snapshot_id':
                self._snapshot_id = data[key]
            elif attr == 'volumeid':
                self._volume_id = data[key]
            elif attr == 'availability_zone':
                self._availability_zone = data[key]
            elif attr == 'iops':
                self._iops = data[key]
            elif attr == 'size':
                self._size = data[key]
            elif attr == 'encrypted':
                self._encrypted = data[key]
            elif attr == 'volume_type':
                self._volume_type = data[key]

        logger.info('Deserialized Volume {}'.format(self._local_name))
        logger.debug(
            'name={}, availability_zone={} | available={}'.format(
                self._local_name, self._availability_zone, self._available)
        )

    def serialize(self):
        logger.info('Serializing Volume {}'.format(self._local_name))

        result = super(Volume, self).serialize()
        result.update({
            'snapshot_id': self._snapshot_id,
            'volume_id': self._volume_id,
            'availability_zone': self._availability_zone,
            'iops': self._iops,
            'size': self._size,
            'volume_type': self._volume_type,
            'encrypted': self._encrypted,
        })

        return result

    def get_dependencies(self):
        deps = []
        logger.debug(
            'Generating a dependency list for Volume creation: []'
        )

        return deps

    @Resource.validate_create(logging)
    def create(self):
        tasks = (
            create_task('check_snapshot', self._check_snapshot),
            create_task('create_volume', self._create_volume, ('check_snapshot',)),
            create_task('create_tags', self._create_tags, ('create_volume',)),
            create_task(
                'check_created', self._check_created, ('create_volume',),
                retries=self.stack.settings['retries'],
                delay=self.stack.settings['delay']
            ),
        )
        results = run_tasks(tasks)

        if len(results.failed) > 0:
            logger.debug('Failed to provision volume {}'.format(self._local_name))
            return False

    @Resource.validate_destroy(logging)
    def destroy(self):
        if self._volume_id and get_volume(self._volume_id):
            conn = boto.connect_ec2()
            rc = conn.delete_volume(self._volume_id)

            if not rc:
                StackError(
                    'Failed to destroy Volume {}. ID={}\n'
                    .format(self._local_name, self._volume_id),
                    name=__name__
                )
        else:
            logger.debug(
                "Volume {} does not exist or cannot be found."
                .format(self._local_name)
            )

        self._volume_id = None
        self._available = False

    def _create_volume(self):
        conn = boto.connect_ec2()
        if not self._volume_id:
            logger.debug('Creating volume {}'.format(self._local_name))
            volume = conn.create_volume(
                size=self._size,
                zone=self._availability_zone,
                snapshot=self._snapshot_id,
                volume_type=self._volume_type,
                iops=self._iops,
                encrypted=self._encrypted
            )

            if volume:
                self._volume_id = volume.id
                logger.debug("Volume {} created".format(self._volume_id))
            else:
                raise StackError(
                    "Failed to create Volume {}".format(self._local_name),
                    name=__name__
                )

        return True

    def _create_tags(self):
        conn = boto.connect_ec2()
        self._tags.update(self.stack.tags)
        conn.create_tags(self._volume_id, self._tags)
        return True

    def _check_snapshot(self):
        conn = boto.connect_ec2()
        if self._snapshot_id and not self._size:
            snapshots = conn.get_all_snapshots(
                snapshot_ids=[self._snapshot_id]
            )

            if len(snapshots) > 0 and snapshots[0] is not None:
                self._size = snapshots[0].volume_size
            else:
                raise StackError(
                    'Could not find snapshot matching snapshot {}'
                    .format(self._snapshot_id),
                    name=__name__
                )

        return True

    def _check_created(self):
        volume = get_volume(self._volume_id)
        if volume:
            logger.debug('Volume status = {}'.format(volume.status))

            if volume.status == 'available':
                self._available = True

            else:
                self._available = False
        else:
            self._available = False

        return self._available
