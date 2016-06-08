# encoding: utf-8
from ..convert import convert, convert_storage, read_mapping
from ..testing import Example, sync_zodb_connection
import BTrees.IIBTree
import BTrees.OOBTree
import ZODB.POSException
import persistent
import persistent.list
import persistent.mapping
import transaction
import zodb.py3migrate.convert
import zodbpickle


def test_convert__main__1(zodb_storage, zodb_root, tmpdir, capsys):
    """It converts a storage."""
    zodb_root['obj'] = Example(binary=b'bär1', text=b'tëxt')
    transaction.commit()
    zodb_storage.close()

    file = tmpdir.join('config.ini')
    file.write("""
[zodbpickle.binary]
zodb.py3migrate.testing.Example.binary

[utf-8]
zodb.py3migrate.testing.Example.text
""")

    zodb.py3migrate.convert.main(
        [zodb_storage.getName(), '--config={}'.format(file)])
    out, err = capsys.readouterr()
    assert '''\
Converted 2 binary fields: (number of occurrences)
zodb.py3migrate.testing.Example.binary (1)
zodb.py3migrate.testing.Example.text (1)
''' == out
    assert '' == err


def test_convert__convert__1(zodb_storage, capsys, tmpdir):
    """It applys the mapping for all objects of a storage."""
    file = tmpdir.join('config.ini')
    file.write('')
    convert(zodb_storage, str(file))
    out, err = capsys.readouterr()
    assert 'Converted 0 binary fields: (number of occurrences)\n' == out


def test_convert__read_mapping__1(tmpdir):
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
    mapping = read_mapping(str(file))
    assert {
        'foo.bar.Baz.image': 'zodbpickle.binary',
        'foo.bar.Baz.text': 'utf-8',
        'foo.bar.Baz.title': 'utf-8',
        'foo.bar.Baz.legacy': 'latin-1',
        "BTrees.OOBTree.OOBTree['7b6d22fa-594e']": 'latin-1',
    } == mapping


def test_convert__convert_storage__1(zodb_storage, zodb_root):
    """It persists conversion in ZODB."""
    from ZODB.DB import DB
    zodb_root['obj'] = Example(img=b'avatär')
    transaction.commit()
    mapping = {
        'zodb.py3migrate.testing.Example.img': 'zodbpickle.binary',
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


def test_convert__convert_storage__2(zodb_storage, zodb_root):
    """It converts only binary strings that appear in the mapping."""
    zodb_root['obj'] = Example(img=b'avatär', background_image=b'gïf')
    transaction.commit()
    mapping = {
        'zodb.py3migrate.testing.Example.img': 'zodbpickle.binary',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {
        'zodb.py3migrate.testing.Example.img': 1,
    } == result
    assert {} == errors

    sync_zodb_connection(zodb_root)
    assert b'avatär' == zodb_root['obj'].img
    assert isinstance(zodb_root['obj'].img, zodbpickle.binary)
    assert b'gïf' == zodb_root['obj'].background_image
    assert not isinstance(zodb_root['obj'].background_image, zodbpickle.binary)


def test_convert__convert_storage__3(zodb_storage, zodb_root):
    """It decodes binary string using encoding given by section name."""
    zodb_root['obj'] = Example(
        title=u'bïnäry'.encode('utf-8'), text=u'bïnäry'.encode('latin-1'))
    transaction.commit()
    mapping = {
        'zodb.py3migrate.testing.Example.title': 'utf-8',
        'zodb.py3migrate.testing.Example.text': 'latin-1',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {
        'zodb.py3migrate.testing.Example.title': 1,
        'zodb.py3migrate.testing.Example.text': 1,
    } == result
    assert {} == errors

    sync_zodb_connection(zodb_root)
    assert u'bïnäry' == zodb_root['obj'].title
    assert isinstance(zodb_root['obj'].title, unicode)
    assert u'bïnäry' == zodb_root['obj'].text
    assert isinstance(zodb_root['obj'].text, unicode)


def test_convert__convert_storage__4(zodb_storage, zodb_root):
    """It does not convert keys that are binary strings."""
    zodb_root['obj'] = Example(**{b'bïnäry': u'unicode'})
    transaction.commit()
    mapping = {
        'zodb.py3migrate.testing.Example.bïnäry': 'utf-8',
    }
    result, errors = convert_storage(zodb_storage, mapping)
    assert {} == result
    assert {} == errors
    sync_zodb_connection(zodb_root)
    assert u'unicode' == getattr(zodb_root['obj'], b'bïnäry')


def test_convert__convert_storage_5(zodb_storage, zodb_root):
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


def test_convert__convert_storage_6(zodb_storage, zodb_root):
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


def test_convert__convert_storage_7(zodb_storage, zodb_root):
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
