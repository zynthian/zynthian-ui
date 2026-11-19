"""zyngui.zynthian_gui_control: the menu of the control view (bare instance, no Tk widgets)."""

from types import SimpleNamespace

import pytest

from zyngui.zynthian_gui_control import zynthian_gui_control


@pytest.mark.parametrize("proc_id, shown", [(-2, []), (-3, []), (1, ["processor_options"])])
def test_menu_shows_processor_options_except_for_special_processors(proc_id, shown):
    screen = zynthian_gui_control.__new__(zynthian_gui_control)
    screens = []
    screen.zyngui = SimpleNamespace(get_current_processor=lambda: SimpleNamespace(id=proc_id),
                                    show_screen=screens.append)
    assert screen.show_menu()
    assert screens == shown
