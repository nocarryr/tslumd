from loguru import logger
import asyncio
import socket
import string
import argparse
import enum
from typing import List, Dict, Tuple, Sequence, Iterable

from pydispatch import Dispatcher, Property, DictProperty, ListProperty

from tslumd import TallyColor, TallyType, Tally, UmdSender
from tslumd.utils import logger_catch
from tslumd.sender import ClientArgAction


class AnimateMode(enum.Enum):
    vertical = 1
    horizontal = 2

class TallyTypeGroup:
    tally_type: TallyType
    num_tallies: int
    tally_colors: List[TallyColor]
    def __init__(self, tally_type: TallyType, num_tallies: int):
        if tally_type == TallyType.no_tally:
            raise ValueError(f'TallyType cannot be {TallyType.no_tally}')
        self.tally_type = tally_type
        self.num_tallies = num_tallies
        self.tally_colors = [TallyColor.OFF for _ in range(num_tallies)]

    def reset_all(self, color: TallyColor = TallyColor.OFF):
        self.tally_colors[:] = [color for _ in range(self.num_tallies)]

    def update_tallies(self, tallies: Iterable[Tally]) -> List[int]:
        attr = self.tally_type.name
        changed = []
        for tally in tallies:
            color = self.tally_colors[tally.index]
            cur_value = getattr(tally, attr)
            if cur_value == color:
                continue
            setattr(tally, attr, color)
            changed.append(tally.index)
        return changed

class AnimatedSender(UmdSender):
    tally_groups: Dict[TallyType, TallyTypeGroup]
    num_tallies = 8
    update_interval = 1
    def __init__(self, clients=None):
        super().__init__(clients)
        for i in range(self.num_tallies):
            self.add_tally(i, text=string.ascii_uppercase[i])

        self.tally_groups = {}
        for tally_type in TallyType:
            if tally_type == TallyType.no_tally:
                continue
            tg = TallyTypeGroup(tally_type, self.num_tallies)
            self.tally_groups[tally_type] = tg

    async def open(self):
        if self.running:
            return
        await super().open()
        self.update_task = asyncio.create_task(self.update_loop())

    async def close(self):
        if not self.running:
            return
        # self.running = False
        self.update_task.cancel()
        try:
            await self.update_task
        except asyncio.CancelledError:
            pass
        self.update_task = None
        await super().close()

    def set_animate_mode(self, mode: AnimateMode):
        self.animate_mode = mode
        if mode == AnimateMode.vertical:
            self.cur_group = TallyType.rh_tally
            self.cur_index = -2
        elif mode == AnimateMode.horizontal:
            self.cur_index = 0
            self.cur_group = TallyType.no_tally
        for tg in self.tally_groups.values():
            tg.reset_all()

    def animate_tallies(self):
        if self.animate_mode == AnimateMode.vertical:
            self.animate_vertical()
        elif self.animate_mode == AnimateMode.horizontal:
            self.animate_horizontal()

    def animate_vertical(self):
        colors = [c for c in TallyColor if c != TallyColor.OFF]

        tg = self.tally_groups[self.cur_group]
        start_ix = self.cur_index
        tg.reset_all()

        for color in colors:
            ix = start_ix + color.value-1
            if 0 <= ix < self.num_tallies:
                tg.tally_colors[ix] = color
        start_ix += 1

        if start_ix > self.num_tallies:
            self.cur_index = -2
            if self.cur_group == TallyType.rh_tally:
                self.cur_group = TallyType.txt_tally
            elif self.cur_group == TallyType.txt_tally:
                self.cur_group = TallyType.lh_tally
            else:
                self.set_animate_mode(AnimateMode.horizontal)
        else:
            self.cur_index = start_ix

    def animate_horizontal(self):
        tally_types = [t for t in TallyType]
        while tally_types[0] != self.cur_group:
            t = tally_types.pop(0)
            tally_types.append(t)
        for i, t in enumerate(tally_types):
            if t == TallyType.no_tally:
                continue
            tg = self.tally_groups[t]
            tg.reset_all()
            try:
                color = TallyColor(i+1)
            except ValueError:
                color = TallyColor.OFF
            tg.tally_colors[self.cur_index] = color
        try:
            t = TallyType(self.cur_group.value+1)
            self.cur_group = t
        except ValueError:
            self.cur_index += 1
            self.cur_group = TallyType.no_tally
            if self.cur_index >= self.num_tallies:
                self.set_animate_mode(AnimateMode.vertical)

    @logger_catch
    async def update_loop(self):
        self.set_animate_mode(AnimateMode.vertical)

        def update_tallies():
            changed = set()
            for tg in self.tally_groups.values():
                _changed = tg.update_tallies(self.tallies.values())
                changed |= set(_changed)
            return changed

        await self.connected_evt.wait()

        while self.running:
            await asyncio.sleep(self.update_interval)
            if not self.running:
                break
            self.animate_tallies()
            changed_ix = update_tallies()
            # changed_tallies = [self.tallies[i] for i in changed_ix]
            # await self.update_queue.put(changed_tallies)


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        '-c', '--client', dest='clients', action=ClientArgAction#, type=str,
    )
    args = p.parse_args()

    logger.info(f'Sending to clients: {args.clients!r}')

    loop = asyncio.get_event_loop()
    sender = AnimatedSender(clients=args.clients)

    # async def run():
    #     await sender.open()
    #     await asyncio.sleep(10)
    #     await sender.close()
    # try:
    #     loop.run_until_complete(run())
    # finally:
    #     loop.close()

    loop.run_until_complete(sender.open())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(sender.close())
    finally:
        loop.close()

if __name__ == '__main__':
    main()
