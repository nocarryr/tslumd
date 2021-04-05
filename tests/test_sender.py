import asyncio
import pytest

from tslumd import TallyType, TallyColor, Tally, UmdReceiver, UmdSender

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

    async with receiver:
        async with sender:
            # Create initial tallies using text method
            for i in range(100):
                sender.set_tally_text(i, f'Tally-{i}')
                tx_tally = sender.tallies[i]

                evt_args, evt_kwargs = await evt_listener.get()
                rx_tally = evt_args[0]
                assert rx_tally == tx_tally

            # Create one more tally using ``set_tally_color``
            sender.set_tally_color(200, TallyType.lh_tally, TallyColor.GREEN)
            tx_tally = sender.tallies[200]
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
                    sender.set_tally_color(tx_tally.index, tally_type, TallyColor.RED)

                    evt_args, evt_kwargs = await evt_listener.get()
                    rx_tally = evt_args[0]
                    assert rx_tally is receiver.tallies[tx_tally.index]
                    assert rx_tally == tx_tally

            # Change the text of the extra tally from above and check
            sender.set_tally_text(200, 'Tally-200')
            tx_tally = sender.tallies[200]
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
                    sender.set_tally_color(tx_tally.index, tally_type, TallyColor.AMBER)
                sender.set_tally_text(tx_tally.index, f'foo-{tx_tally.index}')

            # Wait for updates from last loop to get to the receiver
            # and check the results
            _ = await evt_listener.get()
            while not evt_listener.empty():
                _ = await evt_listener.get()

            for tx_tally in sender.tallies.values():
                rx_tally = receiver.tallies[tx_tally.index]
                assert rx_tally == tx_tally