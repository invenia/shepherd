# from iamkeys import AccessKey
# from iamuser import user
# from volume import Volume
# from instance import Instance
# from securitygroup import SecurityGroup
# from securityingress import SecurityGroupIngress

# max seconds to wait for any non instance stack resources to create
# CREATE_TIMEOUT = 60
import boto


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

    if group_name:
        name = group_name
        if stack and stack.get_resource_by_name(group_name):
            name = stack.get_global_resource_name(group_name)

        resp = conn.get_all_security_groups(groupnames=[name])
    elif group_id:
        resp = conn.get_all_security_groups(group_ids=[group_id])

    if resp and len(resp) == 1 and resp[0]:
        result = resp[0]

    return result


def get_volume(volume_id):
    result = None
    conn = boto.connect_ec2()
    resp = conn.get_all_volumes(volume_id)

    if resp is not None and len(resp) == 1:
        result = resp[0]

    return result
