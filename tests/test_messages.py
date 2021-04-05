import pytest

from tslumd import TallyColor, Message, Display, MessageType
from tslumd.messages import Flags


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

        msg_bytes = msgobj.build_message()
        parsed, remaining = Message.parse(msg_bytes)

        assert not len(remaining)
        assert parsed == msgobj

        with pytest.raises(ValueError) as excinfo:
            disp = Display(index=1, control=b'foo', text='foo')
        excstr = str(excinfo.value).lower()
        assert 'control' in excstr and 'text' in excstr

        with pytest.raises(ValueError) as excinfo:
            disp = Display(index=1, text='foo', type=MessageType.control)
        excstr = str(excinfo.value).lower()
        assert 'control' in excstr and 'text' in excstr
