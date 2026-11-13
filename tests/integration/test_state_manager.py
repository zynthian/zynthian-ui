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
