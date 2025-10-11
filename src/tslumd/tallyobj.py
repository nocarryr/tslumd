from __future__ import annotations
try:
    from loguru import logger   # type: ignore[missing-import]
except ImportError:             # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)
from typing import Union, Tuple, Iterator, cast, TYPE_CHECKING

from pydispatch import Dispatcher, Property

from tslumd import MessageType, TallyType, TallyColor, TallyKey
if TYPE_CHECKING:
    from .messages import Display, Message

StrOrTallyType = Union[str, TallyType]
StrOrTallyColor = Union[str, TallyColor]

__all__ = ('Tally', 'Screen')

class Tally(Dispatcher):
    """A single tally object

    Properties:
        rh_tally (TallyColor): State of the :term:`right-hand tally <rh_tally>` indicator
        txt_tally (TallyColor): State of the :term:`text tally <txt_tally>` indicator
        lh_tally (TallyColor): State of the :term:`left-hand tally <lh_tally>` indicator
        brightness (int): Tally indicator brightness from 0 to 3
        text (str): Text to display
        control (bytes): Any control data received for the tally indicator
        normalized_brightness (float): The :attr:`brightness` value normalized
            as a float from ``0.0`` to ``1.0``

    :Events:
        .. event:: on_update(instance: Tally, props_changed: set[str])

            Fired when any property changes

        .. event:: on_control(instance: Tally, data: bytes)

            Fired when control data is received for the tally indicator

    .. versionadded:: 0.0.2
        The :event:`on_control` event

    .. versionchanged:: 0.0.5
        Added container emulation
    """
    screen: Screen|None
    """The parent :class:`Screen` this tally belongs to

    .. versionadded:: 0.0.3
    """
    rh_tally = Property(TallyColor.OFF)
    txt_tally = Property(TallyColor.OFF)
    lh_tally = Property(TallyColor.OFF)
    brightness = Property(3)
    normalized_brightness = Property(1.)
    text = Property('')
    control = Property(b'')
    _events_ = ['on_update', 'on_control']
    _prop_attrs = ('rh_tally', 'txt_tally', 'lh_tally', 'brightness', 'text', 'control')
    def __init__(self, index_, **kwargs):
        self.screen = kwargs.get('screen')
        self.__index = index_
        if self.screen is not None:
            self.__id = (self.screen.index, self.__index)
        else:
            self.__id = None
        self._updating_props = False
        self.update(**kwargs)
        self.bind(**{prop:self._on_prop_changed for prop in self._prop_attrs})

    @property
    def index(self) -> int:
        """Index of the tally object from 0 to 65534 (``0xfffe``)
        """
        return self.__index

    @property
    def id(self) -> TallyKey:
        """A key to uniquely identify a :class:`Tally` / :class:`Screen`
        combination.

        Tuple of (:attr:`Screen.index`, :attr:`Tally.index`)

        Raises:
            ValueError: If the :attr:`Tally.screen` is ``None``

        .. versionadded:: 0.0.3
        """
        if self.__id is None:
            raise ValueError(f'Cannot create id for Tally without a screen ({self!r})')
        return self.__id

    @property
    def is_broadcast(self) -> bool:
        """``True`` if the tally is to be "broadcast", meaning sent to all
        :attr:`display indices<.messages.Display.index>`.

        (if the :attr:`index` is ``0xffff``)

        .. versionadded:: 0.0.2
        """
        return self.index == 0xffff

    @classmethod
    def broadcast(cls, **kwargs) -> Tally:
        """Create a :attr:`broadcast <is_broadcast>` tally

        (with :attr:`index` set to ``0xffff``)

        .. versionadded:: 0.0.2
        """
        return cls(0xffff, **kwargs)

    @classmethod
    def from_display(cls, display: Display, **kwargs) -> Tally:
        """Create an instance from the given :class:`~.messages.Display` object
        """
        attrs = set(cls._prop_attrs)
        if display.type.name == 'control':
            attrs.discard('text')
        else:
            attrs.discard('control')
        kw = kwargs.copy()
        kw.update({attr:getattr(display, attr) for attr in cls._prop_attrs})
        return cls(display.index, **kw)

    def set_color(self, tally_type: StrOrTallyType, color: StrOrTallyColor):
        """Set the color property (or properties) for the given TallyType

        Sets the :attr:`rh_tally`, :attr:`txt_tally` or :attr:`lh_tally`
        properties matching the :class:`~.common.TallyType` value(s).

        If the given tally_type is a combination of tally types, all of the
        matched attributes will be set to the given color.

        Arguments:
            tally_type (TallyType or str): The :class:`~.common.TallyType` member(s)
                to set. Multiple types can be specified using
                bitwise ``|`` operators.

                If the argument is a string, it should be formatted as shown in
                :meth:`.TallyType.from_str`
            color (TallyColor or str): The :class:`~.common.TallyColor` to set, or the
                name as a string


        >>> from tslumd import Tally, TallyType, TallyColor
        >>> tally = Tally(0)
        >>> tally.set_color(TallyType.rh_tally, TallyColor.RED)
        >>> tally.rh_tally
        <TallyColor.RED: 1>
        >>> tally.set_color('lh_tally', 'green')
        >>> tally.lh_tally
        <TallyColor.GREEN: 2>
        >>> tally.set_color('rh_tally|txt_tally', 'green')
        >>> tally.rh_tally
        <TallyColor.GREEN: 2>
        >>> tally.txt_tally
        <TallyColor.GREEN: 2>
        >>> tally.set_color('all', 'off')
        >>> tally.rh_tally
        <TallyColor.OFF: 0>
        >>> tally.txt_tally
        <TallyColor.OFF: 0>
        >>> tally.lh_tally
        <TallyColor.OFF: 0>

        .. versionadded:: 0.0.4

        .. versionchanged:: 0.0.5
            Allow string arguments and multiple tally_type members
        """
        self[tally_type] = color

    def get_color(self, tally_type: StrOrTallyType) -> TallyColor:
        """Get the color of the given tally_type

        If tally_type is a combination of tally types, the color returned will
        be a combination all of the matched color properties.

        Arguments:
            tally_type (TallyType or str): :class:`~.common.TallyType` member(s)
                to get the color values from.

                If the argument is a string, it should be formatted as shown in
                :meth:`.TallyType.from_str`


        >>> tally = Tally(0)
        >>> tally.get_color('rh_tally')
        <TallyColor.OFF: 0>
        >>> tally.set_color('rh_tally', 'red')
        >>> tally.get_color('rh_tally')
        <TallyColor.RED: 1>
        >>> tally.set_color('txt_tally', 'red')
        >>> tally.get_color('rh_tally|txt_tally')
        <TallyColor.RED: 1>
        >>> tally.get_color('all')
        <TallyColor.RED: 1>
        >>> tally.set_color('lh_tally', 'green')
        >>> tally.get_color('lh_tally')
        <TallyColor.GREEN: 2>
        >>> tally.get_color('all')
        <TallyColor.AMBER: 3>

        .. versionadded:: 0.0.5
        """
        return self[tally_type]

    def merge_color(self, tally_type: TallyType, color: TallyColor):
        """Merge the color property (or properties) for the given TallyType
        using the :meth:`set_color` method

        Combines the existing color value with the one provided using a bitwise
        ``|`` (or) operation

        Arguments:
            tally_type (TallyType): The :class:`~.common.TallyType` member(s)
                to merge. Multiple types can be specified using
                bitwise ``|`` operators.
            color (TallyColor): The :class:`~.common.TallyColor` to merge

        .. versionadded:: 0.0.4
        """
        for ttype in tally_type:
            cur_color = self[ttype]
            new_color = cur_color | color
            if new_color == cur_color:
                continue
            self[ttype] = new_color

    def merge(self, other: Tally, tally_type: TallyType = TallyType.all_tally):
        """Merge the color(s) from another Tally instance into this one using
        the :meth:`merge_color` method

        Arguments:
            other (Tally): The Tally instance to merge with
            tally_type (TallyType, optional): The :class:`~.common.TallyType`
                member(s) to merge. Multiple types can be specified using
                bitwise ``|`` operators.
                Default is :attr:`~.common.TallyType.all_tally` (all three types)

        .. versionadded:: 0.0.4
        """
        for ttype in tally_type:
            color = other[ttype]
            self.merge_color(ttype, color)

    def update(self, **kwargs) -> set[str]:
        """Update any known properties from the given keyword-arguments

        Returns:
            set: The property names, if any, that changed
        """
        log_updated = kwargs.pop('LOG_UPDATED', False)
        props_changed = set()
        self._updating_props = True
        for attr in self._prop_attrs:
            if attr not in kwargs:
                continue
            val = kwargs[attr]
            if attr == 'control' and val != b'':
                if self.control == val:
                    # logger.debug(f'resetting control, {val=}, {self.control=}')
                    self.control = b''
            if getattr(self, attr) == val:
                continue
            props_changed.add(attr)
            setattr(self, attr, val)
            if attr == 'brightness':
                val = cast(int, val)
                self.normalized_brightness = val / 3
            if log_updated:
                logger.debug(f'{self!r}.{attr} = {val!r}')
        self._updating_props = False
        if 'control' in props_changed and self.control != b'':
            self.emit('on_control', self, self.control)
        if len(props_changed):
            self.emit('on_update', self, props_changed)
        return props_changed

    def update_from_display(self, display: Display) -> set[str]:
        """Update this instance from the values of the given
        :class:`~.messages.Display` object

        Returns:
            set: The property names, if any, that changed
        """
        attrs = set(self._prop_attrs)
        is_control = display.type.name == 'control'
        if is_control:
            attrs.discard('text')
        else:
            attrs.discard('control')
        kw = {attr:getattr(display, attr) for attr in attrs}
        kw['LOG_UPDATED'] = True
        props_changed = self.update(**kw)
        return props_changed

    def to_dict(self) -> dict:
        """Serialize to a :class:`dict`
        """
        d = {attr:getattr(self, attr) for attr in self._prop_attrs}
        d['index'] = self.index
        if self.screen is None:
            d['id'] = None
        else:
            d['id'] = self.id
        return d

    # def to_display(self) -> 'tslumd.messages.Display':
    #     """Create a :class:`~.messages.Display` from this instance
    #     """
    #     kw = self.to_dict()
    #     return Display(**kw)

    def _on_prop_changed(self, instance, value, **kwargs):
        if self._updating_props:
            return
        prop = kwargs['property']
        if prop.name == 'control' and value != b'':
            self.emit('on_control', self, value)
        if prop.name == 'brightness':
            value = cast(int, value)
            self.normalized_brightness = value / 3
        self.emit('on_update', self, set([prop.name]))

    def __getitem__(self, key: StrOrTallyType) -> TallyColor:
        if not isinstance(key, TallyType):
            key = TallyType.from_str(key)
        if key.is_iterable:
            color = TallyColor.OFF
            for tt in key:
                assert tt.name is not None
                color |= getattr(self, tt.name)
            return color
        assert key.name is not None
        return getattr(self, key.name)

    def __setitem__(self, key: StrOrTallyType, value: StrOrTallyColor):
        if not isinstance(key, TallyType):
            key = TallyType.from_str(key)
        if not isinstance(value, TallyColor):
            value = TallyColor.from_str(value)
        if key.is_iterable:
            for tt in key:
                assert tt.name is not None
                setattr(self, tt.name, value)
        else:
            assert key.name is not None
            setattr(self, key.name, value)

    def __eq__(self, other):
        if not isinstance(other, Tally):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        if not isinstance(other, Tally):
            return NotImplemented
        return self.to_dict() != other.to_dict()

    def __repr__(self):
        return f'<{self.__class__.__name__}: ({self})>'

    def __str__(self):
        if self.__id is None:
            return f'{self.index} - "{self.text}"'
        return f'{self.id} - "{self.text}"'

class Screen(Dispatcher):
    """A group of :class:`Tally` displays

    Properties:
        scontrol(bytes): Any control data received for the screen

    :Events:
        .. event:: on_tally_added(tally: Tally)

            Fired when a new :class:`Tally` instance is added to the screen

        .. event:: on_tally_update(tally: Tally, props_changed: set[str])

            Fired when any :class:`Tally` property changes. This is a
            retransmission of :event:`Tally.on_update`

        .. event:: on_tally_control(tally: Tally, data: bytes)

            Fired when control data is received for a :class:`Tally` object.
            This is a retransmission of :event:`Tally.on_control`

        .. event:: on_control(instance: Screen, data: bytes)

            Fired when control data is received for the :class:`Screen` itself

    .. versionadded:: 0.0.3

    """

    tallies: dict[int, Tally]
    """Mapping of :class:`Tally` objects within the screen using their
    :attr:`~Tally.index` as keys
    """

    scontrol = Property(b'')

    _events_ = [
        'on_tally_added', 'on_tally_update', 'on_tally_control', 'on_control',
    ]
    def __init__(self, index_: int):
        self.__index = index_
        self.tallies = {}
        self.bind(scontrol=self._on_scontrol_prop)

    @property
    def index(self) -> int:
        """The screen index from 0 to 65534 (``0xFFFE``)
        """
        return self.__index

    @property
    def is_broadcast(self) -> bool:
        """``True`` if the screen is to be "broadcast", meaning sent to all
        :attr:`screen indices<.messages.Message.screen>`.

        (if the :attr:`index` is ``0xffff``)
        """
        return self.index == 0xffff

    @classmethod
    def broadcast(cls, **kwargs) -> 'Screen':
        """Create a :attr:`broadcast <is_broadcast>` :class:`Screen`

        (with :attr:`index` set to ``0xffff``)
        """
        return cls(0xffff, **kwargs)

    def broadcast_tally(self, **kwargs) -> Tally:
        """Create a temporary :class:`Tally` using :meth:`Tally.broadcast`

        Arguments:
            **kwargs: Keyword arguments to pass to the :class:`Tally` constructor

        Note:
            The tally object is not stored in :attr:`tallies` and no event
            propagation (:event:`on_tally_added`, :event:`on_tally_update`,
            :event:`on_tally_control`) is handled by the :class:`Screen`.
        """
        return Tally.broadcast(screen=self, **kwargs)

    def add_tally(self, index_: int, **kwargs) -> Tally:
        """Create a :class:`Tally` object and add it to :attr:`tallies`

        Arguments:
            index_: The tally :attr:`~Tally.index`
            **kwargs: Keyword arguments passed to create the tally instance

        Raises:
            KeyError: If the given ``index_`` already exists
        """
        if index_ in self:
            raise KeyError(f'Tally exists for index {index_}')
        tally = Tally(index_, screen=self, **kwargs)
        self._add_tally_obj(tally)
        return tally

    def get_or_create_tally(self, index_: int) -> Tally:
        """If a :class:`Tally` object matching the given index exists, return
        it. Otherwise create one and add it to :attr:`tallies`

        This method is similar to :meth:`add_tally` and it can be used to avoid
        exception handling. It does not however take keyword arguments and
        is only intended for object creation.
        """
        if index_ in self:
            return self[index_]
        return self.add_tally(index_)

    def _add_tally_obj(self, tally: Tally):
        assert not tally.is_broadcast
        self.tallies[tally.index] = tally
        tally.bind(
            on_update=self._on_tally_updated,
            on_control=self._on_tally_control,
        )
        self.emit('on_tally_added', tally)

    def update_from_message(self, msg: Message):
        """Handle an incoming :class:`~.Message`
        """
        if msg.screen != self.index and not msg.broadcast:
            return
        if msg.type == MessageType.control:
            self.scontrol = msg.scontrol
        else:
            for dmsg in msg.displays:
                self.handle_dmsg(dmsg)

    def handle_dmsg(self, dmsg: Display):
        if dmsg.is_broadcast:
            for tally in self:
                tally.update_from_display(dmsg)
        else:
            if dmsg.index not in self:
                tally = Tally.from_display(dmsg, screen=self)
                self._add_tally_obj(tally)
                if dmsg.type == MessageType.control:
                    tally.emit('on_control', tally, tally.control)
            else:
                tally = self[dmsg.index]
                tally.update_from_display(dmsg)

    def _on_tally_updated(self, *args, **kwargs):
        self.emit('on_tally_update', *args, **kwargs)

    def _on_tally_control(self, *args, **kwargs):
        self.emit('on_tally_control', *args, **kwargs)

    def _on_scontrol_prop(self, instance: 'Screen', value: bytes, **kwargs):
        if not len(value):
            return
        self.emit('on_control', self, value)

    def __getitem__(self, key: int) -> Tally:
        return self.tallies[key]

    def __contains__(self, key: int) -> bool:
        return key in self.tallies

    def keys(self) -> Iterator[int]:
        yield from sorted((k for k in self.tallies.keys() if k != 0xffff))

    def values(self) -> Iterator[Tally]:
        for key in self.keys():
            yield self[key]

    def items(self) -> Iterator[Tuple[int, Tally]]:
        for key in self.keys():
            yield key, self[key]

    def __iter__(self) -> Iterator[Tally]:
        yield from self.values()

    def __repr__(self):
        return f'<{self.__class__.__name__}: {self}>'

    def __str__(self):
        return f'{self.index}'
