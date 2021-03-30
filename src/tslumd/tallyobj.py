try:
    from loguru import logger
except ImportError: # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)
from typing import Dict, Set

from pydispatch import Dispatcher, Property

from tslumd import TallyType, TallyColor

__all__ = ('Tally',)

class Tally(Dispatcher):
    """A single tally object

    Properties:
        rh_tally (TallyColor): State of the "right-hand" tally indicator
        txt_tally (TallyColor): State of the "text" tally indicator
        lh_tally (TallyColor): State of the "left-hand" tally indicator
        brightness (int): Tally indicator brightness from 0 to 3
        text (str): Text to display

    :Events:
        .. event:: on_update(instance: Tally, props_changed: Sequence[str])

            Fired when any property changes

    """
    rh_tally = Property(TallyColor.OFF)
    txt_tally = Property(TallyColor.OFF)
    lh_tally = Property(TallyColor.OFF)
    brightness = Property(3)
    text = Property('')
    _events_ = ['on_update']
    _prop_attrs = ('rh_tally', 'txt_tally', 'lh_tally', 'brightness', 'text')
    def __init__(self, index_, **kwargs):
        self.__index = index_
        self._updating_props = False
        self.update(**kwargs)
        self.bind(**{prop:self._on_prop_changed for prop in self._prop_attrs})

    @property
    def index(self) -> int:
        """Index of the tally object from ``0`` to ``65534``
        """
        return self.__index

    @classmethod
    def from_display(cls, display: 'tslumd.Display') -> 'Tally':
        """Create an instance from the given :class:`~.messages.Display` object
        """
        kw = {attr:getattr(display, attr) for attr in cls._prop_attrs}
        return cls(display.index, **kw)

    def update(self, **kwargs) -> Set[str]:
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
            if getattr(self, attr) == val:
                continue
            props_changed.add(attr)
            setattr(self, attr, kwargs[attr])
            if log_updated:
                logger.debug(f'{self!r}.{attr} = {val!r}')
        self._updating_props = False
        if len(props_changed):
            self.emit('on_update', self, props_changed)
        return props_changed

    def update_from_display(self, display: 'tslumd.messages.Display') -> Set[str]:
        """Update this instance from the values of the given
        :class:`~.messages.Display` object

        Returns:
            set: The property names, if any, that changed
        """
        kw = {attr:getattr(display, attr) for attr in self._prop_attrs}
        kw['LOG_UPDATED'] = True
        return self.update(**kw)

    def to_dict(self) -> Dict:
        """Serialize to a :class:`dict`
        """
        d = {attr:getattr(self, attr) for attr in self._prop_attrs}
        d['index'] = self.index
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
        self.emit('on_update', self, [prop.name])

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
        return f'{self.index} - "{self.text}"'
