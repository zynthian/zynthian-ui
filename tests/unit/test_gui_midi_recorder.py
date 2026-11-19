"""zyngui.zynthian_gui_midi_recorder: the options of the MIDI file rows."""

from types import SimpleNamespace

import pytest

from zyngui.zynthian_gui_midi_recorder import zynthian_gui_midi_recorder

ROWS = [
    ("START_RECORDING", 0, "Start MIDI Recording", ["", None]),
    [None, 0, "SD> Captured MIDI Tracks"],
    ["/tmp/song.mid", 1, "song (0:10)", ["", None]],
]


def make_screen(index):
    screen = zynthian_gui_midi_recorder.__new__(zynthian_gui_midi_recorder)
    screen.list_data = ROWS
    screen.index = index
    shown = []
    option = SimpleNamespace(config=lambda title, options, cb: shown.append(list(options)))
    screen.zyngui = SimpleNamespace(screens={"option": option}, show_screen=lambda name: None)
    return screen, shown


@pytest.mark.parametrize("index, shown_options", [(0, []), (1, []), (2, [["Rename", "Delete"]])])
def test_file_options_only_on_file_rows(index, shown_options):
    screen, shown = make_screen(index)
    screen.show_smf_options()
    assert shown == shown_options
