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

import os
import logging
import tkinter

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
            fill=zynthian_gui_config.color_tx,
            text='Output',
            anchor="w"
        )

        self.model_title_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_tx_off,
            text='Model:',
            anchor="w"
        )
        self.model_title_line = self.widget_canvas.create_line(
            0, 0, 0, 0,
            width=1,
            fill=zynthian_gui_config.color_tx_off
        )
        self.model_file_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_tx,
            text='',
            width=0,
            anchor="nw"
        )
        self.cabinet_title_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_tx_off,
            text='Cabinet:',
            anchor="w"
        )
        self.cabinet_title_line = self.widget_canvas.create_line(
            0, 0, 0, 0,
            width=1,
            fill=zynthian_gui_config.color_tx_off
        )
        self.cabinet_file_label = self.widget_canvas.create_text(
            0, 0,
            fill=zynthian_gui_config.color_tx,
            text='',
            width=0,
            anchor="nw"
        )

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)

        self.bar_width = round(0.9 * self.width)
        self.bar_height = round(0.1 * self.height)
        self.x0 = round(0.05 * self.width)
        self.y0 = round(0.15 * self.height)
        fs_title = self.bar_height // 2
        fs_file = self.bar_height // 3

        y0 = self.y0
        y1 = self.y0 + self.bar_height
        self.widget_canvas.coords(self.input_level_bg_low, self.x0, y0,
                                  self.x0 + int(0.7 * self.bar_width), y1)
        self.widget_canvas.coords(self.input_level_bg_mid, self.x0 + int(0.7 * self.bar_width), y0,
                                  self.x0 + int(0.9 * self.bar_width), y1)
        self.widget_canvas.coords(self.input_level_bg_high, self.x0 + int(0.9 * self.bar_width), y0,
                                  self.x0 + self.bar_width, y1)
        self.widget_canvas.coords(self.input_level, self.x0, self.y0, self.x0 + self.bar_width, y1)
        self.widget_canvas.coords(self.input_label, self.x0 + 2, self.y0 + self.bar_height // 2)
        self.widget_canvas.itemconfig(self.input_label, font=(zynthian_gui_config.font_family, fs_title))

        y0 = self.y0 + self.bar_height + 2
        y1 = self.y0 + self.bar_height * 2 + 2
        self.widget_canvas.coords(self.output_level_bg_low, self.x0, y0,
                                  self.x0 + int(0.7 * self.bar_width), y1)
        self.widget_canvas.coords(self.output_level_bg_mid, self.x0 + int(0.7 * self.bar_width), y0,
                                  self.x0 + int(0.9 * self.bar_width), y1)
        self.widget_canvas.coords(self.output_level_bg_high, self.x0 + int(0.9 * self.bar_width), y0,
                                  self.x0 + self.bar_width, y1)
        self.widget_canvas.coords(self.output_level, self.x0, y0, self.x0 + self.bar_width, y1)
        self.widget_canvas.coords(self.output_label, self.x0 + 2, self.y0 + self.bar_height + 2 + self.bar_height // 2)
        self.widget_canvas.itemconfig(self.output_label, font=(zynthian_gui_config.font_family, fs_title))

        y0 = self.y0 + int(3.5 * self.bar_height)
        self.widget_canvas.coords(self.model_title_label, self.x0, y0)
        self.widget_canvas.itemconfig(self.model_title_label, font=(zynthian_gui_config.font_family, fs_title))
        self.widget_canvas.coords(self.model_title_line, self.x0, y0 + self.bar_height // 2,
                                  self.x0 + self.bar_width, y0 + self.bar_height // 2)
        self.widget_canvas.coords(self.model_file_label, self.x0, y0 + int(0.8 * self.bar_height))
        self.widget_canvas.itemconfig(self.model_file_label,
                                      width=self.bar_width,
                                      font=(zynthian_gui_config.font_family, fs_file))

        y0 = self.y0 + 6 * self.bar_height
        self.widget_canvas.coords(self.cabinet_title_label, self.x0, y0)
        self.widget_canvas.itemconfig(self.cabinet_title_label, font=(zynthian_gui_config.font_family, fs_title))
        self.widget_canvas.coords(self.cabinet_title_line, self.x0, y0 + self.bar_height // 2,
                                  self.x0 + self.bar_width, y0 + self.bar_height // 2)
        self.widget_canvas.coords(self.cabinet_file_label, self.x0, y0 + int(0.8 * self.bar_height))
        self.widget_canvas.itemconfig(self.cabinet_file_label,
                                      width=self.bar_width,
                                      font=(zynthian_gui_config.font_family, fs_file))

        self.widget_canvas.grid(row=0, column=0, sticky='news')

    def refresh_gui(self):
        if 'MeterIn' in self.monitors:
            #logging.debug(f"MeterIn: {self.monitors['MeterIn']}, Level in: {self.level_in}")
            if self.monitors['MeterIn'] >= self.level_in:
                self.level_in = self.monitors['MeterIn']
            elif self.level_in:
                self.level_in = max(0.9 * self.level_in, 0)
            x = int(self.x0 + self.bar_width * min(1, self.level_in))
            self.widget_canvas.coords(
                self.input_level, x, self.y0, self.x0 + self.bar_width, self.y0 + self.bar_height)
        if 'MeterOut' in self.monitors:
            #logging.debug(f"MeterOut: {self.monitors['MeterOut']}, Level Out: {self.level_out}")
            if self.monitors['MeterOut'] >= self.level_out:
                self.level_out = self.monitors['MeterOut']
            elif self.level_out:
                self.level_out = max(0.9 * self.level_out, 0)
            x = int(self.x0 + self.bar_width * min(1, self.level_out))
            self.widget_canvas.coords(self.output_level, x, self.y0 + self.bar_height + 2,
                                      self.x0 + self.bar_width, self.y0 + self.bar_height * 2 + 2)
        if 'ModelInSize' in self.monitors:
            pass

        if "json" in self.processor.controllers_dict:
            parts = os.path.split(self.processor.controllers_dict["json"].value)
            fname = parts[1]
            self.widget_canvas.itemconfig(self.model_file_label, text=fname)
        if "cabinet" in self.processor.controllers_dict:
            parts = os.path.split(self.processor.controllers_dict["cabinet"].value)
            fname = parts[1]
            self.widget_canvas.itemconfig(self.cabinet_file_label, text=fname)

# ------------------------------------------------------------------------------
