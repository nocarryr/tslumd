tslumd
======

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
    :target: https://docs.astral.sh/uv/
    :alt: uv
.. image:: https://img.shields.io/github/actions/workflow/status/nocarryr/tslumd/python-package.yml
    :alt: GitHub Workflow Status
    :target: https://github.com/nocarryr/tslumd/actions
.. image:: https://img.shields.io/endpoint?url=https://codspeed.io/badge.json
    :target: https://codspeed.io/nocarryr/tslumd
    :alt: CodSpeed
.. image:: https://img.shields.io/pypi/v/tslumd.svg
    :target: https://pypi.org/project/tslumd/
    :alt: PyPI version
.. image:: https://img.shields.io/pypi/l/tslumd.svg
    :target: https://pypi.org/project/tslumd/
    :alt: PyPI license
.. image:: https://img.shields.io/pypi/pyversions/tslumd.svg
    :target: https://pypi.org/project/tslumd/
    :alt: PyPI Python versions
.. image:: https://img.shields.io/pypi/dw/tslumd.svg
    :target: https://pypi.org/project/tslumd/
    :alt: PyPI download week

Client and Server for TSLUMD Tally Protocols

Description
-----------

This project is intended to serve only as a library for other applications
wishing to send or receive tally information using the
`UMDv5.0 Protocol`_ by `TSL Products`_.  It is written in pure Python and
utilizes `asyncio <https://docs.python.org/3.8/library/asyncio.html>`_ for
communication.

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
