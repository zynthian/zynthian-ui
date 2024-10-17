#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for "AidaX" neural emulator plugin
#
# Copyright (C) 2015-2024 Brian Walton <riban@zynthian.org>
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
# Zynthian Widget Class for "AidaX" neural emulator plugin
# ------------------------------------------------------------------------------


class zynthian_widget_aidax(zynthian_widget_base.zynthian_widget_base):

    def __init__(self, parent):
        super().__init__(parent)

        # Geometry vars set accurately during resize
        self.bar_width = 1
        self.bar_height = 1
        self.x0 = 0
        self.y0 = 0
        self.level_in = 0.0
        self.level_out = 0.0

        self.widget_canvas = tkinter.Canvas(self,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        # Create custom GUI elements (position and size set when canvas is grid and size applied)

        self.input_level_bg_low = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="green")
        self.input_level_bg_mid = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="yellow")
        self.input_level_bg_high = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="red")
        self.input_level = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="grey")
        self.input_label = self.widget_canvas.create_text(
            0, 0,
            fill="white",
            text='Input',
            anchor="w"
        )

        self.output_level_bg_low = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="green")
        self.output_level_bg_mid = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="yellow")
        self.output_level_bg_high = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="red")
        self.output_level = self.widget_canvas.create_rectangle(
            0, 0, 0, 0,
            fill="grey")
        self.output_label = self.widget_canvas.create_text(
            0, 0,
            fill="white",
            text='Output',
            anchor="w"
        )

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)

        self.bar_width = round(0.8 * self.width)
        self.bar_height = round(0.1 * self.height)
        self.x0 = round(0.1 * self.width)
        self.y0 = round(0.2 * self.height)

        self.widget_canvas.coords(self.input_level_bg_low, self.x0, self.y0,
                                  self.x0 + int(0.7 * self.bar_width), self.y0 + self.bar_height)
        self.widget_canvas.coords(self.input_level_bg_mid, self.x0 + int(0.7 * self.bar_width),
                                  self.y0, self.x0 + int(0.9 * self.bar_width), self.y0 + self.bar_height)
        self.widget_canvas.coords(self.input_level_bg_high, self.x0 + int(
            0.9 * self.bar_width), self.y0, self.x0 + self.bar_width, self.y0 + self.bar_height)
        self.widget_canvas.coords(self.input_level, self.x0, self.y0,
                                  self.x0 + self.bar_width, self.y0 + self.bar_height)
        self.widget_canvas.coords(
            self.input_label, self.x0 + 2, self.y0 + self.bar_height // 2)
        self.widget_canvas.itemconfig(self.input_label, font=(
            zynthian_gui_config.font_family, self.bar_height // 2))

        self.widget_canvas.coords(self.output_level_bg_low, self.x0, self.y0 + self.bar_height + 2,
                                  self.x0 + int(0.7 * self.bar_width), self.y0 + self.bar_height * 2 + 2)
        self.widget_canvas.coords(self.output_level_bg_mid, self.x0 + int(0.7 * self.bar_width), self.y0 +
                                  self.bar_height + 2, self.x0 + int(0.9 * self.bar_width), self.y0 + self.bar_height * 2 + 2)
        self.widget_canvas.coords(self.output_level_bg_high, self.x0 + int(0.9 * self.bar_width),
                                  self.y0 + self.bar_height + 2, self.x0 + self.bar_width, self.y0 + self.bar_height * 2 + 2)
        self.widget_canvas.coords(self.output_level, self.x0, self.y0 + self.bar_height + 2,
                                  self.x0 + self.bar_width, self.y0 + self.bar_height * 2 + 2)
        self.widget_canvas.coords(
            self.output_label, self.x0 + 2, self.y0 + self.bar_height + 2 + self.bar_height // 2)
        self.widget_canvas.itemconfig(self.output_label, font=(
            zynthian_gui_config.font_family, self.bar_height // 2))

        self.widget_canvas.grid(row=0, column=0, sticky='news')

    def refresh_gui(self):
        if 'MeterIn' in self.monitors:
            if self.monitors['MeterIn'] >= self.level_in:
                self.level_in = self.monitors['MeterIn']
            elif self.level_in:
                self.level_in = max(self.level_in - 0.1 * self.level_in, 0)
            x = int(self.x0 + self.bar_width * min(1, self.level_in))
            self.widget_canvas.coords(
                self.input_level, x, self.y0, self.x0 + self.bar_width, self.y0 + self.bar_height)
        if 'MeterOut' in self.monitors:
            if self.monitors['MeterOut'] >= self.level_out:
                self.level_out = self.monitors['MeterOut']
            elif self.level_out:
                self.level_out = max(self.level_out - 0.1 * self.level_out, 0)
            x = int(self.x0 + self.bar_width * min(1, self.level_out))
            self.widget_canvas.coords(self.output_level, x, self.y0 + self.bar_height + 2,
                                      self.x0 + self.bar_width, self.y0 + self.bar_height * 2 + 2)
        if 'ModelInSize' in self.monitors:
            pass

# ------------------------------------------------------------------------------
