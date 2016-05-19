# encoding: utf-8

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
import zodbpickle


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


def test_migrate__find_obj_with_binary_content__1(zodb_storage, caplog):
    """It logs progress every `watermark` objects."""
    list(zodb.py3migrate.migrate.find_obj_with_binary_content(
        zodb_storage, {}, watermark=1))
    assert (
        '1 of about 1 objects analyzed.' == caplog.records()[-1].getMessage())


def test_migrate__parse__1(zodb_storage, zodb_root):
    """It parses storage and returns result of analysis."""
    zodb_root['obj'] = Example(
        binary_string=b'bär',
        unicode_string=u'föö',
        reference=Example(binary_string=b'bär', unicode_string=u'bümm'))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.binary_string (string)': 2
    } == result
    assert {} == errors


def test_migrate__parse__2(zodb_storage, zodb_root):
    """It returns objects without a dict as errors."""
    zodb_root['tree'] = BTrees.IIBTree.IIBTree()
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {} == result
    assert {
        'BTrees.IIBTree.IIBTree': 1
    } == errors


def test_migrate__parse__3(zodb_storage, caplog):
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
    zodb_root['obj'] = Example(data=['bïnäry', 'anöther_binäry'])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.data (iterable)': 1,
    } == result
    assert {} == errors


def test_migrate__parse__5(zodb_storage, zodb_root):
    """It counts iterable fields that contain iterables with binary strings."""
    zodb_root['obj'] = Example(data=[0, [1, [2, [3, b'binärÿ']]]])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.data (iterable)': 1,
    } == result
    assert {} == errors


def test_migrate__parse__6(zodb_storage, zodb_root):
    """It counts dictionaries that contain binary strings in key or value."""
    zodb_root['0'] = Example(data={u'unïcode_key': u'unïcode_value'})
    zodb_root['1'] = Example(bin_key={b'binäry_key': u'unïcode_value'})
    zodb_root['2'] = Example(bin_value={u'unïcode_key': b'bïnäry_value'})
    zodb_root['3'] = Example(bin_nested_key={u'këy': {b'bïn_key': u'väl'}})
    zodb_root['4'] = Example(bin_nested_val={u'këy': {u'këy': b'bïn_val'}})
    zodb_root['5'] = Example(bin_nested_list={u'këy': [0, [1, b'bïnary']]})
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
    zodb_root['tree'] = BTrees.OOBTree.OOBTree()
    zodb_root['tree']['key'] = b'bïnäry'
    zodb_root['tree']['stuff'] = [{'këy': b'binäry'}]
    zodb_root['tree']['iter'] = [u'unicode_string']
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        "BTrees.OOBTree.OOBTree['key'] (string)": 1,
        "BTrees.OOBTree.OOBTree['stuff'] (iterable)": 1,
    } == result
    assert {} == errors


def test_migrate__parse__8(zodb_storage, zodb_root):
    """It analyzes contents of `BTreeSet`s."""
    zodb_root['set'] = BTrees.OOBTree.OOTreeSet()
    zodb_root['set'].insert(b'bïnäry')
    zodb_root['set'].insert((b'ä', b'ç',))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {
        u"BTrees.OOBTree.OOTreeSet['b\\xc3\\xafn\\xc3\\xa4ry'] (key)": 1,
        u"BTrees.OOBTree.OOTreeSet[('\\xc3\\xa4', '\\xc3\\xa7')] (key)": 1,
    } == result
    assert {} == errors


def test_migrate__parse__9(zodb_storage, caplog):
    """It skips objects that cannot be parsed.

    If the application code setup is incomplete, e.g. ZCML was not setup, some
    code might not work as intended.

    """
    with mock.patch('zodb.py3migrate.migrate.find_binary',
                    side_effect=RuntimeError):
        result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
        assert caplog.records()[-1].exc_text.endswith('RuntimeError')


def test_migrate__parse__10(zodb_storage, zodb_root):
    """It includes first bytes of the string in result if verbose is true."""
    zodb_root['obj'] = Example(
        data=[0, b'löng string containing an umlaut.'])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage, verbose=True)
    assert {
        "zodb.py3migrate.tests.test_migrate.Example.data "
        "(iterable: [0, 'l\\xc3\\xb6ng string contai)": 1,
    } == result
    assert {} == errors


def test_migrate__parse__11(zodb_storage, zodb_root):
    """It ignores binary strings that are marked with `zodbpickle.binary`."""
    zodb_root['obj'] = Example(data=zodbpickle.binary(b'bïnäry'))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.parse(zodb_storage)
    assert {} == result
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


def test_migrate__analyze__1(zodb_storage, capsys):
    """It runs the whole analysis for a path of a storage."""
    zodb_storage.close()
    path = zodb_storage._file_name
    analyze(path)
    out, err = capsys.readouterr()
    assert 'Found 0 binary fields: (number of occurrences)\n' == out
