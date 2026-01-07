#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Digital Audio Peak Meters
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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

    def __init__(self, parent, x0, y0, width, height, vertical=True, tags=()):
        """Initialise digital peak meter

        parent : Frame object within which to draw meter
        x0 : X coordinate of top left corner
        y0 : Y coordinate of top left corner
        width : Width of widget
        height : height of widget
        vertical : True for vertical orientation else horizontal orientation
        tags : Optional list of tags for external control of GUI
        fill: Optional background colour (default: None / transparent)
        """

        self.parent = parent
        self.vertical = vertical
        self.tags = tags

        # initial geometry
        self.x0 = x0
        self.y0 = y0
        self.width = width
        self.height = height
        self.x1 = x0 + width
        self.y1 = y0 + height

        # dB constants
        self.overdB = -3
        self.highdB = -10
        self.lowdB = -50
        self.zerodB = -10

        # Colors
        self.low_color = "#00AA00"
        self.low_hold_color = "#00FF00"
        self.high_color = "#CCCC00"
        self.high_hold_color = "#FFFF00"
        self.over_color = "#CC0000"
        self.over_hold_color = "#FF0000"
        self.mono_color = "#DDDDDD"
        self.mono_hold_color = "#FFFFFF"
        self.line_color = "#999999"
        self.bg_color = color_panel_bg

        self.hold_thickness = 1
        self.mono = False

        # ---------------------------------------------
        # Compute bounds for initial position
        # ---------------------------------------------
        coords = self._compute_bounds()

        # ---------------------------------------------
        # Create canvas items
        # ---------------------------------------------
        self.bg_over = parent.create_rectangle(*coords['bg_over'], width=0, fill=self.over_color, tags=tags)
        self.bg_high = parent.create_rectangle(*coords['bg_high'], width=0, fill=self.high_color, tags=tags)
        self.bg_low = parent.create_rectangle(*coords['bg_low'], width=0, fill=self.low_color, tags=tags)
        self.overlay = parent.create_rectangle(*coords['overlay'], width=0, fill=self.bg_color, tags=tags)
        self.hold = parent.create_rectangle(*coords['hold'], width=0, fill=self.low_color, tags=tags, state=HIDDEN)
        self.zero_line = parent.create_line(*coords['line'], fill=self.line_color, tags=tags)

    # --------------------------------------------------
    # Helper to compute bounds
    # --------------------------------------------------
    def _compute_bounds(self):
        """ Compute all item coordinates and thresholds based on current geometry """
        x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
        width, height = self.width, self.height

        if self.vertical:
            self.y_over = int(y0 + height * self.overdB / self.lowdB)
            self.y_high = int(y0 + height * self.highdB / self.lowdB)
            self.y_low = y1
            self.y_zero = int(y0 + height * self.zerodB / self.lowdB)

            coords = {
                'bg_over': (x0, y0, x1, self.y_over),
                'bg_high': (x0, self.y_over, x1, self.y_high),
                'bg_low': (x0, self.y_high, x1, self.y_low),
                'overlay': (x0, y0, x1, y1),
                'hold': (x0, self.y_low, x1, self.y_low),
                'line': (x0, self.y_zero, x1, self.y_zero)
            }

        else:
            self.x_over = int(x1 - width * self.overdB / self.lowdB)
            self.x_high = int(x1 - width * self.highdB / self.lowdB)
            self.x_low = x0
            self.x_zero = int(x1 - width * self.zerodB / self.lowdB)

            coords = {
                'bg_over': (self.x_over, y0, x1, y1),
                'bg_high': (self.x_high, y0, self.x_over, y1),
                'bg_low': (self.x_low, y0, self.x_high, y1),
                'overlay': (x0, y0, x1, y1),
                'hold': (self.x_low, y0, self.x_low, y1),
                'line': (self.x_zero, y0, self.x_zero, y1)
            }

        return coords

    # --------------------------------------------------
    # Move method reuses same computation
    # --------------------------------------------------
    def move(self, x0, y0, width, height):
        """ Move the meter to another part of the screen
        Args:
            x0: New x coordinate
            y0: New y coordinate
            width: New width
            height: New height
        """

        self.x0 = x0
        self.y0 = y0
        self.width = width
        self.height = height
        self.x1 = x0 + width
        self.y1 = y0 + height

        coords = self._compute_bounds()

        self.parent.coords(self.bg_over, *coords['bg_over'])
        self.parent.coords(self.bg_high, *coords['bg_high'])
        self.parent.coords(self.bg_low, *coords['bg_low'])
        self.parent.coords(self.overlay, *coords['overlay'])
        self.parent.coords(self.hold, *coords['hold'])
        self.parent.coords(self.zero_line, *coords['line'])

    def set_enable(self, enable):
        self.enabled = enable

    def refresh(self, dpm, hold, mono):
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
                if self.mono:
                    self.parent.itemconfig(
                        self.hold, state=NORMAL, fill=self.mono_hold_color)
                else:
                    self.parent.itemconfig(
                        self.hold, state=NORMAL, fill=self.low_hold_color)
            else:
                self.parent.itemconfig(self.hold, state=HIDDEN)
