#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Widget Class for 1/3 Octave Spectrum Meter
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
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
# Zynthian Widget Class for "1/3 Octave Display Spectrum"
# ------------------------------------------------------------------------------


class zynthian_widget_spectr30(zynthian_widget_base.zynthian_widget_base):

    band_freqs = [25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
                  1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]

    band_labels = ["25", "31.5", "40", "50", "63", "80", "100", "125", "160", "200", "250", "315", "400", "500", "630", "800",
                   "1K", "1.25K", "1.6K", "2K", "2.5K", "3.15K", "4K", "5K", "6.3K", "8K", "10K", "12.5K", "16K", "20K"]

    def __init__(self, parent):
        super().__init__(parent)

        self.n_bands = len(self.band_freqs)
        self.mon_bars = []
        self.mon_ticks = []
        self.mon_labels = []

        # Geometry vars - set accurately by sizer
        self.bar_width = 1
        self.tick_height = 1
        self.padx = 1
        self.font_labels = ("monoid", 8)

        self.widget_canvas = tkinter.Canvas(self,
                                            bd=0,
                                            highlightthickness=0,
                                            relief='flat',
                                            bg=zynthian_gui_config.color_bg)
        self.widget_canvas.grid(sticky='news')

        # Create custom GUI elements: bars & ticks
        for i in range(self.n_bands):
            self.mon_bars.append(self.widget_canvas.create_rectangle(
                0, 0, 0, 0, fill=zynthian_gui_config.color_hl))
            self.mon_ticks.append(self.widget_canvas.create_rectangle(
                0, 0, 0, 0, fill=zynthian_gui_config.color_on))
            self.mon_labels.append(self.widget_canvas.create_text(
                0, 0,
                fill=zynthian_gui_config.color_tx,
                text=self.band_labels[i],
                angle=90,
                anchor="nw",
                font=self.font_labels))

    def on_size(self, event):
        if event.width == self.width and event.height == self.height:
            return
        super().on_size(event)
        self.widget_canvas.configure(width=self.width, height=self.height)

        # Geometry vars
        if self.wide:
            w = self.width
        else:
            w = self.width + 2
        self.bar_width = int(w / self.n_bands)
        self.tick_height = int(self.height / 80)
        self.padx = int((w % self.n_bands) / 2)
        self.font_labels_size = int(0.55 * self.bar_width)
        self.font_labels = ("monoid", self.font_labels_size)
        fpad = self.font_labels_size // 4
        x = self.padx + fpad
        for i in range(self.n_bands):
            self.widget_canvas.itemconfig(
                self.mon_labels[i], font=self.font_labels)
            self.widget_canvas.coords(
                self.mon_labels[i], x, self.height - fpad)
            x += self.bar_width

    def refresh_gui(self):
        try:
            scale = (
                12.0 + self.processor.controllers_dict['UIgain'].value) / 12.0
        except:
            scale = 1.0

        i = 0
        x0 = self.padx
        for freq in self.band_freqs:
            try:
                bar_y = int(
                    scale * (100 + self.monitors["band{}".format(freq)]) * self.height / 100)
            except:
                bar_y = 0
            try:
                tick_y = int(
                    scale * (100 + self.monitors["max{}".format(freq)]) * self.height / 100)
            except:
                tick_y = 0

            # logging.debug("FREQ {} => {}, {}".format(freq, bar_y, tick_y))
            self.widget_canvas.coords(
                self.mon_bars[i], x0, self.height, x0 + self.bar_width, self.height - bar_y)
            self.widget_canvas.coords(
                self.mon_ticks[i], x0, self.height - tick_y, x0 + self.bar_width, self.height - tick_y - self.tick_height)

            x0 += self.bar_width
            i += 1

# ------------------------------------------------------------------------------
