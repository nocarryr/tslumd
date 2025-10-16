import dataclasses
import pytest
import itertools
import asyncio

from tslumd import Tally, TallyColor, TallyType, Display


def iter_tally_colors():
    yield from TallyColor

def iter_tally_types_and_colors():
    yield from itertools.product(TallyType.all(), iter_tally_colors())



def test_tally_display_conversion(faker):
    # i = 0
    # if True:
    for _ in range(100):
        i = faker.pyint(max_value=0xfffe)
        disp = Display(index=i)
        tally = Tally(i)
        for tally_type, color in iter_tally_types_and_colors():
            brightness = faker.pyint(max_value=3)
            # print(f'{i=}, {tally_type=}, {color=}')
            disp = dataclasses.replace(disp, brightness=brightness)
            tally.brightness = brightness
            assert 0 <= tally.normalized_brightness <= 1
            assert tally.normalized_brightness == brightness / 3
            assert tally_type.name is not None
            setattr(tally, tally_type.name, color)
            disp = dataclasses.replace(disp, **{tally_type.name: color})
            for word in faker.words(3):
                # print(f'{word=}')
                tally.text = word
                disp = dataclasses.replace(disp, text=word)

                assert disp == Tally.from_display(disp) == tally
                assert disp == Display.from_tally(tally) == tally
                assert Tally.from_display(disp).normalized_brightness == tally.normalized_brightness


def test_color_merge():
    t1 = Tally(0)

    t1.set_color(TallyType.rh_tally | TallyType.lh_tally, TallyColor.RED)
    assert t1.rh_tally == TallyColor.RED
    assert t1.txt_tally == TallyColor.OFF
    assert t1.lh_tally == TallyColor.RED

    t1.set_color(TallyType.rh_tally | TallyType.lh_tally, TallyColor.GREEN)
    assert t1.rh_tally == TallyColor.GREEN
    assert t1.txt_tally == TallyColor.OFF
    assert t1.lh_tally == TallyColor.GREEN

    t1.merge_color(TallyType.all_tally, TallyColor.RED)
    assert t1.rh_tally == TallyColor.AMBER
    assert t1.txt_tally == TallyColor.RED
    assert t1.lh_tally == TallyColor.AMBER

    t1.merge_color(TallyType.all_tally, TallyColor.GREEN)
    assert t1.rh_tally == TallyColor.AMBER
    assert t1.txt_tally == TallyColor.AMBER
    assert t1.lh_tally == TallyColor.AMBER

    # Reset t1 to OFF, OFF, RED
    t1.rh_tally = TallyColor.OFF
    t1.txt_tally = TallyColor.OFF
    t1.lh_tally = TallyColor.RED

    # Another Tally with only `txt_tally` set
    t2 = Tally(1, txt_tally=TallyColor.GREEN)

    # Only `txt_tally` should change
    t1.merge(t2, TallyType.all_tally)
    assert t1.rh_tally == TallyColor.OFF
    assert t1.txt_tally == TallyColor.GREEN
    assert t1.lh_tally == TallyColor.RED

    # Reset t2 to GREEN, RED, GREEN
    # t1 is still OFF, GREEN, RED
    t2.rh_tally = TallyColor.GREEN
    t2.txt_tally = TallyColor.RED
    t2.lh_tally = TallyColor.GREEN

    t1.merge(t2, TallyType.rh_tally | TallyType.lh_tally)
    assert t1.rh_tally == TallyColor.GREEN
    assert t1.txt_tally == TallyColor.GREEN
    assert t1.lh_tally == TallyColor.AMBER

    t1.merge(t2, TallyType.all_tally)
    assert t1.rh_tally == TallyColor.GREEN
    assert t1.txt_tally == TallyColor.AMBER
    assert t1.lh_tally == TallyColor.AMBER

    t2.rh_tally = TallyColor.RED
    t1.merge(t2, TallyType.all_tally)
    assert t1.rh_tally == TallyColor.AMBER
    assert t1.txt_tally == TallyColor.AMBER
    assert t1.lh_tally == TallyColor.AMBER


def test_broadcast(faker):
    for _ in range(1000):
        i = faker.pyint(max_value=0xfffe)
        tally = Tally(i)
        assert not tally.is_broadcast
        assert not Display.from_tally(tally).is_broadcast

    tally1 = Tally(0xffff)
    tally2 = Tally.broadcast()
    assert tally1.is_broadcast
    assert tally2.is_broadcast
    assert Display.from_tally(tally1).is_broadcast
    assert Display.from_tally(tally2).is_broadcast

class Listener:
    def __init__(self):
        self.results = asyncio.Queue()
    async def get(self):
        r = await self.results.get()
        self.results.task_done()
        return r
    async def callback(self, *args, **kwargs):
        # print(f'callback: {tally=}, {props_changed=}')
        await self.results.put(tuple(args))


@pytest.mark.asyncio
async def test_update_event(faker):
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
        assert attr is not None
        should_change = getattr(tally, attr) != color
        # print(f'{tally_type=}, {color=}, {should_change=}')
        setattr(tally, attr, color)
        if should_change:
            _, props_changed = await listener.get()
            assert set(props_changed) == set([attr])
        else:
            await asyncio.sleep(.01)
            assert listener.results.empty()


@pytest.mark.asyncio
async def test_control_event(faker):
    loop = asyncio.get_event_loop()
    listener = Listener()

    disp = Display(index=0)
    tally = Tally.from_display(disp)

    tally.bind_async(loop, on_control=listener.callback)

    for _ in range(100):
        data_len = faker.pyint(min_value=1, max_value=1024)
        control_data = faker.binary(length=data_len)

        disp = Display(index=0, control=control_data)
        tally.update_from_display(disp)

        _, rx_data = await listener.get()
        assert rx_data == tally.control == disp.control == control_data
        assert disp == tally == Tally.from_display(disp)


@pytest.mark.asyncio
async def test_control_event_with_text(faker):
    loop = asyncio.get_event_loop()

    text_listener = Listener()
    ctrl_listener = Listener()

    tally_text = 'foo'

    disp = Display(index=0, text=tally_text)
    tally = Tally.from_display(disp)

    assert disp == tally

    tally.bind_async(loop,
        on_update=text_listener.callback,
        on_control=ctrl_listener.callback,
    )

    for _ in range(100):
        for word in faker.words(3):
            data_len = faker.pyint(min_value=1, max_value=1024)
            control_data = faker.binary(length=data_len)

            disp = Display(index=0, control=control_data)
            tally.update_from_display(disp)

            _, rx_data = await ctrl_listener.get()
            assert rx_data == tally.control == disp.control == control_data
            assert tally.text == tally_text

            _, props_changed = await text_listener.get()
            assert set(props_changed) == set(['control'])

            tally_text=word
            disp = Display(index=0, text=tally_text)
            tally.update_from_display(disp)

            _, props_changed = await text_listener.get()
            assert set(props_changed) == set(['text'])

            assert tally.text == tally_text
            assert tally.control == control_data
