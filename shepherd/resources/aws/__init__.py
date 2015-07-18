# from iamkeys import AccessKey
# from iamuser import user
# from volume import Volume
# from instance import Instance
# from securitygroup import SecurityGroup
# from securityingress import SecurityGroupIngress

# max seconds to wait for any non instance stack resources to create
# CREATE_TIMEOUT = 60
import boto
import logging

from boto.exception import EC2ResponseError

ALLOWED_ERRORS = {
    'volume_not_found': "The volume '{}' does not exist",
    'securitygroup_not_found': "The security group '{}' does not exist",
    'instance_not_found': "The instance ID '{}' does not exist",
}


def catch_response_errors(
    func, args=None, kwargs=None,
    allowed=None, msg=None, logger=None, warn=True
):
    """
    Provides a wrapping function for boto calls that may return an
    EC2ResponseError that you'd like to catch based on the allowed
    string being in the returned xml body. If an exception is thrown and
    the allowed string isn't in the body the exception is reraised.

    Args:
        func (function): the function to call (should be a boto call)
        args (tuple): the positional arguments to the passed in function.
        kwargs (dict): the key values that should be passed to the function.
        allowed (str): the allowed string to look for. [could probably be multiple str if needed]
        msg (str): the warning message to display.
            If left out the warning msg will just be the allowed string.
        logger (logger): An optional logger to use.
        warn (bool): By default if the ResponseError contains the allowed string
            a warning msg will still be logged.

    Returns:
        resp: The response from the function call, True if failure allowed or False.
    """
    resp = False
    if not args:
        args = ()

    if not kwargs:
        kwargs = {}

    if not logger:
        logger = logging.getLogger(__name__)

    try:
        resp = func(*args, **kwargs)
    except EC2ResponseError as exc:
        if allowed in exc.body:
            if not msg:
                msg = allowed
            if warn:
                logger.warn(msg)

            resp = True
        else:
            raise

    return resp


def get_access_key(username, access_key):
    """
    Boto doesn't provide a way to query for a specific access_key
    so we have our own for now.
    """
    result = None
    conn = boto.connect_iam()
    resp = conn.get_all_access_keys(username)
    results = resp['list_access_keys_response']['list_access_keys_result']
    keys = results['access_key_metadata']

    for key in keys:
        if key['access_key_id'] == access_key:
            result = key

    return result


def get_security_group(group_id=None, group_name=None, stack=None):
    result = None
    conn = boto.connect_ec2()
    resp = None
    kwargs = None
    allowed = None

    if group_name:
        name = group_name
        if stack and stack.get_resource_by_name(group_name):
            name = stack.get_global_resource_name(group_name)

        kwargs = {'groupnames': [name]}
        allowed = ALLOWED_ERRORS['securitygroup_not_found'].format(name)
    elif group_id:
        kwargs = {'group_ids': [group_id]}
        allowed = ALLOWED_ERRORS['securitygroup_not_found'].format(group_id)

    assert kwargs is not None

    resp = catch_response_errors(
        conn.get_all_security_groups,
        kwargs=kwargs,
        allowed=allowed,
    )

    if resp and isinstance(resp, list) and len(resp) == 1 and resp[0]:
        result = resp[0]

    return result


def get_volume(volume_id):
    result = None
    conn = boto.connect_ec2()

    resp = catch_response_errors(
        conn.get_all_volumes,
        kwargs={'volume_ids': [volume_id]},
        allowed=ALLOWED_ERRORS['volume_not_found'].format(volume_id)
    )

    if resp and isinstance(resp, list) and len(resp) == 1:
        result = resp[0]

    return result
