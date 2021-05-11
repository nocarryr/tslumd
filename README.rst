tslumd
======

.. image:: https://badge.fury.io/py/tslumd.svg
    :target: https://badge.fury.io/py/tslumd
.. image:: https://img.shields.io/github/workflow/status/nocarryr/tslumd/Python%20package
    :alt: GitHub Workflow Status
.. image:: https://img.shields.io/coveralls/github/nocarryr/tslumd
    :alt: Coveralls

Client and Server for TSLUMD Tally Protocols

Description
-----------

This project is intended to serve only as a library for other applications
wishing to send or receive tally information using the
`UMDv5.0 Protocol`_ by `TSL Products`_.  It is written in pure Python and
utilizes :mod:`asyncio` for communication.

Links
-----

.. list-table::

    * - Project Home
      - https://github.com/nocarryr/tslumd
    * - Documentation
      - https://tslumd.readthedocs.io
    * - PyPI
      - https://pypi.org/project/tslumd


License
-------

Copyright (c) 2021 Matthew Reid <matt@nomadic-recording.com>

tslumd is licensed under the MIT license, please see LICENSE file for details.


.. _UMDv5.0 Protocol: https://tslproducts.com/media/1959/tsl-umd-protocol.pdf
.. _TSL Products: https://tslproducts.com
