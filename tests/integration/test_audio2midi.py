"""Audio to MIDI converter: global processor (engine "AM", id -5) on the real state manager, native layer faked."""

import types

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
    assert {s: zctrls[s].value for s in zctrls} == {
        "onset": -60, "release": -66, "noise": 15,
        "audio_in": 0, "polyphonic": 0, "pitchbend": 1, "bend_range": 2,          # channel 1: mono with pitch bend
        "audio_in_2": 0, "polyphonic_2": 0, "pitchbend_2": 0, "bend_range_2": 2}  # channel 2: mono
    for sfx in ("", "_2"):
        assert zctrls[f"polyphonic{sfx}"].labels == ["mono", "poly"]
        assert zctrls[f"pitchbend{sfx}"].labels == ["off", "on"]
    assert zctrls["audio_in"].labels[0] == "none" and zctrls["audio_in_2"].labels[0] == "none"
    # Control view pages: those of channel 1
    assert proc.engine._ctrl_screens == [["Audio detector (common)", ["onset", "release", "noise"]],
                                         ["MIDI Output", ["audio_in", "polyphonic", "pitchbend", "bend_range"]]]
    assert proc.name == "Audio \u2794 MIDI 1"


def test_control_view_shows_the_pages_of_one_channel(a2m):
    sm, proc, lib = a2m
    proc.engine.set_channel(1)
    assert list(proc.get_ctrl_screens()) == ["Audio detector (common)", "MIDI Output"]
    assert [z.symbol for z in proc.get_ctrl_screen("Audio detector (common)")] == ["onset", "release", "noise"]
    assert [z.symbol for z in proc.get_ctrl_screen("MIDI Output")] == ["audio_in_2", "polyphonic_2", "pitchbend_2",
                                                                      "bend_range_2"]
    assert proc.name == "Audio \u2794 MIDI 2"  # title of the control view
    assert proc.get_basepath() == "Audio \u2794 MIDI 2"
    proc.engine.set_channel(0)
    assert proc.name == "Audio \u2794 MIDI 1"
    assert [z.symbol for z in proc.get_ctrl_screen("MIDI Output")][0] == "audio_in"


@pytest.mark.parametrize("symbol, channel", [("audio_in", 0), ("audio_in_2", 1)])
def test_audio_input_controller_sets_the_channel_input(a2m, fake_autoconnect, symbol, channel):
    sm, proc, lib = a2m
    fake_autoconnect.get_audio_capture_ports.return_value = [object()] * 4
    proc.engine.refresh_audio_in_ctrls()
    assert proc.controllers_dict[symbol].labels[1:] == ["1", "2", "3", "4"]
    fake_autoconnect.request_audio_connect.reset_mock()
    proc.controllers_dict[symbol].set_value(2, True)
    expected = [[], []]
    expected[channel] = [2]
    assert sm.audio2midi_in == expected
    fake_autoconnect.request_audio_connect.assert_called()
    proc.controllers_dict[symbol].set_value(0, True)
    assert sm.audio2midi_in == [[], []]


@pytest.mark.parametrize("audio_in, labels", [
    ([[], []], ("none", "none")),
    ([[2], []], ("none", "same as 1")),  # (channel 1, channel 2) label of the "no input" value
    ([[], [1]], ("same as 2", "none")),
    ([[1], [2]], ("same as 2", "same as 1")),
])
def test_no_input_label_names_the_channel_feeding_it(a2m, audio_in, labels):
    sm, proc, lib = a2m
    sm.audio2midi_in = [list(a) for a in audio_in]
    proc.engine.refresh_audio_in_ctrls()
    assert proc.controllers_dict["audio_in"].labels[0] == labels[0]
    assert proc.controllers_dict["audio_in_2"].labels[0] == labels[1]


def test_no_input_label_follows_the_other_channel(a2m, fake_autoconnect):
    sm, proc, lib = a2m
    proc.controllers_dict["audio_in"].set_value(1, True)
    assert proc.controllers_dict["audio_in_2"].labels[0] == "same as 1"
    assert proc.controllers_dict["audio_in_2"].is_dirty  # redrawn
    proc.controllers_dict["audio_in"].set_value(0, True)
    assert proc.controllers_dict["audio_in_2"].labels[0] == "none"


def test_audio_input_controllers_follow_the_capture_state(a2m, fake_autoconnect):
    """The MIDI capture state holds the audio inputs: the controllers show them, and restoring the processor state
    doesn't change them"""
    import zynautoconnect
    sm, proc, lib = a2m
    fake_autoconnect.get_audio_capture_ports.return_value = [object()] * 4
    zynautoconnect.devices_in[3] = types.SimpleNamespace(aliases=["AUDIO2MIDI:in_2", "Audio \u2794 MIDI"])
    fake_autoconnect.get_midi_in_devid_by_uid.return_value = 3
    sm.set_midi_capture_state({"AUDIO2MIDI:in_2": {"routed_chains": [], "audio_in": [2]}})
    assert proc.controllers_dict["audio_in_2"].value == 2
    proc.set_state({"controllers": {"audio_in_2": {"value": 1}, "audio_in": {"value": 1}}})
    assert sm.audio2midi_in == [[], [2]]


def test_defaults_are_sent_to_library(a2m):
    sm, proc, lib = a2m
    for zctrl in proc.controllers_dict.values():
        proc.engine.send_controller_value(zctrl)
    assert last_call(lib, "setOnsetThreshold") == (-60,)
    assert last_call(lib, "setReleaseThreshold") == (-66,)
    assert last_call(lib, "setNoiseFilter") == (15,)
    calls = [(fn, args) for fn, args in lib.log if fn in ("setPolyphonic", "setPitchBend", "setBendRange")]
    assert sorted(calls[-6:]) == [("setBendRange", (0, 2)), ("setBendRange", (1, 2)), ("setPitchBend", (0, 1)),
                                  ("setPitchBend", (1, 0)), ("setPolyphonic", (0, 0)), ("setPolyphonic", (1, 0))]


@pytest.mark.parametrize("symbol, value, fn, expected", [
    ("onset", -30, "setOnsetThreshold", (-30,)),
    ("release", -60, "setReleaseThreshold", (-60,)),
    ("noise", 80, "setNoiseFilter", (80,)),
    ("polyphonic", 1, "setPolyphonic", (0, 1)),
    ("pitchbend", 0, "setPitchBend", (0, 0)),
    ("bend_range", 12, "setBendRange", (0, 12)),
    ("polyphonic_2", 1, "setPolyphonic", (1, 1)),
    ("pitchbend_2", 1, "setPitchBend", (1, 1)),
    ("bend_range_2", 7, "setBendRange", (1, 7)),
])
def test_controller_change_is_sent_to_library(a2m, symbol, value, fn, expected):
    sm, proc, lib = a2m
    proc.controllers_dict[symbol].set_value(value, True)
    assert last_call(lib, fn) == expected


def test_started_with_midi_services(a2m, monkeypatch):
    """No enable option: the converter always runs (it only analyses what is routed)"""
    from unittest import mock
    sm, proc, lib = a2m
    for name in ("default_rtpmidi", "default_qmidinet", "default_touchosc", "default_bluetooth"):
        monkeypatch.setattr(sm, name, mock.MagicMock())
    lib.log.clear()
    sm.init_midi_services()
    assert sm.is_audio2midi_running()
    sm.init_midi_services()  # e.g. MIDI profile reload: started once
    assert [fn for fn, args in lib.log].count("start") == 1


def test_start(a2m, fake_autoconnect):
    sm, proc, lib = a2m
    assert not sm.is_audio2midi_running()
    sm.start_audio2midi()
    assert sm.is_audio2midi_running()
    fake_autoconnect.request_midi_connect.assert_called_with(True)
    fake_autoconnect.request_audio_connect.assert_called_with(True)


def test_start_applies_controller_values_first(a2m):
    sm, proc, lib = a2m
    proc.controllers_dict["onset"].set_value(-20, False)  # not sent yet
    sm.start_audio2midi()
    names = [fn for fn, args in lib.log]
    assert names.index("setOnsetThreshold") < names.index("start")
    assert last_call(lib, "setOnsetThreshold") == (-20,)


def test_failed_start(a2m):
    sm, proc, lib = a2m
    lib.returns["start"] = 0
    sm.start_audio2midi()
    assert not sm.is_audio2midi_running()


def test_audio_inputs_not_connected_by_default(a2m):
    sm, proc, lib = a2m
    assert sm.audio2midi_in == [[], []]


@pytest.mark.parametrize("uid, index", [("AUDIO2MIDI:in", 0), ("AUDIO2MIDI:in_2", 1)])
def test_audio_inputs_in_midi_capture_state(a2m, fake_autoconnect, uid, index):
    """Each output's capture state holds the audio inputs of the converter input feeding it"""
    import zynautoconnect
    sm, proc, lib = a2m
    zynautoconnect.devices_in[3] = types.SimpleNamespace(aliases=[uid, "Audio \u2794 MIDI"])
    fake_autoconnect.get_midi_in_devid_by_uid.return_value = 3
    sm.set_midi_capture_state({uid: {"zmip_input_mode": True, "disable_ctrldev": False,
                                     "routed_chains": [], "audio_in": [2, 3]}})
    expected = [[], []]
    expected[index] = [2, 3]
    assert sm.audio2midi_in == expected
    fake_autoconnect.request_audio_connect.assert_called()
    assert sm.get_midi_capture_state()[uid]["audio_in"] == [2, 3]
    # A state without audio inputs disconnects them
    sm.set_midi_capture_state({uid: {"routed_chains": []}})
    assert sm.audio2midi_in == [[], []]


def test_default_input_connects_audio_input_1_when_none_connected(a2m, fake_autoconnect):
    """Routing an output to a chain with no audio connected to the converter connects audio input 1 to input 1"""
    sm, proc, lib = a2m
    fake_autoconnect.request_audio_connect.reset_mock()
    assert sm.audio2midi_default_input()
    assert sm.audio2midi_in == [[1], []]
    assert proc.controllers_dict["audio_in"].value == 1
    fake_autoconnect.request_audio_connect.assert_called()


@pytest.mark.parametrize("audio_in", [[[3], []], [[], [2]]])
def test_default_input_keeps_connected_audio_inputs(a2m, fake_autoconnect, audio_in):
    """One connected input feeds both outputs"""
    sm, proc, lib = a2m
    sm.audio2midi_in = [list(a) for a in audio_in]
    fake_autoconnect.request_audio_connect.reset_mock()
    assert not sm.audio2midi_default_input()
    assert sm.audio2midi_in == audio_in
    fake_autoconnect.request_audio_connect.assert_not_called()


def test_controllers_saved_in_state(a2m):
    sm, proc, lib = a2m
    proc.controllers_dict["onset"].set_value(-25, True)
    proc.controllers_dict["polyphonic"].set_value(1, True)
    sm.save_zs3("zs3-0")
    procs = sm.zs3["zs3-0"]["processors"]
    assert procs[-5]["controllers"]["onset"]["value"] == -25
    assert procs[-5]["controllers"]["polyphonic"]["value"] == 1


def test_help_page(a2m):
    import os
    sm, proc, lib = a2m
    assert proc.engine.custom_gui_help_fpath.endswith("/common/audio2midi.html")
    repo_page = os.path.join(os.path.dirname(__file__), "..", "..", "help", "common", "audio2midi.html")
    if os.path.isdir(os.path.join(os.path.dirname(repo_page), "..")):  # zynthian-help checked out next to the UI
        assert os.path.isfile(repo_page)


# --- Outputs: routing and activation ---------------------------------------------------------------------------------

A2M_ZMIPS = [3, 7]  # zmip of each converter output in these tests


@pytest.fixture
def routing(a2m, zyncore, fake_autoconnect):
    """(state manager, fake converter library, routes): routes is the zyncore routing table {(zmop, zmip)}."""
    sm, proc, lib = a2m
    routes = set()

    def set_route(zmop, zmip, route):
        (routes.add if route else routes.discard)((zmop, zmip))

    zyncore.returns["zmop_set_route_from"] = set_route
    zyncore.returns["zmop_get_route_from"] = lambda zmop, zmip: int((zmop, zmip) in routes)
    fake_autoconnect.get_audio2midi_zmips.return_value = list(A2M_ZMIPS)
    fake_autoconnect.is_audio2midi_zmip.side_effect = lambda zmip: zmip in A2M_ZMIPS
    return sm, lib, routes


def active_outputs(lib):
    return {output: active for output, active in (args for fn, args in lib.log if fn == "setOutputActive")}


def test_new_chain_is_not_routed_from_converter_outputs(routing):
    sm, lib, routes = routing
    sm.chain_manager.add_chain(1, midi_chan=0)
    zmop = sm.chain_manager.chains[1].zmop_index
    assert (zmop, 0) in routes and (zmop, 5) in routes        # other MIDI inputs: routed by default
    assert (zmop, 3) not in routes and (zmop, 7) not in routes


def test_only_outputs_routed_to_a_chain_are_active(routing):
    sm, lib, routes = routing
    sm.chain_manager.add_chain(1, midi_chan=0)
    zmop = sm.chain_manager.chains[1].zmop_index
    sm.update_audio2midi_outputs()
    assert active_outputs(lib) == {0: 0, 1: 0}  # Nothing routed: no CPU used
    routes.add((zmop, 7))
    sm.update_audio2midi_outputs()
    assert active_outputs(lib) == {0: 0, 1: 1}


def test_routes_of_removed_chains_do_not_activate_outputs(routing):
    sm, lib, routes = routing
    routes.add((9, 3))  # zmop 9 has no chain
    sm.update_audio2midi_outputs()
    assert active_outputs(lib) == {0: 0, 1: 0}


def test_stopped_converter_outputs_are_inactive(routing, fake_autoconnect):
    sm, lib, routes = routing
    fake_autoconnect.get_audio2midi_zmips.return_value = [None, None]
    sm.update_audio2midi_outputs()
    assert active_outputs(lib) == {0: 0, 1: 0}


def test_new_converter_port_is_routed_to_no_chain(routing):
    sm, lib, routes = routing
    routes.update({(0, 3), (1, 3), (2, 7)})  # e.g. left by another device in the same slot
    sm.restore_audio2midi_port(3, "AUDIO2MIDI:in")
    assert routes == {(2, 7)}


def test_converter_port_routing_restored_from_zs3_is_kept(routing):
    sm, lib, routes = routing
    routes.add((1, 3))
    sm.restore_audio2midi_port(3, "AUDIO2MIDI:in", restored=True)
    assert routes == {(1, 3)}


def test_converter_routing_survives_a_restart(routing):
    sm, lib, routes = routing
    routes.update({(1, 3), (4, 3)})
    sm.forget_audio2midi_port(3, "AUDIO2MIDI:in")             # stopped (e.g. JACK restart)
    assert routes == {(zmop, 3) for zmop in range(16)}         # slot back to the default for other devices
    sm.restore_audio2midi_port(3, "AUDIO2MIDI:in", restored=True)  # started again: newer than the ZS3
    assert routes == {(1, 3), (4, 3)}


def test_converter_routing_is_saved_while_stopped(routing, fake_autoconnect):
    import zynautoconnect
    sm, lib, routes = routing
    sm.audio2midi_routes = {"AUDIO2MIDI:in_2": [2]}
    sm.audio2midi_in = [[1], [2]]
    mcstate = sm.get_midi_capture_state()
    assert mcstate["AUDIO2MIDI:in_2"]["routed_chains"] == [2]
    assert mcstate["AUDIO2MIDI:in_2"]["audio_in"] == [2]
    # ... and restored while stopped: applied once started
    sm.audio2midi_routes = {}
    fake_autoconnect.get_midi_in_devid_by_uid.return_value = None
    sm.set_midi_capture_state({"AUDIO2MIDI:in_2": {"routed_chains": [2, 5]},
                               zynautoconnect.AUDIO2MIDI_UID: {"routed_chains": [], "audio_in": [2]}})
    assert sm.audio2midi_routes == {"AUDIO2MIDI:in_2": [2, 5], "AUDIO2MIDI:in": []}
    assert sm.audio2midi_in == [[2], []]
