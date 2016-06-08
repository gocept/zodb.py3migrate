==========
Change log
==========

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
