# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""Helper to check if ZODB is Python 3 ready by displaying binary fields that might need conversion to unicode.
"""  # noqa

from setuptools import setup, find_packages
import glob


setup(
    name='zodb.py3migrate',
    version='0.5',

    install_requires=[
        'ZODB3',
        'setuptools',
        'zodbpickle',
    ],

    extras_require={
        'test': [
            'mock',
            'pytest',
            'pytest-capturelog',
            'transaction',
            'Products.PythonScripts',
        ],
    },

    entry_points={
        'console_scripts': [
            'zodb-py3migrate-analyze = zodb.py3migrate.analyze:main',
            'zodb-py3migrate-convert = zodb.py3migrate.convert:main',
            'zodb-py3migrate-magic = zodb.py3migrate.magic:main',
        ],
    },

    author='gocept <mail@gocept.com>',
    author_email='mail@gocept.com',
    license='MIT License',
    url='https://bitbucket.org/gocept/zodb.py3migrate/',

    keywords='zodb python3',
    classifiers="""\
License :: OSI Approved
License :: OSI Approved :: MIT License
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: Implementation :: CPython
"""[:-1].split('\n'),
    description=__doc__.strip(),
    long_description='\n\n'.join(open(name).read() for name in (
        'README.rst',
        'HACKING.rst',
        'CHANGES.rst',
    )),

    namespace_packages=['zodb'],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[('', glob.glob('*.txt')),
                ('', glob.glob('*.rst'))],
    zip_safe=False,
)
