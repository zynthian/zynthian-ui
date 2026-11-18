"""Chain manager feedback ("chain_state" websocket stream) on the real chain manager.

- SS_SET_MIDI_CHAN is only sent for user actions (send_signal=True), not while creating chains or loading state.
- zynthian_gui.get_chain_state() reports the real chains (run on a bare zynthian_gui instance).
"""

import json
from types import SimpleNamespace

import pytest

from zyngine.zynthian_signal_manager import zynsigman

pytestmark = pytest.mark.integration


@pytest.fixture
def cm(state_manager):
    cm = state_manager.chain_manager
    for chain_id in [c for c in list(cm.chains) if c != 0]:
        cm.remove_chain(chain_id)
    return cm


@pytest.fixture
def midi_chan_signals():
    seen = []

    def cb(**kw):
        seen.append(kw)
    zynsigman.register(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_MIDI_CHAN, cb)
    yield seen
    zynsigman.unregister(zynsigman.S_CHAIN_MAN, zynsigman.SS_SET_MIDI_CHAN, cb)


def wait_queue(seen, n, timeout=2.0):
    """SS_SET_MIDI_CHAN is a queued signal: wait for the signal thread"""
    import time
    deadline = time.monotonic() + timeout
    while len(seen) < n and time.monotonic() < deadline:
        time.sleep(0.01)


def test_set_midi_chan_signals_only_user_actions(cm, midi_chan_signals):
    cm.add_chain(1, midi_chan=0)
    cm.set_midi_chan(1, 5)                      # internal use (e.g. loading state): no signal
    cm.set_midi_chan(1, 6, send_signal=True)    # user action
    wait_queue(midi_chan_signals, 1)
    import time
    time.sleep(0.1)                             # make sure nothing else arrives
    assert midi_chan_signals == [{"chain_id": 1, "midi_chan": 6}]
    assert cm.chains[1].midi_chan == 6


def test_creating_chains_doesnt_signal_midi_chan(cm, midi_chan_signals):
    cm.add_chain(1, midi_chan=0)
    cm.add_chain(2, midi_chan=1)
    import time
    time.sleep(0.2)
    assert midi_chan_signals == []


def test_get_chain_state_reports_the_real_chains(cm, state_manager):
    from zyngui.zynthian_gui import zynthian_gui
    cm.add_chain(1, midi_chan=0)
    cm.add_chain(2, midi_chan=3)
    cm.set_chain_title(2, "Bass")
    cm.set_active_chain_by_id(2)
    g = zynthian_gui.__new__(zynthian_gui)
    g.chain_manager, g.state_manager = cm, state_manager
    state = g.get_chain_state()
    json.dumps(state)
    assert state["active"] == 2
    chains = {c["id"]: c for c in state["chains"]}
    assert [c["id"] for c in state["chains"]] == list(cm.chains)        # display order, main last
    assert [c["index"] for c in state["chains"]] == list(range(len(cm.chains)))
    assert chains[1]["midi_chan"] == 1 and chains[2]["midi_chan"] == 4
    assert chains[2]["title"] == "Bass"
    assert chains[1]["zmop_index"] == cm.chains[1].zmop_index
    assert chains[0]["midi_chan"] is None
    for chain_id, c in chains.items():
        proc = cm.chains[chain_id].zynmixer_proc
        if proc is None:
            assert c["mixer"] is None
        else:
            assert c["mixer"] == {"bus": proc.zynmixer is state_manager.zynmixer_bus, "strip": proc.mixer_chan}
