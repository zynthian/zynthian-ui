"""The zyngui:widget lookup lives in the base engine, keyed by the engine's LV2 plugin URI.

The jalv engine keeps finding its widget; any other engine that sets plugin_url finds it too; an engine with
no plugin URI keeps its own fixed custom_gui_fpath. zynthian_lv2 is faked, so no lilv is needed.
"""

import types

import pytest

import tests.bootstrap  # noqa: F401  (sandbox + fakes before any zyngine import)

pytestmark = pytest.mark.unit

URI = "urn:zyntest:plugin"
WIDGET = {'uri': 'urn:zyntest:widget', 'fpath': '/w/zynthian_widget_x.py', 'help': '/w/help.html', 'user': False}


@pytest.fixture
def lv2(monkeypatch):
    from zyngine import zynthian_lv2 as z
    state = types.SimpleNamespace(widgets={URI: WIDGET}, lookups=[])

    def lookup(url):
        state.lookups.append(url)
        return state.widgets.get(url)

    monkeypatch.setattr(z, "get_plugin_zyngui_widget", lookup)
    monkeypatch.setattr(z, "check_lv2_changes", lambda: False)
    monkeypatch.setattr(z, "lv2_generation", 1)
    return state


def bare(cls, plugin_url=None):
    """An engine instance without running its (process-starting) constructor."""
    eng = cls.__new__(cls)
    eng.custom_gui_fpath = None
    eng.custom_gui_help_fpath = None
    eng.custom_gui_generation = None
    eng.plugin_url = plugin_url
    return eng


def test_jalv_engine_finds_its_widget(lv2):
    from zyngine.zynthian_engine_jalv import zynthian_engine_jalv
    eng = bare(zynthian_engine_jalv, URI)
    eng.plugin_name = "Zyntest"
    assert eng.get_custom_gui_fpath() == WIDGET['fpath']
    assert eng.custom_gui_help_fpath == WIDGET['help']
    assert eng.custom_gui_generation == 1


def test_base_engine_with_plugin_url_finds_the_widget_on_refresh(lv2):
    from zyngine.zynthian_engine import zynthian_engine
    eng = bare(zynthian_engine, URI)
    eng.refresh_custom_gui()
    assert eng.custom_gui_fpath == WIDGET['fpath']


def test_refresh_follows_a_removed_widget(lv2, monkeypatch):
    from zyngine import zynthian_lv2 as z
    from zyngine.zynthian_engine import zynthian_engine
    eng = bare(zynthian_engine, URI)
    eng.refresh_custom_gui()
    lv2.widgets.clear()
    monkeypatch.setattr(z, "lv2_generation", 2)
    eng.refresh_custom_gui()
    assert eng.custom_gui_fpath is None


def test_engine_without_plugin_url_keeps_its_fixed_widget(lv2):
    from zyngine.zynthian_engine import zynthian_engine
    eng = bare(zynthian_engine)
    eng.custom_gui_fpath = "/fixed/zynthian_widget_clippy.py"
    eng.refresh_custom_gui()
    assert eng.get_custom_gui_fpath() is None
    assert eng.custom_gui_fpath == "/fixed/zynthian_widget_clippy.py"
    assert lv2.lookups == []
