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


def make_gui_with_processor():
    gui = zynthian_gui.__new__(zynthian_gui)
    zctrl = SimpleNamespace(symbol="cutoff")
    proc = SimpleNamespace(controllers_dict={"cutoff": zctrl})
    learned, cleared = [], []
    gui.chain_manager = SimpleNamespace(processors={7: proc},
                                        clear_midi_binding=lambda p, symbol: cleared.append((p, symbol)))
    gui.state_manager = SimpleNamespace(enable_learn_cc=learned.append)
    return gui, proc, zctrl, learned, cleared


@pytest.mark.parametrize("params", [[7, "cutoff"], ["7", "cutoff"]])
def test_cuia_enable_midi_learn_cc_finds_the_controller(params):
    gui, proc, zctrl, learned, cleared = make_gui_with_processor()
    gui.cuia_enable_midi_learn_cc(params)
    assert learned == [zctrl]


@pytest.mark.parametrize("params", [[7, "cutoff"], ["7", "cutoff"]])
def test_cuia_midi_unlearn_node_clears_the_controller(params):
    gui, proc, zctrl, learned, cleared = make_gui_with_processor()
    gui.cuia_midi_unlearn_node(params)
    assert cleared == [(proc, "cutoff")]


@pytest.mark.parametrize("params", [None, [], [7], [8, "cutoff"], [7, "resonance"], ["x", "cutoff"]])
def test_cuia_midi_learn_node_without_such_controller_does_nothing(params):
    gui, proc, zctrl, learned, cleared = make_gui_with_processor()
    gui.cuia_enable_midi_learn_cc(params)
    gui.cuia_midi_unlearn_node(params)
    assert learned == [] and cleared == []


@pytest.mark.parametrize("screen, shown", [
    ("mixer", ["chain_options"]),        # also after a visit to the audio player
    ("audio_player", ["bank_preset", "menu"]),
    ("alsa_mixer", []),
])
def test_cuia_chain_options_after_leaving_the_audio_player(screen, shown):
    gui = zynthian_gui.__new__(zynthian_gui)
    audio_player = SimpleNamespace(id=-3)
    chain = SimpleNamespace(chain_id=1)
    gui.state_manager = SimpleNamespace(audio_player=audio_player, alsa_mixer_processor=SimpleNamespace(id=-2))
    gui.chain_manager = SimpleNamespace(active_chain=chain, get_chain=lambda chain_id: chain)
    gui.current_processor = audio_player  # left over from the audio player view
    gui.current_screen = screen
    calls = []
    gui.screens = {"chain_options": SimpleNamespace(set_chain=lambda c: None)}
    gui.show_screen = calls.append
    gui.cuia_bank_preset = lambda params=None: calls.append("bank_preset")
    gui.cuia_menu = lambda params=None: calls.append("menu")
    gui.cuia_chain_options()
    assert calls == shown
