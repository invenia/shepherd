from nose.tools import assert_raises, assert_equals
from shepherd.common.utils import pascal_to_underscore, get


def test_pascal_to_underscore():
    assert_equals(pascal_to_underscore('MyStr'), 'my_str')
    assert_equals(pascal_to_underscore('myStr'), 'my_str')
    assert_equals(pascal_to_underscore('My-Str'), 'my-_str')
    assert_equals(pascal_to_underscore('my-str'), 'my-str')
    assert_equals(pascal_to_underscore('MYSTR'), 'mystr')
    assert_equals(pascal_to_underscore('2Str'), '2_str')
    assert_equals(pascal_to_underscore('Mystr'), 'mystr')


def test_get():
    keys = ['foo', 'Foo']
    mydict = {'foo': 2, 'bar': 3}
    assert_equals(get(mydict, keys), 2)

    mydict = {'foo': 2, 'Foo': 3}
    assert_raises(KeyError, get, mydict, keys)
    assert_equals(get(mydict, keys, mutually_exclusive=False), 2)

    assert_raises(KeyError, get, mydict, ['car', 'zar'])
