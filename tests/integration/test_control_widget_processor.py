"""Control screen: a widget follows its processor when the processor is reloaded (replaced, same id)."""

import types

import pytest

pytestmark = pytest.mark.integration


def _control(processors):
    """Just the state refresh_widget_processor uses, without building the Tk screen."""
    return types.SimpleNamespace(chain_manager=types.SimpleNamespace(processors=processors))


def _refresh(control, widget):
    from zyngui.zynthian_gui_control import zynthian_gui_control as cls
    cls.refresh_widget_processor(control, widget)


def _widget_on(processor):
    widget = types.SimpleNamespace(processor=processor)
    widget.set_processor = lambda p: setattr(widget, "processor", p)
    return widget


def test_widget_of_reloaded_processor_is_rebound():
    """Reloading a processor replaces the object (same id): a widget still holding the old one is rebound"""
    old = types.SimpleNamespace(id=5, chain=None)  # removed from its chain
    new = types.SimpleNamespace(id=5, chain=object())
    control = _control({5: new})
    widget = _widget_on(old)
    _refresh(control, widget)
    assert widget.processor is new


def test_widget_of_live_or_removed_processor_is_kept():
    live = types.SimpleNamespace(id=5, chain=object())
    removed = types.SimpleNamespace(id=6, chain=None)  # removed, not replaced
    control = _control({5: live})
    for proc in (live, removed, None):
        widget = _widget_on(proc)
        _refresh(control, widget)
        assert widget.processor is proc
