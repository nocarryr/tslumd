import enum

__all__ = ('TallyColor', 'TallyType', 'TallyState')

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
