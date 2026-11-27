# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian widget for "@@NAME@@"
#
# Plugin: <@@URI@@>
# Declared as a zyngui:widget LV2 UI (see the bundle's manifest.ttl).
#
# Data: LV2 output control ports ("monitors"), polled ~30 times/s while shown:
#   self.monitors[symbol] -> float
# Controls: self.processor.controllers_dict[symbol] (zctrl: .value, .set_value(v, True), .nudge(n))
#   The controls of the page being shown: self.zyngui_control.zcontrollers
#
# Generic widget: one bar per output port in MONITORS or, if there are none, one bar per control
# of the current page. Replace it with the widget designed in SPEC.md.
#
# Copyright (C) @@YEAR@@ @@MAKER@@
# License: @@LICENSE@@
# ******************************************************************************

import tkinter

from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

# Output ports shown by this (generic) widget: symbol -> (label, min, max, unit)
MONITORS = {
@@MONITORS@@
}

MAX_ROWS = max(4, len(MONITORS))


class zynthian_widget_@@SYMBOL@@(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)
@@WIDGET_ROWS@@        self.widget_canvas = tkinter.Canvas(self, highlightthickness=0, relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        # Create all the canvas items once: refresh_gui() only moves/changes them
        tx = zynthian_gui_config.color_panel_tx
        self.bars = []
        for i in range(MAX_ROWS):
            self.bars.append({
                'label': self.widget_canvas.create_text(0, 0, anchor=tkinter.W, text="", fill=tx),
                'bg': self.widget_canvas.create_rectangle(0, 0, 0, 0, fill=zynthian_gui_config.color_panel_bg, width=0),
                'bar': self.widget_canvas.create_rectangle(0, 0, 0, 0, fill=zynthian_gui_config.color_on, width=0),
                'value': self.widget_canvas.create_text(0, 0, anchor=tkinter.E, text="", fill=tx),
            })
        self.last = [None] * MAX_ROWS  # Last drawn (label, value) per row

    def on_size(self, event):
        if not super().on_size(event):
            return
        row_h = self.height / MAX_ROWS
        font = (zynthian_gui_config.font_family, max(8, int(row_h * 0.3)))
        x0 = int(self.width * 0.3)
        x1 = int(self.width * 0.8)
        for i, items in enumerate(self.bars):
            y0 = int(i * row_h + row_h * 0.25)
            y1 = int(i * row_h + row_h * 0.75)
            ym = (y0 + y1) // 2
            self.widget_canvas.coords(items['label'], 8, ym)
            self.widget_canvas.itemconfigure(items['label'], font=font)
            self.widget_canvas.coords(items['bg'], x0, y0, x1, y1)
            self.widget_canvas.coords(items['bar'], x0, y0, x0, y1)
            self.widget_canvas.coords(items['value'], self.width - 8, ym)
            self.widget_canvas.itemconfigure(items['value'], font=font)
        self.last = [None] * MAX_ROWS  # Redraw everything with the new geometry

    def get_rows_data(self):
        """List of (label, value, min, max, text) to draw"""
        if MONITORS:
            res = []
            for symbol, (label, vmin, vmax, unit) in MONITORS.items():
                value = self.monitors.get(symbol)
                if value is not None:
                    res.append((label, value, vmin, vmax, f"{value:.1f} {unit}".strip()))
            return res
        # No outputs: show the controls of the current page
        return [(zctrl.short_name, zctrl.value, zctrl.value_min, zctrl.value_max, zctrl.get_value2label())
                for zctrl in self.zyngui_control.zcontrollers[:MAX_ROWS] if zctrl is not None]

    def refresh_gui(self):
        # Called every ~32 ms while shown: only touch the rows whose data changed
        data = self.get_rows_data()
        for i, items in enumerate(self.bars):
            row = data[i] if i < len(data) else None
            key = row[:2] if row else ()
            if key == self.last[i]:
                continue
            self.last[i] = key
            if not row:
                for item in items.values():
                    self.widget_canvas.itemconfigure(item, state=tkinter.HIDDEN)
                continue
            label, value, vmin, vmax, text = row
            for item in items.values():
                self.widget_canvas.itemconfigure(item, state=tkinter.NORMAL)
            try:
                frac = min(1.0, max(0.0, (value - vmin) / (vmax - vmin)))
            except (TypeError, ZeroDivisionError):
                frac = 0.0
            x0, y0, x1, y1 = self.widget_canvas.coords(items['bg'])
            self.widget_canvas.coords(items['bar'], x0, y0, x0 + frac * (x1 - x0), y1)
            self.widget_canvas.itemconfigure(items['label'], text=label)
            self.widget_canvas.itemconfigure(items['value'], text=text)

    # Optional hooks (return True to consume the event, otherwise the control view handles it):
    # def zynpot_cb(self, i, dval): ...
    # def switch(self, i, t): ...
    # def cuia_arrow_up(self, params=None): ...
    # Example of a control from the widget:
    #   zctrl = self.processor.controllers_dict.get("gain"); zctrl.nudge(dval)

