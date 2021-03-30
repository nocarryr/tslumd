import asyncio
import pytest

from tslumd import TallyType, TallyColor, Message, Display, Tally, UmdReceiver

class EventListener:
    def __init__(self):
        self.results = asyncio.Queue()
    async def get(self):
        r = await self.results.get()
        self.results.task_done()
        return r
    def empty(self):
        return self.results.empty()
    async def callback(self, *args, **kwargs):
        await self.results.put((args, kwargs))

@pytest.fixture
async def udp_endpoint(udp_port0):
    class Protocol(asyncio.DatagramProtocol):
        def __init__(self):
            self.queue = asyncio.Queue()
            self.connected_evt = asyncio.Event()
        def connection_made(self, transport):
            self.connected_evt.set()
        def datagram_received(self, data, addr):
            self.queue.put_nowait((data, addr))

    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: Protocol(),
        ('127.0.0.1', udp_port0),
    )
    await protocol.connected_evt.wait()
    yield (transport, protocol, udp_port0)
    transport.close()


@pytest.mark.asyncio
async def test_with_uhs_data(uhs500_msg_bytes, uhs500_msg_parsed, udp_endpoint, udp_port):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    loop = asyncio.get_event_loop()

    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    async with receiver:

        # Send message bytes to receiver
        transport.sendto(uhs500_msg_bytes, ('127.0.0.1', udp_port))

        # Wait for all ``on_tally_added`` events
        _ = await evt_listener.get()
        while not evt_listener.empty():
            _ = await evt_listener.get()

        # Check all receiver tallies against the expected ones
        assert len(receiver.tallies) == len(uhs500_msg_parsed.displays)

        for disp in uhs500_msg_parsed.displays:
            assert disp.index in receiver.tallies
            tally = receiver.tallies[disp.index]
            assert disp == tally

        # Change each display and send the updated message to receiver
        # Then wait for ``on_tally_updated`` events
        receiver.unbind(evt_listener)
        receiver.bind_async(loop, on_tally_updated=evt_listener.callback)
        for disp in uhs500_msg_parsed.displays:
            tally = receiver.tallies[disp.index]

            for tally_type in TallyType:
                if tally_type == TallyType.no_tally:
                    continue
                attr = tally_type.name
                cur_value = getattr(disp, attr)
                if cur_value == TallyColor.RED:
                    new_value = TallyColor.GREEN
                else:
                    new_value = TallyColor.RED
                setattr(disp, attr, new_value)
            disp.text = f'{disp.text}-foo'
            disp.brightness = 1

            transport.sendto(uhs500_msg_parsed.build_message(), ('127.0.0.1', udp_port))

            evt_args, evt_kwargs = await evt_listener.get()
            evt_tally = evt_args[0]
            assert evt_tally is tally
            assert disp == tally

@pytest.mark.asyncio
async def test_rebind(uhs500_msg_bytes, uhs500_msg_parsed, udp_endpoint, udp_port, unused_tcp_port_factory):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    loop = asyncio.get_event_loop()

    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    async with receiver:

        # Send message bytes to receiver and wait for ``on_tally_added`` events
        transport.sendto(uhs500_msg_bytes, ('127.0.0.1', udp_port))
        _ = await evt_listener.get()
        while not evt_listener.empty():
            _ = await evt_listener.get()

        assert len(receiver.tallies) == len(uhs500_msg_parsed.displays)

        # Set up to get ``on_tally_updated`` callbacks
        receiver.unbind(evt_listener)
        receiver.bind_async(loop, on_tally_updated=evt_listener.callback)


        # Change bind address and trigger a change
        await receiver.set_hostaddr('0.0.0.0')
        assert receiver.hostaddr == '0.0.0.0'

        disp = uhs500_msg_parsed.displays[0]
        disp.brightness = 1

        transport.sendto(uhs500_msg_parsed.build_message(), ('0.0.0.0', udp_port))

        evt_args, evt_kwargs = await evt_listener.get()
        evt_tally = evt_args[0]
        assert disp == evt_tally

        # Change bind port and trigger a change
        new_port = unused_tcp_port_factory()
        assert new_port != udp_port

        await receiver.set_hostport(new_port)
        assert receiver.hostport == new_port

        disp.brightness = 2
        transport.sendto(uhs500_msg_parsed.build_message(), ('0.0.0.0', new_port))

        evt_args, evt_kwargs = await evt_listener.get()
        evt_tally = evt_args[0]
        assert disp == evt_tally