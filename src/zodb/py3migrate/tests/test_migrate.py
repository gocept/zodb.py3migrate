from ..migrate import print_results, analyze
import BTrees.IIBTree
import BTrees.OOBTree
import ZODB.POSException
import mock
import persistent
import pkg_resources
import pytest
import transaction
import zodb.py3migrate.migrate


class Example(persistent.Persistent):
    """Object will be stored in ZODB with attributes written added in tests."""

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


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
    zodb_root[u'obj'] = Example(
        binary_string=b'bar',
        unicode_string=u'foo',
        reference=Example(binary_string=b'baz', unicode_string=u'bumm'))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage, watermark=1)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.binary_string (string)': 2
    } == result
    assert {} == errors


def test_migrate__parse__2(zodb_storage, zodb_root):
    """It returns objects without a dict as errors."""
    zodb_root[u'tree'] = BTrees.IIBTree.IIBTree()
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {} == result
    assert {
        'BTrees.IIBTree.IIBTree': 1
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
    zodb_root[u'obj'] = Example(data=['binary', 'another_binary'])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.data (iterable)': 1,
    } == result
    assert {} == errors


def test_migrate__parse__5(zodb_storage, zodb_root):
    """It counts iterable fields that contain iterables with binary strings."""
    zodb_root[u'obj'] = Example(data=[0, [1, [2, [3, b'binary']]]])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.data (iterable)': 1,
    } == result
    assert {} == errors


def test_migrate__parse__6(zodb_storage, zodb_root):
    """It counts dictionaries that contain binary strings in key or value."""
    zodb_root[u'0'] = Example(data={u'unicode_key': u'unicode_value'})
    zodb_root[u'1'] = Example(bin_key={b'binary_key': u'unicode_value'})
    zodb_root[u'2'] = Example(bin_value={u'unicode_key': b'binary_value'})
    zodb_root[u'3'] = Example(bin_nested_key={u'key': {b'bin_key': u'val'}})
    zodb_root[u'4'] = Example(bin_nested_val={u'key': {u'key': b'bin_val'}})
    zodb_root[u'5'] = Example(bin_nested_list={u'key': [0, [1, b'binary']]})
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.bin_key (dict)': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_value (dict)': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_nested_key (dict)': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_nested_val (dict)': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_nested_list (dict)': 1,
    } == result
    assert {} == errors


def test_migrate__parse__7(zodb_storage, zodb_root):
    """It analyzes contents of `BTree`s."""
    zodb_root[u'tree'] = BTrees.OOBTree.OOBTree()
    zodb_root[u'tree'][u'key'] = b'binary'
    zodb_root[u'tree'][u'stuff'] = [{u'key': b'binary'}]
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        "BTrees.OOBTree.OOBTree[u'key'] (string)": 1,
        "BTrees.OOBTree.OOBTree[u'stuff'] (iterable)": 1,
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
