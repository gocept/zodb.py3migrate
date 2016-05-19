from ZODB.DB import DB
import BTrees.IOBTree
import BTrees.LOBTree
import BTrees.OIBTree
import BTrees.OLBTree
import BTrees.OOBTree
import ConfigParser
import ZODB.FileStorage
import ZODB.POSException
import argparse
import collections
import email
import logging
import pdb  # noqa
import persistent
import pkg_resources
import transaction
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


def find_obj_with_binary_content(storage, errors, watermark=10000):
    db = DB(storage)
    connection = db.open()
    next = None
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


def analyze_storage(storage, verbose=False):
    """Analyze a ``FileStorage``.

    Returns a tuple `(result, errors)`
    Where
      `result` is a dict mapping a dotted name of an attribute to the
        number of occurrences in the storage and
      `errors` is a dict mapping a dotted name of a class those instances have
        no `__dict__` to the number of occurrences.
    """
    result = collections.defaultdict(int)
    errors = collections.defaultdict(int)
    for obj, data, key, value, type_ in find_obj_with_binary_content(
            storage, errors):
        klassname = get_classname(obj)
        format_string = get_format_string(
            obj, display_type=True, verbose=verbose)
        result[format_string.format(**locals())] += 1

    return result, errors


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


def convert_storage(storage, mapping, verbose=False):
    """Iterate ZODB objects with binary content and apply mapping."""
    result = collections.defaultdict(int)
    errors = collections.defaultdict(int)
    for obj, data, key, value, type_ in find_obj_with_binary_content(
            storage, errors):
        klassname = get_classname(obj)
        dotted_name = get_format_string(obj).format(**locals())
        encoding = mapping.get(dotted_name, None)
        if encoding is None or type_ == 'key':
            continue

        if encoding == 'zodbpickle.binary':
            data[key] = zodbpickle.binary(value)
        else:
            data[key] = value.decode(encoding)

        obj._p_changed = True
        result[dotted_name] += 1

    return result, errors


def read_mapping(config_path):
    """Create mapping from INI file.

    It maps the section options to the name of their section, thus a
    configuration like below results in a mapping {'foo.Bar.baz': 'utf-8'}.

    [utf-8]
    foo.Bar.baz

    """
    parser = ConfigParser.ConfigParser(allow_no_value=True)
    parser.optionxform = str  # avoid lower casing of option names
    parser.read(config_path)
    mapping = {}
    for section in parser.sections():
        mapping.update(dict.fromkeys(parser.options(section), section))
    return mapping


def analyze(storage, verbose=False):
    """Analyse a whole file storage and print out the results."""
    transaction.doom()
    print_results(
        *analyze_storage(storage, verbose=verbose),
        verb='Found', verbose=verbose)


def convert(storage, config_path, verbose=False):
    """Convert binary strings according to mapping read from config file."""
    mapping = read_mapping(config_path)
    print_results(
        *convert_storage(storage, mapping, verbose=verbose),
        verb='Converted', verbose=verbose)


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
        '-c', '--config', help='Path to conversion config file.')
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Be more verbose in output')
    parser.add_argument(
        '--pdb', action='store_true', help='Drop into a debugger on an error')
    args = parser.parse_args(args)
    try:
        storage = ZODB.FileStorage.FileStorage(
            args.zodb_path, blob_dir=args.blob_dir)
        if args.config:
            convert(storage, args.config, args.verbose)
        else:
            analyze(storage, args.verbose)
    except:
        if args.pdb:
            pdb.post_mortem()
        raise
