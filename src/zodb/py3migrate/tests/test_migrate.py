import ZODB.POSException
from ..migrate import print_results, analyze
import BTrees.OOBTree
import mock
import persistent
import pkg_resources
import pytest
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
    with mock.patch('zodb.py3migrate.migrate.analyze') as analyze:
        path = pkg_resources.resource_filename('zodb.py3migrate', 'migrate.py')
        zodb.py3migrate.migrate.main([path])
        analyze.assert_called_once_with(path, None, False)


def test_migrate__main__2():
    """It returns the exception if one occurred."""
    with mock.patch('zodb.py3migrate.migrate.analyze') as analyze:
            analyze.side_effect = RuntimeError
            with pytest.raises(RuntimeError):
                zodb.py3migrate.migrate.main(['path/to/Data.fs'])


def test_migrate__main__3():
    """It drops into pdb if there was an exception and `--pdb` is set."""
    with mock.patch('zodb.py3migrate.migrate.analyze') as analyze:
        with mock.patch('pdb.post_mortem') as post_mortem:
            analyze.side_effect = RuntimeError
            with pytest.raises(RuntimeError):
                zodb.py3migrate.migrate.main(['path/to/Data.fs', '--pdb'])
            post_mortem.assert_called_once()


def test_migrate__parse__1(zodb_storage, zodb_root):
    """It parses storage and returns result of analysis."""
    zodb_root[u'obj'] = Example(b'bar', u'foo', Example(b'baz', u'bumm'))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage, watermark=1)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.binary_string': 2
    } == result
    assert {} == errors


def test_migrate__parse__2(zodb_storage, zodb_root):
    """It returns objects without a dict as errors."""
    zodb_root[u'tree'] = BTrees.OOBTree.OOBTree()
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {} == result
    assert {
        'BTrees.OOBTree.OOBTree': 1
    } == errors


def test_migrate__parse__3(zodb_storage, zodb_root, caplog):
    """It logs POSKeyErrors.

    They occur e. g. if the file for a blob is not on the hard disk.
    """
    with mock.patch('zodb.py3migrate.migrate.wake_object',
                    side_effect=ZODB.POSException.POSKeyError('\x00')):
        zodb.py3migrate.migrate.parse(zodb_storage)
    rec = caplog.records()[-1]
    assert "POSKeyError: '\\x00'" == rec.getMessage()


def test_migrate__parse__4(zodb_storage, zodb_root):
    """It counts iterable fields that contain binary strings."""
    zodb_root[u'obj'] = Example(b'bar', u'foo', ['binary', 'another_binary'])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.binary_string': 1,
        'zodb.py3migrate.tests.test_migrate.Example.reference (iterable)': 1
    } == result
    assert {} == errors


def test_migrate__print_results__1(capsys):
    """It prints only the results if `verbose` is `False`."""
    print_results({'foo.Bar.baz': 3}, {'asdf.Qwe': 2}, verbose=False)
    out, err = capsys.readouterr()
    assert '''\
Found 1 binary fields: (number of occurrences)
foo.Bar.baz (3)
''' == out


def test_migrate__print_results__2(capsys):
    """It prints the errors, too if `verbose` is `True`."""
    print_results({'foo.Bar.baz': 3}, {'asdf.Qwe': 2}, verbose=True)
    out, err = capsys.readouterr()
    assert '''\
Found 1 classes whose objects do not have __dict__: (number of occurrences)
asdf.Qwe (2)

# ########################################################### #

Found 1 binary fields: (number of occurrences)
foo.Bar.baz (3)
''' == out


def test_migrate__analyze__1(zodb_storage, zodb_root, capsys):
    """It runs the whole analysis for a path of a storage."""
    zodb_storage.close()
    path = zodb_storage._file_name
    analyze(path)
    out, err = capsys.readouterr()
    assert 'Found 0 binary fields: (number of occurrences)\n' == out
