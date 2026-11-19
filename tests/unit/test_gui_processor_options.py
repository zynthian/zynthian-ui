"""zyngui.zynthian_gui_processor_options: randomizing the controllers of a processor."""

import random
from types import SimpleNamespace

from zyngui.zynthian_gui_processor_options import zynthian_gui_processor_options


class Ctrl:
    def __init__(self, symbol, value_min, value_max, is_integer=False):
        self.symbol = symbol
        self.value_min = value_min
        self.value_max = value_max
        self.is_integer = is_integer
        self.value = value_min

    def set_value(self, value):
        self.value = value


def test_randomize_draws_float_values_between_min_and_max():
    ctrls = [Ctrl("pan", -1.0, 1.0), Ctrl("gain", -40.0, -20.0), Ctrl("steps", -5, 5, is_integer=True)]
    screen = zynthian_gui_processor_options.__new__(zynthian_gui_processor_options)
    screen.processor = SimpleNamespace(controllers_dict={c.symbol: c for c in ctrls})
    screen.last_random = {"x": 0}
    random.seed(1)
    for _ in range(200):
        screen.randomize()
        for c in ctrls:
            assert c.value_min <= c.value <= c.value_max
