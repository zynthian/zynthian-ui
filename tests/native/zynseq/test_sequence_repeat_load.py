"""zynseq ``setState``: how a sequence's ``repeat`` / ``followAction`` are loaded (real libzynseq.so).

* ``repeat`` omitted => loops forever (255): sequences loop by default.
* ``repeat`` explicit => kept, notably 0 (disabled) even though getState() writes followAction=RELATIVE for
  every sequence created by insertPhrase().
* Legacy files marked an endless loop with followAction=RELATIVE (and no / a one-shot repeat) => 255.
"""

import json

import pytest

pytestmark = [pytest.mark.native, pytest.mark.jack]

RELATIVE = 1
TRACK = {"chan": 0, "output": 0, "map": 0, "patns": {}}


def load_sequence(lib, **fields):
    """Load a state with one phrase holding one sequence with the given fields; return the sequence's repeat."""
    seq = {"tracks": [TRACK], **fields}
    state = {"scenes": [{"phrases": [{"sequences": [seq]}]}]}
    assert lib.setState(json.dumps(state).encode())
    return lib.getSequenceRepeat(0, 0, 0)


def test_missing_repeat_loops_forever(seq):
    assert load_sequence(seq) == 255


@pytest.mark.parametrize("repeat", [0, 1, 4, 255])
def test_explicit_repeat_is_kept(seq, repeat):
    assert load_sequence(seq, repeat=repeat) == repeat


def test_disabled_sequence_stays_disabled_with_the_loop_follow_action(seq):
    # what getState() writes for the sequences of a channel with no chain
    assert load_sequence(seq, repeat=0, followAction=RELATIVE, followParam=0) == 0


@pytest.mark.parametrize("fields", [{"followAction": RELATIVE}, {"repeat": 1, "followAction": RELATIVE}])
def test_legacy_loop_follow_action_means_endless_loop(seq, fields):
    assert load_sequence(seq, **fields) == 255


def test_disabled_sequences_survive_a_state_round_trip(seq):
    # fresh state: channels have no chain => repeat 0 with followAction RELATIVE
    assert seq.getSequenceRepeat(0, 0, 5) == 0
    assert seq.setState(seq.getState())
    assert seq.getSequenceRepeat(0, 0, 5) == 0
