.. currentmodule:: tslumd.sender

Sender
======

The :class:`UmdSender` class is used to send tally information as UMD packets
to clients on the network. The remote addresses can be specified on initialization
by giving a Sequence of tuples containing the address and port (:data:`Client`).


Starting and Stopping
---------------------

UmdSender does not begin communication when first created.

Starting and stopping can be done by calling the :meth:`UmdSender.open` and
:meth:`UmdSender.close` methods manually

.. doctest:: UmdSender-open-close

    >>> import asyncio
    >>> from tslumd import UmdSender
    >>> async def run():
    ...     sender = UmdSender(clients=[('127.0.0.1', 65000)])
    ...     await sender.open()
    ...     ...
    ...     await sender.close()
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(run())

or it can be used as an :term:`asynchronous context manager`
in an :keyword:`async with` block

.. doctest:: UmdSender-async-with

    >>> import asyncio
    >>> from tslumd import UmdSender
    >>> async def run():
    ...     sender = UmdSender(clients=[('127.0.0.1', 65000)])
    ...     async with sender:
    ...         ...
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(run())


Sending Tally
-------------

Shortcut Methods
^^^^^^^^^^^^^^^^

In :class:`UmdSender`, there are several shortcut methods defined to create
and update tallies without needing to operate on :class:`~tslumd.tallyobj.Tally`
objects directly.

All of these methods operate using a :term:`TallyKey` to specify the
:ref:`Screen <screen-object>` and :ref:`Tally <tally-object>`

.. doctest:: UmdSender-shortcuts

    >>> from pprint import pprint
    >>> from tslumd import UmdSender, TallyType, TallyColor
    >>> sender = UmdSender(clients=[('127.0.0.1', 65000)])
    >>> for cam_num in range(1, 5):
    ...     sender.set_tally_text((1, cam_num), f'Camera {cam_num}') # Creates a new Tally
    >>> pprint(sender.tallies)
    {(1, 1): <Tally: ((1, 1) - "Camera 1")>,
     (1, 2): <Tally: ((1, 2) - "Camera 2")>,
     (1, 3): <Tally: ((1, 3) - "Camera 3")>,
     (1, 4): <Tally: ((1, 4) - "Camera 4")>}
    >>> sender.set_tally_color((1, 1), TallyType.rh_tally, TallyColor.RED)
    >>> cam1_tally = sender.tallies[(1, 1)]
    >>> pprint(cam1_tally.rh_tally)
    <TallyColor.RED: 1>
    >>> # Rename "Camera 4" so you remember not to take their shot for too long
    >>> sender.set_tally_text((1, 4), 'Handheld')
    >>> pprint(sender.tallies)
    {(1, 1): <Tally: ((1, 1) - "Camera 1")>,
     (1, 2): <Tally: ((1, 2) - "Camera 2")>,
     (1, 3): <Tally: ((1, 3) - "Camera 3")>,
     (1, 4): <Tally: ((1, 4) - "Handheld")>}


Direct Tally Changes
^^^^^^^^^^^^^^^^^^^^

In the example above, all of the changes would be sent automatically if the
UmdSender were open (and the event loop running).
To accomplish this, it listens for property changes on each
:class:`~tslumd.tallyobj.Tally` and :class:`~tslumd.tallyobj.Screen` it contains.
This also means that one can operate on a :class:`~tslumd.tallyobj.Tally`
object directly.

.. doctest:: UmdSender-tally-props

    >>> cam2_tally = sender.tallies[(1, 2)]
    >>> cam2_tally.text = 'Jim'
    >>> pprint(sender.tallies)
    {(1, 1): <Tally: ((1, 1) - "Camera 1")>,
     (1, 2): <Tally: ((1, 2) - "Jim")>,
     (1, 3): <Tally: ((1, 3) - "Camera 3")>,
     (1, 4): <Tally: ((1, 4) - "Handheld")>}
    >>> cam2_tally.txt_tally = TallyColor.GREEN
    >>> pprint(sender.tallies[cam2_tally.id].txt_tally)
    <TallyColor.GREEN: 2>
