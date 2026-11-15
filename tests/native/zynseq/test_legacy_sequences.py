"""Snapshot schema V3 -> V4: the old binary (RIFF) sequencer data is converted to JSON by the REAL libzynseq.

zynthian_legacy_snapshot.version_3() decodes the base64 RIFF blob, writes it to a file and asks the library
(``convertToJson``) for the JSON. The public example snapshots in ``../zynthian-data/snapshots`` that still carry
a RIFF blob are used as inputs (skipped when that checkout is not there).
"""

import base64
import ctypes
import json
import types

import pytest

from tests.bootstrap import zynthian_data_snapshots

pytestmark = [pytest.mark.native, pytest.mark.jack]

CORPUS = zynthian_data_snapshots()
RIFF_FILES = sorted(p for p in CORPUS.glob("*.zss") if '"zynseq_riff_b64"' in p.read_text()) if CORPUS else []


@pytest.fixture
def converter(seq):
    import zyngine.zynthian_state_manager  # noqa: F401  (import order: see tests/conftest.py)
    from zyngine.zynthian_legacy_snapshot import zynthian_legacy_snapshot
    seq.convertToJson.restype = ctypes.c_char_p
    seq.convertToJson.argtypes = [ctypes.c_char_p]
    state_manager = types.SimpleNamespace(zynseq=types.SimpleNamespace(libseq=seq))
    return zynthian_legacy_snapshot(state_manager)


def riff_patterns(snapshot):
    """Quantity of pattern blocks in the snapshot's RIFF data."""
    return base64.b64decode(snapshot["zynseq_riff_b64"]).count(b"patn")


@pytest.mark.skipif(not RIFF_FILES, reason="no snapshot with RIFF sequencer data found in ../zynthian-data")
@pytest.mark.parametrize("path", RIFF_FILES, ids=[p.name for p in RIFF_FILES])
def test_riff_sequences_are_converted_to_json(converter, seq, path):
    snapshot = json.loads(path.read_text())
    expected_patterns = riff_patterns(snapshot)
    state = converter.convert_state(snapshot)
    assert "zynseq_riff_b64" not in state
    zynseq = state["zynseq"]
    assert len(zynseq.get("patns") or {}) == expected_patterns, "every pattern block must be converted"
    if expected_patterns:
        assert zynseq["scenes"] and all(scene["phrases"] for scene in zynseq["scenes"])
        for scene in zynseq["scenes"]:
            for phrase in scene["phrases"]:
                assert all(isinstance(s, dict) and "tracks" in s for s in phrase["sequences"])
    # whatever came out, the sequencer accepts it and keeps the patterns
    assert seq.setState(json.dumps(zynseq).encode())
    assert len(json.loads(seq.getState()).get("patns", {})) == expected_patterns
