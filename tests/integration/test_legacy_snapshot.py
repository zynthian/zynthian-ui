"""zynthian_legacy_snapshot: each conversion step, on small synthetic snapshots.

The corpus test (``test_legacy_snapshot_corpus.py``) checks real files convert; these tests pin down *what*
each step does. Inputs are minimal hand-written snapshots of the old formats.
"""

import copy
import json
import math

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def convert(state_manager):
    """convert(snapshot) -> converted state, with no state manager (V1 and V3 need one and are skipped)."""
    from zyngine.zynthian_legacy_snapshot import zynthian_legacy_snapshot

    def run(snapshot):
        return zynthian_legacy_snapshot().convert_state(copy.deepcopy(snapshot))
    return run


@pytest.fixture
def schema():
    from zyngine.zynthian_legacy_snapshot import SNAPSHOT_SCHEMA_VERSION
    return SNAPSHOT_SCHEMA_VERSION


# --- entry points -------------------------------------------------------------------------------------------
def test_a_snapshot_from_the_future_is_refused(convert, schema):
    assert convert({"schema_version": schema + 1, "chains": {}}) is None


def test_fractional_schema_versions_round_up(convert, schema):
    """1.1 is treated as 2 (it already has the 1 -> 2 changes)."""
    state = convert({"schema_version": 1.1, "chains": {"1": {"cc_route": [0, 1]}}, "zs3": {}})
    assert state["schema_version"] == 2
    assert state["chains"]["1"]["cc_route"] == [64, 66, 67, 69, 1]          # V2 -> V3 still applied


def test_current_schema_is_returned_unchanged(convert, schema):
    snap = {"schema_version": schema, "chains": {"1": {"slots": []}}, "zs3": {"zs3-0": {}}}
    assert convert(snap) == snap


def test_convert_file_with_invalid_json_returns_none(state_manager, tmp_path):
    from zyngine.zynthian_legacy_snapshot import zynthian_legacy_snapshot
    bad = tmp_path / "bad.zss"
    bad.write_text("{not json")
    assert zynthian_legacy_snapshot().convert_file(str(bad)) is None
    assert zynthian_legacy_snapshot().convert_file(str(tmp_path / "missing.zss")) is None


def test_the_converted_state_keeps_its_original_schema_version(convert):
    """Characterization: convert_state() does not bump ``schema_version`` (only V0 creates a new state). The state
    manager uses the result directly and saves with the current version, so this only matters to other callers:
    converting the result a second time would apply the steps again."""
    assert convert({"schema_version": 5, "chains": {}, "zs3": {}})["schema_version"] == 5


# --- V2 -> V3: CC pass-through ------------------------------------------------------------------------------
def test_v2_cc_route_flags_become_a_list_of_ccs_plus_pedals(convert):
    flags = [False] * 128
    flags[7] = flags[10] = True
    state = convert({"schema_version": 2, "chains": {"1": {"cc_route": flags}, "2": {}}, "zs3": {}})
    assert state["chains"]["1"]["cc_route"] == [64, 66, 67, 69, 7, 10]
    assert state["chains"]["2"]["cc_route"] == [64, 66, 67, 69]               # pedals always pass


# --- V4 -> V5: mixer strips become processors ----------------------------------------------------------------
def v4_snapshot():
    return {
        "schema_version": 4,
        "chains": {
            "0": {"mixer_chan": 16, "slots": []},                              # main chain
            "1": {"mixer_chan": 0, "slots": [{"1": "ZY"}], "midi_cc": {"7": [1, "volume"]}},
        },
        "zs3": {"zs3-0": {"processors": {"1": {"controllers": {}}},
                          "mixer": {"chan_00": {"level": 0.8, "balance": 0.1},
                                    "chan_16": {"level": 0.5},
                                    "midi_learn": {"0,11": [0, "level"]}}}},
    }


def test_v4_inserts_a_mixer_processor_after_the_last_slot(convert):
    state = convert(v4_snapshot())
    assert state["chains"]["1"]["slots"] == [{"1": "ZY"}, {"2": "MI"}]
    assert "mixer_chan" not in state["chains"]["1"]


def test_v4_main_chain_gets_the_main_mixbus(convert):
    from zyngine.zynthian_state_manager import MAIN_MIXBUS_ID
    state = convert(v4_snapshot())
    assert state["chains"]["0"]["slots"] == [{str(MAIN_MIXBUS_ID): "MR"}]


def test_v4_mixer_values_become_processor_controllers(convert):
    from zyngine.zynthian_state_manager import MAIN_MIXBUS_ID
    procs = convert(v4_snapshot())["zs3"]["zs3-0"]["processors"]
    assert "mixer" not in convert(v4_snapshot())["zs3"]["zs3-0"]
    assert procs[2]["controllers"]["balance"]["value"] == 0.1
    assert MAIN_MIXBUS_ID in procs and "level" in procs[MAIN_MIXBUS_ID]["controllers"]


def test_v4_mixer_midi_learn_binds_the_new_processor(convert):
    ctrl = convert(v4_snapshot())["zs3"]["zs3-0"]["processors"][2]["controllers"]["level"]
    assert ctrl["midi_cc"] == [None, 0, 11, 0]


def test_v4_chain_midi_cc_goes_to_the_base_zs3(convert):
    procs = convert(v4_snapshot())["zs3"]["zs3-0"]["processors"]
    ctrl = procs[1]["controllers"]["volume"]
    assert ctrl["midi_cc"] == ["1", None, 7, 0]


# --- V5 -> V6: MIDI learn keys and the mixer fader law ----------------------------------------------------------
def v5_snapshot(level=0.5):
    return {
        "schema_version": 5,
        "chains": {"1": {"slots": [{"1": "ZY"}, {"2": "MI"}]}},
        "zs3": {"zs3-0": {
            "chains": {"1": {"midi_learn": {"74": [[1, "cutoff"]]}}},
            "midi_capture": {"usb:keyboard": {"midi_learn": {"7": [[2, "level"]]}},
                             "zynseq:output": {"midi_learn": {}}},
            "processors": {"1": {"controllers": {"cutoff": {"value": 64}, "level": {"value": 0.5}}},
                           "2": {"controllers": {"level": {"value": level, "midi_cc_val1": 0.0,
                                                           "midi_cc_val2": 1.0}}}},
        }},
    }


def test_v5_chain_midi_learn_moves_to_every_device_with_hex_keys(convert):
    zs3 = convert(v5_snapshot())["zs3"]["zs3-0"]
    assert "midi_learn" not in zs3["chains"]["1"]
    keyboard = zs3["midi_capture"]["usb:keyboard"]["midi_learn"]
    assert keyboard["ff0007"] == [[2, "level"]]                    # device binding: "ff" + CC
    assert keyboard["01004A"] == [[1, "cutoff"]]                   # chain binding: chain + CC (74 = 0x4A)
    assert zs3["midi_capture"]["zynseq:output"]["midi_learn"] == {}  # not copied to internal sources


def test_v5_midi_learn_conversion_does_not_duplicate_bindings(convert):
    snap = v5_snapshot()
    snap["zs3"]["zs3-0"]["midi_capture"]["usb:keyboard"]["midi_learn"]["ff0007"] = [[2, "level"]]
    keyboard = convert(snap)["zs3"]["zs3-0"]["midi_capture"]["usb:keyboard"]["midi_learn"]
    assert keyboard["ff0007"] == [[2, "level"]]


def v5_aubio_snapshot(enabled="1"):
    snap = v5_snapshot()
    snap["midi_profile_state"] = {"AUBIONOTES_ENABLED": enabled, "BLE_ENABLED": "0"}
    snap["zs3"]["zs3-0"]["midi_capture"]["AUBIO:in"] = {
        "zmip_input_mode": False, "disable_ctrldev": False, "routed_chains": [1], "audio_in": [1, 2],
        "midi_learn": {"7": [[2, "level"]]}}
    return snap


@pytest.mark.parametrize("enabled", ["0", "1"])
def test_v5_aubionotes_enable_is_dropped(convert, enabled):
    """The converter has no enable option: it works when its ports are routed, as the aubionotes ports were"""
    mps = convert(v5_aubio_snapshot(enabled))["midi_profile_state"]
    assert mps == {"BLE_ENABLED": "0"}


def test_v5_aubionotes_midi_input_becomes_audio2midi_input(convert):
    capture = convert(v5_aubio_snapshot())["zs3"]["zs3-0"]["midi_capture"]
    assert "AUBIO:in" not in capture
    a2m = capture["AUDIO2MIDI:in"]
    assert (a2m["zmip_input_mode"], a2m["routed_chains"], a2m["audio_in"]) == (False, [1], [1, 2])
    assert a2m["midi_learn"]["ff0007"] == [[2, "level"]]   # MIDI learn converted like any other device
    assert a2m["midi_learn"]["01004A"] == [[1, "cutoff"]]


def test_v5_without_aubionotes_is_unchanged_by_its_conversion(convert):
    out = convert(v5_snapshot())
    assert "midi_profile_state" not in out
    assert set(out["zs3"]["zs3-0"]["midi_capture"]) == {"usb:keyboard", "zynseq:output"}


def fader_position(gain, headroom_db=10.0, unity=0.75):
    """mixer.c gainToLevel(), written out independently."""
    if gain <= 0:
        return 0.0
    if gain >= 1:
        return min(1.0, unity + (1 - unity) * 20 * math.log10(gain) / headroom_db)
    exp = headroom_db / (1 - unity) * unity * math.log(10) / 20
    return unity * gain ** (1 / exp)


@pytest.mark.parametrize("gain", [0.0, 0.01, 0.25, 0.5, 0.9, 1.0])
def test_v5_mixer_levels_are_converted_from_gain_to_fader_position(convert, gain):
    ctrl = convert(v5_snapshot(gain))["zs3"]["zs3-0"]["processors"]["2"]["controllers"]["level"]
    assert ctrl["value"] == pytest.approx(fader_position(gain), abs=1e-6)
    assert (ctrl["midi_cc_val1"], ctrl["midi_cc_val2"]) == pytest.approx((0.0, 0.75), abs=1e-6)


def test_v5_unity_gain_lands_on_the_fader_unity_mark(convert):
    ctrl = convert(v5_snapshot(1.0))["zs3"]["zs3-0"]["processors"]["2"]["controllers"]["level"]
    assert ctrl["value"] == pytest.approx(0.75)


def test_v5_levels_of_other_processors_are_untouched(convert):
    procs = convert(v5_snapshot())["zs3"]["zs3-0"]["processors"]
    assert procs["1"]["controllers"]["level"]["value"] == 0.5          # a synth's own "level" is not a fader


# --- V0: the pre-schema format ------------------------------------------------------------------------------------
def layer(nick, name, chan):
    return {"engine_nick": nick, "engine_name": name, "midi_chan": chan, "controllers_dict": {},
            "bank_info": ["Bank", 0, "Bank"], "preset_info": ["Preset", 0, "Preset"], "preset_index": 0}


def v0_snapshot(*layers, **extra):
    snap = {"index": 0, "layers": list(layers), "audio_routing": {}, "midi_routing": {},
            "note_range": [{"note_low": 0, "note_high": 127, "octave_trans": 0, "halftone_trans": 0}] * 16}
    snap.update(extra)
    return snap


def test_v0_layers_become_chains_with_a_mixer_strip(convert, schema):
    """Chain id = MIDI channel + 1 (int keys here; they become strings once saved as JSON)."""
    state = convert(v0_snapshot(layer("ZY", "ZynAddSubFX", 0), layer("FS", "FluidSynth", 3)))
    assert state["schema_version"] == schema
    assert state["chains"][1]["midi_chan"] == 0 and state["chains"][4]["midi_chan"] == 3
    assert [list(s.values())[0] for s in state["chains"][1]["slots"]] == ["ZY", "MI"]
    assert state["zs3"]["zs3-0"]["active_chain"] == 1
    json.dumps(state)


def test_v0_note_range_goes_to_the_chain_state(convert):
    ranges = [{"note_low": 0, "note_high": 127, "octave_trans": 0, "halftone_trans": 0}] * 16
    ranges = ranges[:2] + [{"note_low": 36, "note_high": 60, "octave_trans": -1, "halftone_trans": 2}] + ranges[3:]
    chain = convert(v0_snapshot(layer("ZY", "ZynAddSubFX", 2), note_range=ranges))["zs3"]["zs3-0"]["chains"][3]
    assert (chain["note_low"], chain["note_high"], chain["transpose_octave"], chain["transpose_semitone"]) == \
        (36, 60, -1, 2)


@pytest.mark.xfail(strict=True, reason="version_0 indexes note_range[midi_chan] unconditionally; the oldest "
                                       "snapshots have no 'note_range' (they have 'transpose') -> IndexError, "
                                       "zynthian_legacy_snapshot.py:452")
def test_v0_snapshot_without_note_range_converts(convert):
    snap = v0_snapshot(layer("ZY", "ZynAddSubFX", 0))
    del snap["note_range"]
    assert convert(snap)["chains"][1]["midi_chan"] == 0


@pytest.mark.xfail(strict=True, reason="version_0 computes `midi_chan + 1` for every layer; MOD-UI layers in old "
                                       "snapshots have midi_chan None -> TypeError, zynthian_legacy_snapshot.py:432")
def test_v0_mod_ui_layer_without_midi_channel_converts(convert):
    assert convert(v0_snapshot(layer("MD", "MOD-UI", None), layer("ZY", "ZynAddSubFX", 0))) is not None
