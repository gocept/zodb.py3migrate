# encoding: utf-8
from ..migrate import print_results, analyze, convert, convert_storage
import BTrees.IIBTree
import BTrees.OOBTree
import Products.PythonScripts.PythonScript
import ZODB.POSException
import mock
import persistent
import persistent.list
import persistent.mapping
import pkg_resources
import pytest
import transaction
import zodb.py3migrate.migrate
import zodbpickle


def sync_zodb_connection(obj):
    """Sync changes done in another connection to currently used one."""
    transaction.commit()
    obj._p_jar.invalidateCache()
    obj._p_jar.sync()


class Example(persistent.Persistent):
    """Object will be stored in ZODB with attributes written added in tests."""

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


def test_migrate__main__1():
    """It calls `migrate` with given file."""
    with mock.patch('ZODB.FileStorage.FileStorage') as filestorage:
        with mock.patch('zodb.py3migrate.migrate.analyze') as analyze:
            zodb.py3migrate.migrate.main(['path/to/Data.fs'])
            filestorage.assert_called_once_with(
                'path/to/Data.fs', blob_dir=None)
            analyze.assert_called_once_with(filestorage(), False)


def test_migrate__main__1_5():
    """It opens `FileStorage` with blob_dir if path was given."""
    with mock.patch('ZODB.FileStorage.FileStorage') as filestorage:
        with mock.patch('zodb.py3migrate.migrate.analyze'):
            zodb.py3migrate.migrate.main(
                ['path/to/Data.fs', '--blob-dir', 'path/to/blob_dir'])
            filestorage.assert_called_once_with(
                'path/to/Data.fs', blob_dir='path/to/blob_dir')


def test_migrate__main__2():
    """It returns the exception if one occurred."""
    with mock.patch('ZODB.FileStorage.FileStorage'):
        with mock.patch('zodb.py3migrate.migrate.analyze') as analyze:
                analyze.side_effect = RuntimeError
                with pytest.raises(RuntimeError):
                    zodb.py3migrate.migrate.main(['path/to/Data.fs'])


def test_migrate__main__3():
    """It drops into pdb if there was an exception and `--pdb` is set."""
    with mock.patch('ZODB.FileStorage.FileStorage'):
        with mock.patch('zodb.py3migrate.migrate.analyze') as analyze:
            with mock.patch('pdb.post_mortem') as post_mortem:
                analyze.side_effect = RuntimeError
                with pytest.raises(RuntimeError):
                    zodb.py3migrate.migrate.main(['path/to/Data.fs', '--pdb'])
                post_mortem.assert_called_once()


def test_migrate__main__4():
    """It calls `convert` if `--config` was specified."""
    with mock.patch('ZODB.FileStorage.FileStorage') as filestorage:
        with mock.patch('zodb.py3migrate.migrate.convert') as convert:
            zodb_path = pkg_resources.resource_filename(
                'zodb.py3migrate', 'migrate.py')
            config_path = pkg_resources.resource_filename(
                'zodb.py3migrate', 'conftest.py')
            zodb.py3migrate.migrate.main([zodb_path, '--config', config_path])
            convert.assert_called_once_with(filestorage(), config_path, False)


def test_migrate__find_obj_with_binary_content__1(zodb_storage, caplog):
    """It logs progress every `watermark` objects."""
    list(zodb.py3migrate.migrate.find_obj_with_binary_content(
        zodb_storage, {}, watermark=1))
    assert (
        '1 of about 1 objects analyzed.' == caplog.records()[-1].getMessage())


def test_migrate__wake_object__1(caplog):
    """It logs POSKeyErrors.

    They occur e. g. if the file for a blob is not on the hard disk.
    """
    class Sleepy(object):

        def __getattr__(self, key):
            raise ZODB.POSException.POSKeyError('\x00')

    zodb.py3migrate.migrate.wake_object(Sleepy())
    rec = caplog.records()[-1]
    assert "POSKeyError: '\\x00'" == rec.getMessage()


def test_migrate__analyze_storage__1(zodb_storage, zodb_root):
    """It parses storage and returns result of analysis."""
    zodb_root['obj'] = Example(
        binary_string=b'bär',
        unicode_string=u'föö',
        reference=Example(binary_string=b'bär', unicode_string=u'bümm'))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.binary_string is string': 2
    } == result
    assert {} == errors


def test_migrate__analyze_storage__2(zodb_storage, zodb_root):
    """It returns objects without a dict as errors."""
    zodb_root['tree'] = BTrees.IIBTree.IIBTree()
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {} == result
    assert {
        'BTrees.IIBTree.IIBTree': 1
    } == errors


def test_migrate__analyze_storage__4(zodb_storage, zodb_root):
    """It counts iterable fields that contain binary strings."""
    zodb_root['obj'] = Example(data=['bïnäry', 'anöther_binäry'])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.data is iterable': 1,
    } == result
    assert {} == errors


def test_migrate__analyze_storage__5(zodb_storage, zodb_root):
    """It counts iterable fields that contain iterables with binary strings."""
    zodb_root['obj'] = Example(data=[0, [1, [2, [3, b'binärÿ']]]])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.data is iterable': 1,
    } == result
    assert {} == errors


def test_migrate__analyze_storage__6(zodb_storage, zodb_root):
    """It counts dictionaries that contain binary strings in key or value."""
    zodb_root['0'] = Example(data={u'unïcode_key': u'unïcode_value'})
    zodb_root['1'] = Example(bin_key={b'binäry_key': u'unïcode_value'})
    zodb_root['2'] = Example(bin_value={u'unïcode_key': b'bïnäry_value'})
    zodb_root['3'] = Example(bin_nested_key={u'këy': {b'bïn_key': u'väl'}})
    zodb_root['4'] = Example(bin_nested_val={u'këy': {u'këy': b'bïn_val'}})
    zodb_root['5'] = Example(bin_nested_list={u'këy': [0, [1, b'bïnary']]})
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.bin_key is dict': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_value is dict': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_nested_key is dict': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_nested_val is dict': 1,
        'zodb.py3migrate.tests.test_migrate.Example.bin_nested_list is dict': 1
    } == result
    assert {} == errors


def test_migrate__analyze_storage__7(zodb_storage, zodb_root):
    """It analyzes contents of `BTree`s."""
    zodb_root['tree'] = BTrees.OOBTree.OOBTree()
    zodb_root['tree']['key'] = b'bïnäry'
    zodb_root['tree']['stuff'] = [{'këy': b'binäry'}]
    zodb_root['tree']['iter'] = [u'unicode_string']
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        "BTrees.OOBTree.OOBTree['key'] is string": 1,
        "BTrees.OOBTree.OOBTree['stuff'] is iterable": 1,
    } == result
    assert {} == errors


def test_migrate__analyze_storage__8(zodb_storage, zodb_root):
    """It analyzes contents of `BTreeSet`s."""
    zodb_root['set'] = BTrees.OOBTree.OOTreeSet()
    zodb_root['set'].insert(b'bïnäry')
    zodb_root['set'].insert((b'ä', b'ç',))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        u"BTrees.OOBTree.OOTreeSet['b\\xc3\\xafn\\xc3\\xa4ry'] is key": 1,
        u"BTrees.OOBTree.OOTreeSet[('\\xc3\\xa4', '\\xc3\\xa7')] is key": 1,
    } == result
    assert {} == errors


def test_migrate__analyze_storage__8_5(zodb_storage, zodb_root):
    """It analyzes the contents of a `PersistentMapping`."""
    zodb_root['map'] = persistent.mapping.PersistentMapping()
    zodb_root['map']['key'] = b'bïnäry'
    zodb_root['map']['stuff'] = [{'këy': b'binäry'}]
    zodb_root['map']['iter'] = [u'unicode_string']
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        "persistent.mapping.PersistentMapping['key'] is string": 1,
        "persistent.mapping.PersistentMapping['stuff'] is iterable": 1,
    } == result
    assert {} == errors


def test_migrate__analyze_storage__8_6(zodb_storage, zodb_root):
    """It analyzes the contents of a `PersistentList`."""
    zodb_root['map'] = persistent.list.PersistentList()
    zodb_root['map'].append(b'bïnäry')
    zodb_root['map'].append([u'unicode_string'])
    zodb_root['map'].append([{'këy': b'binäry'}])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        "persistent.list.PersistentList[0] is string": 1,
        "persistent.list.PersistentList[2] is iterable": 1,
    } == result
    assert {} == errors


def test_migrate__analyze_storage__9(zodb_storage, zodb_root, caplog):
    """It skips objects that cannot be parsed.

    If the application code setup is incomplete, e.g. ZCML was not setup, some
    code might not work as intended.

    """
    zodb_root['foo'] = b'bär'
    transaction.commit()
    with mock.patch('zodb.py3migrate.migrate.find_binary',
                    side_effect=RuntimeError):
        result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
        assert caplog.records()[-1].exc_text.endswith('RuntimeError')


def test_migrate__analyze_storage__10(zodb_storage, zodb_root):
    """It includes first bytes of the string in result if verbose is true."""
    zodb_root['obj'] = Example(
        data=[0, b'löng string containing an umlaut.'])
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(
        zodb_storage, verbose=True)
    assert {
        "zodb.py3migrate.tests.test_migrate.Example.data "
        "is iterable: [0, 'l\\xc3\\xb6ng string contai": 1,
    } == result
    assert {} == errors


def test_migrate__analyze_storage__11(zodb_storage, zodb_root):
    """It ignores binary strings that are marked with `zodbpickle.binary`."""
    zodb_root['obj'] = Example(data=zodbpickle.binary(b'bïnäry'))
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {} == result
    assert {} == errors


def test_migrate__analyze_storage__12(zodb_storage, zodb_root, caplog):
    """It does not break on `PythonScript` objects."""
    zodb_root['ps'] = Products.PythonScripts.PythonScript.PythonScript('ps')
    zodb_root['ps'].write('print "Hello Python 3!"')
    transaction.commit()
    result, errors = zodb.py3migrate.migrate.analyze_storage(zodb_storage)
    assert {
        'Products.PythonScripts.PythonScript.PythonScript.'
        'Python_magic is string': 1,
        'Products.PythonScripts.PythonScript.PythonScript._code is string': 1
    } == result
    assert {} == errors
    # There is no error message in the log:
    assert 'Analyzing about 2 objects.' == caplog.records()[-1].getMessage()


def test_migrate__print_results__1(capsys):
    """It prints only the results if `verbose` is `False`."""
    print_results(
        {'foo.Bar.baz': 3}, {'asdf.Qwe': 2}, verb='Found', verbose=False)
    out, err = capsys.readouterr()
    assert '''\
Found 1 binary fields: (number of occurrences)
foo.Bar.baz (3)
''' == out


def test_migrate__print_results__2(capsys):
    """It prints the errors, too if `verbose` is `True`."""
    print_results(
        {'foo.Bar.baz': 3}, {'asdf.Qwe': 2}, verb='Converted', verbose=True)
    out, err = capsys.readouterr()
    assert '''\
Found 1 classes whose objects do not have __dict__: (number of occurrences)
asdf.Qwe (2)

# ########################################################### #

Converted 1 binary fields: (number of occurrences)
foo.Bar.baz (3)
''' == out


def test_migrate__analyze__1(zodb_storage, capsys):
    """It runs the whole analysis for a path of a storage."""
    analyze(zodb_storage)
    out, err = capsys.readouterr()
    assert 'Found 0 binary fields: (number of occurrences)\n' == out


def test_migrate__convert__1(zodb_storage, capsys, tmpdir):
    """It applys the mapping for all objects of a storage."""
    file = tmpdir.join('config.ini')
    file.write('')
    convert(zodb_storage, str(file))
    out, err = capsys.readouterr()
    assert 'Converted 0 binary fields: (number of occurrences)\n' == out


def test_migrate__read_mapping__1(tmpdir):
    """It maps dotted name to encoding according to the given config file."""
    file = tmpdir.join('config.ini')
    file.write("""
[zodbpickle.binary]
foo.bar.Baz.image

[utf-8]
foo.bar.Baz.text
foo.bar.Baz.title

[latin-1]
foo.bar.Baz.legacy
BTrees.OOBTree.OOBTree['7b6d22fa-594e']
""")
    mapping = zodb.py3migrate.migrate.read_mapping(str(file))
    assert {
        'foo.bar.Baz.image': 'zodbpickle.binary',
        'foo.bar.Baz.text': 'utf-8',
        'foo.bar.Baz.title': 'utf-8',
        'foo.bar.Baz.legacy': 'latin-1',
        "BTrees.OOBTree.OOBTree['7b6d22fa-594e']": 'latin-1',
    } == mapping


def test_migrate__convert_storage__1(zodb_storage, zodb_root):
    """It persists conversion in ZODB."""
    from ZODB.DB import DB
    zodb_root['obj'] = Example(img=b'avatär')
    transaction.commit()
    mapping = {
        'zodb.py3migrate.tests.test_migrate.Example.img': 'zodbpickle.binary',
    }
    convert_storage(zodb_storage, mapping)
    transaction.commit()

    path = zodb_storage._file_name
    zodb_storage.close()

    storage = ZODB.FileStorage.FileStorage(path)
    db = DB(storage)
    root = db.open().root()
    try:
        assert isinstance(root['obj'].img, zodbpickle.binary)
    finally:
        db.close()
        storage.close()


def test_migrate__convert_storage__2(zodb_storage, zodb_root):
    """It converts only binary strings that appear in the mapping."""
    zodb_root['obj'] = Example(img=b'avatär', background_image=b'gïf')
    transaction.commit()
    mapping = {
        'zodb.py3migrate.tests.test_migrate.Example.img': 'zodbpickle.binary',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.img': 1,
    } == result
    assert {} == errors

    sync_zodb_connection(zodb_root)
    assert b'avatär' == zodb_root['obj'].img
    assert isinstance(zodb_root['obj'].img, zodbpickle.binary)
    assert b'gïf' == zodb_root['obj'].background_image
    assert not isinstance(zodb_root['obj'].background_image, zodbpickle.binary)


def test_migrate__convert_storage__3(zodb_storage, zodb_root):
    """It decodes binary string using encoding given by section name."""
    zodb_root['obj'] = Example(
        title=u'bïnäry'.encode('utf-8'), text=u'bïnäry'.encode('latin-1'))
    transaction.commit()
    mapping = {
        'zodb.py3migrate.tests.test_migrate.Example.title': 'utf-8',
        'zodb.py3migrate.tests.test_migrate.Example.text': 'latin-1',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {
        'zodb.py3migrate.tests.test_migrate.Example.title': 1,
        'zodb.py3migrate.tests.test_migrate.Example.text': 1,
    } == result
    assert {} == errors

    sync_zodb_connection(zodb_root)
    assert u'bïnäry' == zodb_root['obj'].title
    assert isinstance(zodb_root['obj'].title, unicode)
    assert u'bïnäry' == zodb_root['obj'].text
    assert isinstance(zodb_root['obj'].text, unicode)


def test_migrate__convert_storage__4(zodb_storage, zodb_root):
    """It does not convert keys that are binary strings."""
    zodb_root['obj'] = Example(**{b'bïnäry': u'unicode'})
    transaction.commit()
    mapping = {
        'zodb.py3migrate.tests.test_migrate.Example.bïnäry': 'utf-8',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {} == result
    assert {} == errors
    sync_zodb_connection(zodb_root)
    assert u'unicode' == getattr(zodb_root['obj'], b'bïnäry')


def test_migrate__convert_storage_5(zodb_storage, zodb_root):
    """It converts values of a BTree if mapping was given using [repr(key)]."""
    zodb_root['tree'] = BTrees.OOBTree.OOBTree()
    zodb_root['tree']['key'] = b'bïnäry'
    transaction.commit()
    mapping = {
        "BTrees.OOBTree.OOBTree['key']": 'utf-8',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {
        "BTrees.OOBTree.OOBTree['key']": 1,
    } == result
    assert {} == errors
    sync_zodb_connection(zodb_root)
    assert u'bïnäry' == zodb_root['tree']['key']


def test_migrate__convert_storage_6(zodb_storage, zodb_root):
    """It converts values of a PersistentMapping."""
    zodb_root['map'] = persistent.mapping.PersistentMapping()
    zodb_root['map']['key'] = b'bïnäry'
    transaction.commit()
    mapping = {
        "persistent.mapping.PersistentMapping['key']": 'utf-8',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {
        "persistent.mapping.PersistentMapping['key']": 1,
    } == result
    assert {} == errors
    sync_zodb_connection(zodb_root)
    assert u'bïnäry' == zodb_root['map']['key']


def test_migrate__convert_storage_7(zodb_storage, zodb_root):
    """It converts values of a PersistentList."""
    zodb_root['list'] = persistent.list.PersistentList()
    zodb_root['list'].extend([u'unicöde', b'bïnäry'])
    transaction.commit()
    mapping = {
        "persistent.list.PersistentList[1]": 'utf-8',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {
        "persistent.list.PersistentList[1]": 1,
    } == result
    assert {} == errors
    sync_zodb_connection(zodb_root)
    assert [u'unicöde', u'bïnäry'] == zodb_root['list']
