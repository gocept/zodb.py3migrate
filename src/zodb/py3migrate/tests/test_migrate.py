import mock
import persistent
import pkg_resources
import transaction
import zodb.py3migrate.migrate


class Example(persistent.Persistent):
    """Object will be stored in ZODB with attributes written added in tests."""

    def __init__(self, binary_string, unicode_string, reference=None):
        assert isinstance(binary_string, str)  # !!! not python 3 compatible
        assert isinstance(unicode_string, unicode)
        self.binary_string = binary_string
        self.unicode_string = unicode_string
        self.reference = reference


def test_migrate__main__1():
    """It calls migrate with given file."""
    with mock.patch('zodb.py3migrate.migrate.migrate') as migrate:
        path = pkg_resources.resource_filename('zodb.py3migrate', 'migrate.py')
        zodb.py3migrate.migrate.main([path])
        migrate.assert_called_once_with(path)


def test_migrate__parse__1(zodb_storage, zodb_root):
    """It parses ZODB and returns result of analysis."""
    zodb_root['obj'] = Example(b'bar', u'foo', Example(b'baz', u'bumm'))
    transaction.commit()
    result = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.binary_string': 2
    } == result
