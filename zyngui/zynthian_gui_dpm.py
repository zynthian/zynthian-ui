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

import logging
from time import monotonic
from PIL import Image, ImageTk
from tkinter import NORMAL, HIDDEN, TclError

from zyngui.zynthian_gui_config import color_panel_bg, dpm_range_db, dpm_zero_db


# Range and reference are configurable (see zynthian_gui_config). Range must match the value used by the zynmixer lib
DPM_RANGE_DB = dpm_range_db # Span of meter scale below 0dBFS. Default 60
DPM_ZERO_DB = dpm_zero_db # "0dB" reference level. Default -18, the EBU standard
DPM_HIGH_DB = DPM_ZERO_DB # Level (dB) above which meter is yellow, i.e. the "0dB" reference
DPM_OVER_DB = -2.0 # Level (dB) above which meter is red. Not configurable
DPM_OVER_HOLD_S = 4.0 # Time to hold peak indication


def db_to_norm(db):
    """Convert a level in dBFS to a normalised meter position

    The meter scale is linear in dB over DPM_RANGE_DB.
    Returns: 0.0 (DPM_RANGE_DB below full scale or lower) .. 1.0 (0dBFS or above)
    """

    # Match logCurve() in zynmixer lib
    return max(0.0, min(1.0, 1.0 + db / DPM_RANGE_DB))


def run_script(widget, script):
    """Run a Tcl script.
    Optimisation abstraction reduces the quantity of tk.eval() calls.

    widget : Any Tk widget (used to reach the Tcl interpreter)
    script : Tcl script. Does nothing if empty
    Note: Call from the Tk main thread. tkinter marshals calls made from other threads to the main thread and waits for each one
    """

    if not script:
        return
    try:
        widget.tk.eval(script)
    except TclError as e:
        logging.warning(f"DPM update failed: {e}")


class zynthian_gui_dpm():

    bg_images = {} # Dict of background images, indexed by (width, length)

    def __init__(self, parent, x0, y0, width, height, vertical=True, tags=(), main=False):
        """Initialise digital peak meter

        parent : Frame object within which to draw meter
        x0 : X coordinate of top left corner
        y0 : Y coordinate of top left corner
        width : Width of widget
        height : height of widget
        vertical : True for vertical orientation else horizontal orientation
        tags : Optional list of tags for external control of GUI
        main: True if main chain (0) [Default: False]
        """

        self.parent = parent
        self.vertical = vertical
        self.tags = tags
        self.main = main

        # initial geometry
        self.x0 = x0
        self.y0 = y0
        self.width = width
        self.height = height
        self.x1 = x0 + width
        self.y1 = y0 + height

        # dB constants
        self.overdB = DPM_OVER_DB
        self.highdB = DPM_HIGH_DB
        self.zerodB = DPM_ZERO_DB

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
        self.bg_color = "#222222" #color_panel_bg

        self.hold_thickness = 1
        self.mono = 0
        self.over_visible = False
        self.over_ts = 0.0

        self._tcl_path = str(parent)
        self._hold_state = HIDDEN
        self._hold_fill = self.low_color
        self._overlay_pos = None
        self._hold_pos = None

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
        if self.main:
            self.over_indicator = parent.create_rectangle(*coords['over'], width=0, fill="#FF0000", state=HIDDEN)

    # --------------------------------------------------
    # Helper to compute bounds
    # --------------------------------------------------
    def _compute_bounds(self):
        """ Compute all item coordinates and thresholds based on current geometry """
        x0, y0, x1, y1 = self.x0, self.y0, self.x1, self.y1
        width, height = self.width, self.height

        if self.vertical:
            self.y_over = int(y1 - height * db_to_norm(self.overdB))
            self.y_high = int(y1 - height * db_to_norm(self.highdB))
            self.y_low = y1
            self.y_zero = int(y1 - height * db_to_norm(self.zerodB))

            coords = {
                'bg_image': (x0, y0),
                'overlay': (x0, y0, x1, y1),
                'hold': (x0, self.y_low, x1, self.y_low),
                'line': (x0, self.y_zero, x1, self.y_zero),
                'over': (x0, y0, x1, y0 + int(height * 0.02))
            }

        else:
            self.x_over = int(x0 + width * db_to_norm(self.overdB))
            self.x_high = int(x0 + width * db_to_norm(self.highdB))
            self.x_low = x0
            self.x_zero = int(x0 + width * db_to_norm(self.zerodB))

            coords = {
                'bg_image': (x0, y0),
                'overlay': (x0, y0, x1, y1),
                'hold': (self.x_low, y0, self.x_low, y1),
                'line': (self.x_zero, y0, self.x_zero, y1),
                'over': (x1 - int(width * 0.05), y0, x1, y1)
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
        if self.main:
            self.parent.coords(self.over_indicator, *coords['over'])

        # Items have been repositioned so force overlay and hold to be redrawn on next refresh
        self._overlay_pos = None
        self._hold_pos = None

    def set_enable(self, enable):
        self.enabled = enable

    def get_script(self, dpm, hold, mono):
        """ Build a Tcl script that updates the meter, containing commands only for items that have changed.
        Optimisation abstraction reduces the quantity of tk.eval() methods.

        dpm : Normalised level, inverted (1.0 = silence .. 0.0 = full scale), as returned by zynmixer
        hold : Normalised peak hold level, same scale as dpm
        mono : True if channel is mono
        Returns : Tcl script, or empty string if nothing needs to be drawn
        Note: The script is not run here so that scripts from several meters can be batched into one call into Tcl, see run_script()
        """

        cmds = []
        path = self._tcl_path

        if mono != self.mono:
            self.mono = mono
            if mono:
                cmds.append(f"{path} itemconfigure {self.bg_image} -state {HIDDEN}")
                cmds.append(f"{path} itemconfigure {self.bg_mono} -state {NORMAL}")
            else:
                cmds.append(f"{path} itemconfigure {self.bg_image} -state {NORMAL}")
                cmds.append(f"{path} itemconfigure {self.bg_mono} -state {HIDDEN}")

        if self.vertical:
            pos = int(self.y0 + self.height * dpm)
            if pos != self._overlay_pos:
                self._overlay_pos = pos
                cmds.append(f"{path} coords {self.overlay} {self.x0} {self.y0} {self.x1} {pos}")
            hold_pos = int(self.y0 + self.height * hold)
            if pos - hold_pos <= self.hold_thickness:
                state, fill = HIDDEN, None
            else:
                if hold_pos != self._hold_pos:
                    self._hold_pos = hold_pos
                    cmds.append(f"{path} coords {self.hold} {self.x0} {hold_pos} {self.x1} {hold_pos + self.hold_thickness}")
                if hold_pos <= self.y_over:
                    state, fill = NORMAL, self.over_hold_color
                elif hold_pos <= self.y_high:
                    state, fill = NORMAL, self.high_hold_color
                elif hold_pos < self.y_low:
                    state, fill = NORMAL, self.mono_color if self.mono else self.low_hold_color
                else:
                    state, fill = HIDDEN, None
        else:
            pos = int(self.x1 - self.width * dpm)
            if pos != self._overlay_pos:
                self._overlay_pos = pos
                cmds.append(f"{path} coords {self.overlay} {pos} {self.y0} {self.x1} {self.y1}")
            hold_pos = int(self.x1 - self.width * hold)
            if hold_pos - pos <= self.hold_thickness:
                state, fill = HIDDEN, None
            else:
                if hold_pos != self._hold_pos:
                    self._hold_pos = hold_pos
                    cmds.append(f"{path} coords {self.hold} {hold_pos} {self.y0} {hold_pos + self.hold_thickness} {self.y1}")
                if hold_pos > self.x_over:
                    state, fill = NORMAL, self.over_hold_color
                elif hold_pos > self.x_high:
                    state, fill = NORMAL, self.high_hold_color
                elif hold_pos > self.x_low:
                    state, fill = NORMAL, self.mono_hold_color if self.mono else self.low_hold_color
                else:
                    state, fill = HIDDEN, None

        if state == HIDDEN:
            if self._hold_state != HIDDEN:
                self._hold_state = HIDDEN
                cmds.append(f"{path} itemconfigure {self.hold} -state {HIDDEN}")
        elif state != self._hold_state or fill != self._hold_fill:
            self._hold_state = state
            self._hold_fill = fill
            cmds.append(f"{path} itemconfigure {self.hold} -state {NORMAL} -fill {fill}")

        if self.main:
            if dpm <= 0.0:
                self.over_ts = monotonic()
                if not self.over_visible:
                    self.over_visible = True
                    cmds.append(f"{path} itemconfigure {self.over_indicator} -state {NORMAL}")
            elif self.over_visible and monotonic() - self.over_ts >= DPM_OVER_HOLD_S:
                self.over_visible = False
                cmds.append(f"{path} itemconfigure {self.over_indicator} -state {HIDDEN}")

        return "\n".join(cmds)

    def refresh(self, dpm, hold, mono):
        """Update this meter immediately. See get_script() for parameters

        Note: Prefer get_script() and run_script() which optimises for multiple DPM objects
        """

        run_script(self.parent, self.get_script(dpm, hold, mono))

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
        x1 = l * db_to_norm(self.highdB - 4) # Under (green) start green-yellow gradient
        x2 = l * db_to_norm(self.highdB) # Start const yellow
        x3 = max(x2, l * db_to_norm(self.overdB - 6)) # Start yellow-red gradient
        x4 = l * db_to_norm(self.overdB) # Over - start const red

        # Create background image
        img = Image.new("RGB", (width, height), (0, 0, 0))
        pixels = img.load()

        bg_c1 = (0, 150, 0) # Dark green
        bg_c2 = (0, 255, 0) # Green
        bg_c3 = (255, 255, 0) # Yellow
        bg_c4 = (200, 0, 0) # Red

        def lerp(c1, c2, t):
            return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

        for x in range(l):
            if x <= x1:
                # Gradient dark to light green
                t = x / x1 if x1 else 0.0
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
