#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Digital Audio Peak Meters
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2023 Brian Walton <brian@riban.co.uk>
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

from tkinter import NORMAL, HIDDEN
from zyngui.zynthian_gui_config import color_panel_bg


class zynthian_gui_dpm():

    def __init__(self, zynmixer, strip, channel, parent, x0, y0, width, height, vertical=True, tags=()):
        """Initialise digital peak meter

        zynmixer : zynmixer engine object		
        strip : Audio mixer strip
        channel : Audio channel (0=A/Left, 1=B/Right)
        parent : Frame object within which to draw meter
        x0 : X coordinate of top left corner
        y0 : Y coordinate of top left corner
        width : Width of widget
        height : height of widget
        vertical : True for vertical orientation else horizontal orientation
        tags : Optional list of tags for external control of GUI
        """

        self.zynmixer = zynmixer
        self.strip = strip  # Audio mixer strip
        self.channel = channel  # Audio channel 0=A, 1=B
        self.parent = parent
        self.x0 = x0
        self.y0 = y0
        self.width = width
        self.height = height
        self.vertical = vertical

        self.overdB = -3
        self.highdB = -10
        self.lowdB = -50
        self.zerodB = -10

        self.mono = False

        self.hold_thickness = 1
        self.low_color = "#00AA00"
        self.low_hold_color = "#00FF00"
        self.high_color = "#CCCC00"  # yellow
        self.high_hold_color = "#FFFF00"
        self.over_color = "#CC0000"
        self.over_hold_color = "#FF0000"
        self.mono_color = "#DDDDDD"
        self.mono_hold_color = "#FFFFFF"
        self.line_color = "#999999"
        self.bg_color = color_panel_bg

        if self.vertical:
            self.x1 = x0 + width
            self.y1 = y0 + height
            self.y_over = int(self.y0 + self.height * self.overdB / self.lowdB)
            self.y_high = int(self.y0 + self.height * self.highdB / self.lowdB)
            self.y_low = y0 + height
            y_zero = int(self.y0 + self.height * self.zerodB / self.lowdB)

            self.bg_over = self.parent.create_rectangle(
                self.x0, self.y0, self.x1, self.y_over, width=0, fill=self.over_color, tags=tags)
            self.bg_high = self.parent.create_rectangle(
                self.x0, self.y_over, self.x1, self.y_high, width=0, fill=self.high_color, tags=tags)
            self.bg_low = self.parent.create_rectangle(
                self.x0, self.y_high, self.x1, self.y_low, width=0, fill=self.low_color, tags=tags)
            self.overlay = self.parent.create_rectangle(
                self.x0, self.y0, self.x1, self.y1, width=0, fill=self.bg_color, tags=tags)
            self.hold = self.parent.create_rectangle(
                self.x0, self.y_low, self.x1, self.y_low, width=0, fill=self.low_color, tags=tags, state=HIDDEN)
            self.parent.create_line(
                self.x0, y_zero, self.x1, y_zero, fill=self.line_color, tags=tags)

        else:
            self.x1 = x0 + width
            self.y1 = y0 + height
            self.x_over = int(self.x1 - self.width * self.overdB / self.lowdB)
            self.x_high = int(self.x1 - self.width * self.highdB / self.lowdB)
            self.x_low = x0
            x_zero = int(self.x1 - self.width * self.zerodB / self.lowdB)

            self.bg_over = self.parent.create_rectangle(
                self.x_over, self.y0, self.x1, self.y1, width=0, fill=self.over_color, tags=tags)
            self.bg_high = self.parent.create_rectangle(
                self.x_high, self.y0, self.x_over, self.y1, width=0, fill=self.high_color, tags=tags)
            self.bg_low = self.parent.create_rectangle(
                self.x_low, self.y0, self.x_high, self.y1, width=0, fill=self.low_color, tags=tags)
            self.overlay = self.parent.create_rectangle(
                self.x0, self.y0, self.x1, self.y1, width=0, fill=self.bg_color, tags=tags)
            self.hold = self.parent.create_rectangle(
                self.x_low, self.y0, self.x_low, self.y1, width=0, fill=self.low_color, tags=tags, state=HIDDEN)
            self.parent.create_line(
                x_zero, self.y0, x_zero, self.y1, fill=self.line_color, tags=tags)

    def set_strip(self, strip):
        """Set the mixer channel strip

        strip : Mixer channel strip
        """
        self.strip = strip

    def refresh(self, dpm, hold, mono):
        if self.strip is None:
            return
        if mono != self.mono:
            self.mono = mono
            if mono:
                self.parent.itemconfig(self.bg_low, fill=self.mono_color)
            else:
                self.parent.itemconfig(self.bg_low, fill=self.low_color)

        if self.vertical:
            y1 = int(self.y0 + self.height * max(dpm, self.lowdB) / self.lowdB)
            self.parent.coords(self.overlay, (self.x0, self.y0, self.x1, y1))
            y1 = int(self.y0 + self.height *
                     max(hold, self.lowdB) / self.lowdB)
            self.parent.coords(
                self.hold, (self.x0, y1, self.x1, y1 + self.hold_thickness))
            if y1 <= self.y_over:
                self.parent.itemconfig(self.hold, state=NORMAL, fill="#FF0000")
            elif y1 <= self.y_high:
                self.parent.itemconfig(self.hold, state=NORMAL, fill="#FFFF00")
            elif y1 < self.y_low:
                if self.mono:
                    self.parent.itemconfig(
                        self.hold, state=NORMAL, fill="#FFFFFF")
                else:
                    self.parent.itemconfig(
                        self.hold, state=NORMAL, fill="#00FF00")
            else:
                self.parent.itemconfig(self.hold, state=HIDDEN)

        else:
            x0 = int(self.width - self.width *
                     max(dpm, self.lowdB) / self.lowdB)
            self.parent.coords(self.overlay, (x0, self.y0, self.x1, self.y1))
            x0 = int(self.width - self.width *
                     max(hold, self.lowdB) / self.lowdB)
            self.parent.coords(
                self.hold, (x0, self.y0, x0 + self.hold_thickness, self.y1))
            if x0 > self.x_over:
                self.parent.itemconfig(
                    self.hold, state=NORMAL, fill=self.over_hold_color)
            elif x0 > self.x_high:
                self.parent.itemconfig(
                    self.hold, state=NORMAL, fill=self.high_hold_color)
            elif x0 > self.x_low:
                if self.zynmixer.get_mono(self.strip):
                    self.parent.itemconfig(
                        self.hold, state=NORMAL, fill=self.mono_hold_color)
                else:
                    self.parent.itemconfig(
                        self.hold, state=NORMAL, fill=self.low_hold_color)
            else:
                self.parent.itemconfig(self.hold, state=HIDDEN)
