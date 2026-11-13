"""zyngine.zynthian_signal_manager: registration, direct and queued dispatch."""

import threading

import pytest

from zyngine.zynthian_signal_manager import zynthian_signal_manager as SignalManager

TIMEOUT = 2.0


@pytest.fixture
def sigman():
    """A private instance (not the global ``zynsigman``) with its thread stopped afterwards."""
    sm = SignalManager()
    yield sm
    sm.stop()  # daemon thread exits by itself within ~1s; no need to wait


S, SS = SignalManager.S_CHAIN_MAN, SignalManager.SS_ADD_CHAIN


def test_direct_send_calls_callback_synchronously(sigman):
    got = []
    sigman.register(S, SS, lambda **kw: got.append(kw))
    sigman.send(S, SS, chain_id=3)
    assert got == [{"chain_id": 3}]


def test_signals_are_routed_by_id_and_subid(sigman):
    got = []
    sigman.register(S, SS, lambda **kw: got.append("hit"))
    sigman.send(S, SignalManager.SS_REMOVE_CHAIN)
    sigman.send(SignalManager.S_CHAIN, SS)
    assert got == []


def test_multiple_callbacks_called_in_registration_order(sigman):
    order = []
    sigman.register(S, SS, lambda **kw: order.append(1))
    sigman.register(S, SS, lambda **kw: order.append(2))
    sigman.send(S, SS)
    assert order == [1, 2]


def test_registering_same_callback_twice_keeps_single_registration(sigman):
    calls = []

    def cb(**kw):
        calls.append(1)

    sigman.register(S, SS, cb)
    sigman.register(S, SS, cb)
    sigman.send(S, SS)
    assert calls == [1]


def test_unregister(sigman):
    calls = []

    def cb(**kw):
        calls.append(1)

    sigman.register(S, SS, cb)
    sigman.unregister(S, SS, cb)
    sigman.send(S, SS)
    assert calls == []


def test_unregister_all(sigman):
    calls = []

    def cb(**kw):
        calls.append(1)

    sigman.register(S, SS, cb)
    sigman.register(SignalManager.S_GUI, SignalManager.SS_GUI_SHOW_SCREEN, cb)
    sigman.unregister_all(cb)
    sigman.send(S, SS)
    sigman.send(SignalManager.S_GUI, SignalManager.SS_GUI_SHOW_SCREEN)
    assert calls == []


def test_failing_callback_does_not_stop_others(sigman):
    got = []

    def bad(**kw):
        raise RuntimeError("boom")

    sigman.register(S, SS, bad)
    sigman.register(S, SS, lambda **kw: got.append(1))
    sigman.send(S, SS)
    assert got == [1]


@pytest.mark.parametrize("sig,sub", [(-1, 0), (0, -1), (99, 0), (0, 99)])
def test_out_of_range_ids_are_ignored(sigman, sig, sub):
    sigman.register(sig, sub, lambda **kw: pytest.fail("must not be registered"))
    sigman.send(sig, sub)           # must not raise
    sigman.send_queued(sig, sub)    # must not raise


def test_queued_send_runs_callback_on_queue_thread(sigman):
    done = threading.Event()
    seen = {}

    def cb(**kw):
        seen["thread"] = threading.current_thread().name
        seen["kw"] = kw
        done.set()

    sigman.register(S, SS, cb)
    sigman.send_queued(S, SS, x=1)
    assert done.wait(TIMEOUT)
    assert seen["thread"] == "SIGNAL_QUEUE"
    assert seen["kw"] == {"x": 1}


def test_callback_registered_as_queued_is_deferred_even_for_direct_send(sigman):
    done = threading.Event()
    seen = {}

    def cb(**kw):
        seen["thread"] = threading.current_thread().name
        done.set()

    sigman.register_queued(S, SS, cb)
    sigman.send(S, SS)
    assert done.wait(TIMEOUT)
    assert seen["thread"] == "SIGNAL_QUEUE"


def test_failing_queued_callback_does_not_kill_the_queue_thread(sigman):
    done = threading.Event()

    def bad(**kw):
        raise RuntimeError("boom")

    sigman.register(S, SS, bad)
    sigman.register(S, SignalManager.SS_REMOVE_CHAIN, lambda **kw: done.set())
    sigman.send_queued(S, SS)
    sigman.send_queued(S, SignalManager.SS_REMOVE_CHAIN)
    assert done.wait(TIMEOUT)


@pytest.mark.parametrize("prefix", ["SS_GUI_", "SS_SEQ_", "SS_MIDI_ALL", "SS_SET_ACTIVE_CHAIN"])
def test_subsignal_ids_are_unique_inside_a_namespace(prefix):
    """Guards against copy/paste id clashes inside one group of SS_* constants."""
    if prefix.startswith("SS_MIDI"):
        names = ["SS_MIDI_ALL", "SS_MIDI_CC", "SS_MIDI_PC", "SS_MIDI_NOTE_ON", "SS_MIDI_NOTE_OFF", "SS_MIDI_SYSEX"]
    elif prefix == "SS_SET_ACTIVE_CHAIN":  # chain manager namespace
        names = ["SS_SET_ACTIVE_CHAIN", "SS_MOVE_CHAIN", "SS_ADD_CHAIN", "SS_REMOVE_CHAIN",
                 "SS_REMOVE_ALL_CHAINS", "SS_RENAME_CHAIN", "SS_ADD_PROCESSOR", "SS_REMOVE_PROCESSOR"]
    else:
        names = [n for n in vars(SignalManager) if n.startswith(prefix)]
    values = [getattr(SignalManager, n) for n in names]
    assert len(values) > 1
    assert len(values) == len(set(values))


def test_all_subsignal_ids_fit_in_register():
    """Every id must be < last_subsignal+1, or register()/send() silently ignore it."""
    for name, value in vars(SignalManager).items():
        if name.startswith("SS_"):
            assert 0 <= value <= SignalManager.last_subsignal, name
        elif name.startswith("S_"):
            assert 0 <= value <= SignalManager.last_signal, name
