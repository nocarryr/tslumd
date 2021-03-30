"""Implementation of the `UMDv5.0 Protocol`_ by `TSL Products`_ for tally
and other production display/control purposes.

.. _UMDv5.0 Protocol: https://tslproducts.com/media/1959/tsl-umd-protocol.pdf
.. _TSL Products: https://tslproducts.com
"""
try:
    from loguru import logger
except ImportError: # pragma: no cover
    import logging
    logging.basicConfig(format='%(asctime)s\t%(levelname)s\t%(message)s', level=logging.DEBUG)
    logger = logging.getLogger(__name__)
from .common import *
from .tallyobj import *
from .messages import *
from .receiver import *
from .sender import *
