"""Offline detection tests (DSP core through analyse(), no JACK server needed)."""

import numpy as np
import pytest

from tests.native.zynaudio2midi.conftest import NOTE_OFF, NOTE_ON, RATE, analyse, noise, note_ons, pluck, silence


def sequence(notes, secs=0.7, gap=0.3, rate=RATE, **kwargs):
    """Notes one after another, each followed by silence. Returns (signal, start times)."""
    parts, starts, t = [], [], 0.0
    for note in notes:
        parts += [pluck(note, secs, rate=rate, **kwargs), silence(gap, rate)]
        starts.append(t)
        t += secs + gap
    return np.concatenate(parts), starts


def assert_balanced(events):
    """Each note on is followed by a note off of the same note before it is played again, all released at the end."""
    held = set()
    for t, status, note, vel in events:
        if status == NOTE_ON:
            assert note not in held, f"note {note} on twice at {t:.3f}s"
            assert 1 <= vel <= 127
            held.add(note)
        else:
            assert status == NOTE_OFF and note in held, f"unexpected {status:#x} {note} at {t:.3f}s"
            held.remove(note)
    assert not held


# --------------------------------------------------------------------------------------------------------------------
# Monophonic
# --------------------------------------------------------------------------------------------------------------------

MONO_NOTES = [28, 31, 40, 45, 50, 55, 59, 64, 76, 88]  # E1 (bass) .. E6, incl. B0 region and guitar strings


@pytest.mark.parametrize("rate", [44100, 48000, 96000])
def test_mono_detects_each_note_once(a2m, rate):
    signal, starts = sequence(MONO_NOTES, rate=rate)
    events = analyse(a2m, signal, rate)
    assert [note for t, note in note_ons(events)] == MONO_NOTES
    assert_balanced(events)
    for (t, note), start in zip(note_ons(events), starts):
        assert start < t < start + 0.12, f"note {note} on {t - start:.3f}s after it started"


def test_mono_note_off_after_note_stops(a2m):
    events = analyse(a2m, np.concatenate([pluck(57, 0.5, decay=0.5), silence(0.5)]))
    assert [(s, n) for t, s, n, v in events] == [(NOTE_ON, 57), (NOTE_OFF, 57)]
    assert 0.5 < events[1][0] < 0.56


@pytest.mark.parametrize("block", [32, 64, 1024, 4096])
def test_result_does_not_depend_on_block_size(a2m, block):
    signal, _ = sequence([40, 52, 64])
    assert analyse(a2m, signal, block=block) == analyse(a2m, signal, block=256)


def test_mono_ignores_noise(a2m):
    assert analyse(a2m, noise(3, -25)) == []


def test_mono_ignores_notes_below_onset_threshold(a2m):
    quiet = pluck(57, 1.0, amp=0.003)  # ~ -55 dBFS RMS
    assert analyse(a2m, quiet) == []
    a2m.setOnsetThreshold(-70)
    a2m.setReleaseThreshold(-80)
    assert note_ons(analyse(a2m, quiet))[0][1] == 57


def test_mono_retriggers_repeated_note(a2m):
    signal = np.concatenate([pluck(57, 0.25, decay=6) for _ in range(4)])
    events = analyse(a2m, signal)
    assert [note for t, note in note_ons(events)] == [57] * 4
    assert_balanced(events)


def test_mono_legato_note_change(a2m):
    t = np.arange(int(0.3 * RATE)) / RATE
    notes = [60, 62, 64, 65, 67]
    signal = np.concatenate([0.2 * np.sin(2 * np.pi * 440 * 2 ** ((n - 69) / 12) * t) for n in notes])
    events = analyse(a2m, signal)
    assert [note for t, note in note_ons(events)] == notes
    assert_balanced(events)


def test_mono_vibrato_is_one_note(a2m):
    t = np.arange(2 * RATE) / RATE
    phase = 2 * np.pi * np.cumsum(440 * 2 ** (0.4 / 12 * np.sin(2 * np.pi * 6 * t))) / RATE  # +/-40 cents, 6 Hz
    assert [note for t, note in note_ons(analyse(a2m, 0.2 * np.sin(phase)))] == [69]


def test_velocity_follows_level(a2m):
    loud = note_ons_with_velocity(analyse(a2m, pluck(57, 0.5, amp=0.5)))
    soft = note_ons_with_velocity(analyse(a2m, pluck(57, 0.5, amp=0.06)))
    assert soft < loud


def note_ons_with_velocity(events):
    return [v for t, s, n, v in events if s == NOTE_ON][0]


@pytest.mark.parametrize("noise_filter", [0, 50, 100])
def test_mono_noisy_notes(a2m, noise_filter):
    a2m.setNoiseFilter(noise_filter)
    signal, _ = sequence([40, 52, 64, 69], secs=0.6, gap=0.25)
    signal += noise(len(signal) / RATE, -40)
    assert [note for t, note in note_ons(analyse(a2m, signal))] == [40, 52, 64, 69]


def test_noise_filter_delays_note_on(a2m):
    signal = pluck(57, 0.5)
    a2m.setNoiseFilter(0)
    fast = note_ons(analyse(a2m, signal))[0][0]
    a2m.setNoiseFilter(100)
    slow = note_ons(analyse(a2m, signal))[0][0]
    assert fast < slow


def test_release_threshold_above_onset_is_limited(a2m):
    a2m.setReleaseThreshold(-10)  # above onset (-40): behaves as -40
    events = analyse(a2m, np.concatenate([pluck(57, 0.5, decay=0.5), silence(0.5)]))
    assert [(s, n) for t, s, n, v in events] == [(NOTE_ON, 57), (NOTE_OFF, 57)]


def test_parameters_are_clamped(a2m):
    a2m.setOnsetThreshold(10)
    a2m.setReleaseThreshold(-200)
    a2m.setNoiseFilter(150)
    a2m.setPolyphonic(7)
    assert a2m.getOnsetThreshold() == 0
    assert a2m.getReleaseThreshold() == -90
    assert a2m.getNoiseFilter() == 100
    assert a2m.getPolyphonic() == 1


# --------------------------------------------------------------------------------------------------------------------
# Polyphonic
# --------------------------------------------------------------------------------------------------------------------

def chords(chord_list, secs=1.0, gap=0.3, amp=0.2):
    return np.concatenate([np.concatenate([sum(pluck(n, secs, amp=amp) for n in c), silence(gap)])
                           for c in chord_list])


@pytest.mark.parametrize("chord", [[48, 52, 55], [45, 52], [60, 64, 67], [48, 52, 55, 59], [36, 43], [72, 76, 79]])
def test_poly_detects_chord(a2m, chord):
    a2m.setPolyphonic(1)
    events = analyse(a2m, chords([chord]))
    assert sorted(note for t, note in note_ons(events)) == chord
    assert_balanced(events)
    assert all(t < 0.3 for t, note in note_ons(events))


@pytest.mark.xfail(strict=True, reason="Known limitation: a doubled octave no louder than the lower note is taken as its "
                                      "harmonics (the harmonic ghost rejection drops it)")
def test_poly_octave_doubling(a2m):
    a2m.setPolyphonic(1)
    assert sorted(note for t, note in note_ons(analyse(a2m, chords([[45, 57]])))) == [45, 57]


def test_poly_chord_sequence(a2m):
    a2m.setPolyphonic(1)
    events = analyse(a2m, chords([[48, 52, 55], [45, 57], [53, 57, 60]]))
    assert [sorted(n for t, n in note_ons(events) if lo <= t < lo + 1.3) for lo in (0, 1.3, 2.6)] == \
        [[48, 52, 55], [45, 57], [53, 57, 60]]
    assert_balanced(events)


def test_poly_single_notes(a2m):
    a2m.setPolyphonic(1)
    signal, _ = sequence([40, 52, 64, 69, 84], secs=0.6, gap=0.25)
    assert [note for t, note in note_ons(analyse(a2m, signal))] == [40, 52, 64, 69, 84]


def test_poly_retriggers_repeated_note(a2m):
    a2m.setPolyphonic(1)
    signal = np.concatenate([pluck(57, 0.25, decay=6) for _ in range(4)])
    events = analyse(a2m, signal)
    assert [note for t, note in note_ons(events)] == [57] * 4
    assert_balanced(events)


@pytest.mark.parametrize("db", [-35, -25])
def test_poly_ignores_noise(a2m, db):
    a2m.setPolyphonic(1)
    assert analyse(a2m, noise(3, db)) == []


def test_poly_ignores_mains_hum(a2m):
    a2m.setPolyphonic(1)
    hum = 0.03 * np.sin(2 * np.pi * 50 * np.arange(2 * RATE) / RATE)  # below the polyphonic range
    assert analyse(a2m, hum) == []
