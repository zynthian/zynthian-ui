"""zynseq ``getPatternState`` on the REAL libzynseq.so: the getter matching ``setPattern``.

It reads ONE pattern straight from the library (zynseq.get_pattern_data / get_pattern_json, used by the pattern
editor's state feedback), with the same serialization as ``getState`` (patternToJson).
"""

import json
from pathlib import Path

import pytest

from tests.native.zynseq.test_set_pattern import FULL, load

pytestmark = [pytest.mark.native, pytest.mark.jack]

A, B = 990, 991
SCHEMA = Path(__file__).resolve().parents[3] / "zynlibs" / "zynseq" / "pattern.schema.json"


def get(lib, pattern):
    return json.loads(lib.getPatternState(pattern))


def test_round_trips_with_set_pattern(seq):
    load(seq, B, FULL)
    assert get(seq, B) == FULL


def test_matches_get_state(seq):
    load(seq, A, FULL)
    assert get(seq, A) == json.loads(seq.getState())["patns"][str(A)]


def test_reports_live_edits(seq):
    load(seq, A, FULL)
    seq.selectPattern(A)
    seq.addNote(20, 67, 100, 1.0, 0.0)
    assert [20, 0.0, 1.0, 0x90, 67] in [ev[:5] for ev in get(seq, A)["events"]]


def test_reports_empty_patterns(seq):
    # getState() skips patterns without events; getPatternState() reports them with an empty event list
    load(seq, B, {"beats": 2, "events": []})
    assert str(B) not in json.loads(seq.getState()).get("patns", {})
    got = get(seq, B)
    assert (got["beats"], got["events"]) == (2, [])


def test_matches_the_schema(seq):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text())
    load(seq, B, FULL)
    jsonschema.validate(get(seq, B), schema)
    load(seq, B, {"events": []})
    jsonschema.validate(get(seq, B), schema)
