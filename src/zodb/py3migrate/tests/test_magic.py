from ..magic import set_magic
import mock
import os.path
import pkg_resources
import transaction
import zodb.py3migrate.magic


def test_magic__main__1():
    """It calls set_magic with the given file and version."""
    with mock.patch('zodb.py3migrate.magic.set_magic') as set_magic:
        path = pkg_resources.resource_filename('zodb.py3migrate', 'magic.py')
        zodb.py3migrate.magic.main([path, 'Python3'])
        set_magic.assert_called_once_with(path, 'Python3')


def test_magic__set_magic__1(zodb_storage, zodb_root):
    """It sets the magic bytes to ``FS30`` for Python 3."""
    zodb_root['asdf'] = [1, 2, 3]
    transaction.commit()
    zodb_storage.close()
    path = zodb_storage._file_name
    size_before = os.path.getsize(path)
    assert size_before > 4  # Filestorage actually has contents.
    set_magic(path, 'Python3')
    with open(path) as zodb:
        assert 'FS30' == zodb.read(4)
    assert size_before == os.path.getsize(path)


def test_magic__set_magic__2(zodb_storage):
    """It sets the magic bytes to ``FS21`` for Python 2."""
    zodb_storage.close()
    path = zodb_storage._file_name
    set_magic(path, 'Python3')
    set_magic(path, 'Python2')
    with open(path) as zodb:
        assert 'FS21' == zodb.read(4)
