"""zyngine.zynthian_controller: value model, scaling, toggles, labels, MIDI output."""

import pytest

import sys

from zyngine.zynthian_controller import zynthian_controller as Controller


def module():
    """The module object. ``from zyngine import zynthian_controller`` yields the *class*
    (zyngine/__init__ star-imports it, shadowing the submodule), so go via sys.modules."""
    return sys.modules["zyngine.zynthian_controller"]


class FakeEngine:
    """Minimal engine: records values pushed to it."""

    def __init__(self):
        self.sent = []

    def send_controller_value(self, zctrl):
        self.sent.append((zctrl.symbol, zctrl.value))


def make(options=None, engine=None, symbol="ctl"):
    return Controller(engine, symbol, options)


# ---------------------------------------------------------------------------
# Construction / defaults
# ---------------------------------------------------------------------------

def test_defaults_without_options():
    c = make()
    assert c.symbol == c.name == c.short_name == "ctl"
    assert c.value == 0
    assert c.is_integer is True
    assert c.value_range == 0 or c.value_range is None  # not configured until options are set


def test_numeric_range_integer():
    c = make({"value_min": 0, "value_max": 100, "value": 25})
    assert (c.value_min, c.value_max, c.value_range, c.value) == (0, 100, 100, 25)
    assert c.value_mid == 50
    assert c.is_integer


def test_numeric_range_float():
    c = make({"value_min": 0.0, "value_max": 1.0, "value": 0.5})
    assert c.is_integer is False
    assert c.value_range == 1.0


def test_default_range_is_midi_0_127():
    c = make({"name": "x"})
    assert (c.value_min, c.value_max) == (0, 127)


def test_value_default_seeds_value():
    c = make({"value_min": 0, "value_max": 10, "value_default": 4})
    assert c.value == 4


def test_name_sets_short_name_unless_given():
    assert make({"name": "Cutoff"}).short_name == "Cutoff"
    assert make({"name": "Cutoff", "short_name": "Cut"}).short_name == "Cut"


# ---------------------------------------------------------------------------
# set_value / clamping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("given,expected", [(-5, 0), (0, 0), (50, 50), (100, 100), (500, 100)])
def test_set_value_clamps(given, expected):
    c = make({"value_min": 0, "value_max": 100})
    c.set_value(given)
    assert c.value == expected


def test_integer_controller_truncates():
    c = make({"value_min": 0, "value_max": 100})
    c.set_value(12.9)
    assert c.value == 12


def test_float_controller_keeps_fraction():
    c = make({"value_min": 0.0, "value_max": 1.0})
    c.set_value(0.25)
    assert c.value == 0.25


def test_readonly_ignores_set_value():
    c = make({"value_min": 0, "value_max": 10, "value": 3})
    c.set_readonly()
    c.set_value(9)
    assert c.value == 3


def test_sustain_pedal_is_readonly():
    assert make({"value_max": 127}, symbol="sustain pedal").readonly


def test_set_value_marks_dirty_and_notifies_engine():
    eng = FakeEngine()
    c = make({"value_min": 0, "value_max": 10}, engine=eng)
    c.is_dirty = False
    c.set_value(7)
    assert c.is_dirty
    assert eng.sent == [("ctl", 7)]


def test_set_value_same_value_does_not_notify():
    eng = FakeEngine()
    c = make({"value_min": 0, "value_max": 10, "value": 5}, engine=eng)
    c.set_value(5)
    assert eng.sent == []


def test_send_false_suppresses_engine_notification():
    eng = FakeEngine()
    c = make({"value_min": 0, "value_max": 10}, engine=eng)
    c.set_value(3, send=False)
    assert c.value == 3 and eng.sent == []


def test_send_value_callback_is_called_and_errors_are_contained():
    c = make({"value_min": 0, "value_max": 10})
    seen = []
    c.set_send_value_cb(lambda z: seen.append(z.value))
    c.set_value(4)
    assert seen == [4]
    c.set_send_value_cb(lambda z: 1 / 0)
    c.set_value(5)  # must not raise
    c.reset_send_value_cb()
    c.set_value(6)
    assert seen == [4]


def test_reset_value_restores_default():
    c = make({"value_min": 0, "value_max": 10, "value_default": 2})
    c.set_value(9)
    c.reset_value()
    assert c.value == 2


# ---------------------------------------------------------------------------
# Toggle / trigger / labels
# ---------------------------------------------------------------------------

def test_two_labels_make_a_toggle():
    c = make({"labels": ["off", "on"], "value": 0})
    assert c.is_toggle
    assert (c.value_min, c.value_max) == (0, 127)
    c.toggle()
    assert c.value == 127
    c.toggle()
    assert c.value == 0


def test_toggle_snaps_to_nearest_end():
    c = make({"labels": ["off", "on"]})
    c.set_value(100)
    assert c.value == 127
    c.set_value(10)
    assert c.value == 0


def test_single_label_is_detected_as_trigger():
    c = make({"labels": ["go"]})
    assert c.is_trigger


def test_single_label_range_collapses_to_value_max():
    """Characterization (current behaviour, possibly unintended): a one-label controller gets
    ticks == [value_max], so value_min == value_max == 127 and set_value() never changes anything."""
    eng = FakeEngine()
    c = make({"labels": ["go"]}, engine=eng)
    assert (c.value_min, c.value_max, c.value) == (127, 127, 127)
    c.set_value(127)
    assert eng.sent == []


def test_trigger_sends_then_returns_to_min():
    eng = FakeEngine()
    c = make({"is_trigger": True, "value_min": 0, "value_max": 1}, engine=eng)
    c.set_value(1)
    assert eng.sent == [("ctl", 1)]
    assert c.value == c.value_min


def test_labels_generate_even_ticks():
    c = make({"labels": ["a", "b", "c", "d"], "value_min": 0, "value_max": 9})
    assert c.ticks == [0, 3, 6, 9]
    assert not c.is_toggle


def test_label_value_conversion_roundtrip():
    c = make({"labels": ["sine", "saw", "square"]})
    assert c.ticks == [0, 1, 2]
    assert c.get_label2value("saw") == 1
    assert c.get_value2label(2) == "square"
    c.set_value("square")
    assert c.value == 2


def test_value2label_snaps_to_closest_tick():
    c = make({"labels": ["a", "b", "c"], "value_min": 0, "value_max": 100})
    assert c.get_value2label(60) == "b"
    assert c.get_value2index(95) == 2


def test_pipe_separated_value_max_defines_labels():
    c = make({"value_max": "lo|mid|hi"})
    assert c.labels == ["lo", "mid", "hi"]


def test_explicit_ticks_reversed_range():
    c = make({"labels": ["x", "y"], "ticks": [10, 0]})
    assert c.range_reversed is True
    assert (c.value_min, c.value_max) == (0, 10)


def test_cycling_toggle_through_ticks():
    c = make({"labels": ["a", "b", "c"], "value": 0})
    c.toggle()
    assert c.value == 1
    c.toggle()
    c.toggle()
    assert c.value == 0


def test_unknown_label_returns_zero():
    c = make({"labels": ["a", "b", "c"]})
    assert c.get_label2value("zzz") == 0


# ---------------------------------------------------------------------------
# Nudging
# ---------------------------------------------------------------------------

def test_nudge_uses_nudge_factor():
    c = make({"value_min": 0, "value_max": 100, "value": 10, "nudge_factor": 5})
    c.nudge(2)
    assert c.value == 20
    c.nudge(-1)
    assert c.value == 15


def test_nudge_fine():
    c = make({"value_min": 0.0, "value_max": 1.0, "value": 0.5, "nudge_factor": 0.1, "nudge_factor_fine": 0.01})
    c.nudge(1, fine=True)
    assert c.value == pytest.approx(0.51)


def test_nudge_walks_ticks_and_stops_at_ends():
    c = make({"labels": ["a", "b", "c"], "value": 1})
    c.nudge(1)
    assert c.value == 2
    c.nudge(5)
    assert c.value == 2
    c.nudge(-10)
    assert c.value == 0


def test_nudge_is_clamped_to_range():
    c = make({"value_min": 0, "value_max": 10, "value": 9, "nudge_factor": 5})
    c.nudge(1)
    assert c.value == 10


@pytest.mark.parametrize("rng,expected", [
    (1.0, 0.01), (10.0, 0.1), (100.0, 1), (1000.0, 10)])
def test_default_nudge_factor_for_float_controls(rng, expected):
    c = make({"value_min": 0.0, "value_max": rng})
    assert c.nudge_factor == expected


def test_logarithmic_nudge_moves_monotonically():
    c = make({"value_min": 0.0, "value_max": 1000.0, "value": 100.0, "is_logarithmic": True})
    before = c.value
    c.nudge(1)
    assert c.value > before
    mid = c.value
    c.nudge(-2)
    assert c.value < before < mid


def test_path_controller_nudge_requests_file_selector(monkeypatch):
    mod = module()
    sent = []
    monkeypatch.setattr(mod.zynsigman, "send_queued", lambda *a, **kw: sent.append((a, kw)))
    c = make({"is_path": True, "path_file_types": ["wav"], "path_dir_names": ["samples"]})
    assert c.nudge(1) is True
    (sig, sub), kw = sent[0]
    assert (sig, sub) == (mod.zynsigman.S_GUI, mod.zynsigman.SS_GUI_SHOW_FILE_SELECTOR)
    assert kw["fexts"] == ["wav"] and kw["dirnames"] == ["samples"]
    assert c.value == ""


def test_path_controller_value_is_string():
    c = make({"is_path": True})
    c.set_value("/tmp/a.wav")
    assert c.value == "/tmp/a.wav"


# ---------------------------------------------------------------------------
# MIDI mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [(0, 0), (100, 127), (50, 63)])
def test_midi_value_linear(value, expected):
    c = make({"value_min": 0, "value_max": 100, "value": value})
    assert c.get_ctrl_midi_val() == expected


def test_midi_value_with_custom_cc_range():
    c = make({"value_min": 0, "value_max": 100, "value": 50})
    c.midi_cc_val1, c.midi_cc_val2 = 0, 200
    c.midi_cc_range = 200
    assert c.get_ctrl_midi_val() == 31


def test_midi_value_zero_range_is_zero():
    c = make({"value_min": 5, "value_max": 5, "value": 5})
    assert c.get_ctrl_midi_val() == 0


def test_osc_value_for_toggle_is_boolean():
    c = make({"labels": ["off", "on"], "value": 127})
    assert c.get_ctrl_osc_val() is True
    c.set_value(0)
    assert c.get_ctrl_osc_val() is False


def test_get_path_precedence():
    c = make({"value_max": 10})
    assert c.get_path() is None
    c.set_options({"midi_chan": 3, "midi_cc": 74})
    assert c.get_path() == "3#74"
    c.set_options({"graph_path": "a/b"})
    assert c.get_path() == "a/b"
    c.set_options({"osc_path": "/x"})
    assert c.get_path() == "/x"


def test_send_midi_cc_via_chain_zmop(zyncore):
    from types import SimpleNamespace
    c = make({"value_min": 0, "value_max": 127, "value": 64, "midi_chan": 2, "midi_cc": 74,
              "processor": SimpleNamespace(chain=SimpleNamespace(zmop_index=5))})
    c.send_midi_cc()
    assert zyncore.calls_to("zmop_send_ccontrol_change") == [(5, 2, 74, 64)]
    assert zyncore.call_count("ui_send_ccontrol_change") == 0


def test_send_midi_cc_falls_back_to_ui_port(zyncore):
    c = make({"value_min": 0, "value_max": 127, "value": 10, "midi_chan": 1, "midi_cc": 7})
    c.send_midi_cc()
    assert zyncore.calls_to("ui_send_ccontrol_change") == [(1, 7, 10)]


def test_engine_without_send_method_falls_back_to_midi(zyncore):
    """send_controller_value missing on the engine => MIDI CC is used instead."""
    c = make({"value_min": 0, "value_max": 127, "midi_chan": 0, "midi_cc": 7}, engine=object())
    c.set_value(99)
    assert zyncore.calls_to("ui_send_ccontrol_change") == [(0, 7, 99)]


def test_bypass_controller_emits_signal(monkeypatch):
    mod = module()
    sent = []
    monkeypatch.setattr(mod.zynsigman, "send_queued", lambda *a, **kw: sent.append((a, kw)))
    c = make({"labels": ["off", "on"], "is_bypass": True})
    c.set_value(127)
    assert sent and sent[0][0] == (mod.zynsigman.S_PROCESSOR, mod.zynsigman.SS_PROCESSOR_BYPASS)
    assert sent[0][1]["zctrl"] is c


# ---------------------------------------------------------------------------
# Engine feedback suppression
# ---------------------------------------------------------------------------

def test_ignore_engine_feedback_window(monkeypatch):
    mod = module()
    now = [100.0]
    monkeypatch.setattr(mod, "monotonic", lambda: now[0])
    c = make({"value_max": 10})
    assert c.get_ignore_engine_fb() is False
    c.set_ignore_engine_fb(2.0)
    assert c.get_ignore_engine_fb() is True   # inside window
    assert c.get_ignore_engine_fb() is False  # consumed
    c.set_ignore_engine_fb(2.0)
    now[0] = 103.0
    assert c.get_ignore_engine_fb() is False  # expired


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def test_get_state_full_vs_delta():
    c = make({"value_min": 0, "value_max": 100, "value_default": 10})
    assert c.get_state(full=False).get("value") is None
    c.set_value(40)
    assert c.get_state(full=False)["value"] == 40
    assert c.get_state(full=True)["value"] == 40


def test_get_state_reports_custom_midi_cc_range():
    c = make({"value_min": 0, "value_max": 100})
    c.midi_cc_val1 = 10
    assert c.get_state()["midi_cc_val1"] == 10
