# Zynthian widgets for LV2 plugins

A zynthian widget is a Python/Tk module shown in the control view of a processor (`chain_control` → control
pages), next to the 4 controller knobs. For LV2 plugins it's declared in the LV2 data as a UI of class
`zyngui:widget`, so zynthian finds it through lilv like any other plugin UI.

## Data flow

| Direction | Mechanism | Rate |
|---|---|---|
| Plugin → widget | **LV2 output control ports** ("monitors"): jalv's `monitors` command prints them, the engine parses them into `processor.engine.lv2_monitors_dict` (symbol → float) | Requested on every `update()` (~32 ms) while the widget is shown; the reply is asynchronous, so `self.monitors` holds the values of the previous request |
| Widget → plugin | Input controls: `zctrl = self.processor.controllers_dict["symbol"]`, then `zctrl.set_value(v, True)`, `zctrl.nudge(±n)`, `zctrl.toggle()` | Immediate |
| Plugin params → widget | `self.processor.controllers_dict["symbol"].value` (current value of an input control) | Read when needed |

Consequences for the spec:
- Only floats. Arrays need one output port each (spectr30 uses 30). Keep it small; every port is parsed every tick.
- No atom/string/event data reaches the widget. Peaks between polls are lost unless the plugin holds them
  (peak-hold / decay in the DSP, reset when read is not possible: use a time-based decay).
- Only **input** control ports become zynthian controllers (pages of 4, grouped by `pg:group`, ordered by
  `lv2:displayPriority`, hidden with `pprop:notOnGUI`). Output ports never appear as controllers.

## Widget module

File `zynthian_widget_<name>.py`, defining class `zynthian_widget_<name>` (same name as the file stem; the loader
requires it) derived from `zyngui.zynthian_widget_base.zynthian_widget_base` (a `tkinter.Frame`):

```python
import tkinter
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

class zynthian_widget_mything(zynthian_widget_base.zynthian_widget_base):
    def __init__(self, parent):
        super().__init__(parent)          # sets self.processor = None, self.monitors = None, self.width/height
        self.widget_canvas = tkinter.Canvas(self, highlightthickness=0, relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')
        # create all canvas items here, once

    def on_size(self, event):             # layout: called on resize; base returns False if size unchanged
        if not super().on_size(event):
            return
        # recompute coords of the items for self.width x self.height

    def refresh_gui(self):                # called ~every 32 ms while shown, after self.monitors was refreshed
        value = self.monitors.get("level")
        # update coords/itemconfigure ONLY if the value changed
```

Lifecycle and hooks (base class and `zyngui/zynthian_gui_control.py`):

| Hook | When | Notes |
|---|---|---|
| `__init__(parent)` | First time the widget is shown | `parent` is the control screen (`self.zyngui_control`) |
| `set_processor(processor)` | Each time it's shown for a processor | Override to read processor info; call `super()` |
| `on_size(event)` | Resize | Layout only |
| `update()` → `get_monitors()` → `refresh_gui()` | Every ~32 ms in control mode, while shown | Don't override `update()` |
| `show()` / `hide()` | Shown/hidden | `self.shown` |
| `zynpot_cb(i, dval)` | Knob turned | Return True to consume it (otherwise the knob moves its controller) |
| `switch(i, t)` | Switch pushed (`t`: S/B/L) | Return True to consume |
| `cuia_<name>(params)` | Any CUIA while the widget is current | Return True to consume (e.g. `cuia_arrow_up`) |
| `update_wsleds(leds)` | V5 LED refresh | Optional |
| `hide_on_select_mode()` | Select mode | Return False to keep it visible while browsing pages |

**Height**: by default the widget uses the full control area (`self.rows = layout['rows']`, 4 on V5/Z2, 2 on V4)
and hides the list of pages. A **half-height** widget sets `self.rows = max(1, self.rows // 2)` in `__init__` after
`super().__init__()`: the list of pages stays visible above it (like `zynthian_widget_drawbar.py`). Good for simple
widgets (a few meters, a value, a small graph); suggest it and ask the user when unsure.

**Built-in widgets take over designated pages**: when a page has a control designated `param:attack/decay/sustain/
release/delay/hold/fade` (envelope), `param:cutoffFrequency/resonance` (filter) or `param:drawbar`, zynthian shows its
built-in widget for that page instead of the plugin's widget (`zynthian_gui_control.get_screen_type`). Design pages
with that in mind: e.g. ADSR in its own group of 4 gets an envelope graph; the plugin widget shows on the other pages.

Module-level `MULTI_INSTANCE = True` creates one widget instance per processor (otherwise one shared instance,
re-targeted with `set_processor()`).

Look & feel: use `zynthian_gui_config` colours (`color_bg`, `color_panel_bg`, `color_panel_tx`, `color_on`,
`color_off`, `color_hl`, `color_tx`, `color_tx_off`, `color_warn`, `color_error`, ...), `font_family` and font sizes
derived from the widget height. Existing widgets to learn from: `zynthian-ui/lv2/*-zyngui.lv2/*.py` (spectr30 =
bars from many outputs, tunaone = text + indicator, nam/aidax = file info) and `zynthian-ui/zyngui/zynthian_widget_*.py`
(organelle = knob/switch handling, sooperlooper = controls from the widget).

Performance (it runs on a Raspberry Pi, at ~30 fps, in the UI thread):
- Create canvas items once; in `refresh_gui()` only `coords()` / `itemconfigure()`, and only when the value changed.
- No `delete()`/`create_*()` per tick, no images regenerated per tick, no threads, no file I/O.
- Avoid work when nothing changed (compare with the last drawn value).

## Declaring the widget (zyngui:widget)

Vocabulary: `http://zynthian.org/ns/lv2/zyngui#` (ontology bundle `zynthian-ui/lv2/zyngui.lv2/`).

```turtle
@prefix ui:     <http://lv2plug.in/ns/extensions/ui#> .
@prefix zyngui: <http://zynthian.org/ns/lv2/zyngui#> .

<PLUGIN_URI> ui:ui <WIDGET_UI_URI> .

<WIDGET_UI_URI>
	a zyngui:widget ;
	ui:binary <zynthian_widget_NAME.py> ;
	zyngui:apiVersion 1 ;
	zyngui:help <zynthian_widget_NAME.html> .
```

- **Case A** (own plugin): the triples are appended to the plugin bundle's `manifest.ttl` by the project's
  `make zyngui` step (DPF regenerates `manifest.ttl` on every build). Widget UI URI: `<PLUGIN_URI>#zyngui`.
- **Case B** (existing plugin): a separate **extension bundle** `<name>-zyngui.lv2/` with only this manifest, the
  `.py` and the help page. It must NOT declare `<PLUGIN_URI> a lv2:Plugin` (lilv ignores a second declaration),
  and the triples must be in `manifest.ttl` (always loaded). One bundle may declare widgets for several plugins.
  Widget UI URI: `http://zynthian.org/plugins/zyngui/user/<name>#<name>` (user) or
  `http://zynthian.org/plugins/zyngui/<name>#<name>` (built-in).
- Locations (all in `LV2_PATH`): built-in widgets `zynthian-ui/lv2/` (zynthian-ui commits), user widgets
  `/zynthian/zynthian-plugins/lv2-widgets/`, plugins `/zynthian/zynthian-plugins/lv2/`.
- Precedence: highest supported `zyngui:apiVersion`, then user widgets (files outside zynthian-ui) over built-in.
- Several plugins sharing one widget: list several `ui:ui` triples to the same UI.

## Help page

`zyngui:help` points to an HTML file in the bundle. Write a plain fragment (`<h1>`, `<p>`, `<ul>`, `<h2>`...): the
help screen adds the zynthian-help stylesheet and the `help_ui` body class, so it looks like the other help pages.
Shown with the help action on the processor's control view. Keep it short: what the widget shows, what each page
of controls does, tips.

## Hot reload (no UI restart)

- New/removed bundles in an `LV2_PATH` folder are detected when the widget is shown, a jalv engine is created or the
  engine list opens.
- Files updated **inside** an existing bundle (manifest, help): `touch $ZYNTHIAN_CONFIG_DIR/lv2.stamp`
  (`zyn_device.sh` does it).
- An updated widget `.py` is re-imported the next time it's shown (file mtime/size), old instances destroyed.
- Plugin binary / ports changes: the running jalv keeps the old code: use "Reload <plugin>" in the processor
  options (keeps preset, parameters, MIDI learn), or remove/add the processor.

## Code references (zynthian-ui)

- `zyngui/zynthian_widget_base.py`, `zyngui/zynthian_gui_control.py` (`show_widget`, `load_widget_module`,
  `plot_zctrls`), `zyngine/zynthian_engine_jalv.py` (`get_custom_gui_fpath`, `refresh_custom_gui`,
  `get_monitors_dict`), `zyngine/zynthian_lv2.py` (`get_plugin_zyngui_widget`, `check_lv2_changes`,
  `get_plugin_ports`).
