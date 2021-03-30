import asyncio
import dataclasses
from dataclasses import dataclass, field
import enum
import struct
from typing import List, Tuple, Dict

from tslumd import TallyColor, Tally

__all__ = ('Display', 'Message')

class Flags(enum.IntFlag):
    """Message flags
    """
    NO_FLAGS = 0 #: No flags set
    UTF16 = 1
    """Indicates text formatted as ``UTF-16LE`` if set, otherwise ``UTF-8``"""

    SCONTROL = 2
    """Indicates the message contains ``SCONTROL`` data if set, otherwise ``DMESG``
    """

@dataclass
class Display:
    """A single tally "display"
    """
    index: int #: The display index
    rh_tally: TallyColor = TallyColor.OFF #: Right hand tally indicator
    txt_tally: TallyColor = TallyColor.OFF #: Text tally indicator
    lh_tally: TallyColor = TallyColor.OFF #: Left hand tally indicator
    brightness: int = 3 #: Display brightness (from 0 to 3)
    text: str = '' #: Text to display
    @classmethod
    def from_dmsg(cls, flags: Flags, dmsg: bytes) -> Tuple['Display', bytes]:
        """Construct an instance from a ``DMSG`` portion of received message.

        Any remaining message data after the relevant ``DMSG`` is returned along
        with the instance.
        """
        hdr = struct.unpack('<2H', dmsg[:4])
        dmsg = dmsg[4:]
        ctrl = hdr[1]
        kw = dict(
            index=hdr[0],
            rh_tally=TallyColor(ctrl & 0b11),
            txt_tally=TallyColor(ctrl >> 2 & 0b11),
            lh_tally=TallyColor(ctrl >> 4 & 0b11),
            brightness=ctrl >> 6 & 0b11,
        )
        is_control_data = ctrl & 0x8000 == 0x8000
        if is_control_data:
            raise ValueError('Control data undefined for UMDv5.0')
        else:
            txt_byte_len = struct.unpack('<H', dmsg[:2])[0]
            dmsg = dmsg[2:]
            txt_bytes = dmsg[:txt_byte_len]
            dmsg = dmsg[txt_byte_len:]
            if Flags.UTF16 in flags:
                txt = txt_bytes.decode('UTF-16le')
            else:
                if b'\0' in txt_bytes:
                    txt_bytes = txt_bytes.split(b'\0')[0]
                txt = txt_bytes.decode('UTF-8')
            kw['text'] = txt
        return cls(**kw), dmsg

    def to_dmsg(self, flags: Flags) -> bytes:
        """Build ``dmsg`` bytes to be included in a message
        (called from :meth:`Message.build_message`)
        """
        ctrl = self.rh_tally & 0b11
        ctrl += (self.txt_tally & 0b11) << 2
        ctrl += (self.lh_tally & 0b11) << 4
        ctrl += (self.brightness & 0b11) << 6
        if Flags.UTF16 in flags:
            txt_bytes = bytes(self.text, 'UTF16-le')
        else:
            txt_bytes = bytes(self.text, 'UTF-8')
        txt_byte_len = len(txt_bytes)
        data = bytearray(struct.pack('<3H', self.index, ctrl, txt_byte_len))
        data.extend(txt_bytes)
        return data

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_tally(cls, tally: Tally) -> 'Display':
        """Create a :class:`Display` from the given :class:`~.Tally`
        """
        kw = tally.to_dict()
        return cls(**kw)

    def __eq__(self, other):
        if not isinstance(other, (Display, Tally)):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        if not isinstance(other, (Display, Tally)):
            return NotImplemented
        return self.to_dict() != other.to_dict()

@dataclass
class Message:
    """A single UMDv5 message packet
    """
    version: int = 0 #: Protocol minor version
    flags: int = Flags.NO_FLAGS #: The message :class:`Flags` field
    screen: int = 0 #: Screen index
    displays: List[Display] = field(default_factory=list)
    """A list of :class:`Display` instances"""

    scontrol: bytes = b''
    """SCONTROL data (if present).  Not currently implemented"""

    def __post_init__(self):
        if not isinstance(self.flags, Flags):
            self.flags = Flags(self.flags)

    @classmethod
    def parse(cls, msg: bytes) -> Tuple['Message', bytes]:
        """Parse incoming message data to create a :class:`Message` instance.

        Any remaining message data after parsing is returned along with the instance.
        """
        data = struct.unpack('<HBBH', msg[:6])
        byte_count, version, flags, screen = data
        kw = dict(
            version=version,
            flags=Flags(flags),
            screen=screen,
        )
        msg = msg[2:]
        remaining = msg[byte_count:]
        msg = msg[4:byte_count]
        obj = cls(**kw)
        if Flags.SCONTROL in obj.flags:
            obj.scontrol = msg
            return obj, remaining
        while len(msg):
            disp, msg = Display.from_dmsg(obj.flags, msg)
            obj.displays.append(disp)
        return obj, remaining

    def build_message(self) -> bytes:
        """Build a message packet from data in this instance
        """
        if Flags.SCONTROL in self.flags:
            payload = bytearray(self.scontrol)
        else:
            payload = bytearray()
            for display in self.displays:
                payload.extend(display.to_dmsg(self.flags))
        payload_byte_count = len(payload)
        fmt = f'<HBBH{payload_byte_count}B'
        pbc = struct.calcsize(fmt) - 2
        data = bytearray(struct.pack('<HBBH', pbc, self.version, self.flags, self.screen))
        data.extend(payload)
        return bytes(data)
