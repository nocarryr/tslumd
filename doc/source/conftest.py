# from loguru import logger
import pytest
import asyncio
import socket

@pytest.fixture(scope='session')
def non_loopback_hostaddr():
    hostname, aliases, addrs = socket.gethostbyname_ex(socket.gethostname())
    addrs = [addr for addr in addrs if addr != '127.0.0.1']
    assert len(addrs)
    return addrs[0]


@pytest.fixture(scope='function')
def new_loop(request, doctest_namespace):
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    policy.set_event_loop(loop)
    doctest_namespace['loop'] = loop
    yield loop
    loop.close()
    policy.set_event_loop(None)

def receiver_setup(request, loop, hostaddr):
    cleanup_coro = None
    from tslumd import UmdSender, TallyType, TallyColor

    sender = UmdSender(clients=[(hostaddr, 65000)], all_off_on_close=False)
    screen_index = 1

    async def open_sender():
        await sender.open()
        sender_task = asyncio.create_task(run_sender())
        return sender_task

    async def run_sender():
        await sender.connected_evt.wait()
        for i in range(1, 5):
            tally_key = (screen_index, i)
            sender.set_tally_text(tally_key, f'Camera {i}')
        for i, color in ((1, TallyColor.RED), (2, TallyColor.GREEN)):
            await asyncio.sleep(.5)
            sender.set_tally_color((screen_index, i), TallyType.rh_tally, color)
        return sender

    sender_task = loop.run_until_complete(open_sender())

    async def cleanup():
        await sender_task
        await sender.close()

    yield
    loop.run_until_complete(cleanup())
    if not loop.is_closed():
        loop.close()
    asyncio.set_event_loop_policy(None)

@pytest.fixture(scope="function", autouse=True)
def doctest_stuff(request, new_loop, non_loopback_hostaddr):
    node_name = request.node.name
    loop = asyncio.get_event_loop()
    assert loop is new_loop
    if node_name == 'receiver.rst':
        yield from receiver_setup(request, new_loop, non_loopback_hostaddr)
    else:
        yield
