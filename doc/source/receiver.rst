Receiver
========

The :class:`~tslumd.receiver.UmdReceiver` class is used to listen for and process
UMD :term:`packets <Packet>` from the network. It will create
:ref:`Screens <screen-object>` and :ref:`Tallies <tally-object>` as information
for them arrives and store the instances in its
:attr:`~tslumd.receiver.UmdReceiver.screens` and :attr:`~tslumd.receiver.UmdReceiver.tallies`
dictionaries.

The :event:`~tslumd.receiver.UmdReceiver.on_screen_added` event is used to listen
for new Screen objects and the :event:`~tslumd.receiver.UmdReceiver.on_tally_added`
is used to listen for new Tally objects (which will be fired for all new Tallies
across all Screens).

Like Screens, the Receiver will propagate the "on_update" event of each Screen
and emit its own :event:`~tslumd.receiver.UmdReceiver.on_tally_updated` event.
Because of this, one may only need to subscribe to a single event to handle
all Tally changes across all Screens.

.. todo::
    The UmdReceiver.on_tally_updated and Screen.on_tally_update event names
    are inconsistent. One of the two needs to be decided on.
