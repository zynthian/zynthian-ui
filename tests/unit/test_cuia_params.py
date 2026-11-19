"""CUIA handlers of zyngui.zynthian_gui with parameters as they arrive from CUIA strings and untyped OSC.

zynthian_gui can't be built in tests (its __init__ starts the whole UI): the handlers run on a bare
instance (``__new__``) holding only the attributes they use.
"""

from types import SimpleNamespace

import pytest

from zyngui.zynthian_gui import zynthian_gui


class Ctrl:
    def __init__(self):
        self.values = []

    def set_value(self, value):
        self.values.append(value)


def make_gui_with_chains():
    gui = zynthian_gui.__new__(zynthian_gui)
    level = {cid: Ctrl() for cid in (0, 1, 2)}
    chains = {cid: SimpleNamespace(zynmixer_proc=SimpleNamespace(controllers_dict={"level": level[cid]}))
              for cid in (0, 1, 2)}
    gui.chain_manager = SimpleNamespace(chains=chains, active_chain=chains[2])
    return gui, level


@pytest.mark.parametrize("params, chain_id", [
    ([1, "level", 0.5], 1),
    (["1", "level", "0.5"], 1),
    (["-1", "level", "0.5"], 0),
    (["None", "level", "0.5"], 2),
    ([None, "level", 0.5], 2),
])
def test_cuia_mixer_converts_string_parameters(params, chain_id):
    gui, level = make_gui_with_chains()
    gui.cuia_mixer(params)
    assert level[chain_id].values == [0.5]
    assert all(not ctrl.values for cid, ctrl in level.items() if cid != chain_id)


@pytest.mark.parametrize("params", [[1, 0.25], ["1", "0.25"]])
def test_cuia_zynpot_abs_converts_string_parameters(params):
    gui = zynthian_gui.__new__(zynthian_gui)
    calls = []
    screen = SimpleNamespace(zynpot_abs=lambda i, val: calls.append((i, val)))
    gui.get_current_screen_obj = lambda: screen
    gui.cuia_zynpot_abs(params)
    assert calls == [(1, 0.25)]


@pytest.mark.parametrize("params, selected", [(None, []), ([], []), ([3], [3]), (["3"], [3]), (["x"], [])])
def test_cuia_select_without_or_with_a_bad_index_does_nothing(params, selected):
    gui = zynthian_gui.__new__(zynthian_gui)
    calls = []
    screen = SimpleNamespace(select=calls.append)
    gui.get_current_screen_obj = lambda: screen
    gui.cuia_select(params)
    assert calls == selected
