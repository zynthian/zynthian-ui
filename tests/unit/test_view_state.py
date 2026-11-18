"""View state reported by the "screen_state" websocket feedback (get_state / state_key of each view type).

The views need the whole UI to be built, so get_state() runs on bare instances (``__new__``) holding only
the attributes it reads. Which signals the views send is checked on the device (zynthian-operator skill).
"""

import json
from types import SimpleNamespace

from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui.zynthian_gui_engine import zynthian_gui_engine
from zyngui.zynthian_gui_selector_grid import zynthian_gui_selector_grid
from zyngui.zynthian_gui_chain_control import zynthian_gui_chain_control
from zyngui.zynthian_side_chain import zynthian_side_chain
from zyngui.zynthian_gui_confirm import zynthian_gui_confirm
from zyngui.zynthian_gui_fullscreen_modal import zynthian_gui_fullscreen_modal
from zyngui.zynthian_gui_base import zynthian_gui_base


def bare(cls, **attrs):
    obj = cls.__new__(cls)
    for k, v in attrs.items():
        setattr(obj, k, v)
    return obj


def selector(items, index):
    # list_data rows: (action, index, label, ...); action None => header/separator
    return bare(zynthian_gui_selector, list_data=[(None if it.startswith("> ") else "x", i, it)
                                                  for i, it in enumerate(items)], index=index)


def test_selector_reports_labels_and_selection():
    s = selector(["> MIDI", "Program Change", "Test MIDI"], 2)
    assert s.state_key == "zyngui_selector"
    assert s.get_state() == {"items": ["> MIDI", "Program Change", "Test MIDI"], "selected": 2}
    assert s.get_state("list") == s.get_state()
    assert s.get_state("select") == {"selected": 2}      # selection changes don't rebuild the list


def test_engine_adds_categories_on_full_state_only():
    e = bare(zynthian_gui_engine, list_data=[("A", 0, "None"), ("B", 1, "GVerb")], index=1,
             engine_cats=["Delay", "Reverb"], cat_index=1)
    assert e.state_key == "zyngui_engine"
    assert e.get_state() == {"items": ["None", "GVerb"], "selected": 1,
                             "categories": {"items": ["Delay", "Reverb"], "selected": 1}}
    assert e.get_state("select") == {"selected": 1}


def test_grid_reports_button_titles_columns_and_empty_cells():
    g = bare(zynthian_gui_selector_grid, config=[{"title": "Add\nChain"}, None, {"title": "Admin"}],
             selected_node=2, columns=3)
    assert g.state_key == "zyngui_selector_grid"
    # Empty cells keep their position, so indexes match SELECT
    assert g.get_state() == {"items": ["Add Chain", "", "Admin"], "selected": 2, "columns": 3}
    assert g.get_state("select") == {"selected": 2}


def side_chain(shown):
    control = SimpleNamespace(chain_shown=shown)
    return bare(zynthian_side_chain, chain_control=control, selected_index=1,
                nodes=[{"title": "Chain Options"}, {"title": "MIDI Input\nCH#01"}, {"title": "Mixer"}])


def test_side_chain_reports_blocks_and_its_parent():
    sc = side_chain(True)
    assert sc.state_key == "chain_blocks"
    assert sc.get_state() == {"items": ["Chain Options", "MIDI Input CH#01", "Mixer"], "selected": 1}
    assert sc.get_state_parent() is sc.chain_control
    assert sc.is_state_shown()
    assert not side_chain(False).is_state_shown()


def test_chain_control_nests_the_blocks_and_the_embedded_view():
    sub = selector(["> Pad", "Filter"], 1)
    cc = bare(zynthian_gui_chain_control, chain_shown=True, chain_canvas=side_chain(True), subscreen=sub)
    assert cc.state_key == "zyngui_chain_control"
    assert cc.get_state() == {"chain_blocks": {"items": ["Chain Options", "MIDI Input CH#01", "Mixer"], "selected": 1},
                              "zyngui_selector": {"items": ["> Pad", "Filter"], "selected": 1}}
    cc.chain_shown = False
    assert cc.get_state() == {"zyngui_selector": {"items": ["> Pad", "Filter"], "selected": 1}}


def test_confirm_reports_its_question():
    c = bare(zynthian_gui_confirm, text=SimpleNamespace(get=lambda: "Remove chain?"), shown=True)
    assert c.state_key == "zyngui_confirm"
    assert c.get_state() == {"text": "Remove chain?"}
    assert c.get_state_parent() is None and c.is_state_shown()


def test_fullscreen_modals_and_base_views_report_nothing_by_default():
    m = bare(zynthian_gui_fullscreen_modal, shown=False)
    assert m.state_key is None and m.get_state() == {} and not m.is_state_shown()
    b = bare(zynthian_gui_base, parent=None, shown=True)
    assert b.state_key is None and b.get_state() == {} and b.get_state_parent() is None


def test_states_are_json_serializable():
    for view in (selector(["a"], 0), side_chain(True),
                 bare(zynthian_gui_selector_grid, config=[{"title": "x"}], selected_node=0, columns=3)):
        json.dumps(view.get_state())
