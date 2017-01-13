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
import logging
import pdb  # noqa
import transaction
import persistent
import zodbpickle


log = logging.getLogger(__name__)


def wake_object(obj):
    """Wake the object so its `__dict__` gets filled."""
    try:
        getattr(obj, 'some_attribute', None)
    except ZODB.POSException.POSKeyError as e:
        # For example if a ZODB Blob was not found.
        log.error('POSKeyError: %s', e)


def is_container(obj):
    return isinstance(obj, (
        BTrees.IOBTree.IOBTree,
        BTrees.LOBTree.LOBTree,
        BTrees.OIBTree.OIBTree,
        BTrees.OLBTree.OLBTree,
        BTrees.OOBTree.OOBTree,
        persistent.mapping.PersistentMapping,
        persistent.list.PersistentList))


def is_treeset(obj):
    return isinstance(obj, (
        BTrees.IOBTree.IOTreeSet,
        BTrees.LOBTree.LOTreeSet,
        BTrees.OIBTree.OITreeSet,
        BTrees.OLBTree.OLTreeSet,
        BTrees.OOBTree.OOTreeSet))


def get_data(obj):
    """Return data of object. Return `None` if not possible.

    We try to fetch data by reading __dict__, but this is not possible for
    `BTree`s. Call `keys` or `items` on obj respectively.

    """
    result = None
    if is_container(obj):
        result = obj
    elif is_treeset(obj):
        result = dict.fromkeys(obj.keys())
    else:
        try:
            result = vars(obj)
        except TypeError:
            pass
    return result


def find_binary(value):
    """Return type if value is or contains binary strings. None otherwise."""
    if isinstance(value, persistent.Persistent):
        # Avoid duplicate analysis of the same object and circular references
        return None
    if isinstance(value, zodbpickle.binary):
        # Already marked as binary, skip.
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
        try:
            for v in value:
                if find_binary(v):
                    return 'iterable'
        except TypeError:
            # e. g. <type 'tuple'> has __iter__ but as it is a class it can
            # not be called successfully.
            pass
    return None


def get_classname(obj):
    return obj.__class__.__module__ + '.' + obj.__class__.__name__


def get_items(obj):
    """Get the items of a dict-like or list-like object."""
    if hasattr(obj, 'items'):
        items = obj.items()
    else:
        items = enumerate(obj)
    return items


def find_obj_with_binary_content(
        storage, errors, start_at=None, limit=None, watermark=10000):
    """Generator which finds objects in `storage` having binary content.

    Yields tuple: (object, data, key-name, value, type)

    `type` can be one of 'string', 'dict', 'iterable', 'key'.
    """
    db = DB(storage)
    connection = db.open()
    if start_at is not None:
        next = ZODB.utils.repr_to_oid(start_at)
    else:
        next = None  # first OID in storage
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

        wake_object(obj)
        data = get_data(obj)
        if data is None:
            errors[klassname] += 1
            continue

        for key, value in get_items(data):
            try:
                type_ = find_binary(value)
                if type_ is not None:
                    yield obj, data, key, value, type_
                type_ = find_binary(key)
                if type_ is not None:
                    yield obj, data, key, key, 'key'
            except:
                log.error('Could not execute %r', value, exc_info=True)
                continue

        count += 1
        if count % watermark == 0:
            log.warn('%s of about %s objects analyzed.', count, len_storage)
            transaction.savepoint()
            connection.cacheMinimize()
        if limit is not None and count >= limit:
            return


def get_format_string(obj, display_type=False, verbose=False):
    format_string = ''
    if is_treeset(obj) or is_container(obj):
        format_string = '{klassname}[{key!r}]'
    else:
        format_string = '{klassname}.{key}'

    if display_type:
        format_string += ' is {type_}%s' % (
            ': {value!r:.30}' if verbose else '')

    return format_string


def print_results(result, errors, verb, verbose):
    """Print the analysis results."""
    if verbose:
        print ("Found {} classes whose objects do not have __dict__: "
               "(number of occurrences)".format(len(errors)))
        for key, value in sorted_by_key(errors):
            print "{} ({})".format(key, value)
        print
        print "# ########################################################### #"
        print
    print "{} {} binary fields: (number of occurrences)".format(
        verb, len(result))
    for key, value in sorted_by_key(result):
        print "{} ({})".format(key, value)


def sorted_by_key(dict):
    """Get dict entries sorted by the key."""
    for key in sorted(dict):
        yield key, dict[key]


def get_argparse_parser(description):
    """Return an ArgumentParser with the default configuration."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        'zodb_path', help='Path to Data.fs', metavar='Data.fs')
    group = parser.add_argument_group('General options')
    group.add_argument(
        '-b', '--blob-dir', default=None,
        help='Path to the blob directory if ZODB blobs are used.')
    group.add_argument(
        '-v', '--verbose', action='store_true',
        help='Be more verbose in output')
    group.add_argument(
        '--pdb', action='store_true', help='Drop into a debugger on an error')
    return parser


def run(parser, callable, *arg_names, **kw):
    """Parse the command line args and feed them to `callable`.

    *arg_names ... command line arguments which should be used as arguments of
                   the `callable`.
    **kw ... Only the key `args` is allowed here to override the command line
             arguments in tests.
    """
    logging.basicConfig(level=logging.INFO)
    args = kw.pop('args', None)
    assert not kw, \
        "Don't know how to handle the following kwargs: {!r}".format(kw)

    args = parser.parse_args(args)
    try:
        storage = ZODB.FileStorage.FileStorage(
            args.zodb_path, blob_dir=args.blob_dir)
        callable_args = [getattr(args, x) for x in arg_names]
        return callable(storage, *callable_args)
    except:
        if args.pdb:
            pdb.post_mortem()
        raise
