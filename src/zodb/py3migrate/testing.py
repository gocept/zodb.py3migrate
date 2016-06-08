import persistent
import transaction


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
