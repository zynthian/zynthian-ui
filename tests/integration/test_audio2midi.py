"""Audio to MIDI converter: global processor (engine "AM", id -5) on the real state manager, native layer faked."""

import pytest

LIB = "libzynaudio2midi.so"


@pytest.fixture
def a2m(state_manager, native_libs):
    """(state manager, processor, fake library). The fake converter starts successfully and tracks running state."""
    lib = native_libs[LIB]
    running = {"value": 0}

    def start():
        running["value"] = 1
        return 1

    def stop():
        running["value"] = 0

    lib.returns["start"] = start
    lib.returns["stop"] = stop
    lib.returns["isRunning"] = lambda: running["value"]
    return state_manager, state_manager.audio2midi_processor, lib


def last_call(lib, name):
    calls = [args for fn, args in lib.log if fn == name]
    return calls[-1] if calls else None


def test_global_processor_exists(a2m):
    sm, proc, lib = a2m
    module = __import__("zyngine.zynthian_state_manager", fromlist=["AUDIO2MIDI_ID"])
    assert proc.id == module.AUDIO2MIDI_ID == -5
    assert sm.chain_manager.processors[-5] is proc
    assert proc.eng_code == "AM"
    assert proc.chain is None


def test_controllers_and_defaults(a2m):
    sm, proc, lib = a2m
    zctrls = proc.controllers_dict
    assert list(zctrls) == ["onset", "release", "polyphonic", "noise"]
    assert (zctrls["onset"].value, zctrls["release"].value, zctrls["polyphonic"].value, zctrls["noise"].value) == \
        (-40, -50, 0, 50)
    assert zctrls["polyphonic"].labels == ["mono", "poly"]
    # One control view page with the 4 controllers
    assert [s[1] for s in proc.engine._ctrl_screens] == [["onset", "release", "polyphonic", "noise"]]


def test_defaults_are_sent_to_library(a2m):
    sm, proc, lib = a2m
    for zctrl in proc.controllers_dict.values():
        proc.engine.send_controller_value(zctrl)
    assert last_call(lib, "setOnsetThreshold") == (-40,)
    assert last_call(lib, "setReleaseThreshold") == (-50,)
    assert last_call(lib, "setPolyphonic") == (0,)
    assert last_call(lib, "setNoiseFilter") == (50,)


@pytest.mark.parametrize("symbol, value, fn, expected", [
    ("onset", -30, "setOnsetThreshold", (-30,)),
    ("release", -60, "setReleaseThreshold", (-60,)),
    ("polyphonic", 1, "setPolyphonic", (1,)),
    ("noise", 80, "setNoiseFilter", (80,)),
])
def test_controller_change_is_sent_to_library(a2m, symbol, value, fn, expected):
    sm, proc, lib = a2m
    proc.controllers_dict[symbol].set_value(value, True)
    assert last_call(lib, fn) == expected


def test_disabled_by_default(a2m):
    from zyngui import zynthian_gui_config
    sm, proc, lib = a2m
    assert zynthian_gui_config.midi_audio2midi_enabled == 0
    assert not sm.is_audio2midi_running()
    assert last_call(lib, "start") is None


def test_start_and_stop(a2m, fake_autoconnect):
    from zyngui import zynthian_gui_config
    sm, proc, lib = a2m
    sm.start_audio2midi(save_config=False)
    assert sm.is_audio2midi_running()
    assert zynthian_gui_config.midi_audio2midi_enabled == 1
    fake_autoconnect.request_midi_connect.assert_called_with(True)
    sm.toggle_audio2midi(save_config=False)
    assert not sm.is_audio2midi_running()
    assert last_call(lib, "stop") == ()
    assert zynthian_gui_config.midi_audio2midi_enabled == 0


def test_start_applies_controller_values_first(a2m):
    sm, proc, lib = a2m
    proc.controllers_dict["onset"].set_value(-20, False)  # not sent yet
    sm.start_audio2midi(save_config=False)
    names = [fn for fn, args in lib.log]
    assert names.index("setOnsetThreshold") < names.index("start")
    assert last_call(lib, "setOnsetThreshold") == (-20,)
    sm.stop_audio2midi(save_config=False)


def test_failed_start_stays_disabled(a2m, native_libs):
    from zyngui import zynthian_gui_config
    sm, proc, lib = a2m
    lib.returns["start"] = 0
    sm.start_audio2midi(save_config=False)
    assert not sm.is_audio2midi_running()
    assert zynthian_gui_config.midi_audio2midi_enabled == 0


def test_audio_inputs_in_midi_capture_state(a2m, fake_autoconnect):
    import zynautoconnect
    sm, proc, lib = a2m
    assert sm.audio2midi_in == [1]
    aubio_in = list(sm.aubio_in)
    fake_autoconnect.get_midi_in_devid_by_uid.return_value = 3
    sm.set_midi_capture_state({zynautoconnect.AUDIO2MIDI_UID: {"zmip_input_mode": True, "disable_ctrldev": False,
                                                               "routed_chains": [], "audio_in": [2, 3]}})
    assert sm.audio2midi_in == [2, 3]
    assert sm.aubio_in == aubio_in  # Not mixed up with aubionotes inputs


def test_controllers_saved_in_state(a2m):
    sm, proc, lib = a2m
    proc.controllers_dict["onset"].set_value(-25, True)
    proc.controllers_dict["polyphonic"].set_value(1, True)
    sm.save_zs3("zs3-0")
    procs = sm.zs3["zs3-0"]["processors"]
    assert procs[-5]["controllers"]["onset"]["value"] == -25
    assert procs[-5]["controllers"]["polyphonic"]["value"] == 1
