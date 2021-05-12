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

    @staticmethod
    def from_str(s: str) -> 'TallyColor':
        """Return the member matching the given name (case-insensitive)

        >>> TallyColor.from_str('RED')
        <TallyColor.RED: 1>
        >>> TallyColor.from_str('green')
        <TallyColor.GREEN: 2>
        >>> TallyColor.from_str('Amber')
        <TallyColor.AMBER: 3>

        .. versionadded:: 0.0.5
        """
        return getattr(TallyColor, s.upper())

    def to_str(self) -> str:
        """The member name as a string

        >>> TallyColor.RED.to_str()
        'RED'
        >>> TallyColor.GREEN.to_str()
        'GREEN'
        >>> TallyColor.AMBER.to_str()
        'AMBER'
        >>> (TallyColor.RED | TallyColor.GREEN).to_str()
        'AMBER'

        .. versionadded:: 0.0.5
        """
        return self.name

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

    @property
    def is_iterable(self) -> bool:
        """Returns ``True`` if this is a combination of multiple members

        (meaning it must be iterated over)

        .. versionadded:: 0.0.5
        """
        if self == TallyType.all_tally:
            return True
        return self.name is None

    @classmethod
    def all(cls) -> Iterable['TallyType']:
        """Iterate over all members, excluding :attr:`no_tally` and :attr:`all_tally`

        .. versionadded:: 0.0.4
        """
        for ttype in cls:
            if ttype != TallyType.no_tally and ttype != TallyType.all_tally:
                yield ttype

    @staticmethod
    def from_str(s: str) -> 'TallyType':
        """Create an instance from a string of member name(s)

        The string can be a single member or multiple member names separated by
        a "|". For convenience, the names may be shortened by omitting the
        ``"_tally"`` portion from the end ("rh" == "rh_tally", etc)

        >>> TallyType.from_str('rh_tally')
        <TallyType.rh_tally: 1>
        >>> TallyType.from_str('rh|txt_tally')
        <TallyType.txt_tally|rh_tally: 3>
        >>> TallyType.from_str('rh|txt|lh')
        <TallyType.all_tally: 7>
        >>> TallyType.from_str('all')
        <TallyType.all_tally: 7>

        .. versionadded:: 0.0.5
        """
        if '|' in s:
            result = TallyType.no_tally
            for name in s.split('|'):
                result |= TallyType.from_str(name)
            return result
        s = s.lower()
        if not s.endswith('_tally'):
            s = f'{s}_tally'
        return getattr(TallyType, s)

    def to_str(self) -> str:
        """Create a string representation suitable for use in :meth:`from_str`

        >>> tt = TallyType.rh_tally
        >>> tt.to_str()
        'rh_tally'
        >>> tt |= TallyType.txt_tally
        >>> tt.to_str()
        'rh_tally|txt_tally'
        >>> tt |= TallyType.lh_tally
        >>> tt.to_str()
        'all_tally'

        .. versionadded:: 0.0.5
        """
        if self.name is None:
            return '|'.join((obj.name for obj in self))
        return self.name

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
