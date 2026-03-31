#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Digital Audio Peak Meters
#
# Copyright (C) 2015-2026 Fernando Moyano <jofemodo@zynthian.org>
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
from PIL import Image, ImageDraw, ImageTk

from zyngui.zynthian_gui_config import color_panel_bg


class zynthian_gui_dpm():

    bg_images = {} # Dict of background images, indexed by (length, width)

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
        self.mono = 0

        # ---------------------------------------------
        # Compute bounds for initial position
        # ---------------------------------------------
        coords = self._compute_bounds()

        # ---------------------------------------------
        # Create canvas items
        # ---------------------------------------------
        self.bg_image = parent.create_image(*coords['bg_image'], anchor="nw", image=self.get_bg(width, height), tags=tags)
        self.bg_mono = parent.create_rectangle(*coords['overlay'], width=0, fill=self.mono_color, state=HIDDEN)
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
                'bg_image': (x0, y0),
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
                'bg_image': (x0, y0),
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

        self.parent.itemconfig(self.bg_image, image=self.get_bg(width, height))
        self.parent.coords(self.bg_image, *coords['bg_image'])
        self.parent.coords(self.bg_mono, *coords['overlay'])
        self.parent.coords(self.overlay, *coords['overlay'])
        self.parent.coords(self.hold, *coords['hold'])
        self.parent.coords(self.zero_line, *coords['line'])

    def set_enable(self, enable):
        self.enabled = enable

    def refresh(self, dpm, hold, mono):
        if mono != self.mono:
            self.mono = mono
            if mono:
                self.parent.itemconfig(self.bg_image, state=HIDDEN)
                self.parent.itemconfig(self.bg_mono, state=NORMAL)
            else:
                self.parent.itemconfig(self.bg_image, state=NORMAL)
                self.parent.itemconfig(self.bg_mono, state=HIDDEN)

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

    def get_bg(self, width, height):
        """ Get the tri-colour background image
        Args:
            width: Width in pixels
            height: Height in pixels
        Returns: Background image
        """

        if (width, height) in self.bg_images:
            return self.bg_images[(width, height)]
        if width > height:
            w = height
            l = width
            vertical = False
        else:
            w = width
            l = height
            vertical = True
        x1 = l * 0.73 # Under (green) start green-yellow gradient
        x2 = l * 0.80 # Start const yellow
        x3 = l * 0.90 # Start yellow-red gradient
        x4 = l * 0.97 # Over (red) start const red

        # Create background image
        img = Image.new("RGB", (width, height), (0, 0, 0))
        pixels = img.load()

        bg_c1 = (0, 150, 0) # Dark green
        bg_c2 = (0, 255, 0) # Green
        bg_c3 = (255, 255, 0) # Yellow
        bg_c4 = (255, 0, 0) # Red

        def lerp(c1, c2, t):
            return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

        for x in range(l):
            if x <= x1:
                # Gradient dark to light green
                t = x / x1
                color = lerp(bg_c1, bg_c2, t)
            elif x < x2:
                # Gradient green to yellow
                t = (x - x1) / (x2 - x1)
                color = lerp(bg_c2, bg_c3, t)
            elif x < x3:
                # Constant yellow
                color = bg_c3
            elif x < x4:
                # Gradient yellow to red
                t = (x - x3) / (x4 - x3)
                color = lerp(bg_c3, bg_c4, t)
            else:
                # Constant red
                color = bg_c4
            for y in range(w):
                if vertical:
                    pixels[y, l - x - 1] = (*color, 255)
                else:
                    pixels[x, y] = (*color, 255)

        self.bg_images[(width, height)] = ImageTk.PhotoImage(img)
        return self.bg_images[(width, height)]