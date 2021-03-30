from pathlib import Path
import json
import pytest

from tslumd import TallyColor, Message, Display

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / 'data'
MESSAGE_FILE = DATA_DIR / 'uhs500-message.umd'
MESSAGE_JSON = DATA_DIR / 'uhs500-tally.json'

@pytest.fixture
def uhs500_msg_bytes() -> bytes:
    """Real message data received from an AV-UHS500 switcher
    """
    return MESSAGE_FILE.read_bytes()

@pytest.fixture
def uhs500_msg_parsed() -> Message:
    """Expected :class:`~tslumd.messages.Message` object
    matching data from :func:`uhs500_msg_bytes`
    """
    data = json.loads(MESSAGE_JSON.read_text())
    data['scontrol'] = b''
    displays = []
    for disp in data['displays']:
        for key in ['rh_tally', 'txt_tally', 'lh_tally']:
            disp[key] = getattr(TallyColor, disp[key])
        displays.append(Display(**disp))
    data['displays'] = displays
    return Message(**data)

@pytest.fixture
def udp_port0(unused_tcp_port_factory):
    return unused_tcp_port_factory()

@pytest.fixture
def udp_port(unused_tcp_port_factory):
    return unused_tcp_port_factory()
