import asyncio
import pytest

from tslumd import (
    TallyType, TallyColor, TallyKey, Tally, Screen, UmdReceiver, UmdSender,
    Message, Display,
)

class EventListener:
    def __init__(self):
        self.results = asyncio.Queue()
    async def get(self):
        r = await asyncio.wait_for(self.results.get(), 1)
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
async def test_with_uhs_data(udp_port):

    loop = asyncio.get_event_loop()

    sender = UmdSender(clients=[('127.0.0.1', udp_port)])
    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    screen_index = 1

    async with receiver:
        async with sender:
            # Create initial tallies using text method
            for i in range(100):
                t_id = (screen_index, i)
                sender.set_tally_text(t_id, f'Tally-{i}')
                tx_tally = sender.tallies[t_id]
                screen = sender.screens[screen_index]
                assert screen[i] is tx_tally

                evt_args, evt_kwargs = await evt_listener.get()
                rx_tally = evt_args[0]
                assert rx_tally == tx_tally

            # Create one more tally using ``set_tally_color``
            t_id = (screen_index, 200)
            sender.set_tally_color(t_id, TallyType.lh_tally, TallyColor.GREEN)
            tx_tally = sender.tallies[t_id]
            assert screen[200] is tx_tally
            evt_args, evt_kwargs = await evt_listener.get()
            rx_tally = evt_args[0]
            assert rx_tally == tx_tally

            # Allow the sender to do a full refresh.  Nothing should have changed
            await asyncio.sleep(sender.tx_interval)
            assert evt_listener.empty()

            # Connect to ``on_tally_updated`` events
            receiver.unbind(evt_listener)
            receiver.bind_async(loop, on_tally_updated=evt_listener.callback)


            # Change each tally/tally_type color to red and check the received values
            for tx_tally in sender.tallies.values():
                for tally_type in TallyType.all():
                    sender.set_tally_color(tx_tally.id, tally_type, TallyColor.RED)

                    evt_args, evt_kwargs = await evt_listener.get()
                    rx_tally = evt_args[0]
                    assert rx_tally is receiver.tallies[tx_tally.id]
                    assert rx_tally == tx_tally

            # Change the text of the extra tally from above and check
            t_id = (screen_index, 200)
            sender.set_tally_text(t_id, 'Tally-200')
            tx_tally = sender.tallies[t_id]
            evt_args, evt_kwargs = await evt_listener.get()
            rx_tally = evt_args[0]
            assert rx_tally == tx_tally

            # Let the sender to another full refresh
            await asyncio.sleep(sender.tx_interval)
            assert evt_listener.empty()

            # Change all tally/tally_type colors, but don't wait for results yet
            for tx_tally in sender.tallies.values():
                for tally_type in TallyType.all():
                    sender.set_tally_color(tx_tally.id, tally_type, TallyColor.AMBER)
                sender.set_tally_text(tx_tally.id, f'foo-{tx_tally.index}')

            # Wait for updates from last loop to get to the receiver
            # and check the results
            _ = await evt_listener.get()
            while not evt_listener.empty():
                _ = await evt_listener.get()

            for tx_tally in sender.tallies.values():
                rx_tally = receiver.tallies[tx_tally.id]
                assert rx_tally == tx_tally

@pytest.mark.asyncio
async def test_tally_type_variations(udp_port):

    loop = asyncio.get_event_loop()

    sender = UmdSender(clients=[('127.0.0.1', udp_port)])
    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    tally_listener = EventListener()
    receiver.bind_async(loop, on_tally_updated=tally_listener.callback)

    tally_type_strs = ('rh', 'txt', 'lh')
    tally_types = (TallyType.rh_tally, TallyType.txt_tally, TallyType.lh_tally)


    def get_tally_colors(tally):
        d = {}
        for tt in tally_types:
            d[tt] = tally[tt]
        return d

    async def wait_for_rx(tally_type):
        tally_types = set()
        if not isinstance(tally_type, TallyType):
            tally_type = TallyType.from_str(tally_type)
        if tally_type.is_iterable:
            for tt in tally_type:
                tally_types.add(tt.name)
        else:
            tally_types.add(tally_type.name)
        props = set()
        for _ in range(len(tally_types)):
            evt_args, evt_kwargs = await tally_listener.get()
            props |= evt_args[1]
            if props == tally_types:
                break
        assert props == tally_types

    screen_index = 1

    async with receiver:
        async with sender:

            for i in range(10):
                t_id = (screen_index, i)
                expected = {key:TallyColor.OFF for key in tally_types}

                tally = None
                rx_tally = None

                for tt_str, tt in zip(tally_type_strs, tally_types):

                    sender.set_tally_color(t_id, tt_str, TallyColor.RED)
                    expected[tt] = TallyColor.RED

                    tally = sender.tallies[t_id]
                    assert get_tally_colors(tally) == expected

                    if rx_tally is None:
                        evt_args, evt_kwargs = await evt_listener.get()
                        rx_tally = evt_args[0]
                        assert rx_tally == tally
                    else:
                        await wait_for_rx(tt)
                        assert get_tally_colors(rx_tally) == expected

                    sender.set_tally_color(t_id, tt, TallyColor.GREEN)
                    expected[tt] = TallyColor.GREEN
                    assert get_tally_colors(tally) == expected

                    await wait_for_rx(tt)
                    assert get_tally_colors(rx_tally) == expected

                    sender.set_tally_color(t_id, tt_str, 'off')
                    expected[tt] = TallyColor.OFF
                    assert get_tally_colors(tally) == expected

                    await wait_for_rx(tt)
                    assert get_tally_colors(rx_tally) == expected

                    sender.set_tally_color(t_id, tt, 'red')
                    expected[tt] = TallyColor.RED
                    assert get_tally_colors(tally) == expected

                    await wait_for_rx(tt)
                    assert get_tally_colors(rx_tally) == expected


                sender.set_tally_color(t_id, 'all', 'off')
                expected = {key:TallyColor.OFF for key in tally_types}
                assert get_tally_colors(tally) == expected
                assert tally['all'] == TallyColor.OFF

                await wait_for_rx('rh|txt|lh')
                assert get_tally_colors(rx_tally) == expected

                sender.set_tally_color(t_id, 'lh|rh', 'red')
                expected[TallyType.rh_tally] = TallyColor.RED
                expected[TallyType.lh_tally] = TallyColor.RED
                assert get_tally_colors(tally) == expected
                assert tally['all'] == TallyColor.RED

                await wait_for_rx('lh|rh')
                assert get_tally_colors(rx_tally) == expected

                sender.set_tally_color(t_id, 'txt', 'green')
                expected[TallyType.txt_tally] = TallyColor.GREEN
                assert get_tally_colors(tally) == expected

                await wait_for_rx('txt')
                assert get_tally_colors(rx_tally) == expected

                assert tally['all'] == tally['lh|txt'] == tally['rh|txt'] == TallyColor.AMBER


@pytest.mark.asyncio
async def test_broadcast_display(udp_port):
    loop = asyncio.get_event_loop()

    sender = UmdSender(clients=[('127.0.0.1', udp_port)])
    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=evt_listener.callback)

    async def wait_for_receiver():
        _ = await evt_listener.get()
        while not evt_listener.empty():
            _ = await evt_listener.get()

        await asyncio.sleep(sender.tx_interval)
        assert evt_listener.empty()

    color_kw = {attr:TallyColor.RED for attr in ['rh_tally', 'txt_tally', 'lh_tally']}

    screen_index = 1

    async with receiver:
        async with sender:
            # Create initial tallies
            for i in range(10):
                t_id = (screen_index, i)
                tx_tally = sender.add_tally(t_id, **color_kw)
                screen = sender.screens[screen_index]
                assert screen[i] is tx_tally
                tx_tally.text = f'Tally-{i}'

                evt_args, evt_kwargs = await evt_listener.get()
                rx_tally = evt_args[0]
                assert rx_tally == tx_tally

            # Connect to ``on_tally_updated`` events
            receiver.unbind(evt_listener)
            receiver.bind_async(loop, on_tally_updated=evt_listener.callback)

            # Send a broadcast tally for each color setting all TallyType's to it
            for color in TallyColor:
                color_kw = {k:color for k in color_kw.keys()}
                await sender.send_broadcast_tally(screen_index, **color_kw)
                await wait_for_receiver()

                # Check the tally colors and make sure the text values remained
                for rx_tally in receiver.tallies.values():
                    tx_tally = sender.tallies[rx_tally.id]
                    assert rx_tally.text == tx_tally.text == f'Tally-{rx_tally.index}'
                    assert rx_tally.rh_tally == tx_tally.rh_tally == color
                    assert rx_tally.txt_tally == tx_tally.txt_tally == color
                    assert rx_tally.lh_tally == tx_tally.lh_tally == color


            # Broadcast all colors to "OFF" and set all names to 'foo'
            color_kw = {k:TallyColor.OFF for k in color_kw.keys()}
            await sender.send_broadcast_tally(screen_index, text='foo', **color_kw)
            await wait_for_receiver()

            # Check the tally colors and text values
            for rx_tally in receiver.tallies.values():
                tx_tally = sender.tallies[rx_tally.id]
                assert rx_tally.text == tx_tally.text == 'foo'
                assert rx_tally.rh_tally == tx_tally.rh_tally == TallyColor.OFF
                assert rx_tally.txt_tally == tx_tally.txt_tally == TallyColor.OFF
                assert rx_tally.lh_tally == tx_tally.lh_tally == TallyColor.OFF



            # Send broadcast tally control messages
            for control_data in [b'foo', b'bar', b'baz']:
                await sender.send_broadcast_tally(screen_index, control=control_data)
                await wait_for_receiver()

                # Check for the correct control data and ensure other values
                # remain unchanged
                for rx_tally in receiver.tallies.values():
                    tx_tally = sender.tallies[rx_tally.id]
                    assert rx_tally.control == tx_tally.control == control_data
                    assert rx_tally.text == tx_tally.text == 'foo'
                    assert rx_tally.rh_tally == tx_tally.rh_tally == TallyColor.OFF
                    assert rx_tally.txt_tally == tx_tally.txt_tally == TallyColor.OFF
                    assert rx_tally.lh_tally == tx_tally.lh_tally == TallyColor.OFF

            # Do the same as above, but using the `sender.send_broadcast_tally_control` method
            # and change one tally color
            for control_data in [b'abc', b'def', b'ghi']:
                await sender.send_broadcast_tally_control(screen_index, control_data, rh_tally=TallyColor.RED)

                await wait_for_receiver()

                # Check for the correct control data and ensure other values
                for rx_tally in receiver.tallies.values():
                    tx_tally = sender.tallies[rx_tally.id]
                    assert rx_tally.control == tx_tally.control == control_data
                    assert rx_tally.text == tx_tally.text == 'foo'
                    assert rx_tally.rh_tally == tx_tally.rh_tally == TallyColor.RED
                    assert rx_tally.txt_tally == tx_tally.txt_tally == TallyColor.OFF
                    assert rx_tally.lh_tally == tx_tally.lh_tally == TallyColor.OFF



@pytest.mark.asyncio
async def test_scontrol(faker, udp_port):
    loop = asyncio.get_event_loop()

    sender = UmdSender(clients=[('127.0.0.1', udp_port)])
    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    evt_listener = EventListener()
    receiver.bind_async(loop, on_scontrol=evt_listener.callback)
    bc_listener = EventListener()
    receiver.broadcast_screen.bind_async(loop, on_control=bc_listener.callback)

    async with receiver:
        async with sender:
            for i in range(100):
                data_len = faker.pyint(min_value=1, max_value=1024)
                control_data = faker.binary(length=data_len)

                await sender.send_scontrol(screen_index=i, data=control_data)

                evt_args, evt_kwargs = await evt_listener.get()

                rx_screen, rx_data = evt_args
                assert rx_screen.index == i
                assert rx_data == control_data

                # Send broadcast
                await sender.send_broadcast_scontrol(data=control_data)

                # Wait for the broadcast screen
                evt_args, evt_kwargs = await bc_listener.get()
                rx_screen, rx_data = evt_args
                assert rx_screen is receiver.broadcast_screen
                assert rx_data == control_data

                # Wait for each currently existing screen
                num_screens = i+1
                for j in range(num_screens):
                    evt_args, evt_kwargs = await evt_listener.get()
                    rx_screen, rx_data = evt_args
                    assert rx_data == control_data


@pytest.mark.asyncio
async def test_disp_control(faker, udp_port):
    loop = asyncio.get_event_loop()

    sender = UmdSender(clients=[('127.0.0.1', udp_port)])
    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    add_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=add_listener.callback)

    tally_listener = EventListener()
    receiver.bind_async(loop, on_tally_control=tally_listener.callback)

    screen_index = 1

    async with receiver:
        async with sender:
            for i in range(100):
                t_id = (screen_index, i)
                sender.set_tally_text(t_id, f'Tally-{i}')
                tx_tally = sender.tallies[t_id]

                evt_args, evt_kwargs = await add_listener.get()
                rx_tally = evt_args[0]
                assert rx_tally == tx_tally


                data_len = faker.pyint(min_value=1, max_value=1024)
                control_data = faker.binary(length=data_len)

                await sender.send_tally_control(t_id, control_data)
                assert tx_tally.control == control_data

                evt_args, evt_kwargs = await tally_listener.get()
                _rx_tally, rx_data = evt_args
                assert _rx_tally is rx_tally

                assert rx_data == rx_tally.control == tx_tally.control == control_data


            t_id = (screen_index, 200)
            data_len = faker.pyint(min_value=1, max_value=1024)
            control_data = faker.binary(length=data_len)
            await sender.send_tally_control(t_id, control_data)

            tx_tally = sender.tallies[t_id]

            evt_args, evt_kwargs = await add_listener.get()
            rx_tally = evt_args[0]
            assert rx_tally.control == tx_tally.control == control_data
            assert rx_tally == tx_tally

@pytest.mark.asyncio
async def test_queued_updates_are_separate_messages(udp_endpoint, udp_port):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    loop = asyncio.get_event_loop()

    sender = UmdSender(clients=[('127.0.0.1', endpoint_port)])

    screens = {}

    async with sender:
        # Create 10 screens with 10 tallies each
        # and trigger an update by `set_tally_text`.
        #
        # Don't await within the loop so the sender.update_queue gets filled up
        for screen_index in range(10):
            screen = Screen(screen_index)
            screens[screen_index] = screen
            for tally_index in range(10):
                t_id = (screen_index, tally_index)
                txt = f'Tally-{t_id}'
                sender.set_tally_text(t_id, txt)

        # Now give the `sender.tx_loop` a chance to process the queue
        await asyncio.sleep(.1)

        # Check each message to make sure they only have a single screen's data.
        assert not protocol.queue.empty()
        while not protocol.queue.empty():
            data, addr = await protocol.queue.get()
            protocol.queue.task_done()

            parsed, _ = Message.parse(data)
            print(f'screen {parsed.screen} disp_len={len(parsed.displays)}')
            # print(parsed)
            screen = screens[parsed.screen]
            screen.update_from_message(parsed)

        # Ensure nothing got packed incorrectly by the unique tally.id in the text field
        for screen in screens.values():
            for tally in screen:
                assert tally.text == f'Tally-{tally.id}'
                assert len(screen.tallies) == 10

@pytest.mark.asyncio
async def test_all_off_on_close(faker, udp_port):
    loop = asyncio.get_event_loop()

    sender = UmdSender(
        clients=[('127.0.0.1', udp_port)],
        all_off_on_close=True,
    )
    receiver = UmdReceiver(hostaddr='127.0.0.1', hostport=udp_port)

    add_listener = EventListener()
    receiver.bind_async(loop, on_tally_added=add_listener.callback)

    tally_listener = EventListener()
    receiver.bind_async(loop, on_tally_updated=tally_listener.callback)

    async with receiver:
        async with sender:
            for screen_index in range(10):
                for i in range(10):
                    t_id = (screen_index, i)
                    sender.set_tally_text(t_id, f'Tally-{i}')
                    tx_tally = sender.tallies[t_id]

                    evt_args, evt_kwargs = await add_listener.get()
                    rx_tally = evt_args[0]
                    assert rx_tally == tx_tally

                    for ttype in TallyType.all():
                        setattr(tx_tally, ttype.name, TallyColor.RED)

                        evt_args, evt_kwargs = await tally_listener.get()
                        assert getattr(rx_tally, ttype.name) == TallyColor.RED

        # Sender is closed and should have broadcast "all-off"
        _ = await asyncio.wait_for(tally_listener.get(), timeout=1)
        while not tally_listener.empty():
            _ = await tally_listener.get()
        for rx_tally in receiver.tallies.values():
            assert rx_tally.rh_tally == TallyColor.OFF
            assert rx_tally.txt_tally == TallyColor.OFF
            assert rx_tally.lh_tally == TallyColor.OFF

@pytest.mark.asyncio
async def test_broadcast_screen_updates(udp_endpoint, udp_port):
    transport, protocol, endpoint_port = udp_endpoint
    assert udp_port != endpoint_port

    loop = asyncio.get_event_loop()

    sender = UmdSender(clients=[('127.0.0.1', endpoint_port)])

    screens = {}
    bc_screen = Screen.broadcast()

    async with sender:

        # Create 10 screens with 10 tallies each and set their initial values to
        # `text='Tally-{tally.id}', rh_tally=TallyColor.RED`
        for screen_index in range(10):
            screen = Screen(screen_index)
            screens[screen_index] = screen
            for tally_index in range(10):
                t_id = (screen_index, tally_index)
                txt = f'Tally-{t_id}'
                sender.set_tally_text(t_id, txt)
                tx_tally = sender.tallies[t_id]

                # Wait for data from the sender and parse it manually into the screen
                data, addr = await protocol.queue.get()
                protocol.queue.task_done()
                parsed, _ = Message.parse(data)
                assert parsed.screen == screen_index
                screen.update_from_message(parsed)

                assert tally_index in screen
                tally = screen[tally_index]
                assert tally.text == txt

        # For each screen, send a broadcast tally setting `rh_tally` to `RED`
        for screen_index, screen in screens.items():
            await sender.send_broadcast_tally(screen_index, rh_tally=TallyColor.RED)

            # Wait for data and parse it again into the screen
            data, addr = await protocol.queue.get()
            protocol.queue.task_done()

            parsed, _ = Message.parse(data)
            assert parsed.screen == screen_index
            screen.update_from_message(parsed)

            for tally in screen:
                assert tally.rh_tally == TallyColor.RED

        # For each tally, send a screen-broadcast (not tally-broadcast) setting
        # `text='Broadcast-{tally.index}', rh_tally=TallyColor.GREEN`
        for tally_index in range(10):
            t_id = (0xffff, tally_index)
            txt = f'Broadcast-{tally_index}'
            tally = sender.broadcast_screen.add_tally(tally_index, text=txt)#, rh_tally=TallyColor.GREEN)
            tally.rh_tally = TallyColor.GREEN

            # Wait for data and parse it into a separate broadcast screen
            data, addr = await protocol.queue.get()
            protocol.queue.task_done()
            parsed, _ = Message.parse(data)
            assert parsed.screen == 0xffff
            bc_screen.update_from_message(parsed)

            assert tally_index in bc_screen
            bc_tally = bc_screen[tally_index]
            assert bc_tally.id == t_id
            assert bc_tally.text == txt
            assert bc_tally.rh_tally == TallyColor.GREEN

            # Parse the same screen-broadcast message into each of the 10 normal screens
            # This **should** change the tally values as well
            # (unless I'm mis-interpreting the specification)
            for screen in screens.values():
                screen.update_from_message(parsed)

                sc_tally = screen[tally_index]

                assert sc_tally.text == txt
                assert sc_tally.rh_tally == TallyColor.GREEN


        # Wait for the periodic refresh from the sender which **should** send
        # the original tally states and not the broadcast ones (?)
        #
        # That's unclear, but we definitely don't want the broadcast screen
        # sending constant updates, so let's check that doesn't happen.
        # (even though that isn't specifically stated either)
        assert protocol.queue.empty()
        await asyncio.sleep(sender.tx_interval * 2)

        assert not protocol.queue.empty()
        while not protocol.queue.empty():
            data, addr = await protocol.queue.get()
            protocol.queue.task_done()
            parsed, _ = Message.parse(data)

            assert parsed.screen in screens
            assert parsed.screen != 0xffff

            screen = screens[parsed.screen]
            screen.update_from_message(parsed)

            for tally in screen:
                assert tally.text == f'Tally-{tally.id}'
                assert tally.rh_tally == TallyColor.RED
