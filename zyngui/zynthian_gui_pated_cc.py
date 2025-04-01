#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pattern Editor Base Class
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

import os
import tkinter
import logging
import tkinter.font as tkfont

# Zynthian specific modules
from zynlibs.zynseq import zynseq
from zynlibs.zynsmf import zynsmf
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_pated_base import *

# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern CC Editor GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_pated_cc(zynthian_gui_pated_base):

    DEFAULT_VIEW_STEPS = 16
    DEFAULT_VIEW_ROWS = 128

    # Function to initialise class
    def __init__(self):
        self.cc_num = 64
        self.row0 = 8
        super().__init__()

    # Function to get name of this view
    def get_name(self):
        return "pattern cc editor"

    def get_title(self):
        title = super().get_title()
        return f"{title}: CC{self.cc_num}"

    # Function to enable edit mode => It *MUST* be redefined in child class
    #   mode: Edit mode to enable [EDIT_MODE_NONE | others to define in child classes]
    def set_edit_mode(self, mode):
        super().set_edit_mode(mode)

    # -------------------------------------------------------------------------
    # Pattern menu
    # -------------------------------------------------------------------------

    def get_menu_options(self):
        return super().get_menu_options()

    def menu_cb(self, option, params):
        super().menu_cb()

    # -------------------------------------------------------------------------
    # Pattern management
    # -------------------------------------------------------------------------

    # Function to load new pattern
    # index: Pattern index
    def load_pattern(self, index):
        super().load_pattern(index)

    # -------------------------------------------------------------------------
    # Controller callback
    # -------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        super().send_controller_value(zctrl)

    # -------------------------------------------------------------------------
    # Touch event management
    # -------------------------------------------------------------------------

    # Function to handle grid mouse down
    # event: Mouse event
    def on_grid_press(self, event):
        pass

    # Function to handle grid mouse drag
    # event: Mouse event
    def on_grid_drag(self, event):
        pass

    # Function to handle grid mouse release
    # event: Mouse event
    def on_grid_release(self, event):
        pass

    def on_gesture(self, gtype, value):
        pass

    def swipe_vertical_action(self):
        pass

    # Function to toggle event
    # step: step number (column)
    # row: keymap index
    # Returns: Event number if note added else None
    def toggle_event(self, step, row):
        pass

    # Function to remove an event
    # step: step number (column)
    # row: keymap index
    def remove_event(self, step, row):
        pass

    # -------------------------------------------------------------------------
    # Geometry management
    # -------------------------------------------------------------------------

    def get_pianoroll_num_cells(self):
        return 128

    def calculate_geometry_limits(self):
        # Row height limits
        self.max_row_height = self.grid_height // 6
        self.min_row_height = self.grid_height // 128

        # Step width limits
        self.max_step_width = self.grid_width // 8
        self.min_step_width = self.grid_width // 64
        try:
            self.min_step_width = max(self.min_step_width, self.grid_width // self.n_steps)
        except:
            pass

    # Function to get cell coordinates
    # col: Column number (step)
    # row: Row number (keymap index)
    # duration: Duration of cell in steps
    # offset: Factor to offset start of note
    # return: Coordinates required to draw cell
    def get_cell(self, col, row, duration, offset):
        x1 = int((col + offset) * self.step_width) + 1
        y1 = self.grid_height - (self.row0 + row + 1) * self.row_height + 1
        x2 = x1 + int(self.step_width * duration) - 1
        y2 = y1 + self.row_height - 1
        return [x1, y1, x2, y2]

    # -------------------------------------------------------------------------
    # Drawing functions
    # -------------------------------------------------------------------------

    def redraw_grid_pending(self, redraw_pending):
        super().redraw_grid_pending(redraw_pending)
        if redraw_pending > 1:
            self.piano_roll.delete("valtick")
            self.grid_canvas.delete("gridhline")

            if redraw_pending > 2:
                row_min = 0
                row_max = 129
            else:
                row_min = self.selected_cell[1]
                row_max = self.selected_cell[1]

            grid_font = tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=self.row_height * 4)
            for row in range(row_min, row_max):
                if row % 8 == 0:
                    ypos = self.grid_height - (self.row0 + row) * self.row_height
                    self.piano_roll.create_text(self.piano_roll_width - 2, ypos - 0.5 * self.row_height, text=str(row), font=grid_font, anchor="e", fill="white", tags="valtick")
                    self.grid_canvas.create_line(0, ypos, self.total_width, ypos, fill=GRID_LINE_WEAK, tags="gridhline")
                # Draw row of note cells
                if row < 128:
                    #self.draw_row(row, True)
                    pass

            # Set z-order to allow duration to show
            if redraw_pending > 2:
                for step in range(self.n_steps):
                    self.grid_canvas.tag_lower(f"step{step}")

    # Function to draw pianoroll content
    def draw_pianoroll(self):
        self.piano_roll.delete(tkinter.ALL)
        pass

    # Function to draw a grid cell
    # step: Step (column) index
    # row: Index of row
    # white: True for white notes
    def draw_cell(self, step, row, white=None):
        pass

    # Function to update selectedCell
    # step: Step (column) of selected cell (Optional - default to reselect current column)
    # row: Index of keymap to select (Optional - default to reselect current row).
    #      Maybe outside visible range to scroll display
    def select_cell(self, step=None, row=None):
        super().select_cell(step, row)

    # -------------------------------------------------------------------------
    # Event management
    # -------------------------------------------------------------------------

    # Function to refresh status
    def refresh_status(self):
        super().refresh_status()

    def set_edit_title(self):
        super().set_edit_title()

    # Function to handle zynpots value change
    #   i: Zynpot index [0..n]
    #   dval: Current value of zyncoder
    def zynpot_cb(self, i, dval):
        if super().zynpot_cb(i, dval):
            return
        if i == self.ctrl_order[0]:
            self.cc_num += dval
            if self.cc_num < 1:
                self.cc_num = 1
            elif self.cc_num > 127:
                self.cc_num = 127
            self.set_title()
            return True
        elif i == self.ctrl_order[2]:
            self.select_cell(None, self.selected_cell[1] - dval)
        elif i == self.ctrl_order[3]:
            self.select_cell(self.selected_cell[0] + dval, None)

# ------------------------------------------------------------------------------
