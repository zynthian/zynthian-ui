"""zyngui.zynthian_gui_pated_notes: grid touch/mouse handling (on a bare instance, no Tk widgets)."""

from types import SimpleNamespace

import pytest

from zyngui.zynthian_gui_pated_notes import zynthian_gui_pated_notes


def make_screen():
    screen = zynthian_gui_pated_notes.__new__(zynthian_gui_pated_notes)
    screen.grid_drag_start = SimpleNamespace(x=100, y=100, time=0)
    screen.grid_drag_count = 0
    screen.drag_note = False
    screen.step_width = 10
    screen.row_height = 10
    screen.step_offset = 5
    screen.keymap_offset = 0
    screen.view_rows = 8
    screen.selected_cell = [0, 0]
    screen.offsets = []
    screen.set_step_offset = screen.offsets.append
    screen.set_keymap_offset = lambda offset: None
    screen.select_cell = lambda *args: None
    return screen


def test_a_horizontal_drag_scrolls():
    screen = make_screen()
    screen.on_grid_drag(SimpleNamespace(x=60, y=100, time=100))
    assert screen.grid_drag_count == 1
    assert screen.offsets and screen.offsets[-1] > 5


@pytest.mark.parametrize("x, y", [(100, 100), (101, 101)])
def test_a_tap_isnt_a_drag(x, y):
    screen = make_screen()
    screen.on_grid_drag(SimpleNamespace(x=x, y=y, time=100))
    assert screen.grid_drag_count == 0
