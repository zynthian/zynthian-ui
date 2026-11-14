"""libzynsmf JACK player and recorder, on the REAL library with a dummy jackd in freewheel.

Ported from the legacy ``zynlibs/zynsmf/unit_tests.py`` (groups ab: player port, play states, transport). The JACK
client is called ``zynsmf`` (the legacy tests looked for ``zynmidiplayer``), with ports ``midi_out`` (player) and
``midi_in`` (recorder). The player follows the JACK transport: it is STARTING until the transport rolls.
"""

import jack
import pytest

from tests.jacktest import FreewheelRunner, MidiSource, Recorder
from tests.native.zynsmf.conftest import PLAYING, STARTING, STOPPED

pytestmark = [pytest.mark.native, pytest.mark.jack]

FRAME_TOL = 256      # one process cycle: events are placed on cycle boundaries
BEAT = 24000         # frames per beat at 120 BPM, 48 kHz


class Rig:
    def __init__(self, server):
        self.server = server
        self.runner = FreewheelRunner(server)
        self.rec = Recorder(server, midi_ports=("out",))
        self.src = MidiSource(server)
        self.jack = jack.Client("zyntest_smf_ctl", servername=server.name, no_start_server=True)
        for client in (self.runner, self.rec, self.src):
            client.activate()
        self.jack.activate()                       # a timebase master must be an active client

    def ports(self):
        return {p.name for p in self.jack.get_ports("zynsmf:")}

    def listen(self):
        self.rec.client.connect("zynsmf:midi_out", self.rec.midi_ports["out"])
        self.rec.clear()

    def run(self, seconds):
        self.runner.run_seconds(seconds)

    def events(self):
        out = self.rec.midi["out"]
        return [(f - out[0][0], d) for f, d in out] if out else []

    def become_timebase_master(self, bpm=120.0):
        """Provide tempo information through the JACK transport, as zynseq does in a running Zynthian."""
        def timebase(state, blocksize, pos, new_pos):
            pos.valid = jack.POSITION_BBT
            pos.bar, pos.beat, pos.tick = 1, 1, 0
            pos.bar_start_tick = 0.0
            pos.beats_per_bar, pos.beat_type, pos.ticks_per_beat = 4.0, 4.0, 1920.0
            pos.beats_per_minute = bpm
        self.jack.set_timebase_callback(timebase)
        self.run(0.1)

    def close(self):
        self.jack.deactivate()
        self.jack.close()
        for client in (self.src, self.rec, self.runner):
            client.close()


@pytest.fixture(scope="module")
def rig(jack_server, zynsmf_lib):
    rig = Rig(jack_server)
    yield rig
    rig.close()


@pytest.fixture
def player(song, rig):
    """The song attached to the JACK player; the transport stopped."""
    assert song.attachPlayer()
    rig.listen()
    rig.jack.transport_stop()
    rig.run(0.1)
    yield song
    song.lib.stopPlayback()
    rig.jack.transport_stop()
    rig.run(0.1)


# --- port lifecycle -----------------------------------------------------------------------------------------
def test_attach_player_creates_the_midi_out_port_and_remove_deletes_it(song, rig):
    assert "zynsmf:midi_out" not in rig.ports()
    assert song.attachPlayer()
    assert "zynsmf:midi_out" in rig.ports()
    song.lib.removePlayer()
    assert "zynsmf:midi_out" not in rig.ports()


def test_attach_player_to_an_invalid_smf_fails(zynsmf_lib):
    assert not zynsmf_lib.attachPlayer(None)


def test_attach_recorder_creates_the_midi_in_port(smf, rig):
    assert smf.attachRecorder()
    assert "zynsmf:midi_in" in rig.ports()
    smf.lib.removeRecorder()
    assert "zynsmf:midi_in" not in rig.ports()


# --- play state follows the JACK transport ------------------------------------------------------------------
def test_play_state_follows_the_transport(player, rig):
    lib = player.lib
    assert lib.getPlayState() == STOPPED
    lib.startPlayback()
    assert lib.getPlayState() == STARTING          # waits for the transport
    rig.run(0.2)
    assert lib.getPlayState() == STARTING and rig.jack.transport_state == jack.STOPPED
    rig.jack.transport_start()
    rig.run(0.2)
    assert lib.getPlayState() == PLAYING
    lib.stopPlayback()
    rig.run(0.2)
    assert lib.getPlayState() == STOPPED


def test_stopping_the_transport_stops_playback(player, rig):
    lib = player.lib
    lib.startPlayback()
    rig.jack.transport_start()
    rig.run(0.2)
    assert lib.getPlayState() == PLAYING
    rig.jack.transport_stop()
    rig.run(0.2)
    assert lib.getPlayState() == STOPPED


def test_playback_stops_by_itself_at_the_end_of_the_song(player, rig):
    lib = player.lib
    lib.startPlayback()
    rig.jack.transport_start()
    rig.run(0.5)
    assert lib.getPlayState() == PLAYING
    rig.run(1.5)                                    # the song lasts 1 s
    assert lib.getPlayState() == STOPPED


def test_loop_restarts_the_song(player, rig):
    lib = player.lib
    lib.setLoop(True)
    lib.startPlayback()
    rig.jack.transport_start()
    rig.run(3.5)                                    # 3+ song lengths
    assert lib.getPlayState() in (STARTING, PLAYING)
    lib.setLoop(False)
    rig.run(1.5)
    assert lib.getPlayState() == STOPPED


def test_start_without_player_attached_does_nothing(zynsmf_lib):
    zynsmf_lib.removePlayer()
    zynsmf_lib.startPlayback()
    assert zynsmf_lib.getPlayState() == STOPPED


# --- the MIDI that comes out ----------------------------------------------------------------------------------
@pytest.mark.xfail(strict=True, reason="zynsmf.cpp onJackProcess: the event offset is computed as "
                                       "`g_dPosition - nNow` (a position in ticks minus an absolute JACK frame "
                                       "time), which wraps to ~4e9 so jack_midi_event_reserve fails and EVERY "
                                       "event is dropped (JACK logs 'time parameter is out of range'). Forcing "
                                       "the offset to 0 in a scratch build makes the notes come out on time.")
def test_playback_emits_the_song_on_time(player, rig):
    lib = player.lib
    lib.startPlayback()
    rig.jack.transport_start()
    rig.run(2.0)
    ev = rig.events()
    assert [d for _, d in ev] == [bytes([0x90, 60, 100]), bytes([0x80, 60, 0]),
                                  bytes([0x90, 62, 90]), bytes([0x80, 62, 0])]
    frames = [f for f, _ in ev]
    assert frames[0] == 0
    for got, want in zip(frames, (0, BEAT, BEAT, 2 * BEAT)):
        assert got == pytest.approx(want, abs=FRAME_TOL)


# --- recorder -------------------------------------------------------------------------------------------------
def record(smf, rig, bpm=120.0):
    """Record 3 MIDI events (note on ch3, note off ch3 one beat later, note on ch4 two beats later); return the events.

    zynsmf takes the recording tempo from the JACK transport (zynseq is the timebase master in a running Zynthian).
    The transport must be rolling with a timebase master when recording starts: a stopped transport reports 0 BPM,
    which makes the recorder's ticks-per-frame infinite and puts every event at tick 0."""
    rig.become_timebase_master(bpm)
    rig.jack.transport_start()
    rig.run(0.2)
    assert smf.attachRecorder()
    rig.src.port.connect("zynsmf:midi_in")
    rig.run(0.2)
    smf.lib.startRecording()
    assert smf.lib.isRecording()
    start = rig.runner.frame_time + 2048
    rig.src.schedule([(start, bytes([0x92, 64, 100])), (start + BEAT, bytes([0x82, 64, 0])),
                      (start + 2 * BEAT, bytes([0x93, 67, 80]))])
    rig.run(2.0)
    smf.lib.stopRecording()
    assert not smf.lib.isRecording()
    rig.src.clear()
    rig.jack.transport_stop()
    rig.jack.release_timebase()
    return smf.events()


def test_recorder_captures_midi_input_with_timing(smf, rig):
    """The first MIDI event starts the recording; later events are timed relative to it (96 ticks per beat)."""
    ev = record(smf, rig)
    beat = smf.getTicksPerQuarterNote()
    assert beat == 96
    notes = [(e["time"], e["status"], e["v1"], e["v2"]) for e in ev if e["status"] in (0x92, 0x82, 0x93)]
    assert notes[:3] == [(0, 0x92, 64, 100), (beat, 0x82, 64, 0), (2 * beat, 0x93, 67, 80)]
    # each channel is recorded on its own track
    assert {e["track"] for e in ev if e["status"] in (0x92, 0x82)} == {2}
    assert {e["track"] for e in ev if e["status"] == 0x93} == {3}


def test_recorder_releases_notes_still_held_when_it_stops(smf, rig):
    ev = record(smf, rig)
    assert any(e["status"] == 0x80 and e["v1"] == 67 and e["track"] == 3 for e in ev)


@pytest.mark.xfail(strict=True, reason="zynsmf.cpp onJackProcess: `case MIDI_NOTE_OFF:` has no break and falls "
                                       "through into `case MIDI_NOTE_ON:`, which marks the note as held again, so "
                                       "stopRecording() appends a spurious note-off for every note ever released")
def test_recorder_adds_no_note_off_for_notes_already_released(smf, rig):
    ev = record(smf, rig)
    assert [e for e in ev if e["status"] in (0x82, 0x80) and e["v1"] == 64 and e["track"] == 2] == [
        e for e in ev if e["status"] == 0x82 and e["v1"] == 64]            # only the recorded 0x82, no extra 0x80


