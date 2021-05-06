import enum
from typing import Tuple, Iterable

__all__ = ('TallyColor', 'TallyType', 'TallyState', 'MessageType', 'TallyKey')

class TallyColor(enum.IntFlag):
    """Color enum for tally indicators

    Since this is an :class:`~enum.IntFlag`, its members can be combined using
    bitwise operators, making :attr:`AMBER` a combination of
    :attr:`RED` and :attr:`GREEN`

    This allows merging one color with another

    >>> from tslumd import TallyColor
    >>> TallyColor.RED
    <TallyColor.RED: 1>
    >>> TallyColor.GREEN
    <TallyColor.GREEN: 2>
    >>> TallyColor.AMBER
    <TallyColor.AMBER: 3>
    >>> TallyColor.RED | TallyColor.GREEN
    <TallyColor.AMBER: 3>


    .. versionchanged:: 0.0.4
        Bitwise operators
    """
    OFF = 0             #: Off
    RED = 1             #: Red
    GREEN = 2           #: Green
    AMBER = RED | GREEN #: Amber

class TallyType(enum.Enum):
    """Enum for the three tally display types in the UMD protocol
    """
    no_tally = 0  #: No-op
    rh_tally = 1  #: "Right-hand" tally
    txt_tally = 2 #: "Text" tally
    lh_tally = 3  #: "Left-hand" tally

    @classmethod
    def all(cls) -> Iterable['TallyType']:
        """Iterate over all members, excluding :attr:`no_tally`

        .. versionadded:: 0.0.4
        """
        for ttype in cls:
            if ttype != TallyType.no_tally:
                yield ttype

class TallyState(enum.IntFlag):
    OFF = 0     #: Off
    PREVIEW = 1 #: Preview
    PROGRAM = 2 #: Program

class MessageType(enum.Enum):
    """Message type

    .. versionadded:: 0.0.2
    """
    _unset = 0
    display = 1 #: A message containing tally display information
    control = 2 #: A message containing control data

TallyKey = Tuple[int, int]
"""A tuple of (:attr:`screen_index <.Screen.index>`,
:attr:`tally_index <.Tally.index>`) to uniquely identify a single :class:`.Tally`
within its :class:`.Screen`
"""
