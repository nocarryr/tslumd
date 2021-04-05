try:
    from loguru import logger
except ImportError: # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)
import asyncio
from typing import Dict, Tuple, Set, Optional

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from tslumd import Tally, TallyColor, MessageType, Message, Display
from tslumd.utils import logger_catch

__all__ = ('UmdReceiver',)




class UmdProtocol(asyncio.DatagramProtocol):
    def __init__(self, receiver: 'UmdReceiver'):
        self.receiver = receiver
    def connection_made(self, transport):
        logger.debug(f'transport={transport}')
        self.transport = transport
        self.receiver.connected_evt.set()
    def datagram_received(self, data, addr):
        self.receiver.parse_incoming(data, addr)


class UmdReceiver(Dispatcher):
    """Receiver for UMD messages

    Arguments:
        hostaddr (str): The local host address to bind the server to. Defaults
            to :attr:`DEFAULT_HOST`
        hostport (int): The port to listen on. Defaults to :attr:`DEFAULT_PORT`

    :Events:
        .. on_tally_added(tally: Tally)

            Fired when a :class:`~.Tally` instance is added to :attr:`tallies`

        .. on_tally_updated(tally: Tally)

            Fired when any :class:`~.Tally` instance has been updated

        .. on_scontrol(screen: int, data: bytes)

            Fired when a message with :attr:`~.Message.scontrol` data is received

            * ``screen`` : The :attr:`~.Message.screen` from the incoming
              control message
            * ``data`` : The control data

    """

    DEFAULT_HOST: str = '0.0.0.0' #: The default host address to listen on
    DEFAULT_PORT: int = 65000 #: The default host port to listen on

    tallies: Dict[int, Tally]
    """Mapping of :class:`~.Tally` objects using
    the :attr:`~.Tally.index` as keys
    """

    running: bool
    """``True`` if the client / server are running
    """

    loop: asyncio.BaseEventLoop
    """The :class:`asyncio.BaseEventLoop` associated with the instance"""

    _events_ = ['on_tally_added', 'on_tally_updated', 'on_scontrol']
    def __init__(self, hostaddr: str = DEFAULT_HOST, hostport: int = DEFAULT_PORT):
        self.__hostaddr = hostaddr
        self.__hostport = hostport
        self.tallies = {}
        self.loop = asyncio.get_event_loop()
        self.running = False
        self._connect_lock = asyncio.Lock()
        self.connected_evt = asyncio.Event()

    @property
    def hostaddr(self) -> str:
        """The local host address to bind the server to
        """
        return self.__hostaddr

    @property
    def hostport(self) -> int:
        """The port to listen on
        """
        return self.__hostport

    async def open(self):
        """Open the server
        """
        async with self._connect_lock:
            if self.running:
                return
            logger.debug('UmdReceiver.open()')
            self.running = True
            self.connected_evt.clear()
            self.transport, self.protocol = await self.loop.create_datagram_endpoint(
                lambda: UmdProtocol(self),
                local_addr=(self.hostaddr, self.hostport),
                reuse_port=True,
            )
            await self.connected_evt.wait()
            logger.info('UmdReceiver running')

    async def close(self):
        """Close the server
        """
        async with self._connect_lock:
            if not self.running:
                return
            logger.debug('UmdReceiver.close()')
            self.running = False
            self.transport.close()
            self.connected_evt.clear()
            logger.info('UmdReceiver closed')

    async def set_bind_address(self, hostaddr: str, hostport: int):
        """Set the :attr:`hostaddr` and :attr:`hostport` and restart the server
        """
        if hostaddr == self.hostaddr and hostport == self.hostport:
            return
        running = self.running
        if running:
            await self.close()
        self.__hostaddr = hostaddr
        self.__hostport = hostport
        if running:
            await self.open()

    async def set_hostaddr(self, hostaddr: str):
        """Set the :attr:`hostaddr` and restart the server
        """
        await self.set_bind_address(hostaddr, self.hostport)

    async def set_hostport(self, hostport: int):
        """Set the :attr:`hostport` and restart the server
        """
        await self.set_bind_address(self.hostaddr, hostport)

    @logger_catch
    def parse_incoming(self, data: bytes, addr: Tuple[str, int]):
        """Parse data received by the server
        """
        while True:
            message, remaining = Message.parse(data)
            if message.type == MessageType.control:
                self.emit('on_scontrol', message.screen, message.scontrol)
            else:
                for display in message.displays:
                    self.update_display(display)
            if not len(remaining):
                break

    def update_display(self, rx_display: Display):
        """Update or create a :class:`~.Tally` from data received
        by the server
        """
        if rx_display.index not in self.tallies:
            tally = Tally.from_display(rx_display)
            self.tallies[rx_display.index] = tally
            logger.debug(f'New Tally: {tally}')
            self.emit('on_tally_added', self.tallies[rx_display.index])
            return
        tally = self.tallies[rx_display.index]
        changed = tally.update_from_display(rx_display)
        if changed:
            self.emit('on_tally_updated', tally)

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    umd = UmdReceiver()

    loop.run_until_complete(umd.open())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(umd.close())
    finally:
        loop.close()
