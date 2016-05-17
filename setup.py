# This should be only one line. If it must be multi-line, indent the second
# line onwards to keep the PKG-INFO file format intact.
"""Helper to check if ZODB is Python 3 ready by displaying binary fields that might need conversion to unicode.
"""

from setuptools import setup, find_packages
import glob
import os.path


def project_path(*names):
    return os.path.join(os.path.dirname(__file__), *names)


setup(
    name='zodb.py3migrate',
    version='0.1.dev0',

    install_requires=[
        'ZODB3',
        'setuptools',
    ],

    extras_require={
        'test': [
            'mock',
            'pytest',
            'transaction',
        ],
    },

    entry_points={
        'console_scripts': [
            'zodb-py3migrate = zodb.py3migrate.migrate:main'
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
    long_description='\n\n'.join(open(project_path(name)).read() for name in (
        'README.rst',
        'HACKING.rst',
        'CHANGES.rst',
    )),

    namespace_packages=['zodb'],
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[('',
                 glob.glob(project_path('*.txt')),
                 glob.glob(project_path('*.rst')))],
    zip_safe=False,
)
