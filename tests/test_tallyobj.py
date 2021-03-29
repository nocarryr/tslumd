import pytest
import itertools
import asyncio

from tslumd import Tally, TallyColor, TallyType, Display

def iter_tally_types():
    for tally_type in TallyType:
        if tally_type == TallyType.no_tally:
            continue
        yield tally_type

def iter_tally_colors():
    yield from TallyColor

def iter_tally_types_and_colors():
    yield from itertools.product(iter_tally_types(), iter_tally_colors())



def test_tally_display_conversion(faker):
    # i = 0
    # if True:
    for _ in range(100):
        i = faker.pyint(max_value=65534)
        disp = Display(index=i)
        tally = Tally(i)
        for tally_type, color in iter_tally_types_and_colors():
            # print(f'{i=}, {tally_type=}, {color=}')
            setattr(tally, tally_type.name, color)
            setattr(disp, tally_type.name, color)
            for word in faker.words(3):
                # print(f'{word=}')
                tally.text = word
                disp.text = word

                assert disp == Tally.from_display(disp) == tally
                assert disp == Display.from_tally(tally) == tally

@pytest.mark.asyncio
async def test_update_event(faker):
    class Listener:
        def __init__(self):
            self.results = asyncio.Queue()
        async def get(self):
            r = await self.results.get()
            self.results.task_done()
            return r
        async def callback(self, tally, props_changed, **kwargs):
            # print(f'callback: {tally=}, {props_changed=}')
            await self.results.put((tally, props_changed))


    loop = asyncio.get_event_loop()
    listener = Listener()

    tally = Tally(0)
    tally.bind_async(loop, on_update=listener.callback)
    tally.text = 'foo'

    _, props_changed = await listener.get()
    assert set(props_changed) == set(['text'])

    d = dict(rh_tally=TallyColor.RED, txt_tally=TallyColor.GREEN, lh_tally=TallyColor.AMBER)
    tally.update(**d)

    _, props_changed = await listener.get()
    assert set(props_changed) == set(d.keys())


    disp = Display(index=0, text=tally.text)
    tally.update_from_display(disp)
    assert disp == tally

    _, props_changed = await listener.get()
    assert set(props_changed) == set(['rh_tally', 'txt_tally', 'lh_tally'])


    for tally_type, color in iter_tally_types_and_colors():
        attr = tally_type.name
        should_change = getattr(tally, attr) != color
        # print(f'{tally_type=}, {color=}, {should_change=}')
        setattr(tally, attr, color)
        if should_change:
            _, props_changed = await listener.get()
            assert set(props_changed) == set([attr])
        else:
            await asyncio.sleep(.01)
            assert listener.results.empty()
