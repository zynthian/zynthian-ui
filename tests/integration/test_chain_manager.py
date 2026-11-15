"""zynthian_chain_manager on the real state manager (engines and the native layer faked).

Chain bookkeeping that the UI relies on: order and navigation, MIDI channels, and the routing loop
("howl-round") detection used before connecting one chain into another.
"""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def cm(state_manager):
    cm = state_manager.chain_manager
    for chain_id in [c for c in list(cm.chains) if c != 0]:
        cm.remove_chain(chain_id)
    return cm


def add(cm, chain_id, midi_chan=None):
    assert cm.add_chain(chain_id, midi_chan=midi_chan) == chain_id
    return chain_id


# --- order and navigation -----------------------------------------------------------------------------------
def test_chains_keep_insertion_order_with_main_last(cm):
    for cid, chan in ((3, 0), (1, 1), (7, 2)):
        add(cm, cid, chan)
    assert list(cm.chains) == [3, 1, 7, 0]
    assert [cm.get_chain_id_by_index(i) for i in range(4)] == [3, 1, 7, 0]
    assert cm.get_chain_index(7) == 2


def test_move_chain(cm):
    for cid in (1, 2, 3):
        add(cm, cid, cid)
    assert cm.move_chain(3, 0) == 0
    assert list(cm.chains) == [3, 1, 2, 0]


def test_move_chain_never_moves_past_the_main_chain(cm):
    for cid in (1, 2):
        add(cm, cid, cid)
    assert cm.move_chain(1, 99) == 1                    # clamped before main
    assert list(cm.chains)[-1] == 0


def test_move_chain_sends_a_signal(cm):
    from zyngine.zynthian_signal_manager import zynsigman
    for cid in (1, 2):
        add(cm, cid, cid)
    seen = []

    def cb(**kw):
        seen.append(kw)
    zynsigman.register(zynsigman.S_CHAIN_MAN, zynsigman.SS_MOVE_CHAIN, cb)
    try:
        cm.move_chain(2, 0)
    finally:
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, zynsigman.SS_MOVE_CHAIN, cb)
    assert seen


def test_move_unknown_chain_fails(cm):
    assert cm.move_chain(42, 0) is None


def test_next_and_previous_chain_stop_at_the_ends(cm):
    for cid in (1, 2):
        add(cm, cid, cid)
    cm.set_active_chain_by_id(1)
    assert cm.next_chain() == 2
    assert cm.next_chain() == 0
    assert cm.next_chain() == 0                          # no wrap-around
    assert cm.previous_chain(5) == 1                     # clamped to the first


# --- MIDI channels ------------------------------------------------------------------------------------------
def test_free_midi_channels_exclude_used_and_master_channels(cm):
    from zyngine.zynthian_chain_manager import MAX_NUM_MIDI_CHANS
    from zyngui import zynthian_gui_config
    add(cm, 1, 0)
    add(cm, 2, 5)
    free = cm.get_free_midi_chans()
    master = zynthian_gui_config.master_midi_channel
    expected = set(range(MAX_NUM_MIDI_CHANS)) - {0, 5, master}
    assert set(free) == expected


def test_chains_by_midi_channel(cm):
    add(cm, 1, 3)
    add(cm, 2, 3)
    add(cm, 4, 9)
    assert set(cm.get_chain_ids_by_midi_chan(3)) == {1, 2}
    assert cm.get_chain_ids_by_midi_chan(10) == []


def test_set_midi_chan_moves_the_chain(cm, zyncore):
    add(cm, 1, 3)
    cm.set_midi_chan(1, 6)
    assert cm.chains[1].midi_chan == 6
    assert 6 not in cm.get_free_midi_chans()


# --- routing loops ------------------------------------------------------------------------------------------
def route(cm, src, *dsts):
    cm.chains[src].midi_out = list(dsts)
    cm.chains[src].audio_out = list(dsts)


@pytest.mark.parametrize("kind", ["midi", "audio"])
def test_direct_loop_is_detected(cm, kind):
    add(cm, 1, 1)
    add(cm, 2, 2)
    route(cm, 2, 1)                                      # 2 -> 1 exists; adding 1 -> 2 closes the loop
    assert getattr(cm, f"will_{kind}_howl")(1, 2)


@pytest.mark.parametrize("kind", ["midi", "audio"])
def test_longer_loop_is_detected(cm, kind):
    for cid in (1, 2, 3):
        add(cm, cid, cid)
    route(cm, 2, 3)
    route(cm, 3, 1)                                      # 2 -> 3 -> 1; adding 1 -> 2 closes it
    assert getattr(cm, f"will_{kind}_howl")(1, 2)


@pytest.mark.parametrize("kind", ["midi", "audio"])
def test_chain_into_itself_is_a_loop(cm, kind):
    add(cm, 1, 1)
    assert getattr(cm, f"will_{kind}_howl")(1, 1)


@pytest.mark.parametrize("kind", ["midi", "audio"])
def test_open_chain_is_not_a_loop(cm, kind):
    for cid in (1, 2, 3):
        add(cm, cid, cid)
    route(cm, 2, 3)
    assert not getattr(cm, f"will_{kind}_howl")(1, 2)
    assert not getattr(cm, f"will_{kind}_howl")(1, 99)   # unknown destination


@pytest.mark.xfail(strict=True, reason="will_midi_howl()/will_audio_howl() keep one visited list across all branches, "
                                       "so two paths that meet again (a diamond, not a loop) are reported as a "
                                       "howl-round and the connection is refused")
@pytest.mark.parametrize("kind", ["midi", "audio"])
def test_converging_paths_are_not_a_loop(cm, kind):
    for cid in (1, 2, 3, 4):
        add(cm, cid, cid)
    route(cm, 2, 3, 4)
    route(cm, 3, 4)                                      # 2 -> 3 -> 4 and 2 -> 4: no cycle
    assert not getattr(cm, f"will_{kind}_howl")(1, 2)
