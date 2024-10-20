#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for envelope screen type
#
# Copyright (C) 2015-2024 Fernando Moyano <fernando@zynthian.org>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import tkinter
import logging

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_widget_base

# ------------------------------------------------------------------------------
# Zynthian Widget Class for envelope screen type
# ------------------------------------------------------------------------------


class zynthian_widget_envelope(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)

        # Geometry vars set accurately during resize
        self.rows = self.zyngui_control.layout['rows'] // 2

        self.widget_canvas = tkinter.Canvas(self,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        self.last_envelope_values = []
        self.drag_zctrl = None

        # Create custom GUI elements (position and size set when canvas is grid and size applied)
        self.envelope_outline_color = zynthian_gui_config.color_low_on
        self.envelope_color = zynthian_gui_config.color_variant(
            zynthian_gui_config.color_low_on, -70)
        self.envelope_polygon = self.widget_canvas.create_polygon(0, 0,
                                                                  outline=self.envelope_outline_color, fill=self.envelope_color, width=3)
        self.drag_polygon = self.widget_canvas.create_polygon(0, 0,
                                                              outline=self.envelope_outline_color, fill=self.envelope_outline_color, width=3, state='hidden')
        # self.release_line = self.widget_canvas.create_line(0, 0, 0, 0,
        # fill=self.envelope_outline_color, state="hidden")
        # self.release_label = self.widget_canvas.create_text(0, 0, text="R", anchor="ne",
        # font=(zynthian_gui_config.font_family, int(1.3*zynthian_gui_config.font_size)),
        # fill=zynthian_gui_config.color_tx, state="hidden")
        self.widget_canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.widget_canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.widget_canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.fade_polarity = 1

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)
        self.widget_canvas.grid(row=0, column=0, sticky='news')
        self.last_envelope_values = []
        self.dy = int(0.95 * self.height)
        if self.zctrls:
            self.dx = self.width // len(self.zctrls)
        self.refresh_gui()

    def show(self):
        zctrls = {}
        self.zctrls = []
        for zctrl in self.processor.get_group_zctrls(self.zyngui_control.screen_info[0]):
            try:
                zctrls[zctrl.envelope] = zctrl
            except:
                pass
        for symbol in ["delay", "attack", "hold", "decay", "sustain", "fade", "release"]:
            if symbol in zctrls:
                self.zctrls.append(zctrls[symbol])
                if symbol == "fade":
                    if zctrls[symbol].value_min < 0:
                        self.fade_polarity = -1
                    else:
                        self.fade_polarity = 1
        self.dx = self.width // len(self.zctrls)
        # self.widget_canvas.itemconfig(self.release_line, state="hidden")
        # self.widget_canvas.itemconfig(self.release_label, state="hidden")
        super().show()

    def refresh_gui(self):
        envelope_values = []
        y_sustain = self.height // 2
        x_release = self.width
        y_fade = None
        for zctrl in self.zctrls:
            envelope_values.append(zctrl.value / zctrl.value_range)
            match zctrl.envelope:
                case "sustain":
                    y_sustain = self.height - zctrl.value / zctrl.value_range * self.dy
                case "release":
                    x_release = self.width - zctrl.value / zctrl.value_range * self.dx
                case "fade":
                    y_fade = self.height - \
                        (1 - 0.5 * (self.fade_polarity - 1) + self.fade_polarity * zctrl.value / zctrl.value_range) * \
                        (self.height - y_sustain) / 2
        if y_fade is None:
            y_fade = y_sustain

        if envelope_values != self.last_envelope_values or self.drag_zctrl:
            x = 0
            y = y0 = self.height
            coords = [x, y0]
            self.envelope_click_ranges = []

            for zctrl in self.zctrls:
                match zctrl.envelope:
                    case "release":
                        x = self.width - zctrl.value / zctrl.value_range * self.dx
                        drag_window = [x, y, self.width,
                                       self.height, x, self.height]
                        self.envelope_click_ranges.append(x)
                        if coords[-2] == self.width:
                            coords[-2] = x  # Fix fade if it exists
                        # self.widget_canvas.coords(self.release_line, x, y, x, y0)
                        # self.widget_canvas.itemconfig(self.release_line, state="normal")
                        # self.widget_canvas.coords(self.release_label, x-3, y)
                        # self.widget_canvas.itemconfig(self.release_label, state="normal")
                    case "sustain":
                        y = y0 - zctrl.value / zctrl.value_range * self.dy
                        drag_window = [x, y0, x, y,
                                       x_release, y_fade, x_release, y0]
                    case "fade":
                        y_offset = (y0 - y) / 2
                        drag_window = [x, y, x, y + y_offset]
                        y = y_fade
                        self.envelope_click_ranges.append(
                            x + (x_release - x) * 0.75)
                        x = x_release
                        drag_window += [x, drag_window[-1], x, y]
                    case _:
                        _x = x
                        drag_window = [x, y]
                        x += zctrl.value / zctrl.value_range * self.dx
                        if zctrl.envelope == "attack":
                            y = y0 - self.dy
                        elif zctrl.envelope == "decay":
                            y = y_sustain
                        drag_window += [x, y, x, self.height, _x, self.height]
                        self.envelope_click_ranges.append(x)
                coords.append(x)
                coords.append(y)
                if self.drag_zctrl == zctrl:
                    self.widget_canvas.coords(self.drag_polygon, drag_window)

            coords.append(self.width)
            coords.append(y0)
            self.envelope_click_ranges.append(self.width)
            self.widget_canvas.coords(self.envelope_polygon, coords)
            self.last_envelope_values = envelope_values
            # Highlight dragged section
            if self.drag_zctrl:
                self.widget_canvas.itemconfig(
                    self.drag_polygon, state="normal")

    def on_canvas_press(self, event):
        self.last_click = event

        # Identify the envelope phase clicked
        for i in range(len(self.envelope_click_ranges) - 1):
            # Allow selection of last phase, near end of penultimate phase
            if i == len(self.envelope_click_ranges) - 2:
                x = self.envelope_click_ranges[i] - (
                    self.envelope_click_ranges[i] - self.envelope_click_ranges[i - 1]) / 4
            else:
                x = self.envelope_click_ranges[i] + (
                    self.envelope_click_ranges[i + 1] - self.envelope_click_ranges[i]) / 4
            if event.x < x:
                self.drag_zctrl = self.zctrls[i]
                self.envelope_click_value = self.drag_zctrl.value
                return
        self.drag_zctrl = self.zctrls[-1]
        self.envelope_click_value = self.drag_zctrl.value

    def on_canvas_drag(self, event):
        if self.drag_zctrl == None:
            return
        dx = (event.x - self.last_click.x) / self.dx
        dy = (event.y - self.last_click.y) / self.dy
        match self.drag_zctrl.envelope:
            case "release":
                self.drag_zctrl.set_value(
                    self.envelope_click_value - self.drag_zctrl.value_range * dx)
            case "sustain":
                self.drag_zctrl.set_value(
                    self.envelope_click_value - self.drag_zctrl.value_range * dy)
            case "fade":
                self.drag_zctrl.set_value(
                    self.envelope_click_value - self.fade_polarity * self.drag_zctrl.value_range * dy)
            case _:
                self.drag_zctrl.set_value(
                    self.envelope_click_value + self.drag_zctrl.value_range * dx)

    def on_canvas_release(self, event):
        self.drag_zctrl = None
        self.widget_canvas.itemconfig(self.drag_polygon, state="hidden")

    def get_monitors(self):
        pass

# ------------------------------------------------------------------------------
