Overview
========

This project uses the `Observer Pattern`_ as its primary means of integration
with other code. This is handled by the `python-dispatch`_ library which provides
methods of `subscribing to events`_ and `property changes`_.

.. _tally-object:

Tally Object
------------

The primary object used for sending or receiving tally information is the
:class:`~tslumd.tallyobj.Tally` object.

When receiving, the Tally object will emit an
:event:`~tslumd.tallyobj.Tally.on_update` event on any change of state with the
Tally instance as the first argument and the property names as the second:

.. doctest::

    >>> from tslumd import Tally, TallyColor
    >>> def my_callback(tally: Tally, props_changed, **kwargs):
    ...     for name in props_changed:
    ...         value = getattr(tally, name)
    ...         print(f'my_callback: {tally!r}.{name} = {value}')
    >>> tally = Tally(0)
    >>> # bind `my_callback` to the `on_update` event
    >>> tally.bind(on_update=my_callback)
    >>> # rh_tally is initialized to "OFF"
    >>> tally.rh_tally
    <TallyColor.OFF: 0>
    >>> tally.rh_tally = TallyColor.RED
    my_callback: <Tally: (0 - "")>.rh_tally = RED


One can also subscribe to any of the properties individually:

.. doctest::

    >>> from tslumd import Tally, TallyColor
    >>> def my_callback(tally: Tally, value, **kwargs):
    ...     prop = kwargs['property']
    ...     print(f'my_callback: {tally!r}.{prop.name} = {value}')
    >>> tally = Tally(0)
    >>> # bind `my_callback` to the `text` property
    >>> tally.bind(text=my_callback)
    >>> # does not reach the callback
    >>> tally.rh_tally = TallyColor.RED
    >>> # but this does
    >>> tally.text = 'foo'
    my_callback: <Tally: (0 - "")>.text = foo


.. _screen-object:

Screen Object
-------------

:class:`~tslumd.tallyobj.Tally` objects should never be created directly (as in
the examples above). They are instead created by the
:class:`~tslumd.tallyobj.Screen` object and stored in its
:attr:`~tslumd.tallyobj.Screen.tallies` dictionary, using the Tally's
:attr:`index <tslumd.tallyobj.Tally.index>` as the key.

When receiving, they are created automatically when necessary (when data is
received). The :event:`~tslumd.tallyobj.Screen.on_tally_added` event can be used
to listen for new Tally objects.

Screens also propagate the "on_update" event for all of their Tally objects and
emit their own :event:`~tslumd.tallyobj.Screen.on_tally_update` event.
This can reduce the amount of code and callbacks when handling multiple tallies.

When sending, Tally objects are created by using either the
:meth:`~tslumd.tallyobj.Screen.add_tally` and
:meth:`~tslumd.tallyobj.Screen.get_or_create_tally` methods.

.. _Observer Pattern: https://en.wikipedia.org/wiki/Observer_pattern
.. _python-dispatch: https://pypi.org/project/python-dispatch/
.. _subscribing to events: https://python-dispatch.readthedocs.io/en/latest/dispatcher.html#usage
.. _property changes: https://python-dispatch.readthedocs.io/en/latest/properties.html
