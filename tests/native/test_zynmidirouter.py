"""ZynMidiRouter behaviour, checked on the REAL compiled library (TOUCH_ONLY build, dummy jackd).

MIDI goes in through a JACK port (``dev0_in``) and is observed on the router's outputs (``chN_out``,
``mod_out``, ...) and in the queue captured for the UI. Expected values were derived from
``zyncoder/zynmidirouter.c`` and confirmed against the running library.

Router vocabulary: a *zmip* is an input (24 devices, seq, step, ctrl, internal), a *zmop* an output
(16 chains, mod, step, ctrl, 24 devices). By default every chain output is routed from every device, but
has NO MIDI channel assigned (``midi_chan = -1``), so nothing flows until the test assigns one.
"""

import ctypes

import pytest

from tests.fakes.zyncore import ROUTER_CONSTANTS

pytestmark = [pytest.mark.native, pytest.mark.jack]

NOTE_ON, NOTE_OFF, CC, PROG, BEND = 0x90, 0x80, 0xB0, 0xC0, 0xE0
ZMOP_MOD = 16
FLAG_DROPPC, FLAG_DROPCC, FLAG_DROPSYS, FLAG_DROPSYSEX, FLAG_DROPNOTE = 1, 2, 4, 8, 16


def note_on(chan, note=60, vel=100):
    return [NOTE_ON | chan, note, vel]


def note_off(chan, note=60):
    return [NOTE_OFF | chan, note, 0]


@pytest.fixture
def lib(router):
    for name in ("zmop_get_note_low", "zmop_get_note_high"):
        getattr(router.lib, name).restype = ctypes.c_ubyte
    return router.lib


# --- the fake must agree with the real library ----------------------------------------------------------
@pytest.mark.parametrize("name,expected", sorted(ROUTER_CONSTANTS.items()))
def test_fake_zyncore_constants_match_the_real_library(lib, name, expected):
    """tests/fakes/zyncore.py hard-codes these; this keeps the fake honest."""
    assert getattr(lib, name)() == expected


# --- ports -----------------------------------------------------------------------------------------------
def test_router_exposes_the_expected_jack_ports(router):
    import jack
    client = jack.Client("portlister", servername=router.server.name, no_start_server=True)
    try:
        ins = {p.shortname for p in client.get_ports("ZynMidiRouter:", is_midi=True, is_input=True)}
        outs = {p.shortname for p in client.get_ports("ZynMidiRouter:", is_midi=True, is_output=True)}
    finally:
        client.close()
    assert ins == {f"dev{i}_in" for i in range(24)} | {"seq_in", "step_in", "ctrl_in"}
    assert outs == ({f"ch{i}_out" for i in range(16)} | {"mod_out", "step_out", "ctrl_out"}
                    | {f"dev{i}_out" for i in range(24)})


# --- channel routing ------------------------------------------------------------------------------------
def test_chain_without_midi_channel_gets_nothing(router, lib):
    router.listen("ch0")
    assert router.send(note_on(0)) == {}


def test_chain_receives_only_its_own_midi_channel(router, lib):
    """Not in active-chain mode: a chain with MIDI channel 3 passes channel 3 and drops the rest."""
    router.listen("ch0")
    lib.zmip_set_flag_active_chain(0, 0)
    lib.zmop_set_midi_chan(0, 3)
    assert router.send(note_on(3)) == {"ch0": [bytes(note_on(3))]}
    assert router.send(note_on(4)) == {}


def test_each_chain_gets_its_own_channel(router, lib):
    router.listen("ch0", "ch1")
    lib.zmip_set_flag_active_chain(0, 0)
    lib.zmop_set_midi_chan(0, 0)
    lib.zmop_set_midi_chan(1, 1)
    assert router.send(note_on(0), note_on(1)) == {"ch0": [bytes(note_on(0))], "ch1": [bytes(note_on(1))]}


def test_active_chain_mode_sends_everything_to_the_active_chain_translated(router, lib):
    """Keyboard input (active-chain flag) goes to the active chain only, on that chain's channel."""
    router.listen("ch0", "ch1")
    lib.zmop_set_midi_chan(0, 3)
    lib.zmop_set_midi_chan(1, 5)
    lib.set_active_chain(1)
    assert router.send(note_on(9)) == {"ch1": [bytes(note_on(5))]}
    lib.set_active_chain(0)
    assert router.send(note_on(9)) == {"ch0": [bytes(note_on(3))]}


def test_active_chain_none_drops_keyboard_notes(router, lib):
    router.listen("ch0")
    lib.zmop_set_midi_chan(0, 0)
    lib.set_active_chain(-1)
    assert router.send(note_on(0)) == {}


def test_notes_pressed_on_one_chain_are_released_there_after_active_chain_change(router, lib):
    """Note-off must follow its note-on even if the active chain changed in between (no stuck notes)."""
    router.listen("ch0", "ch1")
    lib.zmop_set_midi_chan(0, 0)
    lib.zmop_set_midi_chan(1, 1)
    lib.set_active_chain(0)
    assert router.send(note_on(0)) == {"ch0": [bytes(note_on(0))]}
    lib.set_active_chain(1)
    assert router.send(note_off(0)) == {"ch0": [bytes(note_off(0))]}
    assert router.send(note_on(0)) == {"ch1": [bytes(note_on(1))]}


# --- routing zmip => zmop -------------------------------------------------------------------------------
def test_unrouting_an_input_stops_it_reaching_a_chain(router, lib):
    router.listen("ch0")
    lib.zmip_set_flag_active_chain(0, 0)
    lib.zmop_set_midi_chan(0, 0)
    assert router.send(note_on(0)) != {}
    lib.zmop_set_route_from(0, 0, 0)
    assert router.send(note_on(0)) == {}
    lib.zmop_set_route_from(0, 0, 1)
    assert router.send(note_on(0)) != {}


# --- note range & transpose -----------------------------------------------------------------------------
@pytest.fixture
def chain0(router, lib):
    router.listen("ch0")
    lib.zmip_set_flag_active_chain(0, 0)
    lib.zmop_set_midi_chan(0, 0)
    return router


def test_note_range_drops_notes_outside(chain0, lib):
    lib.zmop_set_note_low(0, 50)
    lib.zmop_set_note_high(0, 70)
    assert chain0.send(note_on(0, 60)) == {"ch0": [bytes(note_on(0, 60))]}
    assert chain0.send(note_on(0, 49)) == {}
    assert chain0.send(note_on(0, 71)) == {}


def test_transpose_octave_and_semitone(chain0, lib):
    lib.zmop_set_transpose_octave(0, 1)
    lib.zmop_set_transpose_semitone(0, 2)
    assert chain0.send(note_on(0, 60)) == {"ch0": [bytes(note_on(0, 74))]}


def test_note_off_uses_the_transpose_of_its_note_on(chain0, lib):
    """Changing transpose while a note is held must not leave a hanging note."""
    lib.zmop_set_transpose_octave(0, 1)
    assert chain0.send(note_on(0, 60)) == {"ch0": [bytes(note_on(0, 72))]}
    lib.zmop_set_transpose_octave(0, -1)
    assert chain0.send(note_off(0, 60)) == {"ch0": [bytes(note_off(0, 72))]}


def test_transpose_out_of_range_drops_the_note(chain0, lib):
    lib.zmop_set_transpose_octave(0, 5)
    assert chain0.send(note_on(0, 100)) == {}


def test_global_transpose_adds_to_chain_transpose(chain0, lib):
    lib.set_global_transpose(2)
    lib.zmop_set_transpose_semitone(0, 1)
    assert chain0.send(note_on(0, 60)) == {"ch0": [bytes(note_on(0, 63))]}


# --- drop flags -----------------------------------------------------------------------------------------
def test_drop_cc_blocks_cc_unless_explicitly_routed(chain0, lib):
    lib.zmop_set_flag_dropcc(0, 1)
    assert chain0.send([CC, 7, 100]) == {}
    routed = (ctypes.c_ubyte * 128)()
    routed[7] = 1
    lib.zmop_set_cc_route(0, routed)
    assert chain0.send([CC, 7, 100]) == {"ch0": [bytes([CC, 7, 100])]}
    assert chain0.send([CC, 8, 100]) == {}


def test_drop_program_change(chain0, lib):
    assert chain0.send([PROG, 5]) == {"ch0": [bytes([PROG, 5])]}
    lib.zmop_set_flag_droppc(0, 1)
    assert chain0.send([PROG, 5]) == {}


def test_drop_notes_keeps_other_events(chain0, lib):
    lib.zmop_set_flag_dropnote(0, 1)
    assert chain0.send(note_on(0), [CC, 7, 1]) == {"ch0": [bytes([CC, 7, 1])]}


# --- MIDI event filter / mapping (set by MidiFilterRule) --------------------------------------------------
def test_event_ignore_rule_drops_only_that_event(chain0, lib):
    lib.set_midi_filter_event_ignore(0xB, 0, 7)
    assert chain0.send([CC, 7, 100]) == {}
    assert chain0.send([CC, 8, 100]) == {"ch0": [bytes([CC, 8, 100])]}
    lib.reset_midi_filter_event_map()
    assert chain0.send([CC, 7, 100]) == {"ch0": [bytes([CC, 7, 100])]}


def test_event_map_rewrites_cc_number(chain0, lib):
    lib.set_midi_filter_event_map(0xB, 0, 7, 0xB, 0, 74)
    assert chain0.send([CC, 7, 100]) == {"ch0": [bytes([CC, 74, 100])]}


def test_midi_filter_rule_text_drives_the_real_router(chain0, lib, monkeypatch):
    """End to end: the production parser (zynthian_midi_filter) calling the real library."""
    from zyngine import zynthian_midi_filter as mf
    monkeypatch.setattr(mf, "lib_zyncore", lib)
    # The channel in the rule text is passed to the library unchanged, so it is 0-based: CH#0 is MIDI channel 1.
    mf.MidiFilterRule("IGNORE CH#1 CC#7")
    assert chain0.send([CC, 7, 100]) != {}  # channel 1 (CH#0) is not affected
    mf.MidiFilterRule("IGNORE CH#0 CC#7")
    assert chain0.send([CC, 7, 100]) == {}
    assert chain0.send([CC, 8, 100]) != {}


# --- UI capture ------------------------------------------------------------------------------------------
def test_device_events_are_captured_for_the_ui_with_device_index(chain0, lib):
    chain0.send(note_on(2, 64, 90))
    assert chain0.ui_events() == [(0, NOTE_ON | 2, 64, 90)]


def test_ui_reserved_channels_are_captured_but_not_routed(chain0, lib):
    lib.zmip_set_ui_midi_chans(0, 1 << 0)  # channel 1 reserved for the UI
    assert chain0.send(note_on(0)) == {}
    assert chain0.ui_events() == [(0, NOTE_ON, 60, 100)]


# --- system messages -------------------------------------------------------------------------------------
def test_sysex_is_ignored_unless_input_has_system_flag_and_output_allows_it(chain0, lib):
    sysex = [0xF0, 0x7E, 0x7F, 0x06, 0x01, 0xF7]
    lib.zmop_set_flag_dropsysex(0, 1)
    assert chain0.send(sysex) == {}
    lib.zmop_set_flag_dropsysex(0, 0)
    out = chain0.send(sysex)
    assert out == {"ch0": [bytes(sysex)]}


# --- direct send (used by the Python side to inject MIDI) -------------------------------------------------
def test_internal_direct_send_reaches_the_chains(chain0, lib):
    """zmip_send_* on the internal input (ZMIP_FAKE_INT) is how Python injects MIDI into the router.

    Only inputs created with FLAG_ZMIP_DIRECTIN have a ring buffer; calling zmip_send_* on a plain device
    input (e.g. 0) dereferences NULL and segfaults the process (zyncoder bug, see tests/README.md),
    so this test deliberately uses the internal input."""
    chain0.rec.clear()
    assert lib.zmip_send_note_on(lib.zmip_get_int_index(), 0, 62, 90) == 1
    chain0.runner.run(2048)
    assert [d for _, d in chain0.rec.midi["ch0"]] == [bytes(note_on(0, 62, 90))]
