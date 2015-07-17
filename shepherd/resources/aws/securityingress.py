from __future__ import print_function

import boto

from shepherd.common.plugins import Resource
from shepherd.common.exceptions import StackError
from shepherd.resources.aws import get_security_group


class SecurityGroupIngress(Resource):
    def __init__(self):
        super(SecurityGroupIngress, self).__init__('aws')
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

        self._logger.debug(
            'Generating a dependency list for EC2 Security Group Ingress '
            'creation: %s', ', '.join((dep.local_name for dep in deps))
        )

        return deps

    # I may not be making these request properly
    # documentation appears to say I can either make a port based rule
    # with an ip OR a group based rule with source group id
    @Resource.validate_create()
    def create(self):
        self._set_group_names()

        conn = boto.connect_ec2()
        resp = self._exec(conn.authorize_security_group)
        if resp:
            self._available = True
        else:
            raise StackError(
                'Failed to create EC2 Security Group Ingress {}\n{}'
                .format(self._local_name, resp),
                logger=self._logger
            )

    @Resource.validate_destroy()
    def destroy(self):
        self._set_group_names()

        conn = boto.connect_ec2()
        resp = self._exec(conn.revoke_security_group)
        if resp:
            self._available = False
        else:
            raise StackError(
                'Failed to destroy EC2 Security Group Ingress {}\n{}'
                .format(self._local_name, resp),
                logger=self._logger
            )

    def _set_group_names(self):
        if self._group_name and not self._group_id:
            self._group_id = get_security_group(group_name=self._group_name, stack=self.stack).id

        if self._src_security_group_name and not self._src_group_id:
            self._src_group_id = get_security_group(
                group_name=self._src_security_group_name,
                stack=self.stack
            ).id

    def _exec(self, operation):
        return operation(
            group_id=self._group_id,
            src_security_group_group_id=self._src_group_id,
            cidr_ip=self._cidr_ip,
            ip_protocol=self._ip_protocol,
            from_port=self._from_port,
            to_port=self._to_port
        )
