import struct
import pytest

from tslumd import TallyColor, Message, Display, MessageType
from tslumd.tallyobj import Tally, Screen
from tslumd.messages import (
    Flags, ParseError, DmsgParseError,
    DmsgControlParseError, MessageParseError, MessageLengthError,
)


def build_multi_display_message(num_displays: int) -> tuple[Message, list[int]]:
    """Build a message with enough displays to require multiple packets
    when built, returning the message object and a list of the lengths
    of each packet.
    """
    msgobj = Message()
    msg_lengths = []
    text_format = 'Foo {:05d}'
    text_length = len(text_format.format(0))

    # Initial message header length
    cur_msg_length = 6

    # Dmsg header + text length bytes + text bytes
    dmsg_length = 4 + 2 + text_length

    for i in range(num_displays):
        msgobj.displays.append(Display(index=i, text=text_format.format(i)))
        if cur_msg_length + dmsg_length > 2048:
            msg_lengths.append(cur_msg_length)
            cur_msg_length = 6 + dmsg_length
        else:
            cur_msg_length += dmsg_length
    msg_lengths.append(cur_msg_length)
    assert not any(l > 2048 for l in msg_lengths)
    return msgobj, msg_lengths


@pytest.fixture
def message_with_multi_packet_displays() -> tuple[Message, list[int]]:
    """Message with enough displays to require at least 6 packets
    but not so many as to make the test take too long.
    """
    return build_multi_display_message(6 * 136 + 1)  # 6 full packets + 1 display


@pytest.fixture
def message_with_lots_of_displays() -> tuple[Message, list[int]]:
    return build_multi_display_message(4096)


@pytest.fixture(
    params=[
        'Hello, world! 😊',
        'こんにちは世界',  # Japanese
        'Привет, мир!',   # Russian
        'مرحبا بالعالم',  # Arabic
        '😊🌍🚀',         # Emojis
    ]
)
def utf16_text(request) -> str:
    return request.param


@pytest.fixture
def utf16_message(utf16_text):
    """Construct message bytes containing a single display with non-ASCII text

    Building manually to ensure proper isolation from the library code.
    """
    ver = 0
    flags = 0x01    # bit 0 set for UTF-16
    screen = 1
    disp = 1
    ctrl = 0        # no control
    text_bytes = bytes(utf16_text, 'utf-16le')
    packet = bytearray(
        struct.pack('<BBHHHH', ver, flags, screen, disp, ctrl, len(text_bytes))
    )
    packet.extend(text_bytes)
    pbc = len(packet)
    packet = bytearray(struct.pack('<H', pbc)) + packet
    return bytes(packet)



def test_uhs_message(uhs500_msg_bytes, uhs500_msg_parsed):
    parsed, remaining = Message.parse(uhs500_msg_bytes)
    assert not len(remaining)
    assert parsed == uhs500_msg_parsed


def test_messages():
    msgobj = Message(version=1, screen=5)
    rh_tallies = [getattr(TallyColor, attr) for attr in ['RED','OFF','GREEN','AMBER']]
    lh_tallies = [getattr(TallyColor, attr) for attr in ['GREEN','RED','OFF','RED']]
    txt_tallies = [getattr(TallyColor, attr) for attr in ['OFF','GREEN','AMBER','GREEN']]
    txts = ['foo', 'bar', 'baz', 'blah']
    indices = [4,3,7,1]
    for i in range(4):
        disp = Display(
            index=indices[i], rh_tally=rh_tallies[i], lh_tally=lh_tallies[i],
            txt_tally=txt_tallies[i], text=txts[i], brightness=i,
        )
        msgobj.displays.append(disp)

    parsed, remaining = Message.parse(msgobj.build_message())
    assert not len(remaining)

    for i in range(len(rh_tallies)):
        disp1, disp2 = msgobj.displays[i], parsed.displays[i]
        assert disp1.rh_tally == disp2.rh_tally == rh_tallies[i]
        assert disp1.lh_tally == disp2.lh_tally == lh_tallies[i]
        assert disp1.txt_tally == disp2.txt_tally == txt_tallies[i]
        assert disp1.text == disp2.text == txts[i]
        assert disp1.index == disp2.index == indices[i]
        assert disp1 == disp2

    for attr in ['version', 'flags', 'screen', 'scontrol']:
        assert getattr(msgobj, attr) == getattr(parsed, attr)

    assert msgobj == parsed


def test_packet_length(faker, message_with_lots_of_displays):
    msgobj, msg_lengths = message_with_lots_of_displays

    # Make sure the 2048 byte limit is respected
    with pytest.raises(MessageLengthError):
        _ = msgobj.build_message()

    # Ensure that the limit can be bypassed
    msg_bytes = msgobj.build_message(ignore_packet_length=True)
    parsed, remaining = Message.parse(msg_bytes)
    assert parsed == msgobj

    # Iterate over individual message packets and make sure we get all displays
    all_parsed_displays = []
    for i, msg_bytes in enumerate(msgobj.build_messages()):
        assert len(msg_bytes) <= 2048
        assert len(msg_bytes) == msg_lengths[i]
        parsed, remaining = Message.parse(msg_bytes)
        assert not len(remaining)
        all_parsed_displays.extend(parsed.displays)

    assert len(all_parsed_displays) == len(msgobj.displays)
    for disp, parsed_disp in zip(msgobj.displays, all_parsed_displays):
        assert disp.index == parsed_disp.index
        assert disp.text == parsed_disp.text

    # Create an SCONTROL that exceeds the limit
    msgobj = Message(scontrol=faker.binary(length=2048))
    with pytest.raises(MessageLengthError):
        it = msgobj.build_messages()
        _ = next(it)

    # Create a Dmsg control that exceeds the limit
    msgobj = Message(displays=[Display(index=0, control=faker.binary(length=2048))])
    with pytest.raises(MessageLengthError):
        it = msgobj.build_messages()
        _ = next(it)


def test_broadcast_message(faker):
    for i in range(1000):
        # Create Messages with random `screen` value in the non-broadcast range
        # and ensure the `is_broadcast` field is correct in both the
        # instance and its parsed version
        screen = faker.pyint(max_value=0xfffe)
        msgobj = Message(screen=screen)
        msgobj.displays.append(Display(index=i))
        assert not msgobj.is_broadcast

        parsed, remaining = Message.parse(msgobj.build_message())
        assert not msgobj.is_broadcast

    # Create broadcast Messages using both methods and check the `is_broadcast`
    # field on the instances and their parsed versions
    msgobj1 = Message(screen=0xffff)
    msgobj1.displays.append(Display(index=1))
    assert msgobj1.is_broadcast
    parsed1, remaining = Message.parse(msgobj1.build_message())
    assert parsed1.is_broadcast

    msgobj2 = Message.broadcast(displays=[Display(index=1)])
    assert msgobj2.is_broadcast
    parsed2, remaining = Message.parse(msgobj2.build_message())
    assert parsed2.is_broadcast

    assert msgobj1 == msgobj2 == parsed1 == parsed2


def test_broadcast_display(uhs500_msg_parsed, faker):

    disp_attrs = ('rh_tally', 'txt_tally', 'lh_tally', 'text', 'brightness')
    msgobj = Message()

    for uhs_disp in uhs500_msg_parsed.displays:
        assert not uhs_disp.is_broadcast

        # General kwargs excluding the `index`
        kw = {attr:getattr(uhs_disp, attr) for attr in disp_attrs}

        # Create random Displays within non-broadcast range and check the
        # `is_broadcast` field of the instance and its parsed version
        for _ in range(1000):
            ix = faker.pyint(max_value=0xfffe)
            disp = Display(index=ix, **kw)
            assert not disp.is_broadcast

            parsed, remaining = Display.from_dmsg(msgobj.flags, disp.to_dmsg())
            assert not parsed.is_broadcast
            assert parsed == disp

        # Create broadcast Displays using both methods and check the
        # `is_broadcast` field on the instances and their parsed versions
        bc_disp1 = Display.broadcast(**kw)
        bc_disp2 = Display(index=0xffff, **kw)
        assert bc_disp1.is_broadcast
        assert bc_disp2.is_broadcast

        parsed1, remaining = Display.from_dmsg(msgobj.flags, bc_disp1.to_dmsg())
        assert parsed1.is_broadcast

        parsed2, remaining = Display.from_dmsg(msgobj.flags, bc_disp2.to_dmsg())
        assert parsed2.is_broadcast

        assert bc_disp1 == bc_disp2 == parsed1 == parsed2

        # Add the broadcast Display to the Message at the top
        msgobj.displays.append(bc_disp1)

    # Check the `is_broadcast` field in the displays after Message building / parsing
    parsed, remaining = Message.parse(msgobj.build_message())
    for parsed_disp, bc_disp in zip(parsed.displays, msgobj.displays):
        assert parsed_disp.is_broadcast
        assert parsed_disp == bc_disp



def test_scontrol(faker):
    for _ in range(100):
        data_len = faker.pyint(min_value=1, max_value=1024)
        control_data = faker.binary(length=data_len)

        msgobj = Message(scontrol=control_data)
        assert msgobj.type == MessageType.control
        assert Flags.SCONTROL in msgobj.flags

        msg_bytes = msgobj.build_message()
        parsed, remaining = Message.parse(msg_bytes)
        assert not len(remaining)

        assert parsed.type == MessageType.control
        assert parsed.scontrol == control_data
        assert parsed == msgobj

        disp = Display(index=1)

        with pytest.raises(ValueError) as excinfo:
            disp_msg = Message(displays=[disp], scontrol=control_data)
        assert 'SCONTROL' in str(excinfo.value)


def test_dmsg_control(uhs500_msg_parsed, faker):
    tested_zero = False
    for _ in range(10):
        msgobj = Message(version=1, screen=5)
        for orig_disp in uhs500_msg_parsed.displays:
            if not tested_zero:
                data_len = 0
                tested_zero = True
            else:
                data_len = faker.pyint(min_value=0, max_value=1024)
            control_data = faker.binary(length=data_len)

            kw = orig_disp.to_dict()
            del kw['text']
            kw['control'] = control_data
            if not len(control_data):
                kw['type'] = MessageType.control
            disp = Display(**kw)

            assert disp.type == MessageType.control

            disp_bytes = disp.to_dmsg()
            parsed_disp, remaining = Display.from_dmsg(msgobj.flags, disp_bytes)

            assert not len(remaining)
            assert parsed_disp.control == control_data
            assert parsed_disp == disp

            msgobj.displays.append(disp)

        parsed = None
        for msg_bytes in msgobj.build_messages():
            _parsed, remaining = Message.parse(msg_bytes)
            assert not len(remaining)
            if parsed is None:
                parsed = _parsed
            else:
                parsed.displays.extend(_parsed.displays)
        assert parsed == msgobj

        with pytest.raises(ValueError) as excinfo:
            disp = Display(index=1, control=b'foo', text='foo')
        excstr = str(excinfo.value).lower()
        assert 'control' in excstr and 'text' in excstr

        with pytest.raises(ValueError) as excinfo:
            disp = Display(index=1, text='foo', type=MessageType.control)
        excstr = str(excinfo.value).lower()
        assert 'control' in excstr and 'text' in excstr


def test_invalid_message(uhs500_msg_bytes, faker):
    bad_bytes = faker.binary(length=5)
    with pytest.raises(MessageParseError) as excinfo:
        r = Message.parse(bad_bytes)
    assert 'header' in str(excinfo.value).lower()

    bad_bytes = bytearray(uhs500_msg_bytes)
    bad_byte_count = struct.pack('<H', len(uhs500_msg_bytes) + 10)
    bad_bytes[:2] = bad_byte_count
    bad_bytes = bytes(bad_bytes)
    with pytest.raises(MessageParseError) as excinfo:
        r = Message.parse(bad_bytes)
    assert 'byte count' in str(excinfo.value).lower()


def test_invalid_dmsg(uhs500_msg_bytes, faker):

    # Clip the dmsg header fields
    bad_bytes = bytearray(uhs500_msg_bytes[:8])

    # Insert the correct value for `PBC` field so it gets past initial checks
    bad_byte_count = struct.pack('<H', len(bad_bytes) - 2)
    bad_bytes[:2] = bad_byte_count
    bad_bytes = bytes(bad_bytes)
    with pytest.raises(DmsgParseError) as excinfo:
        r = Message.parse(bad_bytes)
    assert 'dmsg length' in str(excinfo.value).lower()

    # Clip the display text length field to the wrong size
    bad_bytes = bytearray(uhs500_msg_bytes[:10])

    # Insert the correct value for `PBC` field so it gets past initial checks
    bad_byte_count = struct.pack('<H', len(bad_bytes) - 2)
    bad_bytes[:2] = bad_byte_count
    bad_bytes = bytes(bad_bytes)
    with pytest.raises(DmsgParseError) as excinfo:
        r = Message.parse(bad_bytes)
    assert 'text length' in str(excinfo.value).lower()

    # Insert an incorrect value for the text length field
    bad_bytes = bytearray(uhs500_msg_bytes)
    txt_len_bytes = struct.pack('<H', len(uhs500_msg_bytes) + 10)
    bad_bytes[10:12] = txt_len_bytes
    bad_bytes = bytes(bad_bytes)
    with pytest.raises(DmsgParseError) as excinfo:
        r = Message.parse(bad_bytes)
    assert 'invalid text bytes' in str(excinfo.value).lower()


def test_invalid_dmsg_control(uhs500_msg_bytes, faker):
    msg = Message()
    disp = Display(index=1, control=b'foo\x00')
    msg.displays.append(disp)
    msg_bytes = msg.build_message()

    # Clip the length field to the wrong size
    bad_bytes = bytearray(msg_bytes)
    bad_bytes = bad_bytes[:-5]
    bad_byte_count = struct.pack('<H', len(bad_bytes) - 2)
    bad_bytes[:2] = bad_byte_count
    bad_bytes = bytes(bad_bytes)
    with pytest.raises(DmsgControlParseError):
        r = Message.parse(bad_bytes)

    # Clip the control bytes to the wrong length
    bad_bytes = bytearray(msg_bytes)
    bad_bytes = bad_bytes[:-2]
    bad_byte_count = struct.pack('<H', len(bad_bytes) - 2)
    bad_bytes[:2] = bad_byte_count
    bad_bytes = bytes(bad_bytes)
    with pytest.raises(DmsgControlParseError):
        r = Message.parse(bad_bytes)



def test_utf16_text_parse(utf16_text, utf16_message):
    msgobj, remaining = Message.parse(utf16_message)
    assert not len(remaining)
    assert msgobj.screen == 1
    assert len(msgobj.displays) == 1

    disp = msgobj.displays[0]
    assert disp.index == 1
    assert disp.text == utf16_text


def test_utf16_text_parse_to_tally(utf16_text, utf16_message):
    msgobj, remaining = Message.parse(utf16_message)
    assert not len(remaining)
    assert msgobj.screen == 1
    assert len(msgobj.displays) == 1

    screen = Screen(index_=msgobj.screen)
    screen.update_from_message(msgobj)
    assert len(screen.tallies) == len(msgobj.displays)
    disp = msgobj.displays[0]
    tally = screen[disp.index]

    assert disp.index == tally.index
    assert disp.text == tally.text == utf16_text


@pytest.mark.parametrize('auto_flags', [True, False])
def test_utf16_text_build(utf16_text, utf16_message, auto_flags: bool):
    msg_flags = Flags.NO_FLAGS if auto_flags else Flags.UTF16
    msgobj = Message(version=0, screen=1, flags=msg_flags)
    disp = Display(
        index=1,
        text=utf16_text,
        brightness=0,
    )
    msgobj.displays.append(disp)

    if auto_flags:
        with pytest.warns(UnicodeWarning):
            packet = msgobj.build_message()
    else:
        packet = msgobj.build_message()
    assert len(packet) == len(utf16_message)
    assert packet == utf16_message


@pytest.mark.parametrize('auto_flags', [True, False])
def test_utf16_text_build_from_tally(utf16_text, utf16_message, auto_flags: bool):
    screen = Screen(index_=1)
    tally = screen.add_tally(
        index_=1,
        text=utf16_text,
        brightness=0,
    )

    msg_flags = Flags.NO_FLAGS if auto_flags else Flags.UTF16
    msgobj = Message(version=0, screen=1, flags=msg_flags)
    disp = Display.from_tally(tally)
    msgobj.displays.append(disp)

    if auto_flags:
        with pytest.warns(UnicodeWarning):
            packet = msgobj.build_message()
    else:
        packet = msgobj.build_message()
    assert len(packet) == len(utf16_message)
    assert packet == utf16_message


@pytest.mark.benchmark(group='message-parse')
def test_bench_message_parse(uhs500_msg_bytes, uhs500_msg_parsed_fixed_text_length):
    parsed, remaining = Message.parse(uhs500_msg_bytes, retain_text_length=True)
    assert not len(remaining)
    assert parsed == uhs500_msg_parsed_fixed_text_length


@pytest.mark.benchmark(group='message-build')
def test_bench_message_build(uhs500_msg_bytes, uhs500_msg_parsed_fixed_text_length):
    msg_bytes = uhs500_msg_parsed_fixed_text_length.build_message()
    assert len(msg_bytes) == len(uhs500_msg_bytes)
    assert msg_bytes == uhs500_msg_bytes


@pytest.mark.benchmark(group='message-build-multi')
def test_bench_message_build_multi(message_with_multi_packet_displays):
    msgobj, msg_lengths = message_with_multi_packet_displays
    assert len(msg_lengths) > 1
    for i, msg_bytes in enumerate(msgobj.build_messages()):
        msg_len = len(msg_bytes)
        assert msg_len == msg_lengths[i]
