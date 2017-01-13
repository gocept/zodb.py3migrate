from .migrate import print_results, get_argparse_parser, get_format_string
from .migrate import get_classname, find_obj_with_binary_content, run
import ConfigParser
import collections
import logging
import zodbpickle
import transaction


log = logging.getLogger(__name__)


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

    transaction.commit()
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


def convert(storage, config_path, verbose=False):
    """Convert binary strings according to mapping read from config file."""
    mapping = read_mapping(config_path)
    print_results(
        *convert_storage(storage, mapping, verbose=verbose),
        verb='Converted', verbose=verbose)


def main(args=None):
    """Entry point for the convert script."""
    parser = get_argparse_parser(
        "Convert binary fields in a ZODB FileStorage so it can be used with "
        "Python 3.""")
    group = parser.add_argument_group('Convert options')
    group.add_argument(
        '-c', '--config', help='Path to conversion config file.')

    run(parser, convert, 'config', 'verbose', args=args)
