import argparse

VERSION_MAGIC_MAP = {
    'Python2': 'FS21',
    'Python3': 'FS30',
}


def set_magic(path, version):
    """Set the magic bytes to declare the Python version compatibility."""
    with open(path, 'r+b') as file:
        file.write(VERSION_MAGIC_MAP[version])


def main(args=None):
    """Entry point for the zodb-py3migrate-magic script."""
    description = "Set the magic bytes of a ZODB database file."
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        'zodb_path', help='Path to Data.fs', metavar='Data.fs')
    parser.add_argument(
        'version', choices=['Python2', 'Python3'],
        help='Python version the database should be readable with.')
    args = parser.parse_args(args)
    set_magic(args.zodb_path, args.version)
