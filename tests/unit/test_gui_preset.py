"""zyngui.zynthian_gui_preset: the preload info text of the preset list."""

from types import SimpleNamespace

import pytest

from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_preset import zynthian_gui_preset
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info


def make_screen(engine_allows):
    screen = zynthian_gui_preset.__new__(zynthian_gui_preset)
    engine = SimpleNamespace(allow_preset_preload=engine_allows, allow_timer_preload=lambda _: True)
    screen.processor = SimpleNamespace(engine=engine, preset_list=[], load_preset_list=lambda: None)
    return screen


@pytest.mark.parametrize("config_preload, engine_allows, info", [
    (True, True, "Preload enabled."),
    (True, False, "Preload disabled."),
    (False, True, "Preload disabled."),
])
def test_info_text_follows_allow_preset_preload(monkeypatch, config_preload, engine_allows, info):
    monkeypatch.setattr(zynthian_gui_config, "preset_preload", config_preload)
    monkeypatch.setattr(zynthian_gui_selector_info, "fill_list", lambda self: None)
    screen = make_screen(engine_allows)
    screen.fill_list()
    assert screen.default_info.startswith(info)
