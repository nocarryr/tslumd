try:
    from loguru import logger
except ImportError: # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)
import asyncio
from typing import Dict, Tuple, Set, Optional

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from tslumd import Tally, Screen, TallyKey, Message

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
        .. event:: on_tally_added(tally: Tally)

            Fired when a :class:`~.Tally` instance is added to :attr:`tallies`

        .. event:: on_tally_updated(tally: Tally)

            Fired when any :class:`~.Tally` instance has been updated

        .. event:: on_tally_control(tally: Tally, data: bytes)

            Fired when control data has been received for a :class:`~.Tally`

            .. versionadded:: 0.0.3

        .. event:: on_screen_added(screen: Screen)

            Fired when a :class:`~.Screen` instance is added to :attr:`screens`

            .. versionadded:: 0.0.3

        .. event:: on_scontrol(screen: int, data: bytes)

            Fired when a message with :attr:`~.Message.scontrol` data is received

            * ``screen`` : The :attr:`~.Message.screen` from the incoming
              control message
            * ``data`` : The control data

            .. versionadded:: 0.0.2

    """

    DEFAULT_HOST: str = '0.0.0.0' #: The default host address to listen on
    DEFAULT_PORT: int = 65000 #: The default host port to listen on

    screens: Dict[int, Screen]
    """Mapping of :class:`~.Screen` objects by :attr:`~.Screen.index`

    .. versionadded:: 0.0.3
    """

    broadcast_screen: Screen
    """A :class:`~.Screen` instance created using :meth:`.Screen.broadcast`

    .. versionadded:: 0.0.3
    """

    tallies: Dict[TallyKey, Tally]
    """Mapping of :class:`~.Tally` objects by their :attr:`~.Tally.id`

    .. versionchanged:: 0.0.3
        The keys are now a combination of the :class:`~.Screen` and
        :class:`.Tally` indices
    """

    running: bool
    """``True`` if the client / server are running
    """

    loop: asyncio.BaseEventLoop
    """The :class:`asyncio.BaseEventLoop` associated with the instance"""

    _events_ = [
        'on_tally_added', 'on_tally_updated', 'on_tally_control',
        'on_screen_added', 'on_scontrol',
    ]
    def __init__(self, hostaddr: str = DEFAULT_HOST, hostport: int = DEFAULT_PORT):
        self.__hostaddr = hostaddr
        self.__hostport = hostport
        self.screens = {}
        self.broadcast_screen = Screen(0xffff)
        self._bind_screen(self.broadcast_screen)
        self.screens[self.broadcast_screen.index] = self.broadcast_screen
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

    def parse_incoming(self, data: bytes, addr: Tuple[str, int]):
        """Parse data received by the server
        """
        while True:
            message, remaining = Message.parse(data)
            if message.screen not in self.screens:
                screen = Screen(message.screen)
                self.screens[screen.index] = screen
                self._bind_screen(screen)
                self.emit('on_screen_added', screen)
                logger.debug(f'new screen: {screen.index}')
            else:
                screen = self.screens[message.screen]

            if message.is_broadcast:
                for screen in self.screens.values():
                    screen.update_from_message(message)
            else:
                screen.update_from_message(message)
            if not len(remaining):
                break

    def _bind_screen(self, screen: Screen):
        screen.bind(
            on_tally_added=self._on_screen_tally_added,
            on_tally_update=self._on_screen_tally_update,
            on_tally_control=self._on_screen_tally_control,
            on_control=self._on_screen_control,
        )

    def _on_screen_tally_added(self, tally: Tally, **kwargs):
        if tally.id not in self.tallies:
            self.tallies[tally.id] = tally
        self.emit('on_tally_added', tally, **kwargs)

    def _on_screen_tally_update(self, *args, **kwargs):
        self.emit('on_tally_updated', *args, **kwargs)

    def _on_screen_tally_control(self, *args, **kwargs):
        self.emit('on_tally_control', *args, **kwargs)

    def _on_screen_control(self, *args, **kwargs):
        self.emit('on_scontrol', *args, **kwargs)

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
