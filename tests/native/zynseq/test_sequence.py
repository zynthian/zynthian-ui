"""zynseq sequences, tracks and playback on the REAL libzynseq.so, on a dummy jackd in freewheel.

Ported from the legacy ``zynlibs/zynseq/unit_tests.py`` (groups ae..ag and the transport tests of ``test.py``), updated
for the current API: a sequence is addressed by (scene, phrase, sequence), a track plays patterns at a position
in sequencer clocks (1920 per beat), and the result is checked on the MIDI that leaves the ``output`` JACK port.

Timing at 120 BPM and the default 4 steps per beat: 1 beat = 24000 frames @48 kHz, 1 step = 6000 frames.
"""

import jack
import pytest

from tests.jacktest import FreewheelRunner, Recorder
from tests.native.zynseq.conftest import (
    CLIENT, MODE_END_END, MODE_END_IMMEDIATE, MODE_START_IMMEDIATE, MODE_START_SYNC, PLAYING, REPEAT_ENDLESS, STARTING,
    STOPPED,
    STOPPING)

pytestmark = [pytest.mark.native, pytest.mark.jack]

SEQ0 = (0, 0, 0)       # scene, phrase, sequence
PPQN = 1920
BEAT = 24000           # frames per beat at 120 BPM, 48 kHz
STEP = BEAT // 4       # frames per step at 4 steps per beat
NOTE_ON, NOTE_OFF = 0x90, 0x80
TEST_PATTERN = 1000


class Rig:
    """Runs JACK cycles and records what zynseq plays on its ``output`` port."""

    def __init__(self, server):
        self.server = server
        self.runner = FreewheelRunner(server)
        self.rec = Recorder(server, midi_ports=("out",))
        self.jack = jack.Client("zyntest_seq_transport", servername=server.name, no_start_server=True)
        for client in (self.runner, self.rec):
            client.activate()
        self.rec.client.connect(f"{CLIENT}:output", self.rec.midi_ports["out"])

    def run(self, seconds):
        self.runner.run_seconds(seconds)

    def events(self):
        """Recorded MIDI as [(frame relative to the first event, bytes)]."""
        out = self.rec.midi["out"]
        return [(f - out[0][0], d) for f, d in out] if out else []

    @property
    def transport(self):
        return self.jack.transport_state

    def close(self):
        self.jack.close()
        self.rec.close()
        self.runner.close()


@pytest.fixture(scope="module")
def rig(jack_server, zynseq):
    rig = Rig(jack_server)
    yield rig
    rig.close()


@pytest.fixture
def song(seq, rig):
    """Default library state; sequence 0/0/0 holds ONLY pattern 1000 (notes C4 step 0, D4 step 2) on channel 3."""
    seq.selectPattern(TEST_PATTERN)
    seq.clearNotes()
    seq.addNote(0, 60, 100, 1.0, 0.0)
    seq.addNote(2, 62, 90, 2.0, 0.0)
    assert seq.addPattern(*SEQ0, 0, 0, TEST_PATTERN, True)
    seq.setChannel(*SEQ0, 0, 3)
    seq.setSequenceMode(*SEQ0, MODE_START_IMMEDIATE | MODE_END_END)
    seq.setSequenceRepeat(*SEQ0, 1)
    rig.run(0.3)
    rig.rec.clear()
    return seq


# --- tracks and patterns (no playback) ----------------------------------------------------------------------
def test_default_state_every_sequence_has_a_track_with_a_pattern(seq):
    assert seq.getTracksInSequence(*SEQ0) == 1
    assert seq.getPattern(*SEQ0, 0, 0) >= 0


def test_add_track_to_sequence(seq):
    before = seq.getTracksInSequence(*SEQ0)
    seq.addTrackToSequence(*SEQ0, 0xFFFFFFFF)
    assert seq.getTracksInSequence(*SEQ0) == before + 1


def test_add_get_remove_pattern(seq):
    seq.selectPattern(TEST_PATTERN)
    seq.clearNotes()
    seq.addNote(0, 60, 100, 1.0, 0.0)
    assert seq.addPattern(*SEQ0, 0, 2 * PPQN, TEST_PATTERN, True)
    assert seq.getPattern(*SEQ0, 0, 2 * PPQN) == TEST_PATTERN
    seq.removePattern(*SEQ0, 0, 2 * PPQN)
    assert seq.getPattern(*SEQ0, 0, 2 * PPQN) == -1


def test_overlapping_pattern_needs_force(seq):
    """A pattern cannot be added where another one already plays, unless force removes the old one."""
    seq.clearSequence(*SEQ0)
    seq.selectPattern(TEST_PATTERN)
    seq.addNote(0, 60, 100, 1.0, 0.0)
    assert seq.addPattern(*SEQ0, 0, 0, TEST_PATTERN, False)
    assert not seq.addPattern(*SEQ0, 0, PPQN, 998, False)         # overlaps the first (it is 4 beats long)
    assert seq.getPattern(*SEQ0, 0, PPQN) == -1
    assert seq.addPattern(*SEQ0, 0, PPQN, 998, True)
    assert seq.getPattern(*SEQ0, 0, PPQN) == 998
    assert seq.getPattern(*SEQ0, 0, 0) == -1                      # the old one was removed


def test_sequence_length_follows_its_patterns(seq):
    seq.clearSequence(*SEQ0)
    assert seq.getSequenceLength(*SEQ0) == 0
    seq.selectPattern(TEST_PATTERN)
    seq.setBeatsInPattern(TEST_PATTERN, 4)
    seq.setStepsPerBeat(4)
    seq.addPattern(*SEQ0, 0, 0, TEST_PATTERN, True)
    assert seq.getSequenceLength(*SEQ0) == 4 * PPQN
    seq.setBeatsInPattern(TEST_PATTERN, 6)
    assert seq.getSequenceLength(*SEQ0) == 6 * PPQN
    seq.setStepsPerBeat(8)                                         # finer steps, same duration
    assert seq.getSequenceLength(*SEQ0) == 6 * PPQN


def test_is_empty_depends_on_pattern_content(seq):
    """isEmpty() reports a cached flag, refreshed by updateSequenceInfo() (the UI calls it after editing)."""
    seq.clearSequence(*SEQ0)
    seq.selectPattern(TEST_PATTERN)
    seq.clearNotes()
    seq.addPattern(*SEQ0, 0, 0, TEST_PATTERN, True)
    seq.updateSequenceInfo()
    assert seq.isEmpty(*SEQ0)
    seq.addNote(0, 60, 100, 1.0, 0.0)
    assert seq.isEmpty(*SEQ0), "flag is cached until updateSequenceInfo()"
    seq.updateSequenceInfo()
    assert not seq.isEmpty(*SEQ0)


@pytest.mark.parametrize("channel", [0, 7, 15])
def test_track_channel(seq, channel):
    seq.setChannel(*SEQ0, 0, channel)
    assert seq.getChannel(*SEQ0, 0) == channel


@pytest.mark.parametrize("channel", [16, 17, 255])
def test_track_channel_out_of_range_is_ignored(seq, channel):
    """The legacy test expected an out-of-range channel to read back as 0xFF ("none"); the current library
    simply ignores the request and keeps the previous channel."""
    seq.setChannel(*SEQ0, 0, 7)
    seq.setChannel(*SEQ0, 0, channel)
    assert seq.getChannel(*SEQ0, 0) == 7


def test_sequence_mode_repeat_name_and_tempo_round_trip(seq):
    seq.setSequenceMode(*SEQ0, MODE_START_IMMEDIATE | MODE_END_IMMEDIATE)
    assert seq.getSequenceMode(*SEQ0) == MODE_START_IMMEDIATE | MODE_END_IMMEDIATE
    seq.setSequenceRepeat(*SEQ0, 3)
    assert seq.getSequenceRepeat(*SEQ0) == 3
    seq.setSequenceName(*SEQ0, b"Bass line")
    assert seq.getSequenceName(*SEQ0) == b"Bass line"
    seq.setSequenceTempo(*SEQ0, 90.0)
    assert seq.getSequenceTempo(*SEQ0) == 90.0


# --- playback -----------------------------------------------------------------------------------------------
def test_plays_the_pattern_on_the_track_channel_with_exact_timing(song, rig):
    song.setPlayState(*SEQ0, STARTING)
    rig.run(3.0)
    ev = rig.events()
    assert [d for _, d in ev] == [bytes([0x93, 60, 100]), bytes([0x83, 60, 0]),
                                  bytes([0x93, 62, 90]), bytes([0x83, 62, 0])]
    on1, off1, on2, off2 = (f for f, _ in ev)
    assert on1 == 0
    assert on2 - on1 == 2 * STEP                                    # note at step 2
    assert off1 - on1 == pytest.approx(STEP, abs=40)               # 1 step long (note-off just before the step end)
    assert off2 - on2 == pytest.approx(2 * STEP, abs=40)            # 2 steps long


def test_play_state_and_jack_transport_follow_the_sequence(song, rig):
    assert song.getPlayState(*SEQ0) == STOPPED
    assert rig.transport == jack.STOPPED
    song.setPlayState(*SEQ0, STARTING)
    rig.run(0.3)
    assert song.getPlayState(*SEQ0) == PLAYING
    assert rig.transport == jack.ROLLING
    rig.run(3.0)                                                    # a 4-beat pattern plays once in 2 s
    assert song.getPlayState(*SEQ0) == STOPPED
    assert rig.transport == jack.STOPPED                            # transport stops with the last sequence


def test_repeat_plays_the_pattern_that_many_times(song, rig):
    song.setSequenceRepeat(*SEQ0, 2)
    song.setPlayState(*SEQ0, STARTING)
    rig.run(5.0)
    ons = [f for f, d in rig.events() if d[0] == 0x93 and d[1] == 60]
    assert len(ons) == 2
    assert ons[1] - ons[0] == pytest.approx(4 * BEAT, abs=40)       # second pass one pattern length later


def test_tempo_scales_the_timing(song, rig):
    song.setTempo(60.0)
    song.setPlayState(*SEQ0, STARTING)
    rig.run(5.0)
    ons = [f for f, d in rig.events() if d[0] == 0x93]
    assert ons[1] - ons[0] == pytest.approx(2 * STEP * 2, abs=40)   # twice as slow


def test_two_tracks_play_on_their_own_channels(song, rig):
    song.selectPattern(TEST_PATTERN + 1)
    song.clearNotes()
    song.addNote(0, 72, 80, 1.0, 0.0)
    track = song.addTrackToSequence(*SEQ0, 0xFFFFFFFF)
    song.addPattern(*SEQ0, track, 0, TEST_PATTERN + 1, True)
    song.setChannel(*SEQ0, track, 9)
    song.setPlayState(*SEQ0, STARTING)
    rig.run(3.0)
    played = {(d[0], d[1]) for _, d in rig.events() if d[0] & 0xF0 == NOTE_ON}
    assert played == {(0x93, 60), (0x93, 62), (0x99, 72)}


def test_toggle_play_state_starts_and_stops(song, rig):
    song.setSequenceMode(*SEQ0, MODE_START_IMMEDIATE | MODE_END_IMMEDIATE)
    song.setSequenceRepeat(*SEQ0, REPEAT_ENDLESS)
    song.togglePlayState(*SEQ0)
    rig.run(0.5)
    assert song.getPlayState(*SEQ0) == PLAYING
    song.togglePlayState(*SEQ0)
    rig.run(0.2)
    assert song.getPlayState(*SEQ0) == STOPPED


def test_stop_at_end_of_pattern_lets_it_finish(song, rig):
    song.setSequenceMode(*SEQ0, MODE_START_IMMEDIATE | MODE_END_END)
    song.setSequenceRepeat(*SEQ0, REPEAT_ENDLESS)
    song.setPlayState(*SEQ0, STARTING)
    rig.run(0.6)
    song.setPlayState(*SEQ0, STOPPING)
    assert song.getPlayState(*SEQ0) == STOPPING
    rig.run(0.5)
    assert song.getPlayState(*SEQ0) == STOPPING                     # pattern not finished yet (2 s long)
    rig.run(2.0)
    assert song.getPlayState(*SEQ0) == STOPPED


def test_stop_immediately_does_not_wait_and_releases_notes(song, rig):
    song.setSequenceMode(*SEQ0, MODE_START_IMMEDIATE | MODE_END_IMMEDIATE)
    song.setSequenceRepeat(*SEQ0, REPEAT_ENDLESS)
    song.setPlayState(*SEQ0, STARTING)
    rig.run(0.05)                                                   # C4 (1 step = 0.125 s) is sounding
    song.setPlayState(*SEQ0, STOPPING)
    rig.run(0.5)
    assert song.getPlayState(*SEQ0) == STOPPED
    kinds = [d[0] for _, d in rig.events()]
    assert kinds.count(0x93) == kinds.count(0x83) >= 1, "every note-on must be followed by its note-off"


def test_a_sequence_started_while_another_plays_waits_for_the_sync_point(song, rig):
    """Legacy ag01: with start-at-sync, a second sequence stays STARTING until the next bar boundary
    (4 beats = 2 s at 120 BPM), and then plays in time with the first."""
    song.addPattern(0, 0, 1, 0, 0, TEST_PATTERN, True)
    song.setChannel(0, 0, 1, 0, 4)
    for seq_no in (0, 1):
        song.setSequenceRepeat(0, 0, seq_no, REPEAT_ENDLESS)
    song.setSequenceMode(0, 0, 1, MODE_START_SYNC | MODE_END_END)
    song.setPlayState(*SEQ0, STARTING)
    rig.run(0.5)                                                    # first sequence is a beat into its bar
    assert song.getPlayState(*SEQ0) == PLAYING
    song.setPlayState(0, 0, 1, STARTING)
    rig.run(1.0)                                                    # t = 1.5 s: before the bar boundary
    assert song.getPlayState(0, 0, 1) == STARTING
    assert not any(d[0] & 0x0F == 4 for _, d in rig.events()), "second sequence must be silent until the sync point"
    rig.run(1.0)                                                    # t = 2.5 s: after it
    assert song.getPlayState(0, 0, 1) == PLAYING
    first = [f for f, d in rig.events() if d[:2] == bytes([0x93, 60])]
    second = [f for f, d in rig.events() if d[:2] == bytes([0x94, 60])]
    assert second and first[1] == pytest.approx(second[0], abs=40)  # both start their pattern on the bar line
