from ZODB.DB import DB
import BTrees.IOBTree
import BTrees.LOBTree
import BTrees.OIBTree
import BTrees.OLBTree
import BTrees.OOBTree
import ZODB.FileStorage
import ZODB.POSException
import argparse
import collections
import email
import logging
import pdb  # noqa
import persistent
import pkg_resources


log = logging.getLogger(__name__)


def wake_object(obj):
    """Wake the object so its `__dict__` gets filled."""
    getattr(obj, 'some_attribute', None)


def get_data(obj):
    """Return data of object and format string. Return `None` if not possible.

    We try to fetch data by reading __dict__, but this is not possible for
    `BTree`s. Call `keys` or `items` on obj respectively.

    We use format_string to make clear that binary strings were either found as
    an attribute of obj or as an item contained in a `BTree`.

    """
    try:
        wake_object(obj)
    except ZODB.POSException.POSKeyError as e:
        # For example if a ZODB Blob was not found.
        log.error('POSKeyError: %s', e)
        return None, None

    try:
        return vars(obj), '{klassname}.{key} ({type_})'
    except TypeError:
        result = None
        format_string = '{klassname}[{key!r}] ({type_})'
        if isinstance(obj, (
                BTrees.IOBTree.IOTreeSet,
                BTrees.LOBTree.LOTreeSet,
                BTrees.OIBTree.OITreeSet,
                BTrees.OLBTree.OLTreeSet,
                BTrees.OOBTree.OOTreeSet)):
            result = dict.fromkeys(obj.keys())
        if isinstance(obj, (
                BTrees.IOBTree.IOBTree,
                BTrees.LOBTree.LOBTree,
                BTrees.OIBTree.OIBTree,
                BTrees.OLBTree.OLBTree,
                BTrees.OOBTree.OOBTree)):
            result = obj
        return result, format_string


def find_binary(value):
    """Return type if value is or contains binary strings. None otherwise."""
    if isinstance(value, persistent.Persistent):
        # Avoid duplicate analysis of the same object and circular references
        return None
    if isinstance(value, str):
        try:
            value.decode('ascii')
        except UnicodeDecodeError:
            return 'string'
        else:
            return None
    elif isinstance(value, collections.Mapping):
        for k, v in value.items():
            if find_binary(k) or find_binary(v):
                return 'dict'
    elif hasattr(value, '__iter__'):
        for v in value:
            if find_binary(v):
                return 'iterable'
    return None


def get_classname(obj):
    return obj.__class__.__module__ + '.' + obj.__class__.__name__


def parse(storage, watermark=10000):
    """Parse a file storage.

    Returns a tuple `(result, errors)`
    Where
      `result` is a dict mapping a dotted name of an attribute to the
        number of occurrences in the storage and
      `errors` is a dict mapping a dotted name of a class those instances have
        no `__dict__` to the number of occurrences.
    """
    db = DB(storage)
    connection = db.open()
    next = None
    result = collections.defaultdict(int)
    errors = collections.defaultdict(int)
    len_storage = len(storage)
    log.warn('Analyzing about %s objects.', len_storage)
    count = 0
    run = True
    while run:
        oid, tid, data, next = storage.record_iternext(next)
        if next is None:
            run = False

        obj = connection.get(oid)
        klassname = get_classname(obj)

        data, format_string = get_data(obj)
        if data is None:
            errors[klassname] += 1
            continue

        for key, value in data.items():
            type_ = find_binary(key)
            if type_ is not None:
                type_ = 'key'
                result[format_string.format(**locals())] += 1
            type_ = find_binary(value)
            if type_ is not None:
                result[format_string.format(**locals())] += 1

        count += 1
        if count % watermark == 0:
            log.warn('%s of about %s objects analyzed.', count, len_storage)

    return result, errors


def print_results(result, errors, verbose):
    """Print the analysis results."""
    if verbose:
        print ("Found {} classes whose objects do not have __dict__: "
               "(number of occurrences)".format(len(errors)))
        for key, value in sorted_by_key(errors):
            print "{} ({})".format(key, value)
        print
        print "# ########################################################### #"
        print
    print "Found {} binary fields: (number of occurrences)".format(
        len(result))
    for key, value in sorted_by_key(result):
        print "{} ({})".format(key, value)


def analyze(zodb_path, blob_dir=None, verbose=False):
    """Analyse a whole file storage and print out the results."""
    storage = ZODB.FileStorage.FileStorage(zodb_path, blob_dir=blob_dir)
    print_results(*parse(storage), verbose=verbose)


def sorted_by_key(dict):
    """Get dict entries sorted by the key."""
    for key in sorted(dict):
        yield key, dict[key]


def main(args=None):
    """Entry point for the script."""
    logging.basicConfig(level=logging.INFO)
    description = email.message_from_string(pkg_resources.get_distribution(
        'zodb.py3migrate').get_metadata('PKG-INFO'))['summary']
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        'zodb_path', help='Path to Data.fs', metavar='Data.fs')
    parser.add_argument(
        '-b', '--blob-dir', default=None,
        help='Path to the blob directory if ZODB blobs are used.')
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Be more verbose in output')
    parser.add_argument(
        '--pdb', action='store_true', help='Drop into a debugger on an error')
    args = parser.parse_args(args)
    try:
        analyze(args.zodb_path, args.blob_dir, args.verbose)
    except:
        if args.pdb:
            pdb.post_mortem()
        raise
