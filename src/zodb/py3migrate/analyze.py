from .migrate import print_results, get_argparse_parser, get_format_string
from .migrate import get_classname, find_obj_with_binary_content, run
import collections
import logging
import transaction


log = logging.getLogger(__name__)


def analyze_storage(storage, verbose=False, start_at=None, limit=None):
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
            storage, errors, start_at=start_at, limit=limit):
        klassname = get_classname(obj)
        format_string = get_format_string(
            obj, display_type=True, verbose=verbose)
        result[format_string.format(**locals())] += 1

    return result, errors


def analyze(storage, verbose=False, start_at=None, limit=None):
    """Analyse a whole file storage and print out the results."""
    transaction.doom()
    results = analyze_storage(
        storage, verbose=verbose, start_at=start_at, limit=limit)
    print_results(*results, verb='Found', verbose=verbose)


def main(args=None):
    """Entry point for the analyze script."""
    parser = get_argparse_parser(
        "Analyze binary fields in a ZODB FileStorage that need a conversion "
        "before this FileStorage can be used with Python 3.""")
    group = parser.add_argument_group('Analyze options')
    group.add_argument(
        '--start', default=None,
        help='OID to start analysis with. Default: start with first OID in '
        'storage.')
    group.add_argument(
        '--limit', default=None, type=int,
        help='Analyze at most that many objects. Default: no limit')
    run(parser, analyze, 'verbose', 'start', 'limit', args=args)
