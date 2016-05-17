import ZODB.FileStorage
import argparse
import collections
import email
import pkg_resources
import logging

log = logging.getLogger(__name__)


def parse(storage):
    from ZODB.DB import DB
    db = DB(storage)
    connection = db.open()
    next = None
    result = collections.defaultdict(int)
    len_storage = len(storage)
    log.warn('Analyzing about %s objects (%s bytes)',
             len_storage, storage.getSize())
    count = 0
    while True:
        oid, tid, data, next = storage.record_iternext(next)
        obj = connection.get(oid)
        getattr(obj, 'perform_getattr_to_wake_obj', None)
        klassname = obj.__class__.__module__ + '.' + obj.__class__.__name__
        log.warn('Analyzing %s', klassname)
        try:
            vars(obj)
        except:
            continue
        for key, value in vars(obj).items():
            if isinstance(value, str):
                result['.'.join([klassname, key])] += 1
        count += 1
        if count % 10000 == 0:
            log.warn('%s of %s objects analyzed', count, len_storage)
        if next is None:
            break
    return result


def migrate(zodb_path):
    storage = ZODB.FileStorage.FileStorage(zodb_path)
    result = parse(storage)
    print(result)


def main(args=None):
    logging.basicConfig(level=logging.INFO)
    description = email.message_from_string(pkg_resources.get_distribution(
        'zodb.py3migrate').get_metadata('PKG-INFO'))['summary']
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        'zodb_path', help='Path to Data.fs', metavar='Data.fs')
    args = parser.parse_args(args)
    migrate(args.zodb_path)
