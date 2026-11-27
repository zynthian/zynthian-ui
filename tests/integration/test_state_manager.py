"""Real state manager + chain manager on the faked native layer."""

import sys

import pytest


def test_state_manager_constructs(state_manager, fake_subprocess):
    assert state_manager.chain_manager is not None
    assert state_manager.fast_thread.is_alive() and state_manager.slow_thread.is_alive()


def test_no_real_processes_were_started(state_manager, fake_subprocess):
    """Whatever the state manager shelled out to was intercepted (recorded, not executed)."""
    assert isinstance(fake_subprocess.commands, list)
    # Characterization: today construction runs the power-save script.
    assert any("powersave_control.sh" in str(c) for c in fake_subprocess.commands)


def test_construction_touches_the_native_layer(state_manager, zyncore):
    assert zyncore.call_count() > 0


# ---------------------------------------------------------------------------
# Chains
# ---------------------------------------------------------------------------

@pytest.fixture
def chains(state_manager):
    return state_manager.chain_manager


def test_initial_chains(chains):
    # chain 0 is the main (audio) chain created by the state manager
    assert chains.get_chain(0) is not None
    assert chains.get_chain_count() >= 1


def test_add_and_remove_midi_chain(chains):
    before = chains.get_chain_count()
    cid = chains.add_chain(5, midi_chan=3)
    assert cid == 5
    assert chains.get_chain(5) is not None
    assert chains.get_chain_count() == before + 1
    assert 5 in chains.get_chain_ids_by_midi_chan(3)
    assert chains.remove_chain(5)
    assert chains.get_chain(5) is None
    assert chains.get_chain_count() == before


def test_chain_added_signal(chains):
    import threading
    from zyngine.zynthian_signal_manager import zynsigman
    got = threading.Event()

    def cb(**kw):
        got.set()

    zynsigman.register(zynsigman.S_CHAIN_MAN, zynsigman.SS_ADD_CHAIN, cb)
    try:
        chains.add_chain(7, midi_chan=1)
        assert got.wait(2.0), "SS_ADD_CHAIN (queued) was not delivered"
    finally:
        zynsigman.unregister(zynsigman.S_CHAIN_MAN, zynsigman.SS_ADD_CHAIN, cb)


def test_chain_ids_are_unique(chains):
    chains.add_chain(10, midi_chan=0)
    chains.add_chain(11, midi_chan=0)
    ids = list(chains.chains)
    assert len(ids) == len(set(ids))


def test_set_active_chain(chains):
    chains.add_chain(12, midi_chan=2)
    chains.set_active_chain_by_id(12)
    assert chains.active_chain.chain_id == 12


# ---------------------------------------------------------------------------
# State / snapshots
# ---------------------------------------------------------------------------

def test_get_state_is_json_serialisable_and_versioned(state_manager):
    import json
    from zynthian_state_schema import ZynthianState
    state = state_manager.get_state()
    json.dumps(state)
    assert state["schema_version"] == ZynthianState["schema_version"]


def test_state_has_every_top_level_key_of_the_schema(state_manager):
    from zynthian_state_schema import ZynthianState
    state = state_manager.get_state()
    optional = {"engine_config"}  # only present when an engine has extended configuration
    missing = set(ZynthianState) - optional - set(state)
    assert not missing, f"state is missing documented keys: {sorted(missing)}"


def test_snapshot_save_load_roundtrip(state_manager, zynthian_dirs):
    chains = state_manager.chain_manager
    chains.add_chain(3, midi_chan=4)
    path = str(zynthian_dirs["ZYNTHIAN_MY_DATA_DIR"] / "snapshots" / "roundtrip.zss")
    state_manager.save_snapshot(path)

    chains.remove_chain(3)
    assert chains.get_chain(3) is None

    assert state_manager.load_snapshot(path) is not False
    assert chains.get_chain(3) is not None
    assert 3 in chains.get_chain_ids_by_midi_chan(4)


# --- slow update callbacks ----------------------------------------------------------------------------------
def test_slow_update_callback_is_added(state_manager):
    def cb():
        pass
    before = len(state_manager.slow_update_callbacks)
    state_manager.add_slow_update_callback(1.0, cb)
    try:
        assert len(state_manager.slow_update_callbacks) == before + 1
        assert state_manager.slow_update_callbacks[-1][:2] == [1.0, cb]
    finally:
        state_manager.slow_update_callbacks[:] = [c for c in state_manager.slow_update_callbacks if c[1] is not cb]


# remove_slow_update_callback() once never removed anything (loop variable shadowed the parameter;
# fixed in 7ed6003b). These two tests guard against a regression.


def test_slow_update_callback_is_removed(state_manager):
    def cb():
        pass
    before = len(state_manager.slow_update_callbacks)
    state_manager.add_slow_update_callback(1.0, cb)
    try:
        state_manager.remove_slow_update_callback(cb)
        assert len(state_manager.slow_update_callbacks) == before
    finally:
        state_manager.slow_update_callbacks[:] = [c for c in state_manager.slow_update_callbacks if c[1] is not cb]


def test_adding_a_slow_update_callback_twice_keeps_one(state_manager):
    def cb():
        pass
    before = len(state_manager.slow_update_callbacks)
    try:
        state_manager.add_slow_update_callback(1.0, cb)
        state_manager.add_slow_update_callback(2.0, cb)
        assert len(state_manager.slow_update_callbacks) == before + 1
    finally:
        state_manager.slow_update_callbacks[:] = [c for c in state_manager.slow_update_callbacks if c[1] is not cb]


# ---------------------------------------------------------------------------
# ZS3 restore of chain MIDI inputs
# ---------------------------------------------------------------------------

def test_zs3_restore_feeds_a_chain_from_its_own_router_output(state_manager):
    """A saved MIDI input naming another chain's router output (e.g. the zmop changed) is replaced by the chain's
    own: else the chain plays the other chain's MIDI and nothing of its own"""
    cm = state_manager.chain_manager
    cm.add_chain(1, midi_chan=0)
    cm.add_chain(2, midi_chan=1)
    chain1, chain2 = cm.get_chain(1), cm.get_chain(2)
    assert chain1.zmop_index != chain2.zmop_index
    own1, own2 = (f"ZynMidiRouter:ch{c.zmop_index}_out" for c in (chain1, chain2))
    state_manager.save_zs3("zs3-0")
    state_manager.zs3["zs3-0"]["chains"][1]["midi_in"] = [own2]  # stale: chain 2's router output
    state_manager.load_zs3("zs3-0", autoconnect=False)
    assert chain1.midi_in == [own1]
    assert chain2.midi_in == [own2]


def test_router_midi_inputs_are_fixed_and_others_kept(state_manager):
    import types
    fix = state_manager.fix_chain_router_midi_in
    chain = types.SimpleNamespace(chain_id=3, zmop_index=4)
    assert fix(chain, ["ZynMidiRouter:ch1_out", "MIDI-IN", "ZynMidiRouter:ch4_out"]) == ["ZynMidiRouter:ch4_out",
                                                                                         "MIDI-IN"]
    no_zmop = types.SimpleNamespace(chain_id=3, zmop_index=None)
    assert fix(no_zmop, ["ZynMidiRouter:ch1_out", "MIDI-IN"]) == ["MIDI-IN"]
