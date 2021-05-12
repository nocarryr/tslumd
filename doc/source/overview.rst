Overview
========

This project uses the `Observer Pattern`_ as its primary means of integration
with other code. This is handled by the `python-dispatch`_ library which provides
methods of `subscribing to events`_ and `property changes`_.

.. currentmodule:: tslumd.tallyobj
.. _tally-object:

Tally Object
------------

The primary object used for sending or receiving tally information is the
:class:`Tally` object.

Indicator Properties
^^^^^^^^^^^^^^^^^^^^

It has properties which hold the
:class:`color <tslumd.common.TallyColor>` for the three :ref:`indicator <indicators>`
values (:attr:`Tally.lh_tally`, :attr:`Tally.txt_tally` and :attr:`Tally.rh_tally`)
among others.

These are :class:`~pydispatch.properties.Property` objects which act as observable
:term:`descriptors <descriptor>`, meaning callbacks can be invoked when their
values change.

The :meth:`Tally.set_color` and :meth:`Tally.get_color` methods can also be used
to get and set the values.


Container Support
^^^^^^^^^^^^^^^^^

The indicator properties can be retrieved and assigned using :ref:`subscription <subscriptions>`
notation (``color = tally[key]``, ``tally[key] = color``). In this form, the
expected key and value types match that of :meth:`Tally.set_color` and the return
values match the description in :meth:`Tally.get_color`.

The example shown in :meth:`Tally.get_color` could be rewritten as:

.. doctest::

    >>> from tslumd import Tally
    >>> tally = Tally(0)
    >>> tally['rh_tally']
    <TallyColor.OFF: 0>
    >>> tally['rh_tally'] = 'red'
    >>> tally['rh_tally']
    <TallyColor.RED: 1>
    >>> tally['txt_tally'] = 'red'
    >>> tally['rh_tally|txt_tally']
    <TallyColor.RED: 1>
    >>> tally['all']
    <TallyColor.RED: 1>
    >>> tally['lh_tally'] = 'green'
    >>> tally['lh_tally']
    <TallyColor.GREEN: 2>
    >>> tally['all']
    <TallyColor.AMBER: 3>


Events
^^^^^^

When receiving, the Tally object will emit an
:event:`Tally.on_update` event on any change of state with the
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
    >>> tally = Tally(0, text='foo')
    >>> tally
    <Tally: (0 - "foo")>
    >>> # bind `my_callback` to the `text` property
    >>> tally.bind(text=my_callback)
    >>> # does not reach the callback
    >>> tally.rh_tally = TallyColor.RED
    >>> # but this does
    >>> tally.text = 'bar'
    my_callback: <Tally: (0 - "bar")>.text = bar


.. _screen-object:

Screen Object
-------------

:class:`Tally` objects should never be created directly (as in
the examples above). They are instead created by the :class:`Screen` object
and stored in its :attr:`Screen.tallies` dictionary, using the Tally's
:attr:`index <Tally.index>` as the key.

When receiving, they are created automatically when necessary (when data is
received). The :event:`Screen.on_tally_added` event can be used
to listen for new Tally objects.

Screens also propagate the "on_update" event for all of their Tally objects and
emit their own :event:`Screen.on_tally_update` event.
This can reduce the amount of code and callbacks when handling multiple tallies.

When sending, Tally objects are created by using either the
:meth:`Screen.add_tally` and :meth:`Screen.get_or_create_tally` methods.


Glossary
--------

.. glossary::

    TallyKey
        Combination of :attr:`Screen.index` and :attr:`Tally.index` used to
        uniquely identify a single tally (or :term:`Display`) within a single
        :term:`Screen`.

        :data:`~tslumd.common.TallyKey` is a 2-tuple of integers and is available
        as the :attr:`Tally.id`.

    TallyType
        :class:`~tslumd.common.TallyType` is an enum used to aid in mapping
        the three Tally :ref:`Tally Indicators <indicators>` to the
        :attr:`Tally.lh_tally`, :attr:`Tally.txt_tally` and
        :attr:`Tally.rh_tally` attributes

    TallyColor
        :class:`~tslumd.common.TallyColor` is an enum defining the four
        allowable colors for an :ref:`indicator <indicators>` (including "off")


.. _Observer Pattern: https://en.wikipedia.org/wiki/Observer_pattern
.. _python-dispatch: https://pypi.org/project/python-dispatch/
.. _subscribing to events: https://python-dispatch.readthedocs.io/en/latest/dispatcher.html#usage
.. _property changes: https://python-dispatch.readthedocs.io/en/latest/properties.html
