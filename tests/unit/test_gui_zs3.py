"""zyngui.zynthian_gui_zs3: where the cursor is when the ZS3 screen is shown (bare instance, no Tk widgets)."""

from types import SimpleNamespace

import pytest

from zyngine.zynthian_signal_manager import zynsigman
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_zs3 import zynthian_gui_zs3


@pytest.fixture
def screen(monkeypatch):
    selected = []
    monkeypatch.setattr(zynthian_gui_selector, "fill_list", lambda self: selected.append(self.index))
    monkeypatch.setattr(zynthian_gui_selector, "set_selector", lambda self: None)
    monkeypatch.setattr(zynthian_gui_selector, "set_select_path", lambda self: None)
    zs3 = {"zs3-0": {"title": "Default"}, "zs3-1": {"title": "A"}, "zs3-2": {"title": "B"}}
    state_manager = SimpleNamespace(zs3=zs3, get_zs3_ids=lambda: list(zs3), last_zs3_id="zs3-2")
    s = zynthian_gui_zs3.__new__(zynthian_gui_zs3)
    s.zyngui = SimpleNamespace(state_manager=state_manager)
    s.moving_zs3 = None
    s.alt_mode = False
    s.show_performance = lambda show: None
    s.set_selector = lambda zs_hidden=None: None
    s.set_select_path = lambda: None
    s.selected = selected
    yield s
    zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_LOAD_ZS3, s.cb_load_zs3)
    zynsigman.unregister(zynsigman.S_STATE_MAN, zynsigman.SS_SAVE_ZS3, s.cb_save_zs3)


def test_the_cursor_starts_on_the_last_loaded_zs3(screen):
    screen.index = 1  # a row of the last visit
    assert screen.build_view()
    # rows: save, default, header, A, B
    assert screen.list_data[screen.index][0] == "zs3-2"
    # the listbox selection (done in fill_list) and the cursor are the same row
    assert screen.selected == [screen.index]
