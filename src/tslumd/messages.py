import asyncio
import dataclasses
from dataclasses import dataclass, field
import enum
import struct
from typing import List, Tuple, Dict

from tslumd import TallyColor, Tally

__all__ = ('MessageType', 'Display', 'Message')

class Flags(enum.IntFlag):
    """Message flags
    """
    NO_FLAGS = 0 #: No flags set
    UTF16 = 1
    """Indicates text formatted as ``UTF-16LE`` if set, otherwise ``UTF-8``"""

    SCONTROL = 2
    """Indicates the message contains ``SCONTROL`` data if set, otherwise ``DMESG``
    """

class MessageType(enum.Enum):
    """Message type
    """
    _unset = 0
    display = 1 #: A message containing tally display information
    control = 2 #: A message containing control data

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
    control: bytes = b''
    """Control data (if :attr:`type` is :attr:`~MessageType.control`)"""

    type: MessageType = MessageType.display
    """The message type. One of :attr:`~MessageType.display` or
    :attr:`~MessageType.control`.

    * For :attr:`~MessageType.display` (the default), the message contains
      :attr:`text` information and the :attr:`control` field must be empty.
    * For :attr:`~MessageType.control`, the message contains :attr:`control`
      data and the :attr:`text` field must be empty
    """

    def __post_init__(self):
        if len(self.control):
            self.type = MessageType.control
        if self.type == MessageType.control and len(self.text):
            raise ValueError('Control message cannot contain text')

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
            ctrl, dmsg = cls._unpack_control_data(dmsg)
            kw['control'] = ctrl
            kw['type'] = MessageType.control
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

    @staticmethod
    def _unpack_control_data(data: bytes) -> bytes:
        """Unpack control data (if control bit 15 is set)

        Arguments:
            data: The portion of the ``dmsg`` at the start of the
                "Control Data" field

        Returns:
            bytes: remaining
                The remaining message data after the control data field

        Note:
            This is undefined as of UMDv5.0 and its implementation is
            the author's "best guess" based off of other areas of the protocol

        :meta public:
        """
        length = struct.unpack('<H', data[:2])[0]
        data = data[2:]
        return data[:length], data[length:]

    @staticmethod
    def _pack_control_data(data: bytes) -> bytes:
        """Pack control data (if control bit 15 is set)

        Arguments:
            data: The control data to pack

        Returns:
            bytes: packed
                The packed control data

        Note:
            This is undefined as of UMDv5.0 and its implementation is
            the author's "best guess" based off of other areas of the protocol

        :meta public:
        """
        length = len(data)
        return struct.pack(f'<H{length}s', length, data)

    def to_dmsg(self, flags: Flags) -> bytes:
        """Build ``dmsg`` bytes to be included in a message
        (called from :meth:`Message.build_message`)
        """
        ctrl = self.rh_tally & 0b11
        ctrl += (self.txt_tally & 0b11) << 2
        ctrl += (self.lh_tally & 0b11) << 4
        ctrl += (self.brightness & 0b11) << 6
        if self.type == MessageType.control:
            ctrl |= 0x8000
            data = bytearray(struct.pack('<2H', self.index, ctrl))
            data.extend(self._pack_control_data(self.control))
        else:
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
    def from_tally(cls, tally: Tally, msg_type: MessageType = MessageType.display) -> 'Display':
        """Create a :class:`Display` from the given :class:`~.Tally`
        """
        kw = tally.to_dict()
        if msg_type == MessageType.control:
            del kw['text']
        kw['type'] = msg_type
        return cls(**kw)

    def __eq__(self, other):
        if not isinstance(other, (Display, Tally)):
            return NotImplemented
        self_dict = self.to_dict()
        oth_dict = other.to_dict()
        if isinstance(other, Display):
            return self_dict == oth_dict

        del self_dict['type']
        if self.type == MessageType.control:
            del self_dict['text']
            del oth_dict['text']
        else:
            del self_dict['control']
            del oth_dict['control']

        return self_dict == oth_dict

    def __ne__(self, other):
        if not isinstance(other, (Display, Tally)):
            return NotImplemented
        return not self.__eq__(other)

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
    """SCONTROL data (if :attr:`type` is :attr:`~MessageType.control`)"""

    type: MessageType = MessageType.display
    """The message type. One of :attr:`~MessageType.display` or
    :attr:`~MessageType.control`.

    * For :attr:`~MessageType.display` (the default), the contents of
      :attr:`displays` are used and the :attr:`scontrol` field must be empty.
    * For :attr:`~MessageType.control`, the :attr:`scontrol` field is used and
      :attr:`displays` must be empty.
    """

    def __post_init__(self):
        if not isinstance(self.flags, Flags):
            self.flags = Flags(self.flags)

        if len(self.scontrol) and len(self.displays):
            raise ValueError('SCONTROL message cannot contain displays')

        if len(self.scontrol):
            self.type = MessageType.control

        if self.type == MessageType.control:
            self.flags |= Flags.SCONTROL
        elif self.type == MessageType._unset:
            if Flags.SCONTROL in self.flags:
                self.type = MessageType.control
            else:
                self.type = MessageType.display

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
            type=MessageType._unset,
        )
        msg = msg[2:]
        remaining = msg[byte_count:]
        msg = msg[4:byte_count]
        obj = cls(**kw)
        if obj.type == MessageType.control:
            obj.scontrol = msg
            return obj, remaining
        while len(msg):
            disp, msg = Display.from_dmsg(obj.flags, msg)
            obj.displays.append(disp)
        return obj, remaining

    def build_message(self) -> bytes:
        """Build a message packet from data in this instance
        """
        if self.type == MessageType.control:
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
