import enum

__all__ = ('TallyColor', 'TallyType', 'TallyState', 'MessageType')

class TallyColor(enum.IntEnum):
    """Color enum for tally indicators"""
    OFF = 0   #: Off
    RED = 1   #: Red
    GREEN = 2 #: Green
    AMBER = 3 #: Amber

class TallyType(enum.Enum):
    """Enum for the three tally display types in the UMD protocol
    """
    no_tally = 0  #: No-op
    rh_tally = 1  #: "Right-hand" tally
    txt_tally = 2 #: "Text" tally
    lh_tally = 3  #: "Left-hand" tally

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
