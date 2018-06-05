==========
Change log
==========

0.6 (2018-06-05)
================

- Update requirements to ``ZODB >= 4`` as with an older version the migration
  cannot be done successfully.
  (`#13 <https://github.com/gocept/zodb.py3migrate/issues/13>`_)


0.5 (2017-01-17)
================

- Release as wheel and include all files in release.

- Ensure compatibility with ``setuptools >= 30``.


0.4 (2016-10-29)
================

- Fix brown bag release.


0.3 (2016-10-29)
================

- Fixes for issues #4 and #5: Converted ZODB ist now actually saved,
  using additional subtransactions improves the memory footprint.


0.2 (2016-06-08)
================

- Split up the two functions previously united in the script
  ``bin/zodb-py3migrate`` into ``bin/zodb-py3migrate-analyze`` resp.
  ``bin/zodb-py3migrate-convert``.

- Add new options to the analysis script:

  - ``--start`` to start the analysis with a predefined OID.

  - ``--limit`` to stop the analysis after a certain amount of seen OIDs.

0.1 (2016-05-19)
================

* Initial release.
