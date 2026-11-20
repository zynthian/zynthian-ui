"""Contract tests for every controller-device driver (zyngine/ctrldev), on the real state manager.

Each driver goes through its whole life: construction, init(), a sweep of incoming MIDI (notes, CCs, program
change, pitch bend, pressure, SysEx), refresh(), state save/restore, light_off() and end(). It must not raise,
must only send device feedback to its own output device, and must leave no signal handler registered behind.
"""

import copy
import importlib
import threading

import pytest

from tests.bootstrap import REPO_ROOT

pytestmark = pytest.mark.integration

CTRLDEV = REPO_ROOT / "zyngine" / "ctrldev"
MODULES = sorted(p.stem for p in CTRLDEV.glob("zynthian_ctrldev_*.py")
                 if not p.stem.startswith("zynthian_ctrldev_base"))
IDEV_IN, IDEV_OUT = 1, 2


def midi_sweep():
    """Channel messages are always 3 bytes, as the state manager delivers them (zynmidi_read() slices a 32-bit
    word), so 2-byte messages arrive padded with a 0."""
    events = []
    for chan in (0, 9, 15):
        for note in range(0, 128, 5):
            events += [bytes([0x90 | chan, note, 100]), bytes([0x80 | chan, note, 0]), bytes([0x90 | chan, note, 0])]
        for cc in range(128):
            events += [bytes([0xB0 | chan, cc, 127]), bytes([0xB0 | chan, cc, 0]), bytes([0xB0 | chan, cc, 64])]
        events += [bytes([0xC0 | chan, 5, 0]), bytes([0xE0 | chan, 0, 64]), bytes([0xD0 | chan, 90, 0]),
                   bytes([0xA0 | chan, 60, 50])]
    events += [bytes.fromhex("F0 7E 00 06 02 47 29 00 19 00 00 00 00 00 F7"),   # identity reply
               bytes.fromhex("F0 00 20 29 02 18 F7")]
    return events


class FakeProcess:
    """Stands in for multiprocessing.Process (drivers with a midiproc task): nothing is spawned."""
    started = []

    def __init__(self, target=None, args=()):
        self.target, self.args = target, args

    def start(self):
        FakeProcess.started.append(self.args)

    def terminate(self):
        pass

    def join(self, *a):
        pass


class FakeStepSync:
    """Stands in for the APC Key25 mk2 StepSyncProvider, a multiprocessing.Process with its own JACK client."""

    def __init__(self, steps_per_beat, step_callback):
        self.steps_per_beat = steps_per_beat

    def __getattr__(self, name):          # enable, disable, stop, set_steps_per_beat, end, ...
        return lambda *args, **kwargs: None


def refuse_to_spawn(self):
    raise RuntimeError(f"tests must not start processes ({type(self).__name__})")


def live_foreground_threads():
    return {t for t in threading.enumerate() if t.is_alive() and not t.daemon and t is not threading.main_thread()}


def stop_leaked(driver, threads):
    """Stop what a driver left running, so the test process can still exit."""
    if hasattr(driver, "_init_complete"):
        driver._init_complete = True          # ends the SooperLooper reconnection loop at its next tick
    for t in threads:
        if isinstance(t, threading.Timer):
            t.cancel()
    for t in threads:
        t.join(3.0)


def registered(zynsigman):
    return [[len(sub) for sub in sig] for sig in zynsigman.signal_register]


@pytest.fixture
def driver_env(state_manager, monkeypatch, zyncore):
    import multiprocessing.process
    from zyngine.ctrldev import zynthian_ctrldev_akai_apc_key25_mk2 as apc_mk2
    from zyngine.ctrldev import zynthian_ctrldev_base as base
    from zyngine.zynthian_signal_manager import zynsigman
    monkeypatch.setattr(base, "mp", type("mp", (), {"Process": FakeProcess}))
    monkeypatch.setattr(base, "sleep", lambda s: None, raising=False)
    monkeypatch.setattr(apc_mk2, "StepSyncProvider", FakeStepSync)
    monkeypatch.setattr(multiprocessing.process.BaseProcess, "start", refuse_to_spawn)
    return state_manager, zynsigman


def load_class(module_name):
    module = importlib.import_module(f"zyngine.ctrldev.{module_name}")
    return getattr(module, module_name)


def test_every_driver_module_is_found_by_the_manager(state_manager):
    """The manager's discovery loads a class for every driver module (an import error would drop it silently)."""
    found = set(state_manager.ctrldev_manager.driver_classes)
    assert set(MODULES) <= found, f"not loaded: {sorted(set(MODULES) - found)}"


@pytest.mark.parametrize("module_name", MODULES)
def test_driver_declares_what_it_drives(state_manager, module_name):
    cls = load_class(module_name)
    assert isinstance(cls.dev_ids, list) and all(isinstance(d, str) for d in cls.dev_ids)
    assert cls.get_driver_name()
    assert getattr(cls, "driver_description", None) is None or isinstance(cls.driver_description, str)


# Drivers with a known defect: module -> (exception the lifecycle test fails with, why). The xfail is strict and
# pinned to that exception, so fixing the bug - or breaking the driver in a new way - makes the test fail.
KNOWN_BROKEN = {
    "zynthian_ctrldev_launchkey_mini_mk4_37": (AttributeError,
        "init() registers zynsigman.SS_ZCTRL_SET_VALUE, which does not exist (any more): the driver cannot load"),
    "zynthian_ctrldev_launchkey_mk4_37": (TypeError,
        "update_seq_state(bank, seq, state, mode, group) overrides the zynpad base method, which refresh() and the "
        "SS_SEQ_PLAY_STATE signal call with (phrase, chan): every refresh raises TypeError"),
    "zynthian_ctrldev_riband": (TypeError,
        "update_seq_state(phrase, chan, state, mode) overrides the zynpad base method, which refresh() and the "
        "SS_SEQ_PLAY_STATE signal call with (phrase, chan): every refresh raises TypeError"),
    "zynthian_ctrldev_launchkey_mini_mk3": (AttributeError,
        "a Program Change calls self.zynseq.select_bank(), which zynseq no longer has (AttributeError)"),
    "zynthian_ctrldev_fostex_mixtab": (TypeError,
        "CC#49 (parameter dump request) calls self.get_param(val) without its midi_chan argument (TypeError)"),
    "zynthian_ctrldev_launchpad_pro_mk2": (UnboundLocalError,
        "update_pad(): for a disabled sequence (repeat 0 / mode 0) no colour is chosen, so `vel` is unbound when "
        "the LED is sent (UnboundLocalError)"),
    "zynthian_ctrldev_akai_apc_40_mk2": (AttributeError,
        "pressing a launcher pad over a column without a chain dereferences None (`chain.midi_chan`)"),
    "zynthian_ctrldev_mackiecontrol": (IndexError,
        "pitch bend on a MIDI channel above 8 indexes fader_touch_active out of range (IndexError)"),
    "zynthian_ctrldev_korg_nanokontrol2": (IndexError,
        "a SysEx message that is not a nanoKONTROL2 dump makes the 7-bit decoder read past the end (IndexError)"),
    "zynthian_ctrldev_akai_apc_key25_mk2_sooperlooper": (AssertionError,
        "end() leaves the SooperLooper reconnection loop running: _try_connect_to_sooperlooper() keeps re-scheduling "
        "itself with non-daemon threading.Timer objects (every 1-2 s, forever), which also stops the process exiting"),
    "zynthian_ctrldev_akai_apc_key25_sooperlooper": (AssertionError,
        "inherits the mk2 SooperLooper driver: end() leaves its non-daemon reconnection Timers running"),
}


def lifecycle_params():
    params = []
    for m in MODULES:
        if m in KNOWN_BROKEN:
            exc, reason = KNOWN_BROKEN[m]
            params.append(pytest.param(m, marks=pytest.mark.xfail(strict=True, raises=exc, reason=reason)))
        else:
            params.append(m)
    return params


@pytest.mark.parametrize("module_name", lifecycle_params())
def test_driver_lifecycle(driver_env, zyncore, module_name):
    state_manager, zynsigman = driver_env
    cls = load_class(module_name)
    before = registered(zynsigman)
    threads_before = live_foreground_threads()

    driver = cls(state_manager, IDEV_IN, IDEV_OUT)
    try:
        driver.init()
        for ev in midi_sweep():
            driver.midi_event(ev)
        driver.refresh()
        state = driver.get_state()
        if state is not None:
            driver.set_state(copy.deepcopy(state))
        driver.light_off()
        driver.end()
    finally:
        leaked = live_foreground_threads() - threads_before
        stop_leaked(driver, leaked)

    assert registered(zynsigman) == before, "signal handlers left registered after end()"
    assert not leaked, f"end() left threads running: {sorted(t.name for t in leaked)}"
    targets = {args[0] for name, args in zyncore.log if name.startswith("dev_send")}
    assert targets <= {IDEV_OUT}, f"sent device feedback to {targets - {IDEV_OUT}}"


def test_apc40_mk2_end_unregisters_its_zs3_handler(driver_env):
    """init() registers on_zs3 for SS_LOAD_ZS3; end() must remove it (the signal manager has no
    unregister_queued(): unregister() removes queued handlers too)"""
    state_manager, zynsigman = driver_env
    before = registered(zynsigman)
    driver = load_class("zynthian_ctrldev_akai_apc_40_mk2")(state_manager, IDEV_IN, IDEV_OUT)
    driver.init()
    assert any(cb == driver.on_zs3 for cb, _ in zynsigman.signal_register[zynsigman.S_STATE_MAN][zynsigman.SS_LOAD_ZS3])
    driver.end()
    assert registered(zynsigman) == before, "signal handlers left registered after end()"


def test_behringer_motor_reset_feedback_unregisters_the_pianoteq_callbacks(driver_env):
    """reset_feedback() removes the driver's feedback callback from the Pianoteq controllers (it called
    unregister_send_value_cb() without the callback: TypeError)"""
    from types import SimpleNamespace
    from zyngine.zynthian_controller import zynthian_controller
    state_manager, zynsigman = driver_env
    cls = load_class("zynthian_ctrldev_behringer_motor")
    driver = cls(state_manager, IDEV_IN, IDEV_OUT)
    other = []
    proc = SimpleNamespace(controllers_dict={
        symbol: zynthian_controller(None, symbol, {"value_min": 0, "value_max": 127})
        for symbol in cls.zctrls2ccnum["Pianoteq"]})
    for zctrl in proc.controllers_dict.values():
        zctrl.register_send_value_cb(other.append)
    driver.pianoteq_proc = proc
    driver.setup_feedback()
    assert all(driver.send_feedback in z.send_value_cb for z in proc.controllers_dict.values())
    driver.reset_feedback()
    assert all(z.send_value_cb == [other.append] for z in proc.controllers_dict.values())
