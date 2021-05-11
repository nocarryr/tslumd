.. currentmodule:: tslumd.receiver

Receiver
========

The :class:`~UmdReceiver` class is used to listen for and process
UMD :term:`packets <Packet>` from the network (typically from devices such as
video switchers).


Starting and Stopping
---------------------

The receiver does not begin communication when first created.

Starting and stopping can be done by calling the :meth:`UmdReceiver.open` and
:meth:`UmdReceiver.close` methods manually

.. doctest:: UmdReceiver-open-close

    >>> import asyncio
    >>> from tslumd import UmdReceiver
    >>> async def run():
    ...     receiver = UmdReceiver()
    ...     await receiver.open()
    ...     ...
    ...     await receiver.close()
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(run())

or it can be used as an :term:`asynchronous context manager`
in an :keyword:`async with` block

.. doctest:: UmdReceiver-async-with

    >>> import asyncio
    >>> from tslumd import UmdReceiver
    >>> async def run():
    ...     receiver = UmdReceiver()
    ...     async with receiver:
    ...         ...
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(run())


Object Access
-------------

While running, it will create :ref:`Screens <screen-object>` and
:ref:`Tallies <tally-object>` as information for them arrives. Screens are stored
in the :attr:`~UmdReceiver.screens` dictionary using their
:attr:`~tslumd.tallyobj.Screen.index` as keys.

While each Screen object contains its own Tally instances, the Receiver stores
all Tally objects from all Screens in its own
:attr:`~UmdReceiver.tallies` dictionary
using a :data:`~tslumd.common.TallyKey`, which is a combination of the Screen
index and Tally index. (also used as the :attr:`Tally.id <tslumd.tallyobj.Tally.id>`).


Events
------

The :event:`UmdReceiver.on_screen_added` event is used to listen for new
Screen objects and the :event:`UmdReceiver.on_tally_added` is used to listen
for new Tally objects (which will be fired for all new Tallies across all Screens).

Like Screens, the Receiver will propagate the
:event:`~tslumd.tallyobj.Screen.on_tally_update` event of each Screen and emit
its own :event:`UmdReceiver.on_tally_updated` event.
Because of this, one may only need to subscribe to a single event to handle
all Tally changes across all Screens


Example
-------

In following example, assume a device is sending tally information for four
tallies labeled ``"Camera 1", "Camera 2", "Camera 3", "Camera 4"``.
They are indexed 1 through 4 and their screen index is 1.

.. doctest:: UmdReceiver-events

    >>> import asyncio
    >>> from tslumd import UmdReceiver
    >>> def screen_added(screen, **kwargs):
    ...     print(f'screen_added: {screen!r}')
    >>> def tally_added(tally, **kwargs):
    ...     print(f'tally_added: {tally!r}')
    >>> def tally_updated(tally, props_changed, **kwargs):
    ...     for name in props_changed:
    ...         value = getattr(tally, name)
    ...         print(f'tally_updated: {tally!r}.{name} = {value}')
    >>> loop = asyncio.get_event_loop()
    >>> receiver = UmdReceiver()
    >>> receiver.bind(
    ...     on_screen_added=screen_added,
    ...     on_tally_added=tally_added,
    ...     on_tally_updated=tally_updated,
    ... )
    >>> async def run():
    ...     async with receiver:
    ...         await asyncio.sleep(2)
    >>> loop.run_until_complete(run())
    screen_added: <Screen: 1>
    tally_added: <Tally: ((1, 1) - "Camera 1")>
    tally_added: <Tally: ((1, 2) - "Camera 2")>
    tally_added: <Tally: ((1, 3) - "Camera 3")>
    tally_added: <Tally: ((1, 4) - "Camera 4")>
    tally_updated: <Tally: ((1, 1) - "Camera 1")>.rh_tally = RED
    tally_updated: <Tally: ((1, 2) - "Camera 2")>.rh_tally = GREEN

When the receiver first opens, the :event:`~UmdReceiver.on_screen_added` and
:event:`~UmdReceiver.on_tally_added` events are triggered once they are detected.

After a second or so, the tally for "Camera 1" is set to red and "Camera 2" is
set to green. Both of these trigger the
:event:`~UmdReceiver.on_tally_updated` event as shown above.


.. todo::
    The UmdReceiver.on_tally_updated and Screen.on_tally_update event names
    are inconsistent. One of the two needs to be decided on.
