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
        r = await self.results.get()
        self.results.task_done()
        return r
    def empty(self):
        return self.results.empty()
    async def callback(self, *args, **kwargs):
        await self.results.put((args, kwargs))


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
                for tally_type in TallyType:
                    if tally_type == TallyType.no_tally:
                        continue
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
                for tally_type in TallyType:
                    if tally_type == TallyType.no_tally:
                        continue
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
