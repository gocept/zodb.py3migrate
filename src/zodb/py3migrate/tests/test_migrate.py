# encoding: utf-8
from ..testing import Example
from ..migrate import print_results, find_obj_with_binary_content, run
from ..migrate import get_argparse_parser
import ZODB.POSException
import mock
import pytest
import transaction
import zodb.py3migrate.migrate


@pytest.fixture('module')
def parser():
    """Get a basic argument parser."""
    return get_argparse_parser('desc')


def echo(*args):
    """Echo function `args`."""
    return args


def raise_error(*args):
    """Callable raising a RuntimeError."""
    raise RuntimeError()


def test_migrate__run__1(parser):
    """It calls the callable with a filestorage and the requested arguments."""
    with mock.patch('ZODB.FileStorage.FileStorage') as filestorage:
        result = run(parser, echo, 'verbose', args=['path/to/Data.fs'])
        filestorage.assert_called_once_with(
            'path/to/Data.fs', blob_dir=None)
        assert (filestorage(), False) == result


def test_migrate__run__1_5(parser):
    """It opens `FileStorage` with blob_dir if path was given."""
    with mock.patch('ZODB.FileStorage.FileStorage') as filestorage:
        run(parser, echo,
            args=['path/to/Data.fs', '--blob-dir', 'path/to/blob_dir'])
        filestorage.assert_called_once_with(
            'path/to/Data.fs', blob_dir='path/to/blob_dir')


def test_migrate__run__2(parser):
    """It raises an occurred exception.."""
    with mock.patch('ZODB.FileStorage.FileStorage'):
        with pytest.raises(RuntimeError):
            run(parser, raise_error, args=['path/to/Data.fs'])


def test_migrate__run__3(parser):
    """It drops into pdb if there was an exception and `--pdb` is set."""
    with mock.patch('ZODB.FileStorage.FileStorage'):
        with mock.patch('pdb.post_mortem') as post_mortem:
            with pytest.raises(RuntimeError):
                run(parser, raise_error, args=['path/to/Data.fs', '--pdb'])
            post_mortem.assert_called_once()


def test_migrate__find_obj_with_binary_content__1(zodb_storage, caplog):
    """It logs progress every `watermark` objects."""
    list(find_obj_with_binary_content(zodb_storage, {}, watermark=1))
    assert (
        '1 of about 1 objects analyzed.' == caplog.records()[-2].getMessage())


def test_migrate__find_obj_with_binary_content__2(zodb_storage, zodb_root):
    """It starts the search at a defined OID."""
    zodb_root['obj'] = Example(
        binary=b'bär1',
        reference=Example(binary=b'bär2'))
    transaction.commit()

    # By default start at the root object, we added two objects with binary
    # data:
    assert 2 == len(list(find_obj_with_binary_content(zodb_storage, {})))

    # By request start at requested OID:
    result = list(find_obj_with_binary_content(
        zodb_storage, {}, start_at='0x02'))
    assert 1 == len(result)
    assert b'bär2' == result[0][3]


def test_migrate__find_obj_with_binary_content__3(zodb_storage, zodb_root):
    """It stops the search after the given limit."""
    zodb_root['obj'] = Example(
        binary=b'bär1',
        reference=Example(binary=b'bär2'))
    transaction.commit()

    # By default there is no limit:
    assert 2 == len(list(find_obj_with_binary_content(zodb_storage, {})))

    # By request search is stopped after the limit is reached:
    result = list(find_obj_with_binary_content(
        zodb_storage, {}, limit=2))
    assert 1 == len(result)
    assert b'bär1' == result[0][3]


def test_migrate__wake_object__1(caplog):
    """It logs POSKeyErrors.

    They occur e. g. if the file for a blob is not on the hard disk.
    """
    class Sleepy(object):

        def __getattr__(self, key):
            raise ZODB.POSException.POSKeyError('\x00')

    zodb.py3migrate.migrate.wake_object(Sleepy())
    rec = caplog.records()[-1]
    assert "POSKeyError: '\\x00'" == rec.getMessage()


def test_migrate__print_results__1(capsys):
    """It prints only the results if `verbose` is `False`."""
    print_results(
        {'foo.Bar.baz': 3}, {'asdf.Qwe': 2}, verb='Found', verbose=False)
    out, err = capsys.readouterr()
    assert '''\
Found 1 binary fields: (number of occurrences)
foo.Bar.baz (3)
''' == out


def test_migrate__print_results__2(capsys):
    """It prints the errors, too if `verbose` is `True`."""
    print_results(
        {'foo.Bar.baz': 3}, {'asdf.Qwe': 2}, verb='Converted', verbose=True)
    out, err = capsys.readouterr()
    assert '''\
Found 1 classes whose objects do not have __dict__: (number of occurrences)
asdf.Qwe (2)

# ########################################################### #

Converted 1 binary fields: (number of occurrences)
foo.Bar.baz (3)
''' == out
