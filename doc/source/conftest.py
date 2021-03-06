# from loguru import logger
import pytest
import asyncio

def receiver_setup(request, doctest_namespace):
    node_name = request.node.name
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    policy.set_event_loop(loop)
    # logger.info(f'{request.node=}, {request.function=}, {request.module=}')
    # logger.info(f'event loop: {loop!r}')
    # doctest_namespace['_asyncio'] = asyncio
    # doctest_namespace['_loop'] = loop

    cleanup_coro = None

    from tslumd import UmdSender, TallyType, TallyColor

    sender = UmdSender(clients=[('0.0.0.0', 65000)], all_off_on_close=False)
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
def doctest_stuff(request, doctest_namespace):
    node_name = request.node.name
    if node_name == 'receiver.rst':
        yield from receiver_setup(request, doctest_namespace)
    else:
        yield
