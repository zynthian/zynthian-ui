"""zynseq ``setPattern`` / ``setState`` pattern loading on the REAL libzynseq.so.

Both entry points share one implementation (``patternFromJson``). What they must guarantee:

* every field of the pattern JSON (zynlibs/zynseq/pattern.schema.json) survives load -> getState;
* loading REPLACES the pattern, including its undo/redo history (it would describe the previous content),
  whether or not the pattern is the selected one.
"""

import copy
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.native, pytest.mark.jack]

A, B = 990, 991


def patn(lib, pattern):
    return json.loads(lib.getState())["patns"][str(pattern)]


# Every field set to a non-default value; events cover the extended format and a control change.
FULL = {
    "beats": 6, "steps": 48, "scale": 3, "tonic": 2, "refNote": 72, "zoom": -2,
    "ccnum": [i % 2 == 0 for i in range(128)],
    "quantize": 2, "swingDiv": 2, "swing": 0.25, "humanTime": 0.5, "humanVel": 0.75, "chance": 80,
    "events": [
        #  step off  dur  cmd  v1s v1e v2s v2e spd vfx rmp ch% pfq sch% sfq
        [0, 0.0, 2.0, 0x90, 60, 60, 100, 0, 8, 1, 2, 75, 3, 50, 5],
        [4, 0.5, 1.0, 0x90, 64, 64, 90, 0, 0, 0, 0, 100, 1, 100, 1],
        [8, 0.0, 1.0, 0xB0, 74, 74, 10, 90, 0, 0, 0, 100, 1, 100, 1],
    ],
}


@pytest.fixture
def lib(seq):
    seq.selectPattern(A)
    return seq


def load(lib, pattern, obj):
    lib.setPattern(pattern, json.dumps(obj).encode())


# --- content ------------------------------------------------------------------------------------------------
def test_set_pattern_stores_every_field(lib):
    load(lib, B, FULL)
    assert patn(lib, B) == FULL


def test_set_state_stores_every_field(lib):
    assert lib.setState(json.dumps({"patns": {str(B): FULL}}).encode())
    assert patn(lib, B) == FULL


def test_set_pattern_and_set_state_agree(lib):
    load(lib, A, FULL)
    via_set_pattern = patn(lib, A)
    assert lib.setState(json.dumps({"patns": {str(A): FULL}}).encode())   # setState re-initialises everything
    assert patn(lib, A) == via_set_pattern == FULL


def test_defaults_for_missing_fields(lib):
    load(lib, B, {"events": [[0, 0.0, 1.0, 0x90, 60, 60, 100, 0, 0, 0, 0, 100, 1, 100, 1]]})
    got = patn(lib, B)
    assert (got["beats"], got["steps"], got["refNote"], got["swingDiv"], got["chance"]) == (4, 16, 60, 1, 100)


def test_legacy_event_format_is_accepted(lib):
    # 11 entries: entry 10 is the play chance; ramp / play freq / stutter chance / stutter freq keep addEvent's defaults
    load(lib, B, {"events": [[1, 0.0, 1.0, 0x90, 62, 62, 80, 0, 4, 2, 40]]})
    (ev,) = patn(lib, B)["events"]
    assert ev == [1, 0.0, 1.0, 0x90, 62, 62, 80, 0, 4, 2, 0, 40, 1, 100, 1]


def test_loading_replaces_previous_content(lib):
    load(lib, B, FULL)
    load(lib, B, {"events": [[0, 0.0, 1.0, 0x90, 50, 50, 100, 0, 0, 0, 0, 100, 1, 100, 1]]})
    (ev,) = patn(lib, B)["events"]
    assert ev[4] == 50


def test_state_round_trip_keeps_the_patterns(lib):
    # Only the patterns: the scenes part of the state is not idempotent (sequence repeat / follow action defaults)
    load(lib, A, FULL)
    load(lib, B, copy.deepcopy(FULL))
    first = json.loads(lib.getState())["patns"]
    assert lib.setState(lib.getState())
    assert json.loads(lib.getState())["patns"] == first


def test_written_patterns_match_the_schema(lib):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((Path(__file__).resolve().parents[3] / "zynlibs" / "zynseq" / "pattern.schema.json").read_text())
    load(lib, B, FULL)
    jsonschema.validate(patn(lib, B), schema)


# --- undo history -------------------------------------------------------------------------------------------
def build_history(lib, pattern):
    """Selected pattern gets an undo history with three snapshots."""
    lib.selectPattern(pattern)
    lib.resetPatternSnapshots()
    lib.addNote(0, 60, 100, 1.0, 0.0)
    lib.savePatternSnapshot()
    lib.addNote(1, 62, 100, 1.0, 0.0)
    lib.savePatternSnapshot()
    assert lib.undoPattern()         # history really is walkable
    assert lib.redoPattern()


def assert_no_history(lib, pattern):
    lib.selectPattern(pattern)
    assert not lib.undoPattern()
    assert not lib.redoPattern()


def test_set_pattern_resets_the_undo_history(lib):
    build_history(lib, B)
    load(lib, B, FULL)
    assert_no_history(lib, B)
    assert patn(lib, B) == FULL      # and undo did not bring the old content back


def test_set_pattern_resets_the_history_of_a_pattern_that_is_not_selected(lib):
    build_history(lib, B)
    lib.selectPattern(A)             # A is the selected pattern, B is the one loaded
    load(lib, B, FULL)
    assert_no_history(lib, B)


def test_set_pattern_leaves_other_patterns_history_alone(lib):
    build_history(lib, A)
    load(lib, B, FULL)
    lib.selectPattern(A)
    assert lib.undoPattern()


def test_set_state_resets_the_undo_history(lib):
    build_history(lib, B)
    assert lib.setState(json.dumps({"patns": {str(B): FULL}}).encode())
    assert_no_history(lib, B)
