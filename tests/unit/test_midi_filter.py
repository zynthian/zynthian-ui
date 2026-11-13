"""zyngine.zynthian_midi_filter: rule parsing and the calls made to zyncore.

Ported from the ``TestMidiFilterRule`` class embedded in the module (which is
left untouched) and extended to assert what is sent to the native layer.
"""

import pytest

from zyngine.zynthian_midi_filter import (
    MidiFilterArgs, MidiFilterException, MidiFilterRule, MidiFilterScript)

NON, NOFF, KP, CC, PB, PC, CP = 0x9, 0x8, 0xA, 0xB, 0xE, 0xC, 0xD


# ---------------------------------------------------------------------------
# MidiFilterArgs
# ---------------------------------------------------------------------------

class TestArgs:
    def test_channel_only(self):
        a = MidiFilterArgs(["CH#3"])
        assert a.ch_list == [3]
        assert a.ev_type is None and a.ev_list is None

    def test_ranges_and_lists(self):
        a = MidiFilterArgs(["CH#1,2,3:5", "CC#7"])
        assert a.ch_list == [1, 2, 3, 4, 5]
        assert a.ev_type == "CC"
        assert a.ev_list == [7]

    def test_event_without_number_means_all(self):
        a = MidiFilterArgs(["CH#0", "CC"])
        assert list(a.ev_list) == list(range(128))

    def test_single_arg_types_take_no_number(self):
        a = MidiFilterArgs(["CH#0", "PB"])
        assert a.ev_list == [0]
        with pytest.raises(MidiFilterException):
            MidiFilterArgs(["CH#0", "PB#7"])

    def test_event_only_defaults_to_all_channels(self):
        a = MidiFilterArgs(["CC#1"])
        assert list(a.ch_list) == list(range(16))

    def test_event_only_inherits_channels_from_first_arg(self):
        first = MidiFilterArgs(["CH#2,3"])
        second = MidiFilterArgs(["CC#1"], first)
        assert second.ch_list == [2, 3]

    @pytest.mark.parametrize("args", [
        ["CH#1", "CC#1", "CC#2"],   # too many
        ["CC#1", "CC#2"],           # first must be a channel
        ["CH"],                     # channel needs a number
        ["CH#1", "XX#1"],           # unknown event type
        ["CH#1:2:3"],               # bad range
    ])
    def test_invalid(self, args):
        with pytest.raises(MidiFilterException):
            MidiFilterArgs(args)


# ---------------------------------------------------------------------------
# Rules (ported from the embedded unittest)
# ---------------------------------------------------------------------------

class TestRules:
    def test_absurde_rule_type(self):
        with pytest.raises(MidiFilterException):
            MidiFilterRule("ABSURDE CH#1,2,3:8 PB#7,8", False)

    @pytest.mark.parametrize("rule,expected", [
        ("IGNORE CH#3", 128 * 7),
        ("IGNORE CH#3 CC#5", 1),
        ("IGNORE CH#3,5,7 PB", 3),
        ("IGNORE CH#3:8 CC#1:3", 18),
        ("IGNORE CH#1,2,3:8 CC#1:3,7,8", 40),
    ])
    def test_ignore_rule_count(self, rule, expected):
        assert MidiFilterRule(rule, False).set_rules(False) == expected

    @pytest.mark.parametrize("rule", [
        "IGNORE XH#1,2,3:8 PB#7,8",
        "IGNORE CH#1,2,3:8 XB#7,8",
        "IGNORE CH#1,2,3:8 PB#7,8",   # PB takes no number
        "IGNORE CH#1,2,3:8 CP#1:3",   # CP takes no number
    ])
    def test_bad_ignore_rules(self, rule):
        with pytest.raises(MidiFilterException):
            MidiFilterRule(rule, False)

    @pytest.mark.parametrize("rule,expected", [
        ("MAP CH#3 => CH#1", 128 * 7),
        ("MAP CH#1 CC#5 => CC#7", 1),
        ("MAP CH#3 CC#5 => CH#4 CC#7", 1),
        ("MAP CH#0 CC#71 => CH#1 PB", 1),
        ("MAP CH#3,5,7 CC#5,3 => CH#4,7,8 CC#9,10", 6),
        ("MAP CH#3:8 CC#1:3 => CH#4:9 CC#3:5", 18),
        ("MAP CH#1,2,3:8 CC#1:3,7,8 => CH#5:10,11,12 CC#1,2,4:6", 40),
        ("MAP CH#0:15 CC#45 => CH#15 CC#76", 16),
    ])
    def test_map_rule_count(self, rule, expected):
        assert MidiFilterRule(rule, False).set_rules(False) == expected

    @pytest.mark.parametrize("rule", [
        "MAP XH#1,2,3:8 PB#7,8 => JK#76",
        "MAP CH#1,2,3:8 PB#7,8 => CH#4:11 CC#2,5",
        "MAP CH#2,3:8 CC#7,8 => CH#4:11 CC#2,5",
        "MAP CH#3,4 CC#1 => CH#1,2,3 CC#1",   # channel lists can't be matched
    ])
    def test_bad_map_rules(self, rule):
        with pytest.raises(MidiFilterException):
            MidiFilterRule(rule, False)

    def test_multiline_rule_rejected(self):
        with pytest.raises(MidiFilterException):
            MidiFilterRule("IGNORE CH#1\nIGNORE CH#2", False)


# ---------------------------------------------------------------------------
# What reaches zyncore
# ---------------------------------------------------------------------------

class TestNativeCalls:
    def test_parsing_without_set_rules_touches_nothing(self, zyncore):
        MidiFilterRule("IGNORE CH#3 CC#5", False)
        assert zyncore.call_count() == 0

    def test_ignore_sends_one_call_per_event(self, zyncore):
        MidiFilterRule("IGNORE CH#3 CC#5")
        assert zyncore.calls_to("set_midi_filter_event_ignore") == [(CC, 3, 5)]

    def test_ignore_pitchbend_on_several_channels(self, zyncore):
        MidiFilterRule("IGNORE CH#1,2 PB")
        assert zyncore.calls_to("set_midi_filter_event_ignore") == [(PB, 1, 0), (PB, 2, 0)]

    def test_map_cc_to_cc(self, zyncore):
        MidiFilterRule("MAP CH#1 CC#5 => CC#7")
        assert zyncore.calls_to("set_midi_filter_event_map") == [(CC, 1, 5, CC, 1, 7)]

    def test_map_changes_channel(self, zyncore):
        MidiFilterRule("MAP CH#3 CC#5 => CH#4 CC#7")
        assert zyncore.calls_to("set_midi_filter_event_map") == [(CC, 3, 5, CC, 4, 7)]

    def test_map_cc_to_pitchbend(self, zyncore):
        MidiFilterRule("MAP CH#0 CC#71 => CH#1 PB")
        assert zyncore.calls_to("set_midi_filter_event_map") == [(CC, 0, 71, PB, 1, 0)]

    def test_clean_deletes_map(self, zyncore):
        MidiFilterRule("CLEAN CH#2 CC#9")
        assert zyncore.calls_to("del_midi_filter_event_map") == [(CC, 2, 9)]

    def test_del_rules_cleans_what_it_set(self, zyncore):
        rule = MidiFilterRule("IGNORE CH#2 CC#9:10", False)
        assert rule.del_rules() == 2
        assert zyncore.calls_to("del_midi_filter_event_map") == [(CC, 2, 9), (CC, 2, 10)]


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------

class TestScript:
    def test_string_script(self, zyncore):
        script = MidiFilterScript("IGNORE CH#1 CC#1\nMAP CH#1 CC#2 => CC#3", True)
        assert len(script.rules) == 2
        assert zyncore.call_count("set_midi_filter_event_ignore") == 1
        assert zyncore.call_count("set_midi_filter_event_map") == 1

    def test_list_script_skips_blank_lines_and_comments(self, zyncore):
        script = MidiFilterScript(["", "   ", "// IGNORE CH#9 CC#1", "IGNORE CH#1 CC#1"], True)
        assert list(script.rules) == ["IGNORE CH#1 CC#1"]
        assert zyncore.call_count() == 1

    def test_too_short_rule(self):
        with pytest.raises(MidiFilterException):
            MidiFilterScript("IGNORE", False)

    def test_wrong_script_type(self):
        with pytest.raises(MidiFilterException):
            MidiFilterScript(123, False)

    def test_clean_removes_only_script_rules(self, zyncore):
        script = MidiFilterScript("IGNORE CH#1 CC#1", False)
        script.clean()
        assert zyncore.calls_to("del_midi_filter_event_map") == [(CC, 1, 1)]

    def test_clean_all_resets_event_map(self, zyncore):
        MidiFilterScript().clean_all()
        assert zyncore.call_count("reset_midi_filter_event_map") == 1
