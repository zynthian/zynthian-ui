"""zyngine.zynthian_chain.rebuild_midi_graph() with a processor whose engine isn't there (bare chain, autoconnect stubbed)."""

from types import SimpleNamespace

import pytest

import zynautoconnect
from zyngine.zynthian_chain import zynthian_chain


@pytest.fixture
def lock(monkeypatch):
    state = SimpleNamespace(held=0)

    def acquire():
        state.held += 1
        return True

    def release():
        state.held -= 1

    monkeypatch.setattr(zynautoconnect, "acquire_lock", acquire)
    monkeypatch.setattr(zynautoconnect, "release_lock", release)
    monkeypatch.setattr(zynautoconnect, "request_midi_connect", lambda fast=False: None)
    return state


def make_chain(synth_engine):
    chain = zynthian_chain.__new__(zynthian_chain)
    chain.midi_slots = []
    chain.synth_slots = [[SimpleNamespace(engine=synth_engine, type="MIDI Synth")]]
    chain.audio_slots = [[SimpleNamespace(engine=None, eng_code="JV")]]
    chain.midi_thru = False
    chain.midi_in = []
    chain.midi_out = ["out"]
    return chain


def test_processors_without_engine_are_skipped(lock):
    chain = make_chain(None)
    chain.rebuild_midi_graph()
    assert chain.midi_routes == {"out": []}
    assert lock.held == 0


def test_the_autoconnect_lock_is_released_when_building_fails(lock):
    chain = make_chain(SimpleNamespace())  # an engine without get_jackname()
    with pytest.raises(AttributeError):
        chain.rebuild_midi_graph()
    assert lock.held == 0
