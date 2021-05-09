Protocol Information
====================

Overview
--------

The UMD protocols, developed by `TSL Products`_ are used throughout the
broadcast video industry to control tally indicators in Multiviewer products and
Under-Monitor Displays. The documentation for all versions can be found here:
https://tslproducts.com/media/1959/tsl-umd-protocol.pdf


This library focuses on the most recent version: UMDv5


Physical Layer
--------------

Packets are sent via UDP with a maximum length of 2048 bytes. There is an
option to frame packets using TCP, but this is not currently implemented.


Structure
---------

Screen
^^^^^^

The primary entity within a packet is a "Screen", which can be thought of as
addressing a specific device (such as a large Multiviewer). Screens are
addressed by their index, which can be from 0 to 65534.

Display
^^^^^^^

Within each Screen are "Displays" which can be thought of as a single monitor
window of a Multiviewer. Displays are also addressed by index from 0 65534.

A message packet for a single Screen can contain information for multiple
Displays with the only limitation being the size of the packet itself (2048 bytes).


Indicators
^^^^^^^^^^

For each Display there are two main tally indicators either above or below the
monitor window; one for the "left-hand" side (called :term:`lh_tally`) and one
for the "right-hand" side (called :term:`rh_tally`).
There is also typically a label to identify the source of the monitor.
The label's text can be set as well as its color (:term:`txt_tally`).

These three items can be set individually to specific colors to indicate status
choosing from:

* Off
* Red
* Green
* Amber (yellow)



Glossary
--------

.. glossary::

    Packet
        A single message of up to 2048 bytes containing tally information for
        a single :term:`Screen`

    Screen
        Conceptually, a collection of :term:`Displays <Display>`. Physically,
        a screen is typically a Multiviewer (a large monitor showing many
        smaller, windowed displays).

        Addressed by an index from 0 to 65534

    Display
        A single tally display within a :term:`Screen`. A display can show text
        information and can have up to three
        tally indicators: :term:`lh_tally`, :term:`rh_tally` and :term:`txt_tally`.

        Addressed by an index from 0 to 65534

    lh_tally
        A tally indicator on the "left-hand side" of a :term:`Display` which can
        be illuminated in red, green or amber (yellow)

    rh_tally
        A tally indicator on the "right-hand side" of a :term:`Display` which can
        be illuminated in red, green or amber (yellow)

    txt_tally
        Typically used to control the text color for a :term:`Display` which can
        be one of red, green or amber (yellow)

    Broadcast Screen
        A reserved :term:`Screen` index of 65535 (``0xffff``) that is meant to
        apply to all screens, regardless of their index

    Broadcast Display
        A reserved :term:`Display` index of 65535 (``0xffff``) that is meant to
        apply to all displays within a screen, regardless of their index



.. _TSL Products: https://tslproducts.com
