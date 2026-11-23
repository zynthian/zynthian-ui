"""zynlibs/zynseq/state.schema.json describes the REAL state written and read by libzynseq.so.

Needs ``jsonschema`` (skipped without it): states written by getState() must validate, and the schema's own example
must be accepted by setState() and survive a round trip.
"""

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.native, pytest.mark.jack]

jsonschema = pytest.importorskip("jsonschema")
referencing = pytest.importorskip("referencing")

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "zynlibs" / "zynseq"


@pytest.fixture(scope="module")
def validator():
    from referencing.jsonschema import DRAFT202012
    schemas = {name: json.loads((SCHEMA_DIR / name).read_text()) for name in ("state.schema.json", "pattern.schema.json")}
    registry = referencing.Registry().with_resources(
        [(s["$id"], DRAFT202012.create_resource(s)) for s in schemas.values()])
    jsonschema.Draft202012Validator.check_schema(schemas["state.schema.json"])
    return jsonschema.Draft202012Validator(schemas["state.schema.json"], registry=registry)


def state_of(lib):
    return json.loads(lib.getState())


def test_default_state_is_valid(seq, validator):
    validator.validate(state_of(seq))


def test_state_with_content_is_valid(seq, validator):
    seq.selectPattern(5)
    seq.addNote(0, 60, 100, 1.0, 0.0)
    seq.addNote(4, 64, 90, 2.0, 0.5)
    seq.setSequenceName(0, 0, 3, b"Lead")
    seq.setSequenceMode(0, 0, 3, 5)
    seq.setSequenceRepeat(0, 0, 3, 2)
    seq.addPattern(0, 0, 3, 0, 0, 5, True)
    state = state_of(seq)
    validator.validate(state)
    assert "5" in state["patns"]
    assert state["scenes"][0]["phrases"][0]["sequences"][3]["name"] == "Lead"


def test_handwritten_state_with_timebase_and_legacy_fields(seq, validator):
    state = {
        "tempo": 98.5, "bpb": 3, "scene": 1,
        "scenes": [
            {"phrases": []},
            {"phrases": [{
                "name": "A", "mode": 4, "bpb": 3, "tempo": 110.0, "repeat": 2,
                "followAction": 1, "followParam": -1, "playFlags": 2, "followRepeat": 3,
                "sequences": [{
                    "name": "S", "followAction": 1, "followParam": 0,        # legacy loop marker
                    "tracks": [{"chan": 2, "output": 1, "map": 0, "patns": {"0": 7, "1920": 7}}],
                    "timebase": [{"bar": 2, "tick": 0, "type": 2, "value": 6},
                                 {"bar": 3, "tick": 480, "type": 1, "value": 140}],
                }],
            }]},
        ],
    }
    validator.validate(state)
    assert seq.setState(json.dumps(state).encode())
    written = state_of(seq)
    validator.validate(written)              # and what the library writes back is valid too
    assert written["scenes"][0] is None      # a scene without phrases is written as null
    assert seq.getSequenceRepeat(1, 0, 0) == 255


def test_schema_example_loads_and_round_trips(seq, validator):
    example = json.loads((SCHEMA_DIR / "state.schema.json").read_text())["examples"][0]
    validator.validate(example)
    assert seq.setState(json.dumps(example).encode())
    written = state_of(seq)
    validator.validate(written)
    assert written["patns"]["1"] == example["patns"]["1"] | {k: v for k, v in written["patns"]["1"].items() if k not in example["patns"]["1"]}
    assert written["scenes"][0]["phrases"][0]["name"] == "Intro"


@pytest.mark.parametrize("bad", [
    {"tempo": "fast"},
    {"patns": {"x": {}}},
    {"scenes": [{"phrases": [{"sequences": [{"tracks": [{"chan": 16}]}]}]}]},
    {"scenes": [{"phrases": [{"sequences": [{"repeat": 256}]}]}]},
    {"scenes": [{"phrases": [{"sequences": [{"tracks": [{"patns": {"abc": 1}}]}]}]}]},
    {"unknown": 1},
])
def test_invalid_states_are_rejected(validator, bad):
    assert not validator.is_valid(bad)


# --- real data: the public example snapshots with legacy (RIFF) sequencer data ------------------------------
from tests.native.zynseq.test_legacy_sequences import RIFF_FILES, converter  # noqa: E402,F401  (converter: fixture)


def clamp_event_chances(state):
    """Return (copy of state with event play/stutter chances above 100 set to 100, whether any was above 100)."""
    state = json.loads(json.dumps(state))
    overflow = False
    for patn in (state.get("patns") or {}).values():
        for event in patn.get("events", []):
            for i in (11, 13):
                if len(event) > i and event[i] > 100:
                    event[i], overflow = 100, True
    return state, overflow


@pytest.mark.skipif(not RIFF_FILES, reason="no snapshot with RIFF sequencer data found in ../zynthian-data")
@pytest.mark.parametrize("path", RIFF_FILES, ids=[p.name for p in RIFF_FILES])
def test_converted_legacy_snapshots_are_valid(converter, seq, validator, path):
    state = converter.convert_state(json.loads(path.read_text()))["zynseq"]
    converted, overflow = clamp_event_chances(state)
    validator.validate(converted)                   # what the converter writes
    assert seq.setState(json.dumps(state).encode())
    written, overflow_written = clamp_event_chances(state_of(seq))
    validator.validate(written)                     # what the library then writes
    if overflow or overflow_written:
        pytest.xfail("convertToJson: legacy event 'Play chance' is a 1-byte field (file_format.txt) but is read with "
                     "fileReadBCD() (4 bytes) and scaled x100, giving values up to 10000 instead of 0..100")
