from ZODB.DB import DB
import ZODB.FileStorage
import ZODB.POSException
import argparse
import collections
import email
import logging
import pdb  # noqa
import pkg_resources


log = logging.getLogger(__name__)


def wake_object(obj):
    """Wake the object so its `__dict__` gets filled."""
    getattr(obj, 'some_attribute', None)


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
        try:
            wake_object(obj)
        except ZODB.POSException.POSKeyError as e:
            log.error('POSKeyError: %s', e)
        klassname = obj.__class__.__module__ + '.' + obj.__class__.__name__
        try:
            attribs = vars(obj)
        except TypeError:
            errors[klassname] += 1
            continue
        for key, value in attribs.items():
            if isinstance(value, str):
                result['.'.join([klassname, key])] += 1
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
