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
from zyngui.zynthian_gui_base import zynthian_gui_base

# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern CC Editor GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_pated_cc(zynthian_gui_pated_base):

    DEFAULT_VIEW_STEPS = 16
    DEFAULT_VIEW_ROWS = 128

    # Function to initialise class
    def __init__(self):
        self.row0 = 8
        self.cc_num = 64
        self.interpolateCC = True
        self.marker_width = 5
        super().__init__()
        self.marker_width = self.width // 150

    # Function to get name of this view
    def get_name(self):
        return "pattern cc editor"

    def get_title(self):
        title = f"{super().get_title()}: CC{self.cc_num}"
        # Get CC title from zynstep mapped zctrl
        midi_chan = self.zynseq.libseq.getChannel(self.zynseq.scene, self.phrase, self.sequence, 0)
        zctrl = self.zyngui.chain_manager.get_zynstep_mapped_zctrl(midi_chan, self.cc_num)
        if zctrl:
            title = f"{title} ({zctrl.name})"
        return title

    def set_edit_mode(self, mode):
        # Currently EDIT modes disabled in CC editor
        if mode in (EDIT_MODE_SINGLE, EDIT_MODE_ALL):
            mode = EDIT_MODE_NONE
        super().set_edit_mode(mode)

    def set_edit_title(self):
        super().set_edit_title()

    # -------------------------------------------------------------------------
    # Pattern menu
    # -------------------------------------------------------------------------

    def get_menu_options(self):
        menu_options = super().get_menu_options()
        # Pattern Options
        options = {}
        if self.interpolateCC:
            options[f"\u2612 Interpolate CC{self.cc_num} values"] = 'Interpolate CC OFF'
        else:
            options[f"\u2610 Interpolate CC{self.cc_num} values"] = 'Interpolate CC ON'
        menu_options['PATTERN'].update(options)
        # Pattern Edit
        options = {}
        options[f"Clear pattern CC{self.cc_num}"] = 'Clear pattern CC'
        menu_options['EDIT'].update(options)
        return menu_options

    def menu_cb(self, option, params):
        self.save_last_menu_option()
        match params:
            case 'Interpolate CC OFF':
                self.zynseq.libseq.setInterpolateCC(self.cc_num, False)
                self.interpolateCC = False
                self.redraw_pending = 2
            case 'Interpolate CC ON':
                self.zynseq.libseq.setInterpolateCC(self.cc_num, True)
                self.interpolateCC = True
                self.redraw_pending = 2
            case 'Clear pattern CC':
                self.clear_pattern_cc()
            case _:
                super().menu_cb(option, params)

    def send_controller_value(self, zctrl):
        super().send_controller_value(zctrl)

    # -------------------------------------------------------------------------
    # Pattern management
    # -------------------------------------------------------------------------

    # Function to load new pattern
    # index: Pattern index
    def load_pattern(self, index):
        super().load_pattern(index)
        self.interpolateCC = self.zynseq.libseq.getInterpolateCC(self.cc_num)

    # Function to clear CC events on pattern
    def clear_pattern_cc(self, params=None):
        self.zyngui.show_confirm(f"Clear CC{self.cc_num} in pattern {self.pattern}?", self.do_clear_pattern_cc)

    # Function to actually clear CC events
    def do_clear_pattern_cc(self, params=None):
        self.save_pattern_snapshot(now=True, force=False)
        self.zynseq.libseq.clearControl(self.cc_num)
        self.save_pattern_snapshot(now=True, force=True)
        self.select_cell()

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
        if self.param_editor_zctrl:
            self.disable_param_editor()

        # Get cell coordinates
        row = int((self.total_height - self.grid_canvas.canvasy(event.y)) / self.row_height)
        step = int(self.grid_canvas.canvasx(event.x) / self.step_width)

        # If there is no CC point, add a new CC point
        val = self.get_cc_value(step)
        if val is None:
            self.zynseq.libseq.addControl(step, self.cc_num, row, row, 1, 0)
        # else, change CC value
        else:
            self.zynseq.libseq.setControlValue(step, self.cc_num, row, row)

        # Select the cell
        self.select_cell(step, row)

        # Start drag state variables
        self.swiping = False
        self.grid_drag_start = event
        self.grid_drag_count = 0
        self.swipe_step_speed = 0
        self.swipe_row_speed = 0
        self.swipe_step_dir = 0
        self.swipe_row_dir = 0

    # Function to handle grid mouse drag
    # event: Mouse event
    def on_grid_drag(self, event):
        # Get cell coordinates
        row = int((self.total_height - self.grid_canvas.canvasy(event.y)) / self.row_height)
        step = int(self.grid_canvas.canvasx(event.x) / self.step_width)

        # If there is no CC point, add a new CC point
        val = self.get_cc_value(step)
        if val is None:
            self.zynseq.libseq.addControl(step, self.cc_num, row, row, 1, 0)
        # else, change CC value
        else:
            self.zynseq.libseq.setControlValue(step, self.cc_num, row, row)

        # Select the cell
        self.select_cell(step, row)

    # Function to handle grid mouse release
    # event: Mouse event
    def on_grid_release(self, event):
        pass

    def on_gesture(self, gtype, value):
        pass

    # -------------------------------------------------------------------------
    # Geometry management
    # -------------------------------------------------------------------------

    def get_pianoroll_num_cells(self):
        return 128

    def calculate_geometry_limits(self):
        # Row height limits
        self.max_row_height = self.grid_height // 128
        self.min_row_height = self.grid_height // 128

        # Step width limits
        self.max_step_width = self.grid_width // 16
        self.min_step_width = self.grid_width // 128
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
    def get_cell(self, col, row, duration, offset, height=1):
        x1 = int((col + offset) * self.step_width) + 1
        y1 = self.grid_height - (self.row0 + row + 1) * self.row_height + 1
        x2 = x1 + int(self.step_width * duration) - 1
        y2 = y1 + height * self.row_height - 1
        return [x1, y1, x2, y2]

    def get_cc_value(self, step):
        val = self.zynseq.libseq.getControlValue(step, self.cc_num)
        if val <= 127:
            return val
        else:
            return None

    # -------------------------------------------------------------------------
    # Drawing functions
    # -------------------------------------------------------------------------

    def redraw_grid_pending(self):
        super().redraw_grid_pending()

        if self.redraw_pending > 1:
            if self.redraw_pending > 3:
                self.piano_roll.delete("valtick")
                self.grid_canvas.delete("gridhline")
                grid_font = tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=self.row_height * 4)
                for row in range(0, 129):
                    if row % 8 == 0:
                        ypos = self.grid_height - (self.row0 + row) * self.row_height
                        self.piano_roll.create_text(self.piano_roll_width - 2, ypos - 0.5 * self.row_height, text=str(row), font=grid_font, anchor="e", fill="white", tags="valtick")
                        self.grid_canvas.create_line(0, ypos, self.total_width, ypos, fill=GRID_LINE_WEAK, tags=("gridhline"))

            self.grid_canvas.delete("ccevent")
            for step in range(0, self.n_steps + 1):
                val = self.get_cc_value(step)
                if val is not None:
                    self.draw_cell(step, val)

    # Function to draw pianoroll content
    def draw_pianoroll(self):
        #self.piano_roll.delete(tkinter.ALL)
        pass

    # Function to draw a grid cell
    # step: Step (column) index
    # row: Index of row
    def draw_cell(self, step, row):
        duration = self.zynseq.libseq.getControlDuration(step, self.cc_num)
        offset = self.zynseq.libseq.getControlOffset(step, self.cc_num)
        val2 = self.zynseq.libseq.getControlValueEnd(step, self.cc_num)
        coord = self.get_cell(step, row, duration, offset, row - val2)
        self.grid_canvas.create_line(coord, fill="white", width=2, tags=("ccevent", f"step{step}"))
        if self.interpolateCC:
            coord[2] = coord[0] + self.marker_width
            coord[3] = coord[1] + self.marker_width
            coord[0] -= self.marker_width
            coord[1] -= self.marker_width
            self.grid_canvas.create_rectangle(coord, fill="white", width=0, tags=("ccevent", f"step{step}"))

    # Function to update selectedCell
    # step: Step (column) of selected cell (Optional - default to reselect current column)
    # row: Index of keymap to select (Optional - default to reselect current row).
    #      Maybe outside visible range to scroll display
    def select_cell(self, step=None, row=None):
        # Check column boundaries
        if step is None:
            step = self.selected_cell[0]
        if step < 0:
            step = 0
        elif step >= self.n_steps:
            step = self.n_steps - 1
        else:
            step = int(step)
        # Check step offset
        if step >= self.step_offset + int(self.view_steps):
            # Step is off right of display
            self.set_step_offset(step - int(self.view_steps) + 1)
        elif step < self.step_offset:
            # Step is off left of display
            self.set_step_offset(step)
        # Force row value selection if event in this step
        val = self.get_cc_value(step)
        if val is not None:
            offset = self.zynseq.libseq.getControlOffset(step, self.cc_num)
            row = val
        else:
            offset = 0
            # Check row boundaries
            if row is None:
                row = self.selected_cell[1]
            if row < 0:
                row = 0
            elif row >= self.get_pianoroll_num_cells():
                row = self.get_pianoroll_num_cells() - 1
            else:
                row = int(row)
        self.selected_cell = [step, row]

        if self.edit_mode == EDIT_MODE_BLOCK:
            return

        # Hide selected block
        self.hide_selected_block()
        # Position selector cell-frame
        coord = self.get_cell(step, row, 1, offset)
        if self.interpolateCC:
            sw = self.marker_width + 1
            coord[2] = coord[0] + sw
            coord[3] = coord[1] + sw
            coord[0] -= sw
            coord[1] -= sw
        if not self.rect_selected_cell:
            self.rect_selected_cell = self.grid_canvas.create_rectangle(coord, fill=SELECT_BORDER, outline=SELECT_BORDER,
                                                     width=self.select_thickness, tags="selected_cell")
        else:
            self.grid_canvas.coords(self.rect_selected_cell, coord)
        self.grid_canvas.tag_raise(self.rect_selected_cell)


    # ---------------------------------------------------------------
    # Block edit functionality => Copy/paste block
    # ---------------------------------------------------------------

    def copy_block(self, cut=False):
        self.end_select_block()

    def move_block(self, dstep, drow):
        pass

    def paste_block(self):
        pass

    # -------------------------------------------------------------------------
    # Event management
    # -------------------------------------------------------------------------

    # Function to toggle event
    # step: step number (column)
    # row: row index
    # Returns: Event number if event added else None
    def toggle_event(self, step, row):
        val = self.get_cc_value(step)
        if val is None:
            self.zynseq.libseq.addControl(step, self.cc_num, row, row, 1, 0)
            return self.cc_num
        else:
            self.zynseq.libseq.removeControl(step, self.cc_num)
            return None

    # Function to remove an event
    # step: step number (column)
    # row: row index
    def remove_event(self, step, row):
        val = self.get_cc_value(step)
        if val is not None:
            self.zynseq.libseq.removeControl(step, self.cc_num)

    # Function to refresh status
    def refresh_status(self):
        super().refresh_status()

    # Function to handle zynpots value change
    #   i: Zynpot index [0..n]
    #   dval: Current value of zyncoder
    def zynpot_cb(self, i, dval):
        #logging.debug(f"DVAL {i} => {dval}")
        if zynthian_gui_base.zynpot_cb(self, i, dval):
            return True

        if i == self.ctrl_order[0]:
            if self.edit_mode == EDIT_MODE_NONE:
                self.cc_num += dval
                if self.cc_num < 1:
                    self.cc_num = 1
                elif self.cc_num > 127:
                    self.cc_num = 127
                self.set_title()
                self.interpolateCC = self.zynseq.libseq.getInterpolateCC(self.cc_num)
                self.redraw_pending = 2
                return True
        elif i == self.ctrl_order[2]:
            if self.edit_mode == EDIT_MODE_NONE:
                step = self.selected_cell[0]
                val = self.get_cc_value(step)
                # Change value for existing CC event
                if val is not None:
                    newval = val - dval
                    if newval > 127:
                        newval = 127
                    if newval < 0:
                        newval = 0
                    if newval != val:
                        self.zynseq.libseq.setControlValue(step, self.cc_num, newval, newval)
                # Select cell
                self.select_cell(step, self.selected_cell[1] + dval)
                return True

        if super().zynpot_cb(i, dval):
            return True

# ------------------------------------------------------------------------------
