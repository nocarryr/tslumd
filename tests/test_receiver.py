import asyncio
import pytest
import pytest_asyncio

from tslumd import (
    TallyType, TallyColor, TallyKey, Message, Display,
    Tally, Screen, UmdReceiver,
)
from tslumd.messages import ParseError

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

@pytest_asyncio.fixture
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

    uhs_screen = uhs500_msg_parsed.screen

    async with receiver:

        # Send message bytes to receiver
        transport.sendto(uhs500_msg_bytes, ('127.0.0.1', udp_port))

        # Wait for all ``on_tally_added`` events
        _ = await evt_listener.get()
        while not evt_listener.empty():
            _ = await evt_listener.get()

        screen = receiver.screens[uhs_screen]

        # Check all receiver tallies against the expected ones
        assert len(receiver.tallies) == len(uhs500_msg_parsed.displays)

        for disp in uhs500_msg_parsed.displays:
            assert disp.index in screen
            tally = screen.tallies[disp.index]
            assert tally.id == (uhs_screen, disp.index)
            assert receiver.tallies[tally.id] is tally
            assert disp == tally

        # Change each display and send the updated message to receiver
        # Then wait for ``on_tally_updated`` events
        receiver.unbind(evt_listener)
        receiver.bind_async(loop, on_tally_updated=evt_listener.callback)
        for disp in uhs500_msg_parsed.displays:
            tally = screen.tallies[disp.index]

            for tally_type in TallyType.all():
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
async def test_broadcast_display(uhs500_msg_bytes, uhs500_msg_parsed, udp_endpoint, udp_port, faker):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    loop = asyncio.get_event_loop()

    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    displays_by_index = {disp.index: disp for disp in uhs500_msg_parsed.displays}

    async with receiver:
        # Populate the receiver's tallies and wait for them to be added
        transport.sendto(uhs500_msg_bytes, ('127.0.0.1', udp_port))
        _ = await evt_listener.get()
        while not evt_listener.empty():
            _ = await evt_listener.get()

        assert len(receiver.tallies) == len(uhs500_msg_parsed.displays)

        receiver.unbind(evt_listener)
        receiver.bind_async(loop, on_tally_updated=evt_listener.callback)


        # Send a broadcast display message for each TallyColor with a random brightness
        # The control field is set so the Tally text field is unchanged
        for color in TallyColor:
            brightness = faker.pyint(max_value=3)
            bc_disp = Display.broadcast(
                control=b'foo', rh_tally=color, lh_tally=color, txt_tally=color,
                brightness=brightness,
            )
            msg = Message(displays=[bc_disp])
            transport.sendto(msg.build_message(), ('127.0.0.1', udp_port))

            _ = await evt_listener.get()
            while not evt_listener.empty():
                _ = await evt_listener.get()

            # Check each of the receiver's tallies against the bc_disp values
            # and make sure the text didn't change
            for tally in receiver.tallies.values():
                assert tally.index < 0xffff
                assert not tally.is_broadcast
                assert tally.rh_tally == color
                assert tally.txt_tally == color
                assert tally.lh_tally == color
                assert tally.control == bc_disp.control
                assert tally.brightness == brightness
                assert tally.text == displays_by_index[tally.index].text


@pytest.mark.asyncio
async def test_rebind(
    uhs500_msg_bytes,
    uhs500_msg_parsed,
    udp_endpoint,
    udp_port,
    unused_tcp_port_factory,
    non_loopback_hostaddr
):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    host_addrs = ['127.0.0.1', non_loopback_hostaddr]

    loop = asyncio.get_event_loop()

    receiver = UmdReceiver(hostaddr=host_addrs[0], hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    async with receiver:

        # Send message bytes to receiver and wait for ``on_tally_added`` events
        transport.sendto(uhs500_msg_bytes, (host_addrs[0], udp_port))
        _ = await evt_listener.get()
        while not evt_listener.empty():
            _ = await evt_listener.get()

        assert len(receiver.tallies) == len(uhs500_msg_parsed.displays)

        # Set up to get ``on_tally_updated`` callbacks
        receiver.unbind(evt_listener)
        receiver.bind_async(loop, on_tally_updated=evt_listener.callback)


        # Change bind address and trigger a change
        await receiver.set_hostaddr(host_addrs[1])
        assert receiver.hostaddr == host_addrs[1]

        disp = uhs500_msg_parsed.displays[0]
        disp.brightness = 1

        transport.sendto(uhs500_msg_parsed.build_message(), (host_addrs[1], udp_port))

        evt_args, evt_kwargs = await evt_listener.get()
        evt_tally = evt_args[0]
        assert disp == evt_tally

        # Change bind port and trigger a change
        new_port = unused_tcp_port_factory()
        assert new_port != udp_port

        await receiver.set_hostport(new_port)
        assert receiver.hostport == new_port

        disp.brightness = 2
        transport.sendto(uhs500_msg_parsed.build_message(), (host_addrs[1], new_port))

        evt_args, evt_kwargs = await evt_listener.get()
        evt_tally = evt_args[0]
        assert disp == evt_tally

@pytest.mark.asyncio
async def test_scontrol(faker, udp_endpoint, udp_port):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    loop = asyncio.get_event_loop()

    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_scontrol=evt_listener.callback)

    async with receiver:
        for i in range(100):
            data_len = faker.pyint(min_value=1, max_value=1024)
            control_data = faker.binary(length=data_len)

            msgobj = Message(screen=i, scontrol=control_data)
            transport.sendto(msgobj.build_message(), ('127.0.0.1', udp_port))

            args, kwargs = await evt_listener.get()

            screen, rx_data = args
            assert screen.index == i
            assert rx_data == control_data


@pytest.mark.asyncio
async def test_parse_errors(faker, udp_endpoint, udp_port):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    loop = asyncio.get_event_loop()

    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    msgobj = Message()
    disp = Display(index=0, text='foo')
    msgobj.displays.append(disp)

    async with receiver:
        transport.sendto(msgobj.build_message(), ('127.0.0.1', udp_port))

        _ = await evt_listener.get()

        receiver.unbind(evt_listener)
        receiver.bind_async(loop, on_tally_updated=evt_listener.callback)

        screen = receiver.screens[msgobj.screen]
        rx_disp = screen[disp.index]
        assert rx_disp is receiver.tallies[rx_disp.id]
        assert rx_disp == disp

        for i in range(100):
            num_bytes = faker.pyint(min_value=1, max_value=1024)
            bad_bytes = faker.binary(length=num_bytes)

            with pytest.raises(ParseError):
                receiver.parse_incoming(bad_bytes, ('127.0.0.1', endpoint_port))

            transport.sendto(bad_bytes, ('127.0.0.1', udp_port))

            disp.text = f'foo_{i}'
            transport.sendto(msgobj.build_message(), ('127.0.0.1', udp_port))

            _ = await evt_listener.get()

            assert rx_disp == disp
