from __future__ import annotations
import asyncio
import dataclasses
from dataclasses import dataclass, field
import enum
import struct
import warnings
from typing import Tuple, Iterator, Any, cast

from tslumd import MessageType, TallyColor, Tally

__all__ = (
    'Display', 'Message', 'ParseError', 'MessageParseError',
    'DmsgParseError', 'DmsgControlParseError', 'MessageLengthError',
)


class ParseError(Exception):
    """Raised on errors during message parsing

    .. versionadded:: 0.0.2
    """
    msg: str #: Error message
    value: bytes #: The relevant message bytes containing the error
    def __init__(self, msg: str, value: bytes):
        self.msg = msg
        self.value = value
    def __str__(self):
        return f'{self.msg}: "{self.value!r}"'

class MessageParseError(ParseError):
    """Raised on errors while parsing :class:`Message` objects

    .. versionadded:: 0.0.2
    """
    pass

class DmsgParseError(ParseError):
    """Raised on errors while parsing :class:`Display` objects

    .. versionadded:: 0.0.2
    """
    pass

class DmsgControlParseError(ParseError):
    """Raised on errors when parsing :attr:`Display.control` data

    .. versionadded:: 0.0.2
    """
    pass

class MessageLengthError(ValueError):
    """Raised when message length is larger than 2048 bytes

    .. versionadded:: 0.0.4
    """


class Flags(enum.IntFlag):
    """Message flags
    """
    NO_FLAGS = 0 #: No flags set
    UTF16 = 1
    """Indicates the text fields contain non-ASCII characters encoded as UTF-16LE"""

    SCONTROL = 2
    """Indicates the message contains ``SCONTROL`` data if set, otherwise ``DMESG``
    """

def text_is_ascii(s: str) -> bool:
    try:
        s.encode('ascii')
    except UnicodeEncodeError:
        return False
    return True


@dataclass(frozen=True)
class Display:
    """A single tally "display"
    """
    index: int #: The display index from 0 to 65534 (``0xFFFE``)
    rh_tally: TallyColor = TallyColor.OFF #: Right hand tally indicator
    txt_tally: TallyColor = TallyColor.OFF #: Text tally indicator
    lh_tally: TallyColor = TallyColor.OFF #: Left hand tally indicator
    brightness: int = 3 #: Display brightness (from 0 to 3)
    text: str = '' #: Text to display
    control: bytes = b''
    """Control data (if :attr:`type` is :attr:`~.MessageType.control`)

    .. versionadded:: 0.0.2
    """

    type: MessageType = MessageType.display
    """The message type. One of :attr:`~.MessageType.display` or
    :attr:`~.MessageType.control`.

    * For :attr:`~.MessageType.display` (the default), the message contains
      :attr:`text` information and the :attr:`control` field must be empty.
    * For :attr:`~.MessageType.control`, the message contains :attr:`control`
      data and the :attr:`text` field must be empty

    .. versionadded:: 0.0.2
    """

    is_broadcast: bool = field(init=False)
    """``True`` if the display is to a "broadcast", meaning sent to all display
    indices.

    (if the :attr:`index` is ``0xffff``)

    .. versionadded:: 0.0.2
    """
    text_length: int|None = field(default=None, compare=False)
    """Length of the :attr:`text` field

    If provided, the text output will be zero-padded or truncated to this length.
    If ``None`` (the default), the text length is variable.


    .. note::

        This is mainly for internal use during test runs to match the fixed-length
        text field in actual message bytes.

    .. versionadded:: 0.0.8
    """

    _requires_utf16: bool = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        object.__setattr__(self, 'is_broadcast', self.index == 0xffff)
        if len(self.control):
            object.__setattr__(self, 'type', MessageType.control)
        if self.type == MessageType.control and len(self.text):
            raise ValueError('Control message cannot contain text')
        is_utf16 = not text_is_ascii(self.text)
        object.__setattr__(self, '_requires_utf16', is_utf16)

    @classmethod
    def broadcast(cls, **kwargs) -> Display:
        """Create a :attr:`broadcast <is_broadcast>` display

        (with :attr:`index` set to ``0xffff``)

        .. versionadded:: 0.0.2
        """
        kwargs = kwargs.copy()
        kwargs['index'] = 0xffff
        return cls(**kwargs)

    @classmethod
    def from_dmsg(cls, flags: Flags, dmsg: bytes, retain_text_length: bool = False) -> Tuple[Display, bytes]:
        """Construct an instance from a ``DMSG`` portion of received message.

        Any remaining message data after the relevant ``DMSG`` is returned along
        with the instance.

        Arguments:
            flags: The message :class:`Flags` field
            dmsg: The portion of the message containing the ``DMSG`` data
            retain_text_length: If ``True``, the :attr:`text_length` attribute
                will be set to the length of the text field as found in the
                message bytes. Otherwise (the default), it will be set to ``None``
                and the text length will be variable.

        .. versionchanged:: 0.0.8

            The `retain_text_length` argument was added.
        """
        if len(dmsg) < 4:
            raise DmsgParseError('Invalid dmsg length', dmsg)
        hdr = struct.unpack('<2H', dmsg[:4])
        hdr = cast(Tuple[int, int], hdr)
        dmsg = dmsg[4:]
        ctrl = hdr[1]
        kw: dict[str, Any] = dict(
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
            if len(dmsg) < 2:
                raise DmsgParseError('Invalid text length field', dmsg)
            txt_byte_len = struct.unpack('<H', dmsg[:2])[0]
            dmsg = dmsg[2:]
            txt_bytes = dmsg[:txt_byte_len]
            dmsg = dmsg[txt_byte_len:]
            if len(txt_bytes) != txt_byte_len:
                raise DmsgParseError(
                    f'Invalid text bytes. Expected {txt_byte_len}',
                    txt_bytes,
                )
            if Flags.UTF16 in flags:
                txt = txt_bytes.decode('UTF-16le')
            else:
                txt_length = len(txt_bytes)
                if b'\0' in txt_bytes:
                    txt_bytes = txt_bytes.split(b'\0')[0]
                txt = txt_bytes.decode('UTF-8')
                if retain_text_length:
                    kw['text_length'] = txt_length
                else:
                    kw['text_length'] = None
            kw['text'] = txt
        return cls(**kw), dmsg

    @staticmethod
    def _unpack_control_data(data: bytes) -> Tuple[bytes, bytes]:
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

        .. versionadded:: 0.0.2

        :meta public:
        """
        if len(data) < 2:
            raise DmsgControlParseError('Unknown control data format', data)
        length = struct.unpack('<H', data[:2])[0]
        data = data[2:]
        if len(data) < length:
            raise DmsgControlParseError('Unknown control data format', data)
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

        .. versionadded:: 0.0.2

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
            if self._requires_utf16:
                # The UTF16 flag should be set in the message flags by now
                txt_bytes = bytes(self.text, 'UTF-16le')
            else:
                txt_bytes = bytes(self.text, 'ascii')
            if self.text_length is not None:
                txt_bytes = txt_bytes.ljust(self.text_length, b'\0')[:self.text_length]
            txt_byte_len = len(txt_bytes)
            data = bytearray(struct.pack('<3H', self.index, ctrl, txt_byte_len))
            data.extend(txt_bytes)
        return data

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        del d['is_broadcast']
        del d['text_length']
        del d['_requires_utf16']
        return d

    @classmethod
    def from_tally(cls, tally: Tally, msg_type: MessageType = MessageType.display) -> Display:
        """Create a :class:`Display` from the given :class:`~.Tally`

        .. versionadded:: 0.0.2
            The msg_type argument
        """
        kw = tally.to_dict()
        del kw['id']
        if msg_type == MessageType.control:
            del kw['text']
        elif msg_type == MessageType.display:
            del kw['control']
        kw['type'] = msg_type
        return cls(**kw)

    def __eq__(self, other):
        if not isinstance(other, (Display, Tally)):
            return NotImplemented
        self_dict = self.to_dict()
        oth_dict = other.to_dict()
        if isinstance(other, Display):
            return self_dict == oth_dict
        else:
            del oth_dict['id']

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
    flags: Flags = Flags.NO_FLAGS #: The message :class:`Flags` field
    screen: int = 0 #: Screen index from 0 to 65534 (``0xFFFE``)
    displays: list[Display] = field(default_factory=list)
    """A list of :class:`Display` instances"""

    scontrol: bytes = b''
    """SCONTROL data (if :attr:`type` is :attr:`~.MessageType.control`)"""

    type: MessageType = MessageType.display
    """The message type. One of :attr:`~.MessageType.display` or
    :attr:`~.MessageType.control`.

    * For :attr:`~.MessageType.display` (the default), the contents of
      :attr:`displays` are used and the :attr:`scontrol` field must be empty.
    * For :attr:`~.MessageType.control`, the :attr:`scontrol` field is used and
      :attr:`displays` must be empty.

    .. versionadded:: 0.0.2
    """

    is_broadcast: bool = field(init=False)
    """``True`` if the message is to be "broadcast" to all screens.

    (if :attr:`screen` is ``0xffff``)

    .. versionadded:: 0.0.2
    """

    def __post_init__(self):
        self.is_broadcast = self.screen == 0xffff
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
    def broadcast(cls, **kwargs) -> Message:
        """Create a :attr:`broadcast <is_broadcast>` message

        (with :attr:`screen` set to ``0xffff``)

        .. versionadded:: 0.0.2
        """
        kwargs = kwargs.copy()
        kwargs['screen'] = 0xffff
        return cls(**kwargs)

    @classmethod
    def parse(cls, msg: bytes, retain_text_length: bool = False) -> Tuple[Message, bytes]:
        """Parse incoming message data to create a :class:`Message` instance.

        Any remaining message data after parsing is returned along with the instance.

        Arguments:
            msg: The incoming message bytes to parse
            retain_text_length: Value to pass to :meth:`Display.from_dmsg`

        .. versionchanged:: 0.0.8
            The `retain_text_length` argument was added.
        """
        if len(msg) < 6:
            raise MessageParseError('Invalid header length', msg)
        data = struct.unpack('<HBBH', msg[:6])
        byte_count, version, flags, screen = data
        kw = dict(
            version=version,
            flags=Flags(flags),
            screen=screen,
            type=MessageType._unset,
        )
        msg = msg[2:]
        if len(msg) < byte_count:
            raise MessageParseError(
                f'Invalid byte count. Expected {byte_count}, got {len(msg)}',
                msg,
            )
        remaining = msg[byte_count:]
        msg = msg[4:byte_count]
        obj = cls(**kw)
        if obj.type == MessageType.control:
            obj.scontrol = msg
            return obj, remaining
        while len(msg):
            disp, msg = Display.from_dmsg(obj.flags, msg, retain_text_length)
            obj.displays.append(disp)
        return obj, remaining

    def build_message(self, ignore_packet_length: bool = False) -> bytes:
        """Build a message packet from data in this instance

        Arguments:
            ignore_packet_length (bool, optional): If ``False``, the message limit
                of 2048 bytes is respected, and if exceeded, an exception is raised.
                Otherwise, the limit is ignored. (default is False)

        Raises:
            MessageLengthError: If the message packet is larger than 2048 bytes
                (and ``ignore_packet_length`` is False)

        Note:
            This method is retained for backwards compatability. To properly
            handle the message limit, use :meth:`build_messages`

        .. versionchanged:: 0.0.4

            * The ``ignore_packet_length`` parameter was added
            * Message length is limited to 2048 bytes
        """
        it = self.build_messages(ignore_packet_length=ignore_packet_length)
        data = next(it)
        try:
            next_data = next(it)
        except StopIteration:
            pass
        else:
            if not ignore_packet_length:
                raise MessageLengthError()
        return data

    def build_messages(self, ignore_packet_length: bool = False) -> Iterator[bytes]:
        """Build message packet(s) from data in this instance as an iterator

        The specified maximum packet length of 2048 is respected and if
        necessary, the data will be split into separate messages.

        This method will always function as a :term:`generator`, regardless of
        the number of message packets produced.

        .. versionadded:: 0.0.4
        """
        msg_len_exceeded = False
        next_disp_index = None
        flags = self.flags
        if self.type == MessageType.control:
            payload = bytearray(self.scontrol)
            byte_count = len(payload)
            if byte_count + 6 > 2048:
                raise MessageLengthError()
        else:
            if flags & Flags.UTF16 == 0 and self._requires_utf16():
                warnings.warn(
                    'Message contains UTF-16 text but UTF16 flag is not set. Setting it now.',
                    UnicodeWarning,
                    stacklevel=2,
                )
                flags |= Flags.UTF16
            byte_count = 0
            payload = bytearray()
            for disp_index, display in enumerate(self.displays):
                disp_payload = display.to_dmsg(flags)
                disp_len = len(disp_payload)
                if not ignore_packet_length:
                    if byte_count + disp_len + 6 >= 2048:
                        if disp_index == 0:
                            raise MessageLengthError()
                        msg_len_exceeded = True
                        next_disp_index = disp_index
                        break
                byte_count += disp_len
                payload.extend(disp_payload)
        fmt = f'<HBBH{byte_count}B'
        pbc = struct.calcsize(fmt) - 2
        data = bytearray(struct.pack('<HBBH', pbc, self.version, flags, self.screen))
        data.extend(payload)
        yield bytes(data)

        if msg_len_exceeded:
            displays = self.displays[next_disp_index:]
            attrs = ('version', 'flags', 'screen', 'scontrol', 'type')
            kw = {attr:getattr(self, attr) for attr in attrs}
            kw['displays'] = displays
            sub_msg = Message(**kw)
            yield from sub_msg.build_messages()

    def _requires_utf16(self) -> bool:
        if Flags.UTF16 in self.flags:
            return True
        return any(disp._requires_utf16 for disp in self.displays)
