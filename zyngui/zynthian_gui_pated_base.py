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
from queue import Queue
from datetime import datetime
import tkinter.font as tkfont

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zynlibs.zynsmf import zynsmf
from zyngui import zynthian_gui_base
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------

# Local constants
SELECT_BORDER = zynthian_gui_config.color_on
PLAYHEAD_CURSOR = zynthian_gui_config.color_on
CANVAS_BACKGROUND = zynthian_gui_config.color_panel_bd
GRID_LINE_WEAK = zynthian_gui_config.color_panel_bg
GRID_LINE_STRONG = zynthian_gui_config.color_tx_off
PLAYHEAD_BACKGROUND = zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bd, 40)
PLAYHEAD_LINE = zynthian_gui_config.color_tx_off
PLAYHEAD_HEIGHT = 12
CONFIG_ROOT = "/zynthian/zynthian-data/zynseq"

DRAG_SENSIBILITY = 1.5
SAVE_SNAPSHOT_DELAY = 10

EDIT_MODE_NONE = 0  # Edit mode disabled
EDIT_MODE_SINGLE = 1  # Edit mode enabled for selected note
EDIT_MODE_ALL = 2  # Edit mode enabled for all notes
EDIT_MODE_ZOOM = 3  # Zoom mode
EDIT_MODE_HISTORY = 4  # Edit history mode (undo/redo)

# List of permissible steps per beat
STEPS_PER_BEAT = [1, 2, 3, 4, 6, 8, 12, 24]
INPUT_CHANNEL_LABELS = ['OFF', 'ANY', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']

# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern Editor Base GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_pated_base(zynthian_gui_base.zynthian_gui_base):

    DEFAULT_VIEW_STEPS = 16
    DEFAULT_VIEW_ROWS = 16

    # Function to initialise class
    def __init__(self):
        super().__init__()
        self.zynseq_dpath = os.environ.get('ZYNTHIAN_DATA_DIR', "/zynthian/zynthian-data") + "/zynseq"
        self.patterns_dpath = self.zynseq_dpath + "/patterns"
        self.my_zynseq_dpath = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/zynseq"
        self.my_patterns_dpath = self.my_zynseq_dpath + "/patterns"
        self.my_captures_dpath = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"

        self.state_manager = self.zyngui.state_manager
        self.zynseq = self.state_manager.zynseq

        self.ctrl_order = zynthian_gui_config.layout['ctrl_order']

        self.title = "Pattern 0"
        self.edit_mode = EDIT_MODE_NONE  # Enable encoders to adjust note parameters
        self.copy_source = 1  # Index of pattern to copy
        self.bank = None  # Bank used for pattern editor sequence player
        self.pattern = 0  # Pattern to edit
        self.sequence = None  # Sequence used for pattern editor sequence player
        self.duration = 1.0  # Current note entry duration
        self.velocity = 100  # Current note entry velocity
        self.last_play_mode = zynseq.SEQ_LOOP
        self.playhead = 0
        self.playstate = zynseq.SEQ_STOPPED
        self.n_steps = 0  # Number of steps in current pattern
        self.n_steps_beat = 0  # Number of steps per beat (current pattern)
        self.step_offset = 0  # Step number of left column in grid
        # Array of {"note":MIDI_NOTE_NUMBER, "name":"key name","colour":"key colour"} name and colour are optional
        self.cells = []  # Array of cells indices
        self.selected_cell = [0, 0]
        # What to redraw: 0=nothing, 1=selected cell, 2=selected row, 3=refresh grid, 4=rebuild grid
        self.redraw_pending = 4
        self.rows_pending = Queue()
        self.channel = 0
        self.drawing = False  # mutex to avoid concurrent screen draws
        self.changed = False
        self.changed_ts = 0
        self.midi_record = False  # True when record from MIDI enabled

        # Touch control variables
        self.swiping = 0
        self.swipe_friction = 0.8
        self.swipe_step_dir = 0
        self.swipe_row_dir = 0
        self.swipe_step_speed = 0
        self.swipe_row_speed = 0
        self.swipe_step_offset = 0
        self.swipe_row_offset = 0
        self.grid_drag_start = None  # Coordinates at start of grid drag
        self.piano_roll_drag_start = None
        self.piano_roll_drag_count = 0

        # Geometry contants
        self.grid_height = self.height - PLAYHEAD_HEIGHT
        self.grid_width = int(self.width * 0.91)
        self.base_row_height = self.grid_height // self.DEFAULT_VIEW_ROWS
        self.base_step_width = self.grid_width // self.DEFAULT_VIEW_STEPS
        self.piano_roll_width = self.width - self.grid_width
        # Scale thickness of select border based on screen resolution
        self.select_thickness = 1 + int(self.width / 500)
        # Zoom factor => Negative / Zero / Positive
        self.zoom = 0
        # Geometry variables => change with zoom factor!
        # Quantity of columns (steps) displayed in grid
        self.view_steps = self.DEFAULT_VIEW_STEPS
        self.step_width = self.base_step_width
        # Quantity of rows (notes) displayed in grid
        self.view_rows = self.DEFAULT_VIEW_ROWS
        self.row_height = self.base_row_height

        # Create pattern grid canvas
        self.grid_canvas = tkinter.Canvas(self.main_frame,
                                          width=self.grid_width,
                                          height=self.grid_height,
                                          scrollregion=(0, 0, self.grid_width, self.grid_height),
                                          bg=CANVAS_BACKGROUND,
                                          bd=0,
                                          highlightthickness=0)
        self.update_geometry()
        self.grid_canvas.grid(column=1, row=0)
        self.grid_canvas.bind('<ButtonPress-1>', self.on_grid_press)
        self.grid_canvas.bind('<ButtonRelease-1>', self.on_grid_release)
        self.grid_canvas.bind('<B1-Motion>', self.on_grid_drag)
        self.zyngui.multitouch.tag_bind(self.grid_canvas, None, "gesture", self.on_gesture)


        # Create pianoroll canvas
        self.piano_roll = tkinter.Canvas(self.main_frame,
                                         width=self.piano_roll_width,
                                         height=self.grid_height,
                                         scrollregion=(0, 0, self.piano_roll_width, self.total_height),
                                         bg=CANVAS_BACKGROUND,
                                         bd=0,
                                         highlightthickness=0)
        self.piano_roll.grid(row=0, column=0)
        self.piano_roll.bind("<ButtonPress-1>", self.on_pianoroll_press)
        self.piano_roll.bind("<ButtonRelease-1>", self.on_pianoroll_release)
        self.piano_roll.bind("<B1-Motion>", self.on_pianoroll_motion)
        self.piano_roll.bind("<Button-4>", self.on_pianoroll_wheel)
        self.piano_roll.bind("<Button-5>", self.on_pianoroll_wheel)

        # Create playhead canvas
        self.play_canvas = tkinter.Canvas(self.main_frame,
                                          width=self.grid_width,
                                          height=PLAYHEAD_HEIGHT,
                                          scrollregion=(0, 0, self.grid_width, PLAYHEAD_HEIGHT),
                                          bg=PLAYHEAD_BACKGROUND,
                                          bd=0,
                                          highlightthickness=0)
        self.play_canvas.create_rectangle(0, 0, self.step_width, PLAYHEAD_HEIGHT,
                                          fill=PLAYHEAD_CURSOR,
                                          state="normal",
                                          width=0,
                                          tags="playCursor")
        self.play_canvas.grid(column=1, row=1)

        # Create velocity level indicator canvas
        self.velocity_canvas = tkinter.Canvas(self.main_frame,
                                              width=self.piano_roll_width,
                                              height=PLAYHEAD_HEIGHT,
                                              bg=PLAYHEAD_BACKGROUND,
                                              bd=0,
                                              highlightthickness=0)
        self.velocity_canvas.create_rectangle(0, 0, self.piano_roll_width * self.velocity / 127, PLAYHEAD_HEIGHT,
                                              fill='yellow', width=0, tags="velocityIndicator")
        self.velocity_canvas.grid(column=0, row=1)

        self.zynseq.libseq.setPlayMode(0, 0, zynseq.SEQ_LOOP)
        # Load pattern 1 so that the editor has a default known state
        self.load_pattern(1)

    # Function to get name of this view
    def get_name(self):
        return "pattern editor base"

    # Function to set up behaviour of encoders
    def setup_zynpots(self):
        for i in range(zynthian_gui_config.num_zynpots):
            lib_zyncore.setup_behaviour_zynpot(i, 0)

    def get_title(self):
        title = self.zynseq.get_sequence_name(self.bank, self.sequence)
        try:
            str(int(title))
            # Get preset title from synth engine on this MIDI channel
            midi_chan = self.zynseq.libseq.getChannel(self.bank, self.sequence, 0)
            preset_name = self.zyngui.chain_manager.get_synth_preset_name(midi_chan)
            if not preset_name:
                group = chr(65 + self.zynseq.libseq.getGroup(self.bank, self.sequence))
                title = f"{group}{title}"
        except:
            pass
        if title:
            title = f"Pattern {self.pattern} ({title})"
        else:
            title = f"Pattern {self.pattern}"
        return title

    def set_title(self, title=None, color_fg=None, color_bg=None, timeout=None):
        if not title:
            title = self.get_title()
        if not color_fg:
            color_fg = zynthian_gui_config.color_panel_tx
        if not color_bg:
            color_bg = zynthian_gui_config.color_header_bg
        super().set_title(title, color_fg, color_bg, timeout)

    # Function to enable edit mode => It *MUST* be redefined in child class
    #   mode: Edit mode to enable [EDIT_MODE_NONE | others to define in child classes]
    def set_edit_mode(self, mode):
        self.edit_mode = mode
        if mode == EDIT_MODE_NONE:
            self.set_title()
            self.init_buttonbar()
        else:
            color_fg = zynthian_gui_config.color_header_bg
            color_bg = zynthian_gui_config.color_panel_tx
            self.set_title(f"EDIT MODE {mode}", color_fg, color_bg)
            self.set_edit_title()

    # Function to adjust velocity indicator
    # velocity: Note velocity to indicate
    def set_velocity_indicator(self, velocity):
        self.velocity_canvas.coords("velocityIndicator", 0, 0, self.piano_roll_width * velocity / 127, PLAYHEAD_HEIGHT)

    # Function to show GUI
    def build_view(self):
        if self.sequence is None:
            self.sequence = 0
        if self.bank is None:
            self.bank = 0
        if self.sequence == 0 and self.bank == 0:
            self.zynseq.libseq.setGroup(self.bank, self.sequence, 0xFF)
        self.zynseq.libseq.setSequence(self.bank, self.sequence)
        self.copy_source = self.pattern

        self.setup_zynpots()
        if not self.param_editor_zctrl:
            self.set_title()
        self.last_play_mode = self.zynseq.libseq.getPlayMode(self.bank, self.sequence)
        if self.last_play_mode not in (zynseq.SEQ_LOOP, zynseq.SEQ_LOOPALL):
            self.zynseq.libseq.setPlayMode(self.bank, self.sequence, zynseq.SEQ_LOOP)

        # Set active the first chain with pattern's MIDI chan
        try:
            chain_id = self.zyngui.chain_manager.midi_chan_2_chain_ids[self.channel][0]
            self.zyngui.chain_manager.set_active_chain_by_id(chain_id)
        except:
            logging.error(f"Couldn't set active chain to channel {self.channel}.")

        self.toggle_midi_record(self.midi_record)
        return True

    # Function to hide GUI
    def hide(self):
        if not self.shown:
            return
        super().hide()
        if self.bank == 0 and self.sequence == 0:
            self.zynseq.libseq.setPlayState(self.bank, self.sequence, zynseq.SEQ_STOPPED)
        self.toggle_midi_record(False)
        self.set_edit_mode(EDIT_MODE_NONE)
        #self.zynseq.libseq.setRefNote(int(self.keymap_offset))
        self.zynseq.libseq.setPatternZoom(self.zoom)
        self.zynseq.libseq.setPlayMode(self.bank, self.sequence, self.last_play_mode)
        self.zynseq.libseq.updateSequenceInfo()

    # -------------------------------------------------------------------------
    # Pattern menu
    # -------------------------------------------------------------------------

    def get_menu_options(self):
        menu_options = {}
        extra_options = not zynthian_gui_config.check_wiring_layout(["Z2", "V5"])
        # Global Options
        options = {}
        if not self.zyngui.multitouch._f_device:
            options['Grid zoom'] = 'Grid zoom'
        if extra_options:
            options['Tempo'] = 'Tempo'
        if not zynthian_gui_config.check_wiring_layout(["Z2"]):
            options['Arranger'] = 'Arranger'
        options[f"Beats per Bar ({self.zynseq.libseq.getBeatsPerBar()})"] = 'Beats per bar'
        menu_options["GLOBAL"] = options
        # Pattern Options
        options = {}
        options[f"Beats in pattern ({self.zynseq.libseq.getBeatsInPattern()})"] = 'Beats in pattern'
        options[f"Steps/Beat ({self.n_steps_beat})"] = 'Steps per beat'
        options[f"Swing Divisor ({self.zynseq.libseq.getSwingDiv()})"] = 'Swing Divisor'
        options[f"Swing Amount ({int(100.0 * self.zynseq.libseq.getSwingAmount())}%)"] = 'Swing Amount'
        options[f"Time Humanization ({int(500.0 * self.zynseq.libseq.getHumanTime())})"] = 'Time Humanization'
        menu_options['PATTERN OPTIONS'] = options
        # Pattern Edit
        options = {}
        # options['Add program change'] = 'Add program change'
        if extra_options:
            if self.zynseq.libseq.isMidiRecord():
                options['\u2612 Record from MIDI'] = 'Record MIDI'
            else:
                options['\u2610 Record from MIDI'] = 'Record MIDI'
        if self.zynseq.libseq.getQuantizeNotes():
            options['\u2612 Quantized recording'] = 'Quantized recording'
        else:
            options['\u2610 Quantized recording'] = 'Quantized recording'
        options['Copy pattern'] = 'Copy pattern'
        options['Load pattern'] = 'Load pattern'
        options['Save pattern'] = 'Save pattern'
        options['Clear pattern'] = 'Clear pattern'
        options['Export to SMF'] = 'Export to SMF'
        options['Export to SMF'] = 'Export to SMF'
        menu_options['PATTERN EDIT'] = options
        return menu_options

    # Function to add menus
    def show_menu(self):
        self.disable_param_editor()
        menu_options = self.get_menu_options()
        options = {}
        for subtitle, subopts in menu_options.items():
            options[f"> {subtitle}"] = None
            options.update(subopts)
        self.zyngui.screens['option'].config("Pattern Editor Menu", options, self.menu_cb)
        self.zyngui.show_screen('option')

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.current_screen == "option":
            self.zyngui.close_screen()

    def menu_cb(self, option, params):
        if params == 'Grid zoom':
            self.enable_param_editor(self, 'zoom', {'name': 'Zoom', 'value_min': 1, 'value_max': 64,
                                                    'value_default': 1, 'value': self.zoom})
        elif params == 'Tempo':
            self.zyngui.show_screen('tempo')
        elif params == 'Arranger':
            self.zyngui.show_screen('arranger')
        elif params == 'Beats per bar':
            self.enable_param_editor(self, 'bpb', {'name': 'Beats per bar', 'value_min': 1, 'value_max': 64,
                                                   'value_default': 4, 'value': self.zynseq.libseq.getBeatsPerBar()})

        elif params == 'Beats in pattern':
            self.enable_param_editor(self, 'bip', {'name': 'Beats in pattern', 'value_min': 1, 'value_max': 64,
                                                   'value_default': 4, 'value': self.zynseq.libseq.getBeatsInPattern()},
                                     self.assert_beats_in_pattern)
        elif params == 'Steps per beat':
            self.enable_param_editor(self, 'spb', {'name': 'Steps per beat', 'ticks': STEPS_PER_BEAT,
                                     'value_default': 3, 'value': self.n_steps_beat}, self.assert_steps_per_beat)

        elif params == 'Swing Divisor':
            self.enable_param_editor(self, 'swing_div', {'name': 'Swing Divisor', 'value_min': 1,
                                                         'value_max': self.n_steps_beat, 'value_default': 1,
                                                         'value': self.zynseq.libseq.getSwingDiv()})

        elif params == 'Swing Amount':
            self.enable_param_editor(self, 'swing_amount', {'name': 'Swing Amount', 'value_min': 0, 'value_max': 100,
                                                            'value': int(100.0 * self.zynseq.libseq.getSwingAmount()),
                                                            'value_default': 0})

        elif params == 'Time Humanization':
            self.enable_param_editor(self, 'human_time', {'name': 'Time Humanization', 'value_min': 0, 'value_max': 100,
                                                          'value': int(500.0 * self.zynseq.libseq.getHumanTime()),
                                                          'value_default': 0})
        elif params == 'Add program change':
            self.enable_param_editor(self, 'prog_change', {'name': 'Program', 'value_max': 128,
                                                           'value': self.get_program_change()}, self.add_program_change)
        elif params == 'Record MIDI':
            self.toggle_midi_record()
        elif params == 'Quantized recording':
            self.zynseq.libseq.setQuantizeNotes(not self.zynseq.libseq.getQuantizeNotes())
        elif params == 'Copy pattern':
            self.copy_source = self.pattern
            self.enable_param_editor(self, 'copy', {'name': 'Copy pattern to', 'value_min': 1,
                                     'value_max': zynseq.SEQ_MAX_PATTERNS, 'value': self.pattern}, self.copy_pattern)
        elif params == 'Load pattern':
            self.zyngui.screens['option'].config_file_list("Load pattern",
                                                           [self.patterns_dpath, self.my_patterns_dpath],
                                                           "*.zpat", self.load_pattern_file)
            self.zyngui.show_screen('option')
        elif params == 'Save pattern':
            self.zyngui.show_keyboard(self.save_pattern_file, "pat#{}".format(self.pattern))
        elif params == 'Clear pattern':
            self.clear_pattern()
        elif params == 'Export to SMF':
            self.zyngui.show_keyboard(self.export_smf, "pat#{}".format(self.pattern))

    # -------------------------------------------------------------------------
    # Pattern management
    # -------------------------------------------------------------------------

    # Function to load new pattern
    # index: Pattern index
    def load_pattern(self, index):
        # Save zoom value and vertical position in pattern object
        self.zynseq.libseq.setPatternZoom(self.zoom)
        # Load requested pattern
        if self.bank == 0 and self.sequence == 0:
            self.zynseq.libseq.setChannel(self.bank, self.sequence, 0, self.channel)
        self.zynseq.libseq.selectPattern(index)
        self.pattern = index
        n_steps = self.zynseq.libseq.getSteps()
        n_steps_beat = self.zynseq.libseq.getStepsPerBeat()
        if n_steps != self.n_steps or n_steps_beat != self.n_steps_beat:
            self.n_steps = n_steps
            self.n_steps_beat = n_steps_beat
            self.step_offset = 0
            self.update_geometry()
            self.redraw_pending = 4
        else:
            self.redraw_pending = 3
        if self.selected_cell[0] >= n_steps:
            self.selected_cell[0] = int(n_steps) - 1
        if self.duration > n_steps:
            self.duration = 1
        self.draw_grid()
        self.select_cell()
        self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)
        self.set_title()
        self.set_grid_zoom(self.zynseq.libseq.getPatternZoom())

    def save_pattern_file(self, fname):
        self.zynseq.save_pattern(
            self.pattern, "{}/{}.zpat".format(self.my_patterns_dpath, fname))

    def load_pattern_file(self, fname, fpath):
        if not self.zynseq.is_pattern_empty(self.pattern):
            self.zyngui.show_confirm("Do you want to overwrite pattern '{}'?".format(
                self.pattern), self.do_load_pattern_file, fpath)
        else:
            self.do_load_pattern_file(fpath)

    def do_load_pattern_file(self, fpath):
        self.zynseq.load_pattern(self.pattern, fpath)
        self.changed = False
        self.redraw_pending = 3

    def clean_pattern_snapshots(self):
        self.zynseq.libseq.resetPatternSnapshots()

    # If changed, save snapshot:
    #  + right now, if now=True
    #  + force saving ignoring changed flag
    #  + each loop, if playing
    #  + each SAVE_SNAPSHOT_DELAY seconds, if stopped
    def save_pattern_snapshot(self, now=True, force=False):
        if force or self.changed:
            if now or (self.playstate != zynseq.SEQ_STOPPED and self.playhead == 0):
                self.zynseq.libseq.savePatternSnapshot()
                self.changed = False
                self.changed_ts = 0
            elif self.playstate == zynseq.SEQ_STOPPED:
                ts = datetime.now()
                if self.changed_ts:
                    if (ts - self.changed_ts).total_seconds() > SAVE_SNAPSHOT_DELAY:
                        self.zynseq.libseq.savePatternSnapshot()
                        self.changed = False
                        self.changed_ts = 0
                else:
                    self.changed_ts = ts

    def undo_pattern(self):
        self.save_pattern_snapshot(now=True, force=False)
        if self.zynseq.libseq.undoPattern():
            self.redraw_pending = 3

    def redo_pattern(self):
        if not self.changed and self.zynseq.libseq.redoPattern():
            self.redraw_pending = 3

    def undo_pattern_all(self):
        self.save_pattern_snapshot(now=True, force=False)
        if self.zynseq.libseq.undoPatternAll():
            self.redraw_pending = 3

    def redo_pattern_all(self):
        if not self.changed and self.zynseq.libseq.redoPatternAll():
            self.redraw_pending = 3

    # Function to clear a pattern
    def clear_pattern(self, params=None):
        self.zyngui.show_confirm(f"Clear pattern {self.pattern}?", self.do_clear_pattern)

    # Function to actually clear pattern
    def do_clear_pattern(self, params=None):
        self.save_pattern_snapshot(now=True, force=False)
        self.zynseq.libseq.clear()
        self.save_pattern_snapshot(now=True, force=True)
        self.redraw_pending = 3
        self.select_cell()
        if self.zynseq.libseq.getPlayState(self.bank, self.sequence, 0) != zynseq.SEQ_STOPPED:
            self.zynseq.libseq.sendMidiCommand(0xB0 | self.channel, 123, 0)  # All notes off

    # Function to copy pattern
    def copy_pattern(self, value):
        if self.zynseq.libseq.getLastStep() == -1:
            self.do_copy_pattern(value)
        else:
            self.zyngui.show_confirm(f"Overwrite pattern {value} with content from pattern {self.copy_source}?",
                                     self.do_copy_pattern, value)
        self.load_pattern(self.copy_source)

    # Function to cancel copy pattern operation
    def cancel_copy(self):
        self.load_pattern(self.copy_source)

    # Function to actually copy pattern
    def do_copy_pattern(self, dest_pattern):
        self.zynseq.libseq.copyPattern(self.copy_source, dest_pattern)
        self.pattern = dest_pattern
        self.load_pattern(self.pattern)
        self.copy_source = self.pattern
        # TODO: Update arranger when it is refactored
        # self.zyngui.screen['arranger'].pattern = self.pattern
        # self.zyngui.screen['arranger'].pattern_canvas.itemconfig("patternIndicator", text="{}".format(self.pattern))

    # Function to export pattern to SMF
    def export_smf(self, fname):
        smf = zynsmf.libsmf.addSmf()
        tempo = self.zynseq.libseq.getTempo()
        zynsmf.libsmf.addTempo(smf, 0, tempo)
        ticks_per_step = zynsmf.libsmf.getTicksPerQuarterNote(
            smf) / self.n_steps_beat
        for step in range(self.n_steps):
            time = int(step * ticks_per_step)
            for note in range(128):
                duration = self.zynseq.libseq.getNoteDuration(step, note)
                if duration == 0.0:
                    continue
                duration = int(duration * ticks_per_step)
                velocity = self.zynseq.libseq.getNoteVelocity(step, note)
                zynsmf.libsmf.addNote(
                    smf, 0, time, duration, self.channel, note, velocity)
        zynsmf.libsmf.setEndOfTrack(smf, 0, int(self.n_steps * ticks_per_step))
        zynsmf.save(smf, "{}/{}.mid".format(self.my_captures_dpath, fname))

    # Function to get program change at start of pattern
    # returns: Program change number (1..128) or 0 for none
    def get_program_change(self):
        program = self.zynseq.libseq.getProgramChange(0) + 1
        if program > 128:
            program = 0
        return program

    # Function to add program change at start of pattern
    def add_program_change(self, value):
        self.zynseq.libseq.addProgramChange(0, value)

    def toggle_midi_record(self, midi_record=None):
        if midi_record is None:
            midi_record = not self.midi_record
            self.midi_record = midi_record
        self.zynseq.libseq.enableMidiRecord(midi_record)
        self.save_pattern_snapshot(now=True, force=False)

    # -------------------------------------------------------------------------
    # Controller callback
    # -------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        if zctrl.symbol == 'zoom':
            self.set_grid_zoom(zctrl.value)
            self.param_editor_zctrl.value = self.zoom
        elif zctrl.symbol == 'bpb':
            self.zynseq.libseq.setBeatsPerBar(zctrl.value)
        elif zctrl.symbol == 'swing_amount':
            self.zynseq.libseq.setSwingAmount(zctrl.value/100.0)
        elif zctrl.symbol == 'swing_div':
            self.zynseq.libseq.setSwingDiv(zctrl.value)
        elif zctrl.symbol == 'human_time':
            self.zynseq.libseq.setHumanTime(zctrl.value / 500.0)
        elif zctrl.symbol == 'copy':
            self.load_pattern(zctrl.value)

    # Function to assert steps per beat
    def assert_steps_per_beat(self, value):
        self.zyngui.show_confirm(
            "Changing steps per beat may alter timing and/or lose notes?", self.do_steps_per_beat, value)

    # Function to actually change steps per beat
    def do_steps_per_beat(self, value):
        self.zynseq.libseq.setStepsPerBeat(value)
        self.clean_pattern_snapshots()
        self.n_steps_beat = self.zynseq.libseq.getStepsPerBeat()
        self.n_steps = self.zynseq.libseq.getSteps()
        self.update_geometry()
        self.redraw_pending = 4

    # Function to assert beats in pattern
    def assert_beats_in_pattern(self, value):
        if self.zynseq.libseq.getLastStep() >= self.zynseq.libseq.getStepsPerBeat() * value:
            self.zyngui.show_confirm(
                "Reducing beats in pattern will truncate pattern", self.set_beats_in_pattern, value)
        else:
            self.set_beats_in_pattern(value)

    # Function to assert beats in pattern
    def set_beats_in_pattern(self, value):
        self.zynseq.libseq.setBeatsInPattern(value)
        self.clean_pattern_snapshots()
        self.n_steps = self.zynseq.libseq.getSteps()
        self.update_geometry()
        self.redraw_pending = 4

    # Function to get the index of the closest steps per beat in array of allowed values
    # returns: Index of the closest allowed value
    def get_steps_per_beat_index(self):
        steps_per_beat = self.zynseq.libseq.getStepsPerBeat()
        for index in range(len(STEPS_PER_BEAT)):
            if STEPS_PER_BEAT[index] >= steps_per_beat:
                return index
        return len(STEPS_PER_BEAT) - 1

    # -------------------------------------------------------------------------
    # Touch event management
    # -------------------------------------------------------------------------

    # Function to handle start of pianoroll drag
    def on_pianoroll_press(self, event):
        self.swiping = False
        self.swipe_step_speed = 0
        self.swipe_row_speed = 0
        self.swipe_step_dir = 0
        self.swipe_row_dir = 0
        self.piano_roll_drag_start = event
        self.piano_roll_drag_count = 0

    # Function to handle pianoroll drag motion
    def on_pianoroll_motion(self, event):
        if not self.piano_roll_drag_start:
            return
        self.piano_roll_drag_count += 1
        offset = int(DRAG_SENSIBILITY * (event.y - self.piano_roll_drag_start.y) / self.row_height)
        if offset == 0:
            return
        self.swiping = True
        self.piano_roll_drag_start = event
        self.swipe_step_dir = 0
        self.swipe_row_dir = offset
        return offset

    # Function to handle end of pianoroll drag
    def on_pianoroll_release(self, event):
        # Play note if not drag action
        if self.piano_roll_drag_start and self.piano_roll_drag_count == 0:
            self.on_pianoroll_release_action(event)
        # Swipe
        elif self.swiping:
            dts = (event.time - self.piano_roll_drag_start.time)/1000
            self.swipe_nudge(dts)
        # Reset drag state variables
        self.piano_roll_drag_start = None
        self.piano_roll_drag_count = 0

    def on_pianoroll_release_action(self, event):
        pass

    # Function to handle mouse wheel over pianoroll
    def on_pianoroll_wheel(self, event):
        pass

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

    def swipe_nudge(self, dts):
        try:
            kt = 0.5 * min(0.05 * DRAG_SENSIBILITY / dts, 8)
        except:
            return
        self.swipe_step_speed += kt * self.swipe_step_dir
        self.swipe_row_speed += kt * self.swipe_row_dir
        # logging.debug(f"KT={kt} => SWIPE_STEP_SPEED = {self.swipe_step_speed}, SWIPE_ROW_SPEED = {self.swipe_row_speed}")

    # Update swipe scroll
    def swipe_update(self):
        select_cell = False
        if self.swipe_step_speed:
            # logging.debug(f"SWIPE_UPDATE_STEP => {self.swipe_step_speed}")
            self.swipe_step_offset += self.swipe_step_speed
            self.swipe_step_speed *= self.swipe_friction
            if abs(self.swipe_step_speed) < 0.2:
                self.swipe_step_speed = 0
                self.swipe_step_offset = 0
            if abs(self.swipe_step_offset) > 1:
                self.step_offset += int(self.swipe_step_offset)
                self.swipe_step_offset -= int(self.swipe_step_offset)
                self.set_step_offset(self.step_offset)
                select_cell = True
        if self.swipe_row_speed:
            # logging.debug(f"SWIPE_UPDATE_ROW => {self.swipe_row_speed}")
            self.swipe_row_offset += self.swipe_row_speed
            self.swipe_row_speed *= self.swipe_friction
            if abs(self.swipe_row_speed) < 0.2:
                self.swipe_row_speed = 0
                self.swipe_row_offset = 0
            if abs(self.swipe_row_offset) > 1:
                self.swipe_vertical_action()
                select_cell = True
        if select_cell:
            self.select_cell()

    def swipe_vertical_action(self):
        pass

    # -------------------------------------------------------------------------
    # Geometry management
    # -------------------------------------------------------------------------

    def get_pianoroll_num_cells(self):
        return 128

    # Function to calculate variable gemoetry parameters
    def update_geometry(self):
        # Width & height
        self.total_width = self.n_steps * self.step_width
        self.total_height = 128 * self.row_height
        self.scroll_height = self.total_height - self.grid_height
        # Font size
        self.fontsize_grid = self.row_height // 2
        if self.fontsize_grid > 20:
            self.fontsize_grid = 20  # Ugly font scale limiting
        self.calculate_geometry_limits()
        self.update_scroll_regions()

    def calculate_geometry_limits(self):
        # Row height limits
        self.max_row_height = self.grid_height // 6
        self.min_row_height = self.grid_height // 36

        # Step width limits
        self.max_step_width = self.grid_width // 8
        self.min_step_width = self.grid_width // 64
        try:
            self.min_step_width = max(self.min_step_width, self.grid_width // self.n_steps)
        except:
            pass

    # Update scrollregion in several canvas
    def update_scroll_regions(self):
        if self.total_width > 0:
            self.grid_canvas.config(scrollregion=(0, 0, self.total_width, self.total_height))
            self.piano_roll.config(scrollregion=(0, 0, self.piano_roll_width, self.total_height))
            self.play_canvas.config(scrollregion=(0, 0, self.total_width, PLAYHEAD_HEIGHT))
            # logging.debug(f"GRID SCROLLREGION: {self.total_width} x {self.total_height}")

    # Function to set step offset and move grid view accordingly
    # offset: Step Offset (step at left column)
    def set_step_offset(self, offset=None):
        if offset is not None:
            self.step_offset = offset
        if self.step_offset > self.n_steps - int(self.view_steps):
            self.step_offset = self.n_steps - int(self.view_steps)
        elif self.step_offset < 0:
            self.step_offset = 0
        if self.total_width > 0:
            xpos = self.step_offset * self.step_width / self.total_width
        else:
            xpos = 0
        self.grid_canvas.xview_moveto(xpos)
        self.play_canvas.xview_moveto(xpos)
        # logging.debug(f"OFFSET: {self.step_offset} (NSTEPS: {self.n_steps}, TOTAL WIDTH: {self.total_width})")
        # logging.debug(f"GRID X-SCROLL: {xpos}\n\n")

    def set_grid_zoom(self, new_zoom=0):
        # self.selected_cell
        # Calculate new cell size
        step_width = self.base_step_width + new_zoom
        row_height = self.base_row_height + new_zoom
        # Check step width limits
        if step_width > self.max_step_width:
            step_width = self.max_step_width
        elif step_width < self.min_step_width:
            step_width = self.min_step_width
        # Check row height limits
        if row_height > self.max_row_height:
            row_height = self.max_row_height
        elif row_height < self.min_row_height:
            row_height = self.min_row_height
        # Do nothing if nothing changed
        if self.step_width != step_width:
            self.step_width = step_width
            step_width_changed = True
        else:
            step_width_changed = False
        if self.row_height != row_height:
            self.row_height = row_height
            row_height_changed = True
        else:
            row_height_changed = False
        if not step_width_changed and not row_height_changed:
            return False
        # Adjust real zoom value
        hzoom = self.step_width - self.base_step_width
        vzoom = self.row_height - self.base_row_height
        if abs(hzoom) > abs(vzoom):
            self.zoom = hzoom
        else:
            self.zoom = vzoom
        # Recalculate geometry parameters and scaling factor
        w = self.total_width
        h = self.total_height
        self.update_geometry()
        xscale = self.total_width / w
        yscale = self.total_height / h
        # Scale canvas
        self.grid_canvas.scale("all", 0, 0, xscale, yscale)
        self.play_canvas.scale("all", 0, 0, xscale, 1.0)
        self.piano_roll.scale("all", 0, 0, 1.0, yscale)
        self.update_grid_position(step_width_changed, row_height_changed)
        return True

    def reset_grid_zoom(self):
        self.zoom = 0
        self.view_rows = self.DEFAULT_VIEW_ROWS
        self.view_steps = self.DEFAULT_VIEW_STEPS
        self.row_height = self.base_row_height
        self.step_width = self.base_step_width
        w = self.total_width
        h = self.total_height
        self.update_geometry()
        xscale = self.total_width / w
        yscale = self.total_height / h
        self.grid_canvas.scale("all", 0, 0, xscale, yscale)
        self.play_canvas.scale("all", 0, 0, xscale, 1.0)
        self.piano_roll.scale("all", 0, 0, 1.0, yscale)
        self.reset_grid_offset()

    # Update grid position
    def update_grid_position(self, step_width_changed, row_height_changed):
        if step_width_changed:
            self.set_step_offset()
        if row_height_changed:
            pass
        self.view_rows = self.grid_height / self.row_height
        self.view_steps = self.grid_width / self.step_width

    # Reset grid offset
    def reset_grid_offset(self):
        self.set_step_offset()

    # Function to get cell coordinates
    # col: Column number (step)
    # row: Row number (keymap index)
    # duration: Duration of cell in steps
    # offset: Factor to offset start of note
    # return: Coordinates required to draw cell
    def get_cell(self, col, row, duration, offset):
        x1 = int((col + offset) * self.step_width) + 1
        y1 = self.total_height - (row + 1) * self.row_height + 1
        x2 = x1 + int(self.step_width * duration) - 1
        y2 = y1 + self.row_height - 1
        return [x1, y1, x2, y2]

    # -------------------------------------------------------------------------
    # Drawing functions
    # -------------------------------------------------------------------------

    # Function to draw grid
    def draw_grid(self):
        if self.drawing:
            return
        self.drawing = True
        redraw_pending = self.redraw_pending
        self.redraw_pending = 0

        if self.n_steps == 0:
            self.drawing = False
            return  # TODO: Should we clear grid?

        if len(self.cells) != self.get_pianoroll_num_cells() * self.n_steps:
            redraw_pending = 4
            self.grid_canvas.delete(tkinter.ALL)
            self.draw_pianoroll()
            self.cells = [None] * self.get_pianoroll_num_cells() * self.n_steps
            self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width,
                                    0, 1 + self.step_width * (self.playhead + 1), PLAYHEAD_HEIGHT)

        self.redraw_grid_pending(redraw_pending)
        self.select_cell()
        self.drawing = False

    def redraw_grid_pending(self, redraw_pending):
        # Draw cells of grid
        # self.grid_canvas.itemconfig("gridcell", fill="black")
        if redraw_pending > 3:
            # Redraw gridlines
            self.grid_canvas.delete("gridvline")
            self.play_canvas.delete("beatnum")
            if self.n_steps_beat:
                bnum_font = tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=PLAYHEAD_HEIGHT - 2)
                lh = max(128 * self.row_height - 1, self.grid_height - 1)
                th = int(0.7 * PLAYHEAD_HEIGHT)
                for step in range(0, self.n_steps + 1):
                    xpos = step * self.step_width
                    if step % self.n_steps_beat == 0:
                        self.grid_canvas.create_line(xpos, 0, xpos, lh, fill=GRID_LINE_STRONG, tags="gridvline")
                        if step < self.n_steps:
                            beatnum = 1 + step // self.n_steps_beat
                            if beatnum == 1:
                                anchor = tkinter.NW
                            else:
                                anchor = tkinter.N
                            self.play_canvas.create_text((xpos, -2), text=str(beatnum), font=bnum_font, anchor=anchor,
                                                         fill=GRID_LINE_STRONG, tags="beatnum")
                    else:
                        self.grid_canvas.create_line(xpos, 0, xpos, lh, fill=GRID_LINE_WEAK, tags="gridvline")
                        self.play_canvas.create_line(xpos, 0, xpos, th, fill=PLAYHEAD_LINE, tags="beatnum")

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
        # Position selector cell-frame
        coord = self.get_cell(step, row, 1, 0)
        coord[0] -= 1
        coord[1] -= 1
        cell = self.grid_canvas.find_withtag("selection")
        if not cell:
            cell = self.grid_canvas.create_rectangle(coord, fill="", outline=SELECT_BORDER,
                                                     width=self.select_thickness, tags="selection")
        else:
            self.grid_canvas.coords(cell, coord)
        self.grid_canvas.tag_raise(cell)

    # -------------------------------------------------------------------------
    # Event management
    # -------------------------------------------------------------------------

    def plot_zctrls(self):
        self.swipe_update()

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

    # Function to refresh status
    def refresh_status(self):
        super().refresh_status()
        self.playstate = self.zynseq.libseq.getSequenceState(self.bank, self.sequence) & 0xff
        step = self.zynseq.libseq.getPatternPlayhead()
        if self.playhead != step:
            self.playhead = step
            self.play_canvas.coords("playCursor",
                                    1 + self.playhead * self.step_width, 0,
                                    1 + self.step_width * (self.playhead + 1), PLAYHEAD_HEIGHT)
        if (self.zynseq.libseq.isPatternModified()) and self.redraw_pending < 3:
            self.redraw_pending = 3
        if self.redraw_pending:
            self.draw_grid()
        self.save_pattern_snapshot(now=False, force=False)

    def set_edit_title(self):
        #step = self.selected_cell[0]
        delta = "1"
        zynpot = 2
        self.init_buttonbar([(f"ZYNPOT {zynpot},-1", f"-{delta}"),
                             (f"ZYNPOT {zynpot},+1", f"+{delta}"),
                             ("ZYNPOT 3,-1", "PREV\nPARAM"),
                             ("ZYNPOT 3,+1", "NEXT\nPARAM"),
                             (3, "OK")])

    # Function to handle zynpots value change
    #   i: Zynpot index [0..n]
    #   dval: Current value of zyncoder
    def zynpot_cb(self, i, dval):
        if super().zynpot_cb(i, dval):
            return True

    # Function to handle SELECT button press
    #   st: Button press duration [S=Short, B=Bold, L=Long]
    def switch_select(self, st='S'):
        if super().switch_select(st):
            return
        if st == "S":
            if self.edit_mode == EDIT_MODE_NONE:
                self.toggle_event(self.selected_cell[0], self.selected_cell[1])
            else:
                self.set_edit_mode(EDIT_MODE_NONE)
        elif st == "B":
            if self.edit_mode == EDIT_MODE_NONE:
                self.set_edit_mode(EDIT_MODE_SINGLE)
            elif self.edit_mode == EDIT_MODE_SINGLE:
                self.set_edit_mode(EDIT_MODE_ALL)

    # Function to handle switch press
    #   i: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    #   st: Press type [S=Short, B=Bold, L=Long]
    #   returns True if action fully handled or False if parent action should be triggered
    def switch(self, i, st):
        if i == 0 and st == "S":
            self.show_menu()
            return True
        elif i == 1:
            if st == 'B':
                self.set_edit_mode(EDIT_MODE_HISTORY)
                return True
        elif i == 2:
            if st == 'S':
                self.cuia_toggle_play()
                return True
            elif st == 'B':
                self.cuia_toggle_record()
                return True
            elif st == "P":
                return False
        return False

    # Function to handle BACK button
    def back_action(self):
        if self.edit_mode == EDIT_MODE_NONE:
            return super().back_action()
        self.set_edit_mode(EDIT_MODE_NONE)
        return True

    # CUIA Actions

    # Function to handle CUIA ARROW_RIGHT
    def arrow_right(self):
        if self.zyngui.alt_mode or self.edit_mode == EDIT_MODE_HISTORY:
            self.redo_pattern()
        else:
            self.zynpot_cb(self.ctrl_order[3], 1)

    # Function to handle CUIA ARROW_LEFT
    def arrow_left(self):
        if self.zyngui.alt_mode or self.edit_mode == EDIT_MODE_HISTORY:
            self.undo_pattern()
        else:
            self.zynpot_cb(self.ctrl_order[3], -1)

    # Function to handle CUIA ARROW_UP
    def arrow_up(self):
        if self.param_editor_zctrl:
            self.zynpot_cb(self.ctrl_order[3], 1)
        elif self.edit_mode:
            self.zynpot_cb(self.ctrl_order[2], 1)
        elif self.zyngui.alt_mode:
            self.redo_pattern_all()
        else:
            self.zynpot_cb(self.ctrl_order[2], -1)

    # Function to handle CUIA ARROW_DOWN
    def arrow_down(self):
        if self.param_editor_zctrl:
            self.zynpot_cb(self.ctrl_order[3], -1)
        elif self.edit_mode:
            self.zynpot_cb(self.ctrl_order[2], -1)
        elif self.zyngui.alt_mode:
            self.undo_pattern_all()
        else:
            self.zynpot_cb(self.ctrl_order[2], 1)

    def start_playback(self):
        # Set to start of pattern - work around for timebase issue in library.
        self.zynseq.libseq.setPlayPosition(self.bank, self.sequence, 0)
        self.zynseq.libseq.setPlayState(self.bank, self.sequence, zynseq.SEQ_STARTING)

    def stop_playback(self):
        self.zynseq.libseq.setPlayState(self.bank, self.sequence, zynseq.SEQ_STOPPED)

    def toggle_playback(self):
        if self.zynseq.libseq.getPlayState(self.bank, self.sequence) == zynseq.SEQ_STOPPED:
            self.start_playback()
        else:
            self.stop_playback()

    def get_playback_status(self):
        return self.zynseq.libseq.getPlayState(self.bank, self.sequence)

    def status_short_touch_action(self):
        self.toggle_playback()

    # -------------------------------------------------------------------------
    # CUIA & LEDs methods
    # -------------------------------------------------------------------------

    def cuia_toggle_record(self, params=None):
        self.toggle_midi_record()
        return True

    def cuia_stop(self, params=None):
        self.stop_playback()
        return True

    def cuia_toggle_play(self, params=None):
        self.toggle_playback()
        return True

    def update_wsleds(self, leds):
        wsl = self.zyngui.wsleds
        # REC button:
        if self.zynseq.libseq.isMidiRecord():
            wsl.set_led(leds[1], wsl.wscolor_red)
            # BACK button
            wsl.set_led(leds[8], wsl.wscolor_active2)
        else:
            wsl.set_led(leds[1], wsl.wscolor_active2)
        # STOP button
        wsl.set_led(leds[2], wsl.wscolor_active2)
        # PLAY button:
        pb_status = self.zyngui.screens['pattern_editor'].get_playback_status()
        if pb_status == zynseq.SEQ_PLAYING:
            wsl.set_led(leds[3], wsl.wscolor_green)
        elif pb_status in (zynseq.SEQ_STARTING, zynseq.SEQ_RESTARTING):
            wsl.set_led(leds[3], wsl.wscolor_yellow)
        elif pb_status in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC):
            wsl.set_led(leds[3], wsl.wscolor_red)
        elif pb_status == zynseq.SEQ_STOPPED:
            wsl.set_led(leds[3], wsl.wscolor_active2)
        # Arrow buttons
        if self.zyngui.alt_mode and not (self.param_editor_zctrl or self.edit_mode):
            wsl.set_led(leds[4], wsl.wscolor_active2)
            wsl.set_led(leds[5], wsl.wscolor_active2)
            wsl.set_led(leds[6], wsl.wscolor_active2)
            wsl.set_led(leds[7], wsl.wscolor_active2)

# ------------------------------------------------------------------------------
