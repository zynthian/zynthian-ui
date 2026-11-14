"""zynseq pattern editing on the REAL libzynseq.so.

Ported from the legacy ``zynlibs/zynseq/unit_tests.py`` (groups aa..ac), updated for the current API: the sequencer
clock is 1920 PPQN (the old tests assumed 24), ``addNote`` takes float duration/offset and no longer rejects a long
note, ``setStepsPerBeat`` returns nothing (an invalid value is just ignored), and the file ``load``/``save`` calls
were replaced by ``getState``/``setState``.

Pattern functions act on the *selected* pattern; selecting a pattern that does not exist creates it.
"""

import json

import pytest

pytestmark = [pytest.mark.native, pytest.mark.jack]

PPQN = 1920            # sequencer clocks per beat
PATTERN = 999


@pytest.fixture
def pat(seq):
    """Library in default state with an empty pattern 999 selected."""
    seq.selectPattern(PATTERN)
    seq.clearNotes()
    return seq


def check_pattern(lib, steps_per_beat, beats, pattern=PATTERN):
    """Pattern geometry is self-consistent: steps = beats * steps/beat, length in clocks."""
    steps = beats * steps_per_beat
    clocks_per_step = PPQN // steps_per_beat
    assert lib.getBeatsInPattern(pattern) == beats
    assert lib.getStepsPerBeat() == steps_per_beat
    assert lib.getSteps() == steps
    assert lib.getClocksPerStep(pattern) == clocks_per_step
    assert lib.getPatternLength(pattern) == clocks_per_step * steps


# --- geometry -----------------------------------------------------------------------------------------------
def test_select_pattern_creates_it_with_default_geometry(seq):
    seq.selectPattern(PATTERN)
    assert seq.getPatternIndex() == PATTERN
    assert seq.isPatternEmpty(PATTERN)
    check_pattern(seq, steps_per_beat=4, beats=4)


def test_beats_in_pattern(pat):
    pat.setBeatsInPattern(PATTERN, 5)
    check_pattern(pat, steps_per_beat=4, beats=5)


@pytest.mark.parametrize("steps_per_beat", [1, 2, 3, 4, 6, 8, 12, 24])
def test_permitted_steps_per_beat(pat, steps_per_beat):
    pat.setBeatsInPattern(PATTERN, 5)
    pat.setStepsPerBeat(steps_per_beat)
    check_pattern(pat, steps_per_beat, beats=5)


@pytest.mark.parametrize("steps_per_beat", [0, 5, 7, 9, 10, 100])
def test_unpermitted_steps_per_beat_is_ignored(pat, steps_per_beat):
    pat.setBeatsInPattern(PATTERN, 5)
    pat.setStepsPerBeat(steps_per_beat)
    check_pattern(pat, steps_per_beat=4, beats=5)


@pytest.mark.xfail(strict=True, reason="pattern.cpp Pattern::setStepsPerBeat declares `float fScale` again inside the "
                                       "else branch, shadowing the outer one, so the 'Move events' loop always "
                                       "scales by 1.0 and notes keep their step index (they move in musical time)")
def test_changing_steps_per_beat_keeps_notes_at_the_same_musical_time(pat):
    """A note on step 2 of 4-per-beat (half a beat in) should be on step 4 of 8-per-beat, twice as long in steps."""
    pat.addNote(2, 60, 100, 2.0, 0.0)
    pat.setStepsPerBeat(8)
    assert pat.getNoteVelocity(4, 60) == 100
    assert pat.getNoteDuration(4, 60) == 4.0


# --- notes --------------------------------------------------------------------------------------------------
def test_add_note(pat):
    assert pat.addNote(0, 60, 100, 4.0, 0.0)
    assert pat.getNoteVelocity(0, 60) == 100
    assert pat.getNoteDuration(0, 60) == 4.0
    assert pat.getNoteStart(0, 60) == 0
    assert not pat.isPatternEmpty(PATTERN)


def test_note_lookup_is_per_step_and_note(pat):
    pat.addNote(3, 60, 100, 1.0, 0.0)
    assert pat.getNoteVelocity(3, 60) == 100
    assert pat.getNoteVelocity(3, 61) == 0          # other note
    assert pat.getNoteVelocity(2, 60) == 0          # other step
    assert pat.getNoteDuration(3, 61) == 0.0


def test_note_spanning_steps_is_found_from_any_step_it_covers(pat):
    pat.addNote(2, 60, 100, 3.0, 0.0)
    assert pat.getNoteStart(2, 60) == 2
    assert pat.getNoteStart(4, 60) == 2             # step 4 is inside the 3-step note


def test_add_note_beyond_the_pattern_is_rejected(pat):
    assert not pat.addNote(pat.getSteps(), 60, 100, 1.0, 0.0)
    assert pat.isPatternEmpty(PATTERN)


def test_set_note_velocity(pat):
    pat.addNote(0, 60, 100, 4.0, 0.0)
    pat.setNoteVelocity(0, 60, 123)
    assert pat.getNoteVelocity(0, 60) == 123


def test_note_offset(pat):
    pat.addNote(0, 60, 100, 1.0, 0.0)
    pat.setNoteOffset(0, 60, 0.5)
    assert pat.getNoteOffset(0, 60) == pytest.approx(0.5)


def test_remove_note(pat):
    pat.addNote(0, 60, 100, 1.0, 0.0)
    pat.addNote(1, 62, 100, 1.0, 0.0)
    pat.removeNote(0, 60)
    assert pat.getNoteDuration(0, 60) == 0.0
    assert pat.getNoteVelocity(1, 62) == 100


def test_adding_the_same_note_again_replaces_it(pat):
    pat.addNote(0, 60, 100, 4.0, 0.0)
    pat.addNote(0, 60, 50, 2.0, 0.0)
    assert (pat.getNoteVelocity(0, 60), pat.getNoteDuration(0, 60)) == (50, 2.0)


def test_transpose_moves_all_notes(pat):
    pat.addNote(0, 60, 123, 2.0, 0.0)
    pat.transpose(5)
    assert pat.getNoteDuration(0, 65) == 2.0
    assert pat.getNoteVelocity(0, 65) == 123
    assert pat.getNoteDuration(0, 60) == 0.0
    pat.transpose(-5)
    assert pat.getNoteVelocity(0, 60) == 123


def test_change_velocity_of_all_notes(pat):
    pat.addNote(0, 60, 100, 1.0, 0.0)
    pat.addNote(1, 62, 50, 1.0, 0.0)
    pat.changeVelocityAll(10)
    assert (pat.getNoteVelocity(0, 60), pat.getNoteVelocity(1, 62)) == (110, 60)


def test_copy_pattern(pat):
    pat.addNote(0, 60, 123, 2.0, 0.0)
    pat.copyPattern(PATTERN, 998)
    pat.selectPattern(998)
    assert pat.getNoteDuration(0, 60) == 2.0
    assert pat.getNoteVelocity(0, 60) == 123
    pat.selectPattern(PATTERN)
    assert pat.getNoteVelocity(0, 60) == 123        # the source is untouched


def test_clear_pattern(pat):
    pat.addNote(0, 60, 100, 1.0, 0.0)
    pat.clearPattern(PATTERN)
    assert pat.isPatternEmpty(PATTERN)
    assert pat.getNoteDuration(0, 60) == 0.0


def test_clear_notes(pat):
    pat.addNote(0, 60, 100, 1.0, 0.0)
    pat.clearNotes()
    assert pat.isPatternEmpty(PATTERN)


def test_pattern_modified_flag_is_cleared_by_reading_it(pat):
    pat.isPatternModified()                          # clear whatever select/clear left behind
    pat.addNote(0, 60, 100, 4.0, 0.0)
    assert pat.isPatternModified()
    assert not pat.isPatternModified()


# --- controls and program change ----------------------------------------------------------------------------
def test_control_ramp_without_interpolation(pat):
    """With interpolation off a CC event is stored exactly as given (on, the library re-steps/joins CC events)."""
    pat.setInterpolateCC(7, False)
    assert pat.addControl(0, 7, 20, 100, 4.0, 0.0)
    assert (pat.getControlValue(0, 7), pat.getControlValueEnd(0, 7)) == (20, 100)
    assert pat.getControlDuration(0, 7) == 4.0
    pat.removeControl(0, 7)
    assert pat.getControlDuration(0, 7) == 0.0


def test_control_longer_than_the_pattern_is_rejected(pat):
    pat.setInterpolateCC(7, False)
    assert not pat.addControl(0, 7, 0, 127, pat.getSteps() + 1, 0.0)


def test_program_change(pat):
    assert pat.addProgramChange(0, 42)
    assert pat.getProgramChange(0) == 42


# --- undo / redo --------------------------------------------------------------------------------------------
def test_undo_and_redo_walk_the_snapshot_history(pat):
    """The history holds snapshots taken AFTER each edit (the UI calls savePatternSnapshot after editing);
    undo restores the previous snapshot, so edits made since the last snapshot are discarded with it."""
    pat.resetPatternSnapshots()                      # history = [empty]
    pat.addNote(0, 60, 100, 1.0, 0.0)
    pat.savePatternSnapshot()                        # [empty, {60}]
    pat.addNote(1, 62, 100, 1.0, 0.0)
    pat.savePatternSnapshot()                        # [empty, {60}, {60,62}]
    assert pat.undoPattern()
    assert (pat.getNoteVelocity(0, 60), pat.getNoteVelocity(1, 62)) == (100, 0)
    assert pat.redoPattern()
    assert pat.getNoteVelocity(1, 62) == 100
    assert not pat.redoPattern()                     # nothing newer
    assert pat.undoPattern() and pat.undoPattern()
    assert pat.isPatternEmpty(PATTERN)
    assert not pat.undoPattern()                     # oldest snapshot reached


# --- state (what the UI saves to snapshots) -----------------------------------------------------------------
def pattern_state(lib):
    return json.loads(lib.getState()).get("patns", {})  # no "patns" key when no pattern has content


def test_state_contains_the_pattern(pat):
    pat.addNote(2, 64, 90, 2.0, 0.5)
    patn = pattern_state(pat)[str(PATTERN)]
    assert patn["beats"] == 4 and patn["steps"] == 16
    # event: [step, offset, duration, MIDI command, note, ..., velocity, ...]
    (event,) = patn["events"]
    assert event[:5] == [2, 0.5, 2.0, 0x90, 64] and event[6] == 90


def test_state_round_trip_restores_patterns(pat):
    pat.setBeatsInPattern(PATTERN, 6)
    pat.setStepsPerBeat(8)
    pat.addNote(2, 64, 90, 2.0, 0.0)
    state = pat.getState()
    pat.reset()
    assert str(PATTERN) not in pattern_state(pat)
    assert pat.setState(state)
    pat.selectPattern(PATTERN)
    check_pattern(pat, steps_per_beat=8, beats=6)
    assert pat.getNoteVelocity(2, 64) == 90
    assert pat.getNoteDuration(2, 64) == 2.0


def test_set_state_rejects_garbage(seq):
    assert not seq.setState(b"this is not json")
