try:
    from loguru import logger
except ImportError: # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)
import asyncio
import socket
import argparse
from typing import Dict, Tuple, Set, Optional, Sequence

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from tslumd import Message, Display, TallyColor, TallyType, Tally
from tslumd.utils import logger_catch

Client = Tuple[str, int] #: A network client as a tuple of ``(address, port)``

__all__ = ('Client', 'UmdSender')

class UmdProtocol(asyncio.DatagramProtocol):
    def __init__(self, sender: 'UmdSender'):
        self.sender = sender
    def connection_made(self, transport):
        logger.debug(f'transport={transport}')
        self.transport = transport
        self.sender.connected_evt.set()
    def datagram_received(self, data, addr): # pragma: no cover
        pass

class UmdSender(Dispatcher):
    """Send UMD Messages

    Messages are sent immediately when a change is made to any of the
    :class:`~.Tally` objects in :attr:`tallies`. These can be added by using
    the :meth:`add_tally` method.

    Alternatively, the :meth:`set_tally_color` and :meth:`set_tally_text` methods
    may be used.

    Arguments:
        clients: Intitial value for :attr:`clients`
    """

    tallies: Dict[int, Tally]
    """Mapping of :class:`Tally` objects using the :attr:`~Tally.index` as keys

    Note:
        This should not be altered directly. Use :meth:`add_tally` instead
    """

    running: bool
    """``True`` if the client / server are running
    """

    loop: asyncio.BaseEventLoop
    """The :class:`asyncio.BaseEventLoop` associated with the instance"""

    tx_interval: float = .3
    """Interval to send tally messages, regardless of state changes
    """

    clients: Set[Client]
    """Set of :data:`clients <Client>` to send messages to
    """

    def __init__(self, clients: Optional[Set[Client]] = None):
        self.clients = set()
        if clients is not None:
            for client in clients:
                self.clients.add(client)
        self.tallies = {}
        self.running = False
        self.loop = asyncio.get_event_loop()
        self.update_queue = asyncio.Queue()
        self.update_task = None
        self.tx_task = None
        self.connected_evt = asyncio.Event()

    async def open(self):
        """Open connections and begin data transmission
        """
        if self.running:
            return
        self.connected_evt.clear()
        logger.debug('UmdSender.open()')
        self.running = True
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: UmdProtocol(self),
            family=socket.AF_INET,
        )
        self.tx_task = asyncio.create_task(self.tx_loop())
        logger.info('UmdSender running')

    async def close(self):
        """Stop sending to clients and close connections
        """
        if not self.running:
            return
        logger.debug('UmdSender.close()')
        self.running = False
        await self.update_queue.put(False)
        await self.tx_task
        self.tx_task = None
        self.transport.close()
        logger.info('UmdSender closed')

    def add_tally(self, index_: int, **kwargs) -> Tally:
        """Create a :class:`~.Tally` object and add it to :attr:`tallies`

        Arguments:
            index_: The tally :attr:`~.Tally.index`
            **kwargs: Keyword arguments passed to create the tally instance

        Raises:
            KeyError: If the given ``index_`` already exists
        """
        if index_ in self.tallies:
            raise KeyError(f'Tally exists for index {index_}')
        tally = Tally(index_, **kwargs)
        self.tallies[index_] = tally
        tally.bind_async(self.loop, on_update=self.on_tally_updated)
        logger.debug(f'new tally: {tally}')
        return tally

    def set_tally_color(self, index_: int, tally_type: TallyType, color: TallyColor):
        """Set the tally color for the given index and tally type

        Arguments:
            index_: The tally :attr:`~.Tally.index`
            tally_type: A member of :class:`~.common.TallyType` specifying the
                tally lamp within the display
            color: The member of :class:`~.common.TallyColor` to set
        """
        if tally_type == TallyType.no_tally:
            raise ValueError()
        if index_ not in self.tallies:
            tally = self.add_tally(index_)
        else:
            tally = self.tallies[index_]
        attr = tally_type.name
        setattr(tally, attr, color)

    def set_tally_text(self, index_: int, text: str):
        """Set the tally text for the given index

        Arguments:
            index_: The tally :attr:`~.Tally.index`
            text: The :attr:`~.Tally.text` to set
        """
        if index_ not in self.tallies:
            tally = self.add_tally(index_)
        else:
            tally = self.tallies[index_]
        tally.text = text

    async def on_tally_updated(self, tally: Tally, props_changed: Sequence[str], **kwargs):
        if self.running:
            logger.debug(f'tally update: {tally}')
            await self.update_queue.put(tally.index)

    @logger_catch
    async def tx_loop(self):
        async def get_queue_item(timeout):
            try:
                item = await asyncio.wait_for(self.update_queue.get(), timeout)
            except asyncio.TimeoutError:
                item = None
            return item

        await self.connected_evt.wait()

        while self.running:
            item = await get_queue_item(self.tx_interval)
            if item is False:
                self.update_queue.task_done()
                break
            elif item is None:
                await self.send_full_update()
            else:
                indices = set()
                indices.add(item)
                self.update_queue.task_done()
                while not self.update_queue.empty():
                    try:
                        item = self.update_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if item is False:
                        self.update_queue.task_done()
                        return
                    indices.add(item)
                    self.update_queue.task_done()
                msg = self._build_message()
                tallies = {i:self.tallies[i] for i in indices}
                for key in sorted(tallies.keys()):
                    tally = tallies[key]
                    msg.displays.append(Display.from_tally(tally))
                await self.send_message(msg)

    async def send_message(self, msg: Message):
        data = msg.build_message()
        for client in self.clients:
            self.transport.sendto(data, client)

    async def send_full_update(self):
        msg = self._build_message()
        for tally in self.tallies.values():
            disp = Display.from_tally(tally)
            msg.displays.append(disp)
        await self.send_message(msg)

    def _build_message(self) -> Message:
        return Message()

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()


class ClientArgAction(argparse._AppendAction):
    _default_help = ' '.join([
        'Client(s) to send UMD messages to formatted as "<hostaddr>:<port>".',
        'Multiple arguments may be given.',
        'If nothing is provided, defaults to "127.0.0.1:65000"',
    ])
    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=[('127.0.0.1', 65000)],
                 type_=str,
                 choices=None,
                 required=False,
                 help=_default_help,
                 metavar=None):
        super().__init__(
            option_strings, dest, nargs, const, default,
            type_, choices, required, help, metavar,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        addr, port = values.split(':')
        values = (addr, int(port))
        items = getattr(namespace, self.dest, None)
        if items == [('127.0.0.1', 65000)]:
            items = []
        else:
            items = argparse._copy_items(items)
        items.append(values)
        setattr(namespace, self.dest, items)

def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        '-c', '--client', dest='clients', action=ClientArgAction#, type=str,
    )
    args = p.parse_args()

    logger.info(f'Sending to clients: {args.clients!r}')

    loop = asyncio.get_event_loop()
    sender = UmdSender(clients=args.clients)
    loop.run_until_complete(sender.open())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(sender.close())
    finally:
        loop.close()

if __name__ == '__main__':
    main()
