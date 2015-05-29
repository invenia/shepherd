from nose.tools import assert_is_none, assert_equals, assert_false

from shepherd.common.utils import pascal_to_underscore


def validate_empty_resource(resource):
    assert_is_none(resource.local_name)
    assert_is_none(resource.global_name)
    assert_is_none(resource.stack)
    assert_false(resource.available)
    assert_equals(resource.tags, {})


def validate_deserialized_resource(resource, test_dict):
    for key in test_dict:
        attr_key = '_{}'.format(pascal_to_underscore(key))
        assert_equals(getattr(resource, attr_key), test_dict[key])


def validate_serialized_resource(resource_dict, test_dict):
    for key in test_dict:
        assert_equals(resource_dict[key], test_dict[key])
