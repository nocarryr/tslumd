import struct
import pytest

from tslumd import TallyColor, Message, Display, MessageType
from tslumd.messages import (
    Flags, ParseError, DmsgParseError,
    DmsgControlParseError, MessageParseError, MessageLengthError,
)

@pytest.fixture
def message_with_lots_of_displays():
    msgobj = Message()
    # Message header byte length: 6
    # Dmsg header byte length: 4
    # Text length: 2(length bytes) + 9(chars) = 11
    # Each Dmsg total: 4 + 11 = 15
    # Dmsg's: 4096 * 15 = 61440
    # 4096 Dmsg's with Message header: 4096 * 15 + 6 = 61446 bytes
    for i in range(4096):
        msgobj.displays.append(Display(index=i, text=f'Foo {i:05d}'))
    return msgobj


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
    msgobj = message_with_lots_of_displays

    # Make sure the 2048 byte limit is respected
    with pytest.raises(MessageLengthError):
        _ = msgobj.build_message()

    # Ensure that the limit can be bypassed
    msg_bytes = msgobj.build_message(ignore_packet_length=True)
    parsed, remaining = Message.parse(msg_bytes)
    assert parsed == msgobj

    # Iterate over individual message packets and make sure we get all displays
    all_parsed_displays = []
    for msg_bytes in msgobj.build_messages():
        assert len(msg_bytes) <= 2048
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

            parsed, remaining = Display.from_dmsg(msgobj.flags, disp.to_dmsg(msgobj.flags))
            assert not parsed.is_broadcast
            assert parsed == disp

        # Create broadcast Displays using both methods and check the
        # `is_broadcast` field on the instances and their parsed versions
        bc_disp1 = Display.broadcast(**kw)
        bc_disp2 = Display(index=0xffff, **kw)
        assert bc_disp1.is_broadcast
        assert bc_disp2.is_broadcast

        parsed1, remaining = Display.from_dmsg(msgobj.flags, bc_disp1.to_dmsg(msgobj.flags))
        assert parsed1.is_broadcast

        parsed2, remaining = Display.from_dmsg(msgobj.flags, bc_disp2.to_dmsg(msgobj.flags))
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

            disp_bytes = disp.to_dmsg(msgobj.flags)
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


@pytest.mark.benchmark(group='message-parse')
def test_bench_message_parse(uhs500_msg_bytes, uhs500_msg_parsed):
    parsed, remaining = Message.parse(uhs500_msg_bytes)
    assert not len(remaining)
    assert parsed == uhs500_msg_parsed


@pytest.mark.benchmark(group='message-build')
def test_bench_message_build(uhs500_msg_bytes, uhs500_msg_parsed_fixed_text_length):
    msg_bytes = uhs500_msg_parsed_fixed_text_length.build_message()
    assert len(msg_bytes) == len(uhs500_msg_bytes)
    assert msg_bytes == uhs500_msg_bytes
