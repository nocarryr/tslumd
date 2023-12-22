from __future__ import annotations
try:
    from loguru import logger
except ImportError: # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)
import asyncio
import socket
import argparse
from typing import Tuple, Iterable

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from tslumd import (
    MessageType, Message, Display, TallyColor, TallyType, TallyKey,
    Tally, Screen,
)
from tslumd.tallyobj import StrOrTallyType, StrOrTallyColor
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
        all_off_on_close: Initial value for :attr:`all_off_on_close`

    .. versionchanged:: 0.0.4
        The ``all_off_on_close`` parameter was added
    """

    screens: dict[int, Screen]
    """Mapping of :class:`~.Screen` objects by :attr:`~.Screen.index`

    .. versionadded:: 0.0.3
    """

    tallies: dict[TallyKey, Tally]
    """Mapping of :class:`~.Tally` objects by their :attr:`~.Tally.id`

    Note:
        This should not be altered directly. Use :meth:`add_tally` instead

    .. versionchanged:: 0.0.3
        The keys are now a combination of the :class:`~.Screen` and
        :class:`.Tally` indices
    """

    broadcast_screen: Screen
    """A :class:`~.Screen` instance created using :meth:`.Screen.broadcast`

    .. versionadded:: 0.0.3
    """

    running: bool
    """``True`` if the client / server are running
    """

    loop: asyncio.BaseEventLoop
    """The :class:`asyncio.BaseEventLoop` associated with the instance"""

    tx_interval: float = .3
    """Interval to send tally messages, regardless of state changes
    """

    clients: set[Client]
    """Set of :data:`clients <Client>` to send messages to
    """

    all_off_on_close: bool
    """If ``True``, a broadcast message will be sent before shutdown to turn
    off all tally lights in the system. (default is ``False``)

    .. versionadded:: 0.0.4
    """

    def __init__(self,
                 clients: Iterable[Client]|None = None,
                 all_off_on_close: bool = False):
        self.clients = set()
        if clients is not None:
            for client in clients:
                self.clients.add(client)
        self.all_off_on_close = all_off_on_close
        self.screens = {}
        self.tallies = {}
        self.running = False
        self.loop = asyncio.get_event_loop()
        screen = self.broadcast_screen = Screen.broadcast()
        assert screen.is_broadcast
        self.screens[screen.index] = screen
        self._bind_screen(screen)
        self.update_queue: asyncio.PriorityQueue[TallyKey|Tuple[int, bool]]|None = None
        self.update_task = None
        self.tx_task = None
        self.connected_evt = asyncio.Event()
        self._tx_lock = asyncio.Lock()

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
        await self.update_queue.put((0, False))
        await self.tx_task
        self.tx_task = None
        if self.all_off_on_close:
            logger.debug('sending all off broadcast message')
            await self.send_broadcast_tally(0xffff)
        self.transport.close()
        logger.info('UmdSender closed')

    async def send_scontrol(self, screen_index: int, data: bytes):
        """Send an :attr:`SCONTROL <.Message.scontrol>` message

        Arguments:
            screen_index: The :attr:`~.Message.screen` index for the message
            data: The data to send in the :attr:`~.Message.scontrol` field

        .. versionadded:: 0.0.2
        """
        screen = self.get_or_create_screen(screen_index)
        screen.scontrol = data

    async def send_broadcast_scontrol(self, data: bytes):
        """Send a :attr:`broadcast <.Message.is_broadcast>`
        :attr:`SCONTROL <.Message.scontrol>` message

        Arguments:
            data: The data to send in the :attr:`~.Message.scontrol` field

        .. versionadded:: 0.0.2
        """
        self.broadcast_screen.scontrol = data

    def add_tally(self, tally_id: TallyKey, **kwargs) -> Tally:
        """Create a :class:`~.Tally` object and add it to :attr:`tallies` if
        one does not exist

        If necessary, creates a :class:`~.Screen` using :meth:`get_or_create_screen`

        Arguments:
            tally_id: A tuple of (:attr:`screen_index <.Screen.index>`,
                :attr:`tally_index <.Tally.index>`)
            **kwargs: Keyword arguments passed to create the tally instance

        Raises:
            KeyError: If the given ``tally_id`` already exists

        .. versionchanged:: 0.0.3
            Chaned the ``tally_index`` parameter to ``tally_id``
        """
        if tally_id in self.tallies:
            raise KeyError(f'Tally exists for id {tally_id}')
        screen_index, tally_index = tally_id
        screen = self.get_or_create_screen(screen_index)
        tally = screen.add_tally(tally_index, **kwargs)
        return tally

    def get_or_create_tally(self, tally_id: TallyKey) -> Tally:
        """If a :class:`~.Tally` object matching the given tally id exists,
        return it. Otherwise, create it using :meth:`.Screen.get_or_create_tally`

        This method is similar to :meth:`add_tally` and it can be used to avoid
        exception handling. It does not however take keyword arguments and
        is only intended for object creation.

        .. versionadded:: 0.0.3
        """
        tally = self.tallies.get(tally_id)
        if tally is not None:
            return tally
        screen_index, tally_index = tally_id
        screen = self.get_or_create_screen(screen_index)
        tally = screen.get_or_create_tally(tally_index)
        return tally

    def get_or_create_screen(self, index_: int) -> Screen:
        """Create a :class:`~.Screen` object and add it to :attr:`screens`

        Arguments:
            index_: The screen :attr:`~.Screen.index`

        Raises:
            KeyError: If the given ``index_`` already exists

        .. versionadded:: 0.0.3
        """
        if index_ in self.screens:
            return self.screens[index_]
        screen = Screen(index_)
        self.screens[screen.index] = screen
        self._bind_screen(screen)
        return screen

    def _bind_screen(self, screen: Screen):
        screen.bind(on_tally_added=self._on_screen_tally_added)
        screen.bind_async(self.loop,
            on_tally_update=self.on_tally_updated,
            on_tally_control=self.on_tally_control,
            on_control=self.on_screen_control,
        )

    def set_tally_color(self, tally_id: TallyKey, tally_type: StrOrTallyType, color: StrOrTallyColor):
        """Set the tally color for the given index and tally type

        Uses :meth:`.Tally.set_color`. See the method documentation for details

        Arguments:
            tally_id (TallyKey): A tuple of (:attr:`screen_index <.Screen.index>`,
                :attr:`tally_index <.Tally.index>`)
            tally_type (TallyType or str): :class:`~.common.TallyType` or member
                name as described in :meth:`.Tally.set_color`
            color (TallyColor or str): :class:`~.common.TallyColor` or color
                name as described in :meth:`.Tally.set_color`

        .. versionchanged:: 0.0.3
            Chaned the ``tally_index`` parameter to ``tally_id``

        .. versionchanged:: 0.0.5
            Accept string arguments and match behavior of :meth:`.Tally.set_color`
        """
        if tally_type == TallyType.no_tally:
            raise ValueError()
        tally = self.get_or_create_tally(tally_id)
        tally[tally_type] = color

    def set_tally_text(self, tally_id: TallyKey, text: str):
        """Set the tally text for the given id

        Arguments:
            tally_id: A tuple of (:attr:`screen_index <.Screen.index>`,
                :attr:`tally_index <.Tally.index>`)
            text: The :attr:`~.Tally.text` to set

        .. versionchanged:: 0.0.3
            Chaned the ``tally_index`` parameter to ``tally_id``
        """
        tally = self.get_or_create_tally(tally_id)
        tally.text = text

    async def send_tally_control(self, tally_id: TallyKey, data: bytes):
        """Send :attr:`~.Display.control` data for the given screen and tally index

        Arguments:
            tally_id: A tuple of (:attr:`screen_index <.Screen.index>`,
                :attr:`tally_index <.Tally.index>`)
            control: The control data to send

        .. versionadded:: 0.0.2

        .. versionchanged:: 0.0.3
            Chaned the ``tally_index`` parameter to ``tally_id``
        """
        tally = self.get_or_create_tally(tally_id)
        tally.control = data

    async def send_broadcast_tally_control(self, screen_index: int, data: bytes, **kwargs):
        """Send :attr:`~.Display.control` data as
        :attr:`broadcast <.Display.is_broadcast>` to all listening displays

        Arguments:
            screen_index: The screen :attr:`~.Screen.index`
            **kwargs: Additional keyword arguments to pass to the :class:`~.Tally`
                constructor

        .. versionadded:: 0.0.2

        .. versionchanged:: 0.0.3
            Added the screen_index parameter
        """
        await self.send_broadcast_tally(screen_index, control=data, **kwargs)

    async def send_broadcast_tally(self, screen_index: int, **kwargs):
        """Send a :attr:`broadcast <.Display.is_broadcast>` update
        to all listening displays

        Arguments:
            screen_index: The screen :attr:`~.Screen.index`
            **kwargs: The keyword arguments to pass to the :class:`~.Tally`
                constructor

        .. versionadded:: 0.0.2

        .. versionchanged:: 0.0.3
            Added the screen_index parameter
        """
        screen = self.get_or_create_screen(screen_index)
        tally = screen.broadcast_tally(**kwargs)
        if tally.text == '' or tally.control != b'':
            msg_type = MessageType.control
        else:
            msg_type = MessageType.display
        msg = self._build_message(screen=screen_index)
        disp = Display.from_tally(tally, msg_type=msg_type)
        msg.displays.append(disp)
        async with self._tx_lock:
            await self.send_message(msg)
            screen.unbind(self)
            for oth_tally in screen:
                oth_tally.update_from_display(disp)
            self._bind_screen(screen)

    async def on_tally_updated(self, tally: Tally, props_changed: set[str], **kwargs):
        if self.running:
            if set(props_changed) == set(['control']):
                return
            logger.debug(f'tally update: {tally}')
            await self.update_queue.put(tally.id)

    async def on_tally_control(self, tally: Tally, data: bytes, **kwargs):
        if self.running:
            async with self._tx_lock:
                disp = Display.from_tally(tally, msg_type=MessageType.control)
                assert tally.screen is not None
                msg = self._build_message(
                    screen=tally.screen.index,
                    displays=[disp],
                )
                await self.send_message(msg)


    async def on_screen_control(self, screen: Screen, data: bytes, **kwargs):
        if self.running:
            async with self._tx_lock:
                msg = self._build_message(
                    screen=screen.index,
                    type=MessageType.control,
                    scontrol=data,
                )
                await self.send_message(msg)


    def _on_screen_tally_added(self, tally: Tally, **kwargs):
        self.tallies[tally.id] = tally
        logger.debug(f'new tally: {tally}')

    @logger_catch
    async def tx_loop(self):
        async def get_queue_item(timeout):
            try:
                item = await asyncio.wait_for(self.update_queue.get(), timeout)
                if item[1] is False:
                    return False
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
                if not self._tx_lock.locked():
                    await self.send_full_update()
            else:
                screen_index, _ = item
                ids = set([item])
                self.update_queue.task_done()
                while not self.update_queue.empty():
                    try:
                        item = self.update_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if item is False:
                        self.update_queue.task_done()
                        return
                    _screen_index, _ = item
                    if _screen_index == screen_index:
                        ids.add(item)
                        self.update_queue.task_done()
                    else:
                        await self.update_queue.put(item)
                        break

                msg = self._build_message(screen=screen_index)
                tallies = {i:self.tallies[i] for i in ids}
                async with self._tx_lock:
                    for key in sorted(tallies.keys()):
                        tally = tallies[key]
                        msg.displays.append(Display.from_tally(tally))
                    await self.send_message(msg)

    async def send_message(self, msg: Message):
        for data in msg.build_messages():
            for client in self.clients:
                self.transport.sendto(data, client)

    async def send_full_update(self):
        coros = set()
        for screen in self.screens.values():
            coros.add(self.send_screen_update(screen))
        if not len(coros): # pragma: no cover
            return
        async with self._tx_lock:
            await asyncio.gather(*coros)

    async def send_screen_update(self, screen: Screen):
        if screen.is_broadcast:
            return
        msg = self._build_message(screen=screen.index)
        for tally in screen:
            disp = Display.from_tally(tally)
            msg.displays.append(disp)
        await self.send_message(msg)

    def _build_message(self, **kwargs) -> Message:
        return Message(**kwargs)

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
        addr, port = values.split(':')              # type: ignore
        values = (addr, int(port))
        items = getattr(namespace, self.dest, None)
        if items == [('127.0.0.1', 65000)]:
            items = []
        else:
            items = argparse._copy_items(items)     # type: ignore
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
