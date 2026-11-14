"""libzynsmf: parsing, editing and saving Standard MIDI Files, on the REAL library.

Ported from the legacy ``zynlibs/zynsmf/unit_tests.py`` (which needed a ``test.mid`` that was never committed): the
input files are now built in the tests by ``midifile.py``, so each expectation can be read off the file contents.
"""

import pytest

from tests.native.zynsmf import midifile as mf
from tests.native.zynsmf.conftest import ALL_TRACKS, EVENT_TYPE_MIDI, EVENT_TYPE_META, NO_EVENT

pytestmark = [pytest.mark.native, pytest.mark.jack]


# --- loading ------------------------------------------------------------------------------------------------
def test_load_reports_format_tracks_and_resolution(song):
    assert song.getFormat() == 1
    assert song.getTracks() == 1
    assert song.getTicksPerQuarterNote() == 480
    assert song.getEvents(ALL_TRACKS) == 6          # tempo, 2 x (note on, note off), end of track


def test_duration_in_seconds(song):
    assert song.getDuration() == pytest.approx(1.0)


# Smf::getMicrosecondsPerQuarterNote(t) (smf.cpp) returns the FIRST tempo entry at or AFTER tick t, i.e. the next
# change, and 120 BPM once past the last entry, instead of the tempo in effect at t. The tempo lookup is also what
# getDuration() uses while parsing, so any file whose tempo is not 120 BPM reports a wrong duration.
TEMPO_LOOKUP_BUG = "smf.cpp getMicrosecondsPerQuarterNote: returns the next tempo change, not the one in effect"


def test_tempo_on_the_tick_of_a_tempo_event(smf, tmp_path):
    data = mf.smf([mf.track([(0, mf.tempo(120)), (480, mf.tempo(60)), (960, mf.note_off(0, 60))])])
    assert smf.load_bytes(tmp_path, data)
    assert smf.getTempo(0) == pytest.approx(120.0)
    assert smf.getTempo(480) == pytest.approx(60.0)


@pytest.mark.xfail(strict=True, reason=TEMPO_LOOKUP_BUG)
def test_tempo_in_effect_between_and_after_changes(smf, tmp_path):
    data = mf.smf([mf.track([(0, mf.tempo(120)), (480, mf.tempo(60)), (960, mf.note_off(0, 60))])])
    assert smf.load_bytes(tmp_path, data)
    assert smf.getTempo(479) == pytest.approx(120.0)
    assert smf.getTempo(960) == pytest.approx(60.0)


@pytest.mark.xfail(strict=True, reason=TEMPO_LOOKUP_BUG)
def test_duration_follows_a_constant_tempo(smf, tmp_path):
    slow = mf.smf([mf.track([(0, mf.tempo(60)), (0, mf.note_on(0, 60, 100)), (480, mf.note_off(0, 60))])])
    assert smf.load_bytes(tmp_path, slow)
    assert smf.getDuration() == pytest.approx(1.0)  # one beat at 60 BPM (the library says 0.5: it assumes 120)


@pytest.mark.xfail(strict=True, reason=TEMPO_LOOKUP_BUG)
def test_duration_follows_tempo_changes(smf, tmp_path):
    data = mf.smf([mf.track([(0, mf.tempo(120)), (480, mf.tempo(60)), (960, mf.note_off(0, 60))])])
    assert smf.load_bytes(tmp_path, data)
    assert smf.getDuration() == pytest.approx(0.5 + 1.0)   # one beat at 120 BPM + one at 60


def test_format_0_and_format_2_headers(smf, tmp_path):
    for fmt in (0, 2):
        assert smf.load_bytes(tmp_path, mf.smf([mf.track([(0, mf.note_on(0, 60, 1))])], fmt=fmt))
        assert smf.getFormat() == fmt


def test_multi_track_file(smf, tmp_path):
    data = mf.smf([mf.track([(0, mf.tempo(120))]),
                   mf.track([(0, mf.note_on(0, 60, 100)), (480, mf.note_off(0, 60))]),
                   mf.track([(240, mf.note_on(9, 36, 80)), (480, mf.note_off(9, 36))])])
    assert smf.load_bytes(tmp_path, data)
    assert smf.getTracks() == 3
    ev = smf.events()
    times = [e["time"] for e in ev]
    assert times == sorted(times), "events of all tracks come out merged in time order"
    assert {e["track"] for e in ev} == {0, 1, 2}


def test_running_status_is_parsed(smf, tmp_path):
    """SMF allows omitting a repeated status byte; many files rely on it."""
    track = mf.track([(0, mf.note_on(0, 60, 100)), (10, mf.note_on(0, 62, 100)), (20, mf.note_on(0, 64, 100))],
                     running_status=True)
    assert smf.load_bytes(tmp_path, mf.smf([track]))
    notes = [(e["time"], e["v1"]) for e in smf.events() if e["status"] == 0x90]
    assert notes == [(0, 60), (10, 62), (20, 64)]


@pytest.mark.xfail(strict=True, reason="Smf::load returns true for anything it can open, even a file that is not "
                                       "a Standard MIDI File (it just ends up with no tracks)")
@pytest.mark.parametrize("data", [b"", b"not a midi file", b"MThd\x00\x00\x00\x06\x00\x01"],
                         ids=["empty", "text", "truncated header"])
def test_load_rejects_invalid_files(smf, tmp_path, data):
    assert not smf.load_bytes(tmp_path, data)


@pytest.mark.parametrize("data", [b"", b"not a midi file", b"MThd\x00\x00\x00\x06\x00\x01"],
                         ids=["empty", "text", "truncated header"])
def test_invalid_files_load_as_empty_songs(smf, tmp_path, data):
    """Characterization of the above: whatever the verdict, no events are produced from garbage."""
    smf.load_bytes(tmp_path, data)
    assert smf.getTracks() == 0 and smf.getEvents(ALL_TRACKS) == 0


def test_load_missing_file_fails_and_empties_the_smf(song):
    """Characterization: a failed load discards what was loaded before."""
    assert not song.load(b"/nonexistent/dir/missing.mid")
    assert song.getTracks() == 0
    assert song.getEvents(ALL_TRACKS) == 0


def test_loading_again_replaces_the_content(song, tmp_path):
    assert song.load_bytes(tmp_path, mf.smf([mf.track([(0, mf.note_on(0, 72, 1))])]), "other.mid")
    notes = [e["v1"] for e in song.events() if e["status"] == 0x90]
    assert notes == [72]


def test_unload_clears_everything(song):
    song.unload()
    assert song.getTracks() == 0
    assert song.getDuration() == 0.0


def test_smf_objects_are_counted(zynsmf_lib, smf):
    before = zynsmf_lib.getSmfCount()
    other = zynsmf_lib.addSmf()
    assert zynsmf_lib.getSmfCount() == before + 1
    zynsmf_lib.removeSmf(other)
    assert zynsmf_lib.getSmfCount() == before


# --- event cursor -------------------------------------------------------------------------------------------
def test_event_cursor_walks_the_file_in_time_order(song):
    ev = song.events()
    assert [(e["time"], e["status"]) for e in ev] == [(0, 0x51), (0, 0x90), (480, 0x80), (480, 0x90),
                                                      (960, 0x80), (960, 0x2F)]
    assert [e["type"] for e in ev] == [EVENT_TYPE_META, EVENT_TYPE_MIDI, EVENT_TYPE_MIDI, EVENT_TYPE_MIDI,
                                       EVENT_TYPE_MIDI, EVENT_TYPE_META]


def test_midi_event_fields(song):
    first_note = song.events()[1]
    assert (first_note["channel"], first_note["status"], first_note["v1"], first_note["v2"]) == (0, 0x90, 60, 100)


def test_meta_events_have_no_midi_fields(song):
    tempo_event = song.events()[0]
    assert (tempo_event["channel"], tempo_event["v1"], tempo_event["v2"]) == (0xFF, 0xFF, 0xFF)


def test_cursor_after_the_last_event_reports_none(song):
    song.events()
    assert song.getEvent(False) is False
    assert song.lib.getEventTime() == NO_EVENT


def test_set_position_moves_the_cursor(song):
    song.setPosition(100)
    assert song.getEvent(False)
    assert song.lib.getEventTime() == 480           # first event at or after tick 100
    song.setPosition(0)
    assert song.getEvent(False) and song.lib.getEventTime() == 0


# --- editing and saving -------------------------------------------------------------------------------------
def test_add_note_creates_note_on_and_off(smf):
    smf.addNote(0, 100, 50, 5, 64, 90)
    notes = [(e["time"], e["status"], e["v1"], e["v2"]) for e in smf.events()
             if e["type"] == EVENT_TYPE_MIDI]
    assert notes == [(100, 0x95, 64, 90), (150, 0x85, 64, 0)]


def test_add_tempo_adds_a_tempo_meta_event(smf):
    smf.addTempo(0, 100.0)
    (event,) = smf.events()
    assert (event["time"], event["type"], event["status"]) == (0, EVENT_TYPE_META, 0x51)


@pytest.mark.xfail(strict=True, reason="addTempo adds the meta event but not the tempo map entry that getTempo() "
                                       "reads, so getTempo still says 120")
def test_add_tempo_is_reflected_by_get_tempo(smf):
    smf.addTempo(0, 100.0)
    assert smf.getTempo(0) == pytest.approx(100.0)


def test_set_end_of_track_adds_the_end_marker(smf):
    smf.addNote(0, 0, 100, 0, 60, 100)
    smf.setEndOfTrack(0, 960)
    assert [(e["time"], e["status"]) for e in smf.events()][-1] == (960, 0x2F)


def test_save_writes_a_valid_standard_midi_file(smf, tmp_path):
    smf.addTempo(0, 120.0)
    smf.addNote(0, 0, 480, 0, 60, 100)
    smf.addNote(0, 480, 480, 0, 62, 90)
    smf.setEndOfTrack(0, 960)
    path = tmp_path / "saved.mid"
    assert smf.save(str(path).encode())
    data = path.read_bytes()
    fmt, ntrks, division = mf.header(data)
    assert ntrks == 1 and fmt in (0, 1)
    assert division == smf.getTicksPerQuarterNote() == 96     # resolution of a new, empty SMF


def test_save_then_load_round_trips(smf, zynsmf_lib, tmp_path):
    smf.addTempo(0, 90.0)
    smf.addNote(0, 0, 240, 3, 60, 100)
    smf.addNote(0, 240, 240, 3, 67, 80)
    smf.setEndOfTrack(0, 960)
    path = str(tmp_path / "roundtrip.mid").encode()
    assert smf.save(path)
    original = smf.events()
    other = zynsmf_lib.addSmf()
    try:
        assert zynsmf_lib.load(other, path)
        zynsmf_lib.setPosition(other, 0)
        again = []
        while zynsmf_lib.getEvent(other, False):
            again.append((zynsmf_lib.getEventTime(), zynsmf_lib.getEventStatus(), zynsmf_lib.getEventValue1(),
                          zynsmf_lib.getEventValue2()))
            zynsmf_lib.getEvent(other, True)
        assert again == [(e["time"], e["status"], e["v1"], e["v2"]) for e in original]
        assert zynsmf_lib.getTicksPerQuarterNote(other) == smf.getTicksPerQuarterNote()
    finally:
        zynsmf_lib.removeSmf(other)


def test_save_to_an_unwritable_path_fails(song):
    assert not song.save(b"/nonexistent/dir/out.mid")


# --- track mute / transpose ---------------------------------------------------------------------------------
def test_muted_track_events_are_skipped_by_the_cursor(smf, tmp_path):
    data = mf.smf([mf.track([(0, mf.note_on(0, 60, 100))]), mf.track([(0, mf.note_on(1, 72, 100))])])
    assert smf.load_bytes(tmp_path, data)
    smf.muteTrack(1, True)
    assert smf.isTrackMuted(1) and not smf.isTrackMuted(0)
    assert [e["v1"] for e in smf.events() if e["status"] & 0xF0 == 0x90] == [60]
    smf.muteTrack(1, False)
    assert not smf.isTrackMuted(1)


@pytest.mark.parametrize("semitones", [0, 5, -7, 12, -12])
def test_transpose_round_trip(zynsmf_lib, semitones):
    zynsmf_lib.setTranspose(semitones)
    assert zynsmf_lib.getTranspose() == semitones
    zynsmf_lib.setTranspose(0)
