"""Two outputs with their own mode, sharing the detection (offline, ``analyse()`` with an output bitmask)."""

import numpy as np
import pytest

from tests.native.zynaudio2midi.conftest import NOTE_ON, analyse_outputs, pluck, silence
from tests.native.zynaudio2midi.test_detection import STRING_BEND, chords, glide, notes_and_bends, sequence

MELODY = sequence([40, 45, 50, 55, 59, 64])[0]
CHORDS = chords([[48, 52, 55], [43, 50, 55, 59]], amp=0.15)
SIGNALS = {"melody": MELODY, "chords": CHORDS, "string bend": glide(*STRING_BEND)}
MODES = {"mono": dict(poly=0, bend=0), "mono bend": dict(poly=0, bend=1), "mono bend 12": dict(poly=0, bend=1, rng=12),
         "poly": dict(poly=1, bend=0)}


def configure(lib, output, poly=0, bend=0, rng=2):
    lib.setPolyphonic(output, poly)
    lib.setPitchBend(output, bend)
    lib.setBendRange(output, rng)


def alone(lib, signal, mode):
    """Events of an output with the given mode when it is the only active one."""
    configure(lib, 0, **MODES[mode])
    return analyse_outputs(lib, signal, 0b01)[0]


def test_no_active_output_sends_nothing(a2m):
    assert analyse_outputs(a2m, MELODY, 0b00) == {0: [], 1: []}


def test_an_inactive_output_sends_nothing(a2m):
    events = analyse_outputs(a2m, MELODY, 0b01)
    assert events[0] and events[1] == []
    events = analyse_outputs(a2m, MELODY, 0b10)
    assert events[0] == [] and events[1]


@pytest.mark.parametrize("signal", SIGNALS)
@pytest.mark.parametrize("mode0, mode1", [("mono", "mono bend"), ("mono", "poly"), ("mono bend 12", "poly"),
                                          ("poly", "mono bend"), ("mono", "mono")])
def test_outputs_are_independent(a2m, signal, mode0, mode1):
    """Sharing a detector doesn't change an output: each sends what it sends when it is the only one."""
    sig = SIGNALS[signal]
    expected = (alone(a2m, sig, mode0), alone(a2m, sig, mode1))
    configure(a2m, 0, **MODES[mode0])
    configure(a2m, 1, **MODES[mode1])
    events = analyse_outputs(a2m, sig)
    assert (events[0], events[1]) == expected


def test_bend_and_no_bend_outputs_for_a_string_bend(a2m):
    configure(a2m, 1, bend=1)
    events = analyse_outputs(a2m, glide(*STRING_BEND))
    plain, plain_bends = notes_and_bends(events[0])
    bent, bends = notes_and_bends(events[1])
    assert [n for s, n in plain if s == NOTE_ON] == [57, 58, 59, 58, 57] and plain_bends == []
    assert [n for s, n in bent if s == NOTE_ON] == [57]
    assert max(bends) == pytest.approx(2, abs=0.1)


def test_polyphonic_outputs_send_the_same_notes(a2m):
    configure(a2m, 0, poly=1)
    configure(a2m, 1, poly=1, bend=1)  # pitch bend is monophonic only
    events = analyse_outputs(a2m, CHORDS)
    assert events[0] == events[1]
    assert sorted({n for t, s, n, v in events[0] if s == NOTE_ON}) == [43, 48, 50, 52, 55, 59]


def test_events_are_in_time_order(a2m):
    configure(a2m, 1, poly=1)
    signal = np.concatenate([pluck(57, 0.5), sum(pluck(n, 0.8, amp=0.15) for n in (48, 52, 55)), silence(0.3)])
    events = analyse_outputs(a2m, signal)
    for output in (0, 1):
        times = [t for t, s, n, v in events[output]]
        assert times == sorted(times)



# --- Two audio inputs ------------------------------------------------------------------------------------------------

OTHER_MELODY = sequence([64, 59, 55, 50])[0]


def test_an_output_without_its_input_sends_nothing(a2m):
    assert analyse_outputs(a2m, MELODY, sources=(0, 1)) == {0: analyse_outputs(a2m, MELODY)[0], 1: []}
    assert analyse_outputs(a2m, None, signal2=MELODY) == {0: [], 1: analyse_outputs(a2m, MELODY)[1]}


@pytest.mark.parametrize("source", [0, 1])
def test_either_input_can_feed_both_outputs(a2m, source):
    configure(a2m, 1, bend=1)
    signals = (MELODY, None) if source == 0 else (None, MELODY)
    events = analyse_outputs(a2m, signals[0], signal2=signals[1], sources=(source, source))
    assert events == analyse_outputs(a2m, MELODY)


def test_source_of_an_invalid_output_or_input_is_ignored(a2m):
    a2m.setOutputSource(2, 0)
    a2m.setOutputSource(0, 2)
    assert [a2m.getOutputSource(o) for o in (0, 1)] == [0, 1]


def test_two_inputs_are_independent_channels(a2m):
    """Input 1 => output 1, input 2 => output 2, each as when its input is the only one connected"""
    configure(a2m, 1, poly=1)
    expected = {0: analyse_outputs(a2m, MELODY)[0], 1: analyse_outputs(a2m, CHORDS)[1]}
    events = analyse_outputs(a2m, MELODY, signal2=CHORDS)
    frames = max(len(MELODY), len(CHORDS)) / 48000
    # The shorter input is padded with silence: its notes end at the same time, only the final release moves
    strip = lambda ev: [e for e in ev if e[0] < frames - 0.01]  # noqa: E731
    assert strip(events[0]) == strip(expected[0]) and strip(events[1]) == strip(expected[1])
    assert {n for t, s, n, v in events[0] if s == NOTE_ON} == {40, 45, 50, 55, 59, 64}
    assert {n for t, s, n, v in events[1] if s == NOTE_ON} == {43, 48, 50, 52, 55, 59}


# --- Detection parameters of each channel ----------------------------------------------------------------------------

def test_each_channel_has_its_own_detection_parameters(a2m):
    """With 2 inputs, a channel's thresholds change only its own output"""
    expected = analyse_outputs(a2m, MELODY, signal2=MELODY)
    a2m.setOnsetThreshold(1, 0)  # channel 2 hears nothing
    events = analyse_outputs(a2m, MELODY, signal2=MELODY)
    assert events[0] == expected[0] and events[1] == []
    a2m.setOnsetThreshold(1, -40)
    a2m.setNoiseFilter(0, 0)  # faster, more sensitive detection on channel 1 only
    events = analyse_outputs(a2m, MELODY, signal2=MELODY)
    assert events[1] == expected[1] and events[0] == analyse_outputs(a2m, MELODY)[0]


@pytest.mark.parametrize("source", [0, 1])
def test_one_input_feeding_both_outputs_uses_its_channel_parameters(a2m, source):
    """One detection: the parameters of the input's channel apply to both outputs, the other's are unused"""
    signals = (MELODY, None) if source == 0 else (None, MELODY)
    run = lambda: analyse_outputs(a2m, signals[0], signal2=signals[1], sources=(source, source))  # noqa: E731
    expected = run()
    assert expected[0] and expected[1]
    a2m.setOnsetThreshold(1 - source, 0)  # the other channel
    assert run() == expected
    a2m.setOnsetThreshold(source, 0)  # the input's channel
    assert run() == {0: [], 1: []}


def test_detection_parameters_of_an_invalid_channel_are_ignored(a2m):
    a2m.setOnsetThreshold(2, -10)
    a2m.setReleaseThreshold(2, -20)
    a2m.setNoiseFilter(2, 10)
    assert [a2m.getOnsetThreshold(c) for c in (0, 1)] == [-40, -40]
    assert [a2m.getReleaseThreshold(c) for c in (0, 1)] == [-50, -50]
    assert [a2m.getNoiseFilter(c) for c in (0, 1)] == [50, 50]
