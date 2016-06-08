# encoding: utf-8
from ..analyze import analyze, analyze_storage
from ..testing import Example
import BTrees.IIBTree
import BTrees.OOBTree
import Products.PythonScripts.PythonScript
import mock
import persistent.list
import persistent.mapping
import transaction
import zodb.py3migrate.analyze
import zodbpickle


def test_analyze__main__1(zodb_storage, zodb_root, capsys):
    """It runs an analysis on a given ZODB."""
    zodb_root['obj'] = Example(binary=b'bär1')
    zodb_root['obj2'] = Example(binary2=b'bär2')
    transaction.commit()
    zodb_storage.close()

    zodb.py3migrate.analyze.main(
        [zodb_storage.getName(), '--start=0x01', '--limit=1'])
    out, err = capsys.readouterr()
    assert '''\
Found 1 binary fields: (number of occurrences)
zodb.py3migrate.testing.Example.binary2 is string (1)
''' == out
    assert '' == err


def test_analyze__analyze_storage__1(zodb_storage, zodb_root):
    """It parses storage and returns result of analysis."""
    zodb_root['obj'] = Example(
        binary_string=b'bär',
        unicode_string=u'föö',
        reference=Example(binary_string=b'bär', unicode_string=u'bümm'))
    transaction.commit()

    result, errors = analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.testing.Example.binary_string is string': 2
    } == result
    assert {} == errors


def test_analyze__analyze_storage__2(zodb_storage, zodb_root):
    """It returns objects without a dict as errors."""
    zodb_root['tree'] = BTrees.IIBTree.IIBTree()
    transaction.commit()

    result, errors = analyze_storage(zodb_storage)
    assert {} == result
    assert {
        'BTrees.IIBTree.IIBTree': 1
    } == errors


def test_analyze__analyze_storage__4(zodb_storage, zodb_root):
    """It counts iterable fields that contain binary strings."""
    zodb_root['obj'] = Example(data=['bïnäry', 'anöther_binäry'])
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.testing.Example.data is iterable': 1,
    } == result
    assert {} == errors


def test_analyze__analyze_storage__5(zodb_storage, zodb_root):
    """It counts iterable fields that contain iterables with binary strings."""
    zodb_root['obj'] = Example(data=[0, [1, [2, [3, b'binärÿ']]]])
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.testing.Example.data is iterable': 1,
    } == result
    assert {} == errors


def test_analyze__analyze_storage__6(zodb_storage, zodb_root):
    """It counts dictionaries that contain binary strings in key or value."""
    zodb_root['0'] = Example(data={u'unïcode_key': u'unïcode_value'})
    zodb_root['1'] = Example(bin_key={b'binäry_key': u'unïcode_value'})
    zodb_root['2'] = Example(bin_value={u'unïcode_key': b'bïnäry_value'})
    zodb_root['3'] = Example(bin_nested_key={u'këy': {b'bïn_key': u'väl'}})
    zodb_root['4'] = Example(bin_nested_val={u'këy': {u'këy': b'bïn_val'}})
    zodb_root['5'] = Example(bin_nested_list={u'këy': [0, [1, b'bïnary']]})
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.testing.Example.bin_key is dict': 1,
        'zodb.py3migrate.testing.Example.bin_value is dict': 1,
        'zodb.py3migrate.testing.Example.bin_nested_key is dict': 1,
        'zodb.py3migrate.testing.Example.bin_nested_val is dict': 1,
        'zodb.py3migrate.testing.Example.bin_nested_list is dict': 1
    } == result
    assert {} == errors


def test_analyze__analyze_storage__7(zodb_storage, zodb_root):
    """It analyzes contents of `BTree`s."""
    zodb_root['tree'] = BTrees.OOBTree.OOBTree()
    zodb_root['tree']['key'] = b'bïnäry'
    zodb_root['tree']['stuff'] = [{'këy': b'binäry'}]
    zodb_root['tree']['iter'] = [u'unicode_string']
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        "BTrees.OOBTree.OOBTree['key'] is string": 1,
        "BTrees.OOBTree.OOBTree['stuff'] is iterable": 1,
    } == result
    assert {} == errors


def test_analyze__analyze_storage__8(zodb_storage, zodb_root):
    """It analyzes contents of `BTreeSet`s."""
    zodb_root['set'] = BTrees.OOBTree.OOTreeSet()
    zodb_root['set'].insert(b'bïnäry')
    zodb_root['set'].insert((b'ä', b'ç',))
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        u"BTrees.OOBTree.OOTreeSet['b\\xc3\\xafn\\xc3\\xa4ry'] is key": 1,
        u"BTrees.OOBTree.OOTreeSet[('\\xc3\\xa4', '\\xc3\\xa7')] is key": 1,
    } == result
    assert {} == errors


def test_analyze__analyze_storage__8_5(zodb_storage, zodb_root):
    """It analyzes the contents of a `PersistentMapping`."""
    zodb_root['map'] = persistent.mapping.PersistentMapping()
    zodb_root['map']['key'] = b'bïnäry'
    zodb_root['map']['stuff'] = [{'këy': b'binäry'}]
    zodb_root['map']['iter'] = [u'unicode_string']
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        "persistent.mapping.PersistentMapping['key'] is string": 1,
        "persistent.mapping.PersistentMapping['stuff'] is iterable": 1,
    } == result
    assert {} == errors


def test_analyze__analyze_storage__8_6(zodb_storage, zodb_root):
    """It analyzes the contents of a `PersistentList`."""
    zodb_root['map'] = persistent.list.PersistentList()
    zodb_root['map'].append(b'bïnäry')
    zodb_root['map'].append([u'unicode_string'])
    zodb_root['map'].append([{'këy': b'binäry'}])
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        "persistent.list.PersistentList[0] is string": 1,
        "persistent.list.PersistentList[2] is iterable": 1,
    } == result
    assert {} == errors


def test_analyze__analyze_storage__9(zodb_storage, zodb_root, caplog):
    """It skips objects that cannot be parsed.

    If the application code setup is incomplete, e.g. ZCML was not setup, some
    code might not work as intended.

    """
    zodb_root['foo'] = b'bär'
    transaction.commit()
    with mock.patch('zodb.py3migrate.migrate.find_binary',
                    side_effect=RuntimeError):
        result, errors = analyze_storage(zodb_storage)
        assert caplog.records()[-1].exc_text.endswith('RuntimeError')


def test_analyze__analyze_storage__10(zodb_storage, zodb_root):
    """It includes first bytes of the string in result if verbose is true."""
    zodb_root['obj'] = Example(
        data=[0, b'löng string containing an umlaut.'])
    transaction.commit()
    result, errors = analyze_storage(
        zodb_storage, verbose=True)
    assert {
        "zodb.py3migrate.testing.Example.data "
        "is iterable: [0, 'l\\xc3\\xb6ng string contai": 1,
    } == result
    assert {} == errors


def test_analyze__analyze_storage__11(zodb_storage, zodb_root):
    """It ignores binary strings that are marked with `zodbpickle.binary`."""
    zodb_root['obj'] = Example(data=zodbpickle.binary(b'bïnäry'))
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {} == result
    assert {} == errors


def test_analyze__analyze_storage__12(zodb_storage, zodb_root, caplog):
    """It does not break on `PythonScript` objects."""
    zodb_root['ps'] = Products.PythonScripts.PythonScript.PythonScript('ps')
    zodb_root['ps'].write('print "Hello Python 3!"')
    transaction.commit()
    result, errors = analyze_storage(zodb_storage)
    assert {
        'Products.PythonScripts.PythonScript.PythonScript.'
        'Python_magic is string': 1,
        'Products.PythonScripts.PythonScript.PythonScript._code is string': 1
    } == result
    assert {} == errors
    # There is no error message in the log:
    assert 'Analyzing about 2 objects.' == caplog.records()[-1].getMessage()


def test_analyze__analyze__1(zodb_storage, capsys):
    """It runs the whole analysis for a path of a storage."""
    analyze(zodb_storage)
    out, err = capsys.readouterr()
    assert 'Found 0 binary fields: (number of occurrences)\n' == out
