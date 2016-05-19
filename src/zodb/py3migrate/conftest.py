from ZODB.DB import DB
import ZODB.FileStorage
import pytest
import transaction


@pytest.yield_fixture(scope='function')
def zodb_storage(tmpdir):
    """Create an empty FileStorage."""
    zodb_path = str(tmpdir.mkdir("zodb.py3migrate").join("Data.fs"))
    storage = ZODB.FileStorage.FileStorage(zodb_path)
    yield storage
    storage.close()


@pytest.yield_fixture(scope='function')
def zodb_root(zodb_storage):
    """Return root object of opened ZODB storage."""
    transaction.abort()
    db = DB(zodb_storage)
    connection = db.open()
    yield connection.root()
    connection.close()
