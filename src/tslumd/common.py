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

    def __str__(self):
        return self.name

    def __format__(self, format_spec):
        if format_spec == '':
            return str(self)
        return super().__format__(format_spec)

class TallyType(enum.IntFlag):
    """Enum for the three tally display types in the UMD protocol

    Since this is an :class:`~enum.IntFlag`, its members can be combined using
    bitwise operators. The members can then be iterated over to retrieve the
    individual "concrete" values of :attr:`rh_tally`, :attr:`txt_tally`
    and :attr:`lh_tally`

    >>> from tslumd import TallyType
    >>> list(TallyType.rh_tally)
    [<TallyType.rh_tally: 1>]
    >>> list(TallyType.rh_tally | TallyType.txt_tally)
    [<TallyType.rh_tally: 1>, <TallyType.txt_tally: 2>]
    >>> list(TallyType.all_tally)
    [<TallyType.rh_tally: 1>, <TallyType.txt_tally: 2>, <TallyType.lh_tally: 4>]

    .. versionchanged:: 0.0.4
        Added support for bitwise operators and member iteration
    """
    no_tally = 0  #: No-op
    rh_tally = 1  #: :term:`Right-hand tally <rh_tally>`
    txt_tally = 2 #: :term:`Text tally <txt_tally>`
    lh_tally = 4  #: :term:`Left-hand tally <lh_tally>`
    all_tally = rh_tally | txt_tally | lh_tally
    """Combination of all tally types

    .. versionadded:: 0.0.4
    """

    @classmethod
    def all(cls) -> Iterable['TallyType']:
        """Iterate over all members, excluding :attr:`no_tally` and :attr:`all_tally`

        .. versionadded:: 0.0.4
        """
        for ttype in cls:
            if ttype != TallyType.no_tally and ttype != TallyType.all_tally:
                yield ttype

    def __iter__(self):
        for ttype in self.all():
            if ttype in self:
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
