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

    # Function to initialise class
    def __init__(self):
        self.cc_num = 64
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
    # Controller callback
    # -------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        super().send_controler_value(zctrl)

    # -------------------------------------------------------------------------
    # Touch management
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

    def get_pianoroll_num_cells(self):
        return 128

    def redraw_grid_pending(self, redraw_pending):
        pass

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

    # Function to load new pattern
    # index: Pattern index
    def load_pattern(self, index):
        super().load_pattern(index)

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
            logging.debug(f"CC NUM => {self.cc_num}")
            return True

# ------------------------------------------------------------------------------
