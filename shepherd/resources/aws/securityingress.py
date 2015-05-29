from __future__ import print_function

import logging
import boto

from shepherd.common.plugins import Resource
from shepherd.common.exceptions import StackError
from shepherd.resources.aws import get_security_group

logger = logging.getLogger(__name__)


class SecurityGroupIngress(Resource):
    def __init__(self):
        super(SecurityGroupIngress, self).__init__()
        self._type = 'SecurityGroupIngress'
        self._provider = 'aws'
        self._group_name = None
        self._group_id = None
        self._src_security_group_name = None
        self._src_group_id = None
        self._cidr_ip = None
        self._ip_protocol = None
        self._from_port = None
        self._to_port = None

        self._attributes_map.update({
            'group_name': '_group_name',
            'group_id': '_group_id',
            'src_security_group_name': '_src_security_group_name',
            'src_group_id': '_src_group_id',
            'cidr_ip': '_cidr_ip',
            'ip_protocol': '_ip_protocol',
            'from_port': '_from_port',
            'to_port': '_to_port',
        })

    def get_dependencies(self):
        deps = []

        group = self.stack.get_resource_by_name(self._group_name)
        if group:
            deps.append(group)

        src_group = self.stack.get_resource_by_name(self._src_security_group_name)
        if src_group:
            deps.append(src_group)

        logger.debug(
            'Generating a dependency list for EC2 Security Group Ingress '
            'creation: {}'.format(', '.join((dep.local_name for dep in deps)))
        )

        return deps

    # I may not be making these request properly
    # documentation appears to say I can either make a port based rule
    # with an ip OR a group based rule with source group id
    @Resource.validate_create(logger)
    def create(self):
        conn = boto.connect_ec2()
        resp = None

        if self._group_name and not self._group_id:
            self._group_id = get_security_group(group_name=self._group_name, stack=self.stack).id

        if self._src_security_group_name:
            if not self._src_group_id:
                self._src_group_id = get_security_group(
                    group_name=self._src_security_group_name,
                    stack=self.stack
                )

            resp = conn.authorize_security_group(
                group_id=self._group_id,
                src_security_group_group_id=self._src_group_id,
                ip_protocol=self._ip_protocol,
                from_port=self._from_port,
                to_port=self._to_port
            )

        elif self._cidr_ip:
            resp = conn.authorize_security_group(
                group_id=self._group_id,
                cidr_ip=self._cidr_ip,
                ip_protocol=self._ip_protocol,
                from_port=self._from_port,
                to_port=self._to_port
            )
        else:
            raise StackError(
                'EC2 Security Ingress {} does not have '
                'a cidr_ip or src security group name set'
                .format(self._local_name),
                log=False
            )

        if resp:
            self._available = True
        else:
            raise StackError(
                'Failed to create EC2 Security Group Ingress {}\n{}'
                .format(self._local_name, resp),
                log=False
            )

    @Resource.validate_destroy(logger)
    def destroy(self):
        conn = boto.connect_ec2()
        resp = None

        if self._group_name and not self._group_id:
            self._group_id = get_security_group(group_name=self._group_name, stack=self.stack)

        if self._src_security_group_name:
            if not self._src_group_id:
                self._src_group_id = get_security_group(
                    group_name=self._src_security_group_name,
                    stack=self.stack
                )

            resp = conn.revoke_security_group(
                group_id=self._group_id,
                src_security_group_group_id=self._src_group_id,
                ip_protocol=self._ip_protocol,
                from_port=self._from_port,
                to_port=self._to_port
            )

        elif self._cidr_ip:
            resp = conn.revoke_security_group(
                group_id=self._group_id,
                cidr_ip=self._cidr_ip,
                ip_protocol=self._ip_protocol,
                from_port=self._from_port,
                to_port=self._to_port
            )

        if resp:
            self._available = False
        else:
            raise StackError(
                'Failed to destroy EC2 Security Group Ingress {}\n{}'
                .format(self._local_name, resp),
                log=False
            )
