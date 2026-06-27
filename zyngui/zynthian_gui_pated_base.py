#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pattern Editor Base Class
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

import os
import copy
import tkinter
import logging
from datetime import datetime
import tkinter.font as tkfont

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zynlibs.zynsmf import zynsmf
from zyngui.zynthian_gui_base import zynthian_gui_base
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------

# Local constants
SELECT_BORDER = zynthian_gui_config.color_on
PLAYHEAD_CURSOR = zynthian_gui_config.color_on
CANVAS_BACKGROUND = zynthian_gui_config.color_panel_bd
GRID_LINE_WEAK = "#505050"
GRID_LINE_STRONG = "#A0A0A0"
GRID_LINE_XTRONG = "#FFFFFF"
PLAYHEAD_BACKGROUND = zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bd, 40)
PLAYHEAD_LINE = zynthian_gui_config.color_tx_off
PLAYHEAD_HEIGHT = 12
CONFIG_ROOT = "/zynthian/zynthian-data/zynseq"

DRAG_SENSIBILITY = 1.5
SAVE_SNAPSHOT_DELAY = 10

EDIT_MODE_NONE = 0     # Edit mode disabled
EDIT_MODE_BLOCK = 1    # Block edit mode
EDIT_MODE_SINGLE = 2   # Edit mode enabled for selected note
EDIT_MODE_MULTI = 3    # Edit mode enabled for a selection of notes (or ALL)
EDIT_MODE_HISTORY = 4  # Edit history mode (undo/redo)

# List of permissible steps per beat
STEPS_PER_BEAT = [1, 2, 3, 4, 6, 8, 12, 24]
# List of quantization divisors
QUANTIZATION_DIVISORS = [0, 1, 2, 3, 4, 6, 8]
QUANTIZATION_LABELS = ["DISABLED", "1 step", "1/2 step", "1/3 step", "1/4 step", "1/6 step", "1/8 step"]
# List of available MIDI channels
INPUT_CHANNEL_LABELS = ['OFF', 'ANY', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']

# List of GM instruments
GM_INSTRUMENTS = {
    # Piano
    0: "Acoustic Grand Piano",
    1: "Bright Acoustic Piano",
    2: "Electric Grand Piano",
    3: "Honky-tonk Piano",
    4: "Electric Piano 1",
    5: "Electric Piano 2",
    6: "Harpsichord",
    7: "Clavinet",
    # Chromatic Percussion:
    9: "Celesta",
    10: "Glockenspiel",
    11: "Music Box",
    12: "Vibraphone",
    13: "Marimba",
    14: "Xylophone",
    15: "Tubular Bells",
    16: "Dulcimer",
    # Organ:
    17: "Drawbar Organ",
    18: "Percussive Organ",
    19: "Rock Organ",
    20: "Church Organ",
    21: "Reed Organ",
    22: "Accordion",
    23: "Harmonica",
    24: "Tango Accordion",
    # Guitar:
    25: "Acoustic Guitar (nylon)",
    26: "Acoustic Guitar (steel)",
    27: "Electric Guitar (jazz)",
    28: "Electric Guitar (clean)",
    29: "Electric Guitar (muted)",
    30: "Overdriven Guitar",
    31: "Distortion Guitar",
    32: "Guitar harmonics",
    # Bass:
    33: "Acoustic Bass",
    34: "Electric Bass (finger)",
    35: "Electric Bass (pick)",
    36: "Fretless Bass",
    37: "Slap Bass 1",
    38: "Slap Bass 2",
    39: "Synth Bass 1",
    40: "Synth Bass 2",
    # Strings:
    41: "Violin",
    42: "Viola",
    43: "Cello",
    44: "Contrabass",
    45: "Tremolo Strings",
    46: "Pizzicato Strings",
    47: "Orchestral Harp",
    48: "Timpani",
    49: "String Ensemble 1",
    50: "String Ensemble 2",
    51: "Synth Strings 1",
    52: "Synth Strings 2",
    53: "Choir Aahs",
    54: "Voice Oohs",
    55: "Synth Voice",
    56: "Orchestra Hit",
    # Brass:
    57: "Trumpet",
    58: "Trombone",
    59: "Tuba",
    60: "Muted Trumpet",
    61: "French Horn",
    62: "Brass Section",
    63: "Synth Brass 1",
    64: "Synth Brass 2",
    # Reed:
    65: "Soprano Sax",
    66: "Alto Sax",
    67: "Tenor Sax",
    68: "Baritone Sax",
    69: "Oboe",
    70: "English Horn",
    71: "Bassoon",
    72: "Clarinet",
    # Pipe:
    73: "Piccolo",
    74: "Flute",
    75: "Recorder",
    76: "Pan Flute",
    77: "Blown Bottle",
    78: "Shakuhachi",
    79: "Whistle",
    80: "Ocarina",
    # Synth Lead:
    81: "Lead 1 (square)",
    82: "Lead 2 (sawtooth)",
    83: "Lead 3 (calliope)",
    84: "Lead 4 (chiff)",
    85: "Lead 5 (charang)",
    86: "Lead 6 (voice)",
    87: "Lead 7 (fifths)",
    88: "Lead 8 (bass + lead)",
    # Synth Pad:
    89: "Pad 1 (new age)",
    90: "Pad 2 (warm)",
    91: "Pad 3 (polysynth)",
    92: "Pad 4 (choir)",
    93: "Pad 5 (bowed)",
    94: "Pad 6 (metallic)",
    95: "Pad 7 (halo)",
    96: "Pad 8 (sweep)",
    # Synth Effects:
    97: "FX 1 (rain)",
    98: "FX 2 (soundtrack)",
    99: "FX 3 (crystal)",
    100: "FX 4 (atmosphere)",
    101: "FX 5 (brightness)",
    102: "FX 6 (goblins)",
    103: "FX 7 (echoes)",
    104: "FX 8 (sci-fi)",
    # Ethnic:
    105: "Sitar",
    106: "Banjo",
    107: "Shamisen",
    108: "Koto",
    109: "Kalimba",
    110: "Bag pipe",
    111: "Fiddle",
    112: "Shanai",
    # Percussive:
    113: "Tinkle Bell",
    114: "Agogo",
    115: "Steel Drums",
    116: "Woodblock",
    117: "Taiko Drum",
    118: "Melodic Tom",
    119: "Synth Drum",
    # Sound effects:
    120: "Reverse Cymbal",
    121: "Guitar Fret Noise",
    122: "Breath Noise",
    123: "Seashore",
    124: "Bird Tweet",
    125: "Telephone Ring",
    126: "Helicopter",
    127: "Applause",
    128: "Gunshot"
}

GM2_DRUMKITS = {
    0: "Standard Kit",
    8: "Room Kit",
    16: "Power Kit",
    24: "Electronic Kit",
    25: "TR-808 Kit",
    32: "Jazz Kit",
    40: "Brush Kit",
    48: "Orchestra Kit",
    56: "Sound FX Kit"
}

# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern Editor Base GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_pated_base(zynthian_gui_base):

    DEFAULT_VIEW_STEPS = 16
    DEFAULT_VIEW_ROWS = 16

    clipboard = 8 * [None]      # Pattern clipboard: Array of pattern indexes to copy/paste, shared by all pated instances.

    # Function to initialise class
    def __init__(self):
        super().__init__()
        self.my_data_dpath = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data")
        self.my_patterns_dpath =  self.my_data_dpath + "/files/Patterns"
        self.my_capture_dpath = self.my_data_dpath + "/capture"
        self.my_smf_dpath = self.my_data_dpath + "/files/Midi/patterns"

        self.state_manager = self.zyngui.state_manager
        self.zynseq = self.state_manager.zynseq

        self.ctrl_order = zynthian_gui_config.layout['ctrl_order']

        self.title = "Pattern 0"
        self.alt_mode = False
        self.edit_mode = EDIT_MODE_NONE  # Enable encoders to adjust note parameters
        self.phrase = 0  # Phrase where pattern is used
        self.pattern = 0  # Pattern to edit
        self.sequence = 0  # Sequence used for pattern editor sequence player
        self.channel = 0
        self.seq_info = {}  # Launcher sequence info - None to use phrase 0xffff, sequence 0
        self.last_menu_options = {}  # Last menu options (indexes) saved for each pattern. May be dirty, but we want good UX ;-)
        self.last_smf_import = {}  # Same for import SMF

        self.playhead = 0
        self.playstate = zynseq.SEQ_STOPPED
        self.n_steps = 0  # Number of steps in current pattern
        self.n_steps_beat = 0  # Number of steps per beat (current pattern)
        self.step_offset = 0  # Step number of left column in grid
        self.selected_cell = [0, 60]
        self.rect_selected_cell = None   # Rectangle object selected cell
        self.grid_rows = 0
        self.grid_steps = 0

        # Block edit mode => Copy/paste pattern blocks
        self.block_cell_start = None     # Block start for copy/past (block edit mode)
        self.block_cell_end = None       # Block start for copy/past (block edit mode)
        self.rect_selected_block = None  # Rectangle tkinter object for block edit mode
        self.block_copied = None         # Coordinates of copied block (list of lists)
        self.block_dstep = None          # Horizontal offset of block block when moving around
        self.block_drow = None           # Horizontal offset of block block when moving around
        self.selected_events = None      # Dictionary of selected events indexed by step/note key

        # What to redraw: 0=nothing, 1=selected cell, 2=selected row, 3=refresh grid, 4=rebuild grid
        self.redraw_pending = 4
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
        self.grid_drag_count = 0
        self.piano_roll_drag_start = None
        self.piano_roll_drag_count = 0

        # Geometry constants
        self.grid_height = self.height - PLAYHEAD_HEIGHT
        self.grid_width = int(self.width * 0.91)
        self.piano_roll_width = self.width - self.grid_width
        # Scale thickness of select border based on screen resolution
        self.select_thickness = 1 + int(self.width / 500)
        # Zoom factor => Negative / Zero / Positive
        self.zoom = 0
        # Geometry variables => change with zoom factor!
        self.base_row_height = self.grid_height // self.DEFAULT_VIEW_ROWS
        self.base_step_width = self.grid_width // self.DEFAULT_VIEW_STEPS
        # Quantity of columns (steps) displayed in grid
        self.view_steps = self.DEFAULT_VIEW_STEPS
        self.step_width = self.base_step_width
        # Quantity of rows (notes) displayed in grid
        self.n_rows = 36
        self.view_rows = self.DEFAULT_VIEW_ROWS
        self.row_height = self.base_row_height

        # Create pattern grid canvas
        self.grid_canvas = tkinter.Canvas(self.main_frame,
                                          #scrollregion=(0, 0, self.grid_width, self.grid_height),
                                          bg=CANVAS_BACKGROUND,
                                          bd=0,
                                          highlightthickness=0)
        self.update_geometry()
        self.grid_canvas.grid(column=1, row=0, sticky="nsew")
        self.grid_canvas.bind('<ButtonPress-1>', self.on_grid_press)
        self.grid_canvas.bind('<ButtonRelease-1>', self.on_grid_release)
        self.grid_canvas.bind('<B1-Motion>', self.on_grid_drag)
        self.grid_canvas.bind('<Button-4>', self.on_grid_wheel)
        self.grid_canvas.bind('<Button-5>', self.on_grid_wheel)
        self.zyngui.multitouch.tag_bind(self.grid_canvas, None, "gesture", self.on_gesture)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # Create pianoroll canvas
        self.piano_roll = tkinter.Canvas(self.main_frame,
                                         width=self.piano_roll_width,
                                         #scrollregion=(0, 0, self.piano_roll_width, self.total_height),
                                         bg=CANVAS_BACKGROUND,
                                         bd=0,
                                         highlightthickness=0)
        self.piano_roll.grid(row=0, column=0, stick="ns")
        self.piano_roll.bind("<ButtonPress-1>", self.on_pianoroll_press)
        self.piano_roll.bind("<ButtonRelease-1>", self.on_pianoroll_release)
        self.piano_roll.bind("<B1-Motion>", self.on_pianoroll_motion)
        self.piano_roll.bind("<Button-4>", self.on_pianoroll_wheel)
        self.piano_roll.bind("<Button-5>", self.on_pianoroll_wheel)

        # Create playhead canvas
        self.play_canvas = tkinter.Canvas(self.main_frame,
                                          height=PLAYHEAD_HEIGHT,
                                          #scrollregion=(0, 0, self.grid_width, PLAYHEAD_HEIGHT),
                                          bg=PLAYHEAD_BACKGROUND,
                                          bd=0,
                                          highlightthickness=0)
        self.play_canvas.create_rectangle(0, 0, self.step_width, PLAYHEAD_HEIGHT,
                                          fill=PLAYHEAD_CURSOR,
                                          state="normal",
                                          width=0,
                                          tags="playCursor")
        self.play_canvas.grid(column=1, row=1, sticky="ew")

        # Create velocity level indicator canvas
        self.velocity_canvas = tkinter.Canvas(self.main_frame,
                                              width=self.piano_roll_width,
                                              height=PLAYHEAD_HEIGHT,
                                              bg=PLAYHEAD_BACKGROUND,
                                              bd=0,
                                              highlightthickness=0)
        self.velocity_canvas.create_rectangle(0, 0, 0, PLAYHEAD_HEIGHT, fill='yellow', width=0,
                                              tags="velocityIndicator")
        self.velocity_canvas.grid(column=0, row=1)

        # Configure ALT mode layout depending on hardware
        if zynthian_gui_config.check_wiring_layout(["V5", "TOUCH_ONLY"]):
            self.switch_i_clipboard = [11, 15]
            self.wsleds_i_clipboard = [10, 11]
            self.switch_i_block = 19
            self.wsled_i_block = 12
        elif zynthian_gui_config.check_wiring_layout(["Z2"]):
            self.switch_i_clipboard = [10, 11]
            self.wsleds_i_clipboard = [10, 11]
            self.switch_i_block = 12
            self.wsled_i_block = 12
        elif zynthian_gui_config.check_wiring_layout(["MCP23017"]):
            self.switch_i_clipboard = None
            self.wsleds_i_clipboard = None
            self.switch_i_block = 6
            self.wsled_i_block = None
        else:
            self.switch_i_clipboard = None
            self.wsleds_i_clipboard = None
            self.switch_i_block = None
            self.wsled_i_block = None

    # Function to get name of this view
    def get_name(self):
        return "pated base"

    # Function to set up behaviour of encoders
    def setup_zynpots(self):
        for i in range(zynthian_gui_config.num_zynpots):
            lib_zyncore.setup_behaviour_zynpot(i, 0)

    def get_title(self):
        seq_name = self.zynseq.get_sequence_name(self.zynseq.scene, self.phrase, self.sequence)
        #logging.debug(f"BANK: {bank}, SEQUENCE: {sequence}")
        if seq_name:
            try:
                synth_chain = self.zyngui.chain_manager.get_synth_chain(self.channel)
                chain_name = synth_chain.get_title()
            except:
                chain_name = ""
            if not chain_name:
                chain_name = f"MIDI-{self.channel + 1}"
            return f"{seq_name} {chain_name}"
        else:
            return f"Pattern {self.pattern}"

    def set_title(self, title=None, color_fg=None, color_bg=None, timeout=None):
        if not title:
            title = self.get_title()
        if not color_fg:
            color_fg = zynthian_gui_config.color_panel_tx
        if not color_bg:
            color_bg = zynthian_gui_config.color_header_bg
        super().set_title(title, color_fg, color_bg, timeout)

    def get_evnum_from_row(self, row):
        return row

    def get_row_from_evnum(self, num):
        return

    # Function to enable edit mode => It *MUST* be redefined in child class
    #   mode: Edit mode to enable [EDIT_MODE_NONE | others to define in child classes]
    def set_edit_mode(self, mode):
        self.edit_mode = mode
        color_fg = zynthian_gui_config.color_header_bg
        color_bg = zynthian_gui_config.color_panel_tx
        if mode == EDIT_MODE_SINGLE:
            #self.set_title("Note Parameters", color_fg, color_bg)
            self.set_edit_title()
        elif mode == EDIT_MODE_MULTI:
            #self.set_title("Note Parameters ALL", color_fg, color_bg)
            self.set_edit_title()
        elif self.edit_mode == EDIT_MODE_HISTORY:
            self.set_title("Undo/Redo", color_fg, color_bg)
        elif self.edit_mode == EDIT_MODE_BLOCK:
            if self.block_copied:
                self.set_title("Paste", color_fg, color_bg)
            else:
                self.set_title("Select Block", color_fg, color_bg)
                self.start_select_block()
        else:
            self.set_title()

    # Function to show GUI
    def build_view(self):
        self.zynseq.libseq.selectSequence(self.zynseq.scene, self.phrase, self.sequence)
        # Temporarily set sequence to loop - do not update cache which is used to restore configured state on hide
        self.zynseq.libseq.setSequenceRepeat(self.zynseq.scene, self.phrase, self.sequence, 255)

        self.setup_zynpots()
        if not self.param_editor_zctrl:
            self.set_title()

        self.toggle_midi_record(self.midi_record)
        self.redraw_pending = 4
        return True

    # Function to hide GUI
    def hide(self):
        if not self.shown:
            return
        self.toggle_midi_record(False)
        self.set_edit_mode(EDIT_MODE_NONE)
        #self.zynseq.libseq.setRefNote(int(self.keymap_offset))
        self.zynseq.libseq.setPatternZoom(self.zoom)
        if self.seq_info:
            # Restore sequence (was changed to looping mode for pattern editing)
            self.zynseq.libseq.setSequenceRepeat(self.zynseq.scene, self.phrase, self.sequence, self.seq_info["repeat"])
        else:
            self.stop_playback()
        self.zynseq.refresh_state()
        super().hide()

    # -------------------------------------------------------------------------
    # Pattern menu
    # -------------------------------------------------------------------------

    def get_pattern_length(self, beats=None, bpb=None):
        if beats is None:
            beats = self.zynseq.libseq.getBeatsInPattern(self.pattern)
        if bpb is None:
            bpb = 4
        if bpb > 1:
            bars = beats // bpb
        else:
            bars = 0
        extra_beats = beats % bpb

        if extra_beats == 0:
            beats_text = ""
        elif extra_beats == 1:
            beats_text = "1 beat"
        else:
            beats_text = f"{extra_beats} beats"
        if bars == 0:
            bars_text = ""
        elif bars == 1:
            bars_text = "1 bar"
        else:
            bars_text = f"{bars} bars"
        if bars and extra_beats:
            return f"{bars_text} + {beats_text}"
        else:
            return bars_text + beats_text

    def get_menu_options(self):
        menu_options = {}
        # Global Options
        # Sequence options
        if self.seq_info:
            options = {}
            name = self.seq_info["name"]
            repeat = self.seq_info["repeat"]
            # TODO: Configure start and stop modes
            if repeat > 0:
                if repeat == 255:
                    options["Play mode (LOOP)"] = "Playmode"
                elif repeat == 1:
                    options["Play mode (ONESHOT)"] = "Playmode"
                else:
                    options[f"Play mode (PLAY {repeat} TIMES)"] = "Playmode"
            else:
                options["Play mode (DISABLED)"] = "Playmode"
            program_change = self.zynseq.libseq.getProgramChange(0)
            if program_change > 127:
                program_change = "None"
            options[f"Program Change ({program_change})"] = 'Program Change'
            if name:
                options[f"Rename ({name})"] = 'Rename sequence'
            else:
                options[f"Rename"] = 'Rename sequence'
            menu_options['_SEQUENCE'] = options
        # Pattern Options
        options = {}
        if zynthian_gui_config.touch_navigation or zynthian_gui_config.layout["name"] == "V4":
            if self.get_name() == "pated note":
                options['Edit CC'] = 'Toggle Editor'
            else:
                options['Edit Notes'] = 'Toggle Editor'
        options[f"Length ({self.get_pattern_length()})"] = 'Length'
        options[f"Steps/Beat ({self.n_steps_beat})"] = 'Steps per beat'
        qn = self.zynseq.libseq.getQuantizeNotes()
        if qn <= 0:
            qval = "DISABLED"
        elif qn == 1:
            qval = "1 step"
        elif qn > 1:
            qval = f"1/{self.zynseq.libseq.getQuantizeNotes()} step"
        options[f"Quantization ({qval})"] = 'Quantization'
        options[f"Swing Amount ({int(100.0 * self.zynseq.libseq.getSwingAmount())}%)"] = 'Swing Amount'
        options[f"Swing Divisor ({self.zynseq.libseq.getSwingDiv()})"] = 'Swing Divisor'
        options[f"Time Humanization ({int(100.0 * self.zynseq.libseq.getHumanTime())})"] = 'Time Humanization'
        menu_options['PATTERN'] = options
        # Pattern Edit
        options = {}
        if not self.zyngui.multitouch._f_device:
            options['Grid zoom'] = 'Grid zoom'
        if self.seq_info:
            name = self.zynseq.get_sequence_name(self.zynseq.scene, self.phrase, self.sequence)
            options[f"Copy this ({name}) to clipboard#1"] = ('Copy pattern', 0)
            for i, paste in enumerate(self.clipboard):
                if paste is not None and paste[2] != self.pattern:
                    name = self.zynseq.get_sequence_name(self.zynseq.scene, paste[0], paste[1])
                    options[f"Paste {name} from clipboard#{i+1}"] = ('Paste pattern', i)
        options['Load pattern'] = 'Load pattern'
        options['Save pattern'] = 'Save pattern'
        options['Import from SMF'] = 'Import from SMF'
        options['Export to SMF'] = 'Export to SMF'
        options['Clear pattern ALL'] = 'Clear pattern ALL'
        menu_options['EDIT'] = options
        return menu_options

    # Function to add menus
    def show_menu(self):
        self.disable_param_editor()
        menu_options = self.get_menu_options()
        options = {}
        for subtitle, subopts in menu_options.items():
            if subtitle[0] != "_":
                options[f"> {subtitle}"] = None
            options.update(subopts)
        title = "Sequence options"
        if self.seq_info and self.seq_info["name"]:
            title += ": " + self.seq_info["name"]

        self.zyngui.screens['option'].config(title, options, self.menu_cb, index=self.get_last_menu_option())
        self.zyngui.show_screen('option')

    def toggle_menu(self):
        if self.shown:
            self.show_menu()
        elif self.zyngui.get_current_screen() == "option":
            self.zyngui.close_screen()

    def save_last_menu_option(self):
        self.last_menu_options[self.pattern] = self.zyngui.screens['option'].index

    def get_last_menu_option(self):
        try:
            return self.last_menu_options[self.pattern]
        except:
            return 0

    def menu_cb(self, option, params):
        #self.save_last_menu_option() => Include this in children classes
        if isinstance(params, str):
            param = params
        elif len(params) > 1:
            param = params[0]
        else:
            return
        match param:
            case 'Grid zoom':
                self.enable_param_editor(self, 'zoom', {'name': 'Zoom', 'value_min': 1, 'value_max': 64,
                                                        'value_default': 1, 'value': self.zoom})
            case 'Tempo':
                self.zyngui.show_screen('tempo')
            case 'Toggle Editor':
                self.zyngui.toggle_pated()
            case 'Length':
                labels = []
                n_beats = self.zynseq.libseq.getBeatsInPattern(self.pattern)
                for i in range(1, 65):
                    labels.append(self.get_pattern_length(i, self.bpb))
                self.enable_param_editor(self, 'bip', {'name': 'Length', 'value_min': 1, 'value_max': 64,
                                         'value_default': 4, 'labels': labels, 'value': n_beats},
                                         assert_cb=self.assert_beats_in_pattern)
            case 'Steps per beat':
                self.enable_param_editor(self, 'spb', {'name': 'Steps per beat', 'ticks': STEPS_PER_BEAT,
                                         'value_default': 3, 'value': self.n_steps_beat},
                                         assert_cb=self.assert_steps_per_beat)
            case 'Quantization':
                self.enable_param_editor(self, 'quantization', {'name': 'Quantization Divisor',
                                        'ticks': QUANTIZATION_DIVISORS, 'labels': QUANTIZATION_LABELS,
                                        'value': self.zynseq.libseq.getQuantizeNotes()})
            case 'Swing Amount':
                self.enable_param_editor(self, 'swing_amount', {'name': 'Swing Amount',
                                                                'value_min': 0, 'value_max': 100,
                                                                'value': int(100.0 * self.zynseq.libseq.getSwingAmount()),
                                                                'value_default': 0})
            case 'Swing Divisor':
                self.enable_param_editor(self, 'swing_div', {'name': 'Swing Divisor', 'value_min': 1,
                                                             'value_max': self.n_steps_beat, 'value_default': 1,
                                                             'value': self.zynseq.libseq.getSwingDiv()})
            case 'Time Humanization':
                self.enable_param_editor(self, 'human_time', {'name': 'Time Humanization', 'value_min': 0, 'value_max': 100,
                                                              'value': int(100.0 * self.zynseq.libseq.getHumanTime()),
                                                              'value_default': 0})
            case 'Record MIDI':
                self.toggle_midi_record()
            case 'Copy pattern':
                self.copy_pattern(params[1])
            case 'Paste pattern':
                self.paste_pattern(params[1])
            case 'Load pattern':
                self.zyngui.screens["file_selector"].config(self.load_pattern_file, fexts=["zpat"])
                self.zyngui.show_screen("file_selector")
            case 'Save pattern':
                self.zyngui.show_keyboard(self.save_pattern_file, "pattern_{}".format(self.pattern))
            case 'Import from SMF':
                try:
                    fpath = self.last_smf_import[self.pattern]
                except:
                    fpath = None
                self.zyngui.screens["file_selector"].config(self.analyze_smf, fexts=["mid"], path=fpath)
                self.zyngui.show_screen("file_selector")
            case 'Export to SMF':
                self.zyngui.show_keyboard(self.export_smf, "pattern_{}".format(self.pattern))
            case 'Clear pattern ALL':
                self.clear_pattern_all()

            # Sequence options
            case "Playmode":
                labels = ["DISABLED", "LOOP", "ONESHOT"]
                for i in range(2, 25):
                    labels.append(f"PLAY {i} TIMES")
                repeat = self.seq_info["repeat"]
                if repeat == 0:
                    value = 0  # disabled
                elif repeat == 255:
                    value = 1
                else:
                    value = 1 + repeat
                self.enable_param_editor(self, "playmode", {'name': 'Playmode', 'value': value, 'labels': labels},
                                         assert_cb=self.assert_playmode)
            case "Rename sequence":
                name = self.zynseq.get_sequence_name(self.zynseq.scene, self.phrase, self.sequence)
                self.zyngui.show_keyboard(self.rename_sequence, name, 8)
            case 'Program Change':
                program = self.zynseq.libseq.getProgramChange(0) + 1
                if program > 128:
                    program = 0
                labels = ["None"]
                for i in range(128):
                    labels.append(f"{i}")
                self.enable_param_editor(
                    self,
                    'prog_change',
                    {
                        'name': 'Program',
                        'labels': labels,
                        'value': program
                    }, self.add_program_change)

    def send_controller_value(self, zctrl):
        match zctrl.symbol:
            case 'zoom':
                self.set_grid_zoom(zctrl.value)
                self.param_editor_zctrl.value = self.zoom
            case 'quantization':
                self.zynseq.libseq.setQuantizeNotes(zctrl.value)
            case 'swing_amount':
                self.zynseq.libseq.setSwingAmount(zctrl.value / 100.0)
            case 'swing_div':
                self.zynseq.libseq.setSwingDiv(zctrl.value)
            case 'human_time':
                self.zynseq.libseq.setHumanTime(zctrl.value / 100.0)
            case 'copy':
                self.load_pattern(zctrl.value)

    # Function to assert steps per beat
    def assert_steps_per_beat(self, value):
        self.zyngui.show_confirm("Changing steps per beat may alter timing and/or lose notes?",
                                 self.set_steps_per_beat, value)

    # Function to actually change steps per beat
    def set_steps_per_beat(self, value):
        self.zynseq.libseq.setStepsPerBeat(value)
        self.zynseq.libseq.resetPatternSnapshots()
        self.n_steps_beat = self.zynseq.libseq.getStepsPerBeat()
        self.n_steps = self.zynseq.libseq.getSteps()
        self.update_geometry()
        self.redraw_pending = 4

    # Function to assert beats in pattern
    def assert_beats_in_pattern(self, value):
        if self.zynseq.libseq.getLastStep() >= self.zynseq.libseq.getStepsPerBeat() * value:
            self.zyngui.show_confirm("Reducing beats in pattern will truncate pattern",
                                     self.set_beats_in_pattern, value)
        else:
            self.set_beats_in_pattern(value)

    # Function to assert beats in pattern
    def set_beats_in_pattern(self, value):
        self.zynseq.libseq.setBeatsInPattern(self.pattern, value)
        self.zynseq.libseq.resetPatternSnapshots()
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
    # Sequence management
    # -------------------------------------------------------------------------

    def refresh_sequence_info(self):
        """
        Refresh local sequence info for launcher sequences
        """

        try:
            self.phrase = self.zynseq.phrase
            self.sequence = self.chain_manager.active_chain.midi_chan
            self.channel = self.chain_manager.active_chain.midi_chan
        except:
            self.phrase = 0
            self.sequence = 0
            self.channel = 0
        try:
            self.bpb = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][self.phrase]["bpb"]
        except:
            self.bpb = 0
        if self.bpb == 0:
            self.bpb = self.zynseq.bpb
        try:
            self.seq_info = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][self.phrase]["sequences"][self.sequence]
        except Exception as e:
            logging.error(f"Unable to refresh sequence info for pattern: {e}")
            self.seq_info = {}

    def update_sequence_params(self, params):
        for key in params:
            self.zynseq.set_sequence_param(self.zynseq.scene, self.phrase, self.sequence, key, self.seq_info[key])

    def update_sequence_info(self):
        for key, value in self.seq_info.items():
            self.zynseq.set_sequence_param(self.zynseq.scene, self.phrase, self.sequence, key, value)

    def assert_playmode(self, value):
        # Update the cache only so that we can assert on hide
        # Disable
        if value == 0:
            self.seq_info["repeat"] = 0
        # Loop
        elif value == 1:
            self.seq_info["repeat"] = 255
        # Oneshot/Repeat
        else:
            self.seq_info["repeat"] = value - 1

    def enable_sequence(self):
        if self.seq_info["repeat"] == 0:
            self.assert_playmode(1)
            self.update_sequence_params(["repeat"])

    def disable_sequence(self):
        if self.seq_info["repeat"] > 0:
            self.assert_playmode(0)
            self.update_sequence_params(["repeat"])

    def rename_sequence(self, name):
        self.zynseq.set_sequence_param(self.zynseq.scene, self.phrase, self.sequence, "name", name)
        self.set_title()

    # -------------------------------------------------------------------------
    # Pattern management
    # -------------------------------------------------------------------------

    # Function to load new pattern
    # index: Pattern index
    def load_pattern(self, index):
        # Save zoom value and vertical position in pattern object
        self.zynseq.libseq.setPatternZoom(self.zoom)
        # Load requested pattern
        self.zynseq.libseq.setChannel(self.zynseq.scene, self.phrase, self.sequence, 0, self.channel)
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
        self.draw_grid()
        self.select_cell()
        self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)
        self.set_title()
        self.set_grid_zoom(self.zynseq.libseq.getPatternZoom())

    def save_pattern_file(self, fname):
        fpath = f"{self.my_patterns_dpath}/{fname}.zpat"
        if os.path.exists(fpath):
            self.zyngui.show_confirm(f"Do you want to overwrite pattern file '{fname}'?",
                                     self.do_save_pattern_file, fpath)
        else:
            self.do_save_pattern_file(fpath)

    def do_save_pattern_file(self, fpath):
        self.zynseq.save_pattern(self.pattern, fpath)

    def load_pattern_file(self, fpath):
        if not self.zynseq.is_pattern_empty(self.pattern):
            self.zyngui.show_confirm(f"Do you want to overwrite pattern '{self.pattern}'?",
                                     self.do_load_pattern_file, fpath)
        else:
            self.do_load_pattern_file(fpath)

    def do_load_pattern_file(self, fpath):
        self.zynseq.load_pattern(self.pattern, fpath)
        self.load_pattern(self.pattern)
        # I don't understand why this is needed when steps/beat has changed
        n_beats = self.zynseq.libseq.getBeatsInPattern(self.pattern)
        self.zynseq.libseq.setBeatsInPattern(self.pattern, n_beats)
        # Reset pattern snapshots => No undo/redo after loading pattern!!
        self.zynseq.libseq.resetPatternSnapshots()
        self.changed = False

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

    # Function to clear all events on pattern (notes & CC)
    def clear_pattern_all(self, params=None):
        self.zyngui.show_confirm(f"Clear pattern {self.pattern}?", self.do_clear_pattern_all)

    # Function to actually clear pattern
    def do_clear_pattern_all(self, params=None):
        self.save_pattern_snapshot(now=True, force=False)
        self.zynseq.libseq.clearPattern(self.pattern)
        self.save_pattern_snapshot(now=True, force=True)
        self.redraw_pending = 3
        self.select_cell()
        if self.zynseq.libseq.getPlayState(self.phrase, self.sequence, 0) != zynseq.SEQ_STOPPED:
            self.zynseq.libseq.sendMidiCommand(0xB0 | self.channel, 123, 0)  # All notes off

    # Function to copy current pattern to clipboard
    def copy_pattern(self, i=0, src_info=None):
        if src_info is None or len(src_info) != 3:
            src_info = [self.phrase, self.sequence, self.pattern]
        try:
            self.clipboard[i] = (src_info[0], src_info[1], src_info[2])
        except:
            logging.error(f"Wrong clipboard index => {i}")

    # Function to paste pattern from clipboard
    def paste_pattern(self, i=0, dst_pattern=None):
        try:
            paste = self.clipboard[i]
        except:
            logging.error(f"Wrong clipboard index => {i}")
            return
        # Don't paste from None or over itself
        if paste is None or paste[2] == self.pattern:
            return
        # Overwriting an empty pattern doesn't need confirmation
        #if self.zynseq.libseq.getLastStep() == -1:
        if self.zynseq.libseq.isPatternEmpty(dst_pattern):
            self.do_paste_pattern([i, dst_pattern])
        # Overwriting a busy pattern does need confirmation!
        else:
            name = self.zynseq.get_sequence_name(self.zynseq.scene, paste[0], paste[1])
            self.zyngui.show_confirm(f"Overwrite this pattern with content from {name}?",
                                     self.do_paste_pattern, [i, dst_pattern])

    # Function to actually copy pattern
    def do_paste_pattern(self, params):
        i = params[0]
        dst_pattern = params[1]
        try:
            paste = self.clipboard[i]
        except:
            logging.error(f"Wrong clipboard index => {i}")
            return
        if dst_pattern is None:
            dst_pattern = self.pattern
        # Don't paste from None or over itself
        if paste is None or paste[2] == dst_pattern:
            return
        # Paste from clipboard to current pattern
        self.zynseq.libseq.copyPattern(paste[2], dst_pattern)
        if self.shown:
            self.load_pattern(dst_pattern)

    def analyze_smf(self, fpath):
        # Create SMF object and load file
        smf = zynsmf.libsmf.addSmf()
        if not zynsmf.load(smf, fpath):
            logging.error(f"Failed to load SMF file '{fpath}'")
            return
        event_count = zynsmf.libsmf.getEvents(smf, -1)
        if event_count == 0:
            logging.warning(f"Empty SMF file '{fpath}'")
            return
        logging.debug(f"Loaded SMF file ({event_count} events)")

        ticks_per_beat = zynsmf.libsmf.getTicksPerQuarterNote(smf)
        ticks_per_bar = self.bpb * ticks_per_beat
        start_time = end_time = None

        # Analyze channels
        event_index = 0
        midi_chan_info = [[0, None] for i in range(16)]       # [n_events, program] for each MIDI channel
        zynsmf.libsmf.setPosition(smf, 0)
        while zynsmf.libsmf.getEvent(smf, True):
            event_index += 1
            evtype = zynsmf.libsmf.getEventType()
            # MIDI event
            if evtype == 0x01:
                evstatus = zynsmf.libsmf.getEventStatus();
                evcode = (evstatus & 0xf0) >> 4
                evchan = evstatus & 0x0f
                evtime = zynsmf.libsmf.getEventTime()
                #logging.debug(f"\tEvent {event_index} => 0x{evstatus:02X}: 0x{evcode:X}, {evchan}")
                if evcode in (0x8, 0x9, 0xB):
                    # Count number of note-on events for each MIDI channel
                    midi_chan_info[evchan][0] += 1
                    # Look for first event time
                    if start_time is None:
                        start_bar = evtime // ticks_per_bar
                        start_time = start_bar * self.bpb * ticks_per_beat
                        logging.debug(f"\tStart at bar {start_bar} => {start_time} ticks.")
                elif evcode == 0xC:                                         # Get last program change message for each MIDI channel
                #elif evcode == 0xC and midi_chan_info[evchan][1] is None:  # Get first program change message for each MIDI channel
                    midi_chan_info[evchan][1] = zynsmf.libsmf.getEventValue1()
                # Get last event time
                if start_time is not None and evcode in (0x8, 0x9):
                    end_time = evtime

        # Calculate number of bars
        dtime = end_time - start_time
        n_bars = dtime // ticks_per_bar
        if (dtime % ticks_per_bar) / dtime > 0.1:
            n_bars += 1

        logging.info(f"SMF channel info => {midi_chan_info}")
        options = {}
        for chan, chan_info in enumerate(midi_chan_info):
            if chan_info[0] > 0:
                if chan == 9:
                    program_name = "Drums & Perc"
                    if chan_info[1] is not None:
                        try:
                            program_name += f" ({GM2_DRUMKITS[chan_info[1]]})"
                        except:
                            pass
                elif chan_info[1] is not None:
                    program_name = GM_INSTRUMENTS[chan_info[1]]
                else:
                    program_name = "???"
                options[f"CH {chan + 1}: {program_name}"] = f"{fpath}#{chan}"
        if len(options) > 1:
            self.zyngui.screens['option'].config("SMF Channels", options, self.import_smf_cb)
            self.zyngui.show_screen("option", hmode=self.zyngui.SCREEN_HMODE_NONE)
        elif len(options) == 1:
            opt = list(options.items())[0]
            self.import_smf_cb(opt[0], opt[1], n_bars)

    def import_smf_cb(self, chan_name, fpath, n_bars=None):
        # Parse file path and channel from received parameter
        try:
            parts = fpath.split("#")
            fpath = parts[0]
            self.last_smf_import[self.pattern] = fpath
            midi_chan = int(parts[1])
            logging.debug(f"{chan_name} => {fpath}, CH#{midi_chan} ({n_bars} bars)")
        except:
            logging.error(f"Error while importing SMF => {fpath}")
            return

        # Create SMF object and load file
        smf = zynsmf.libsmf.addSmf()
        if not zynsmf.load(smf, fpath):
            logging.error(f"Failed to load SMF file '{fpath}'")
            return
        event_count = zynsmf.libsmf.getEvents(smf, -1)
        if event_count == 0:
            logging.warning(f"Empty SMF file '{fpath}'")
            return

        # Change pattern length if needed
        if n_bars and n_bars != self.zynseq.libseq.getBeatsInPattern(self.pattern) / self.bpb:
            self.set_beats_in_pattern(min(n_bars, 16) * self.bpb)
        else:
            # If length not changed, ensure we can undo/redo
            self.save_pattern_snapshot(now=True, force=False)
        # TODO => Make undo/redo to work across changes of pattern length

        # Clear pattern
        self.zynseq.libseq.clearNotes()

        # Calculate timing parameters
        ticks_per_beat = zynsmf.libsmf.getTicksPerQuarterNote(smf)
        ticks_per_bar = self.bpb * ticks_per_beat
        ticks_per_step = ticks_per_beat / self.n_steps_beat
        beats_in_pattern = self.n_steps / self.n_steps_beat    # self.zynseq.bpb
        ticks_in_pattern = ticks_per_beat * beats_in_pattern
        logging.debug(f"Loaded SMF file ({event_count} events) => {ticks_per_beat} ticks/beat")

        # Do import
        start_time = None
        event_index = 0
        # Array of [time, velocity] indicating time that note on event received for matching note off and deriving duration
        note_on_info = [None] * 127
        zynsmf.libsmf.setPosition(smf, 0)
        while zynsmf.libsmf.getEvent(smf, True):
            event_index += 1
            evtype = zynsmf.libsmf.getEventType()
            # MIDI event
            if evtype == 0x01:
                evstatus = zynsmf.libsmf.getEventStatus();
                evchan = evstatus & 0x0f
                # Filter MIDI channel
                if evchan == midi_chan:
                    evcode = (evstatus & 0xf0) >> 4
                    evtime = zynsmf.libsmf.getEventTime()
                    #logging.debug(f"\tEvent {event_index} => 0x{evcode:X} at {evtime}")
                    if start_time is not None and evtime > (start_time + ticks_in_pattern):
                        logging.debug(f"\tReached end of pattern at {evtime - start_time}!")
                        break
                    if evcode in (0x8, 0x9, 0xB):
                        # Calculate start time (first event)
                        if start_time is None:
                            start_bar = evtime // ticks_per_bar
                            start_time = start_bar * self.bpb * ticks_per_beat
                            logging.debug(f"\tStart at bar {start_bar} => {start_time} ticks.")
                        if evcode == 0xB:
                            ccnum = zynsmf.libsmf.getEventValue1()
                            ccval = zynsmf.libsmf.getEventValue2()
                            step = int((evtime - start_time) / ticks_per_step)
                            self.zynseq.libseq.addControl(step, ccnum, ccval, ccval, 1, 0)
                        else:
                            note = zynsmf.libsmf.getEventValue1()
                            velo = zynsmf.libsmf.getEventValue2()
                            if evcode == 0x9 and velo:
                                #logging.debug(f"\tNote-on at {evtime} => {note}, {velo}")
                                # Register Note-On
                                note_on_info[note] = [evtime, velo]
                            else:
                                #logging.debug(f"\tNote-off at {evtime} => {note}, {velo}")
                                ninfo = note_on_info[note]
                                if ninfo:
                                    # Add note to pattern
                                    fstep = (ninfo[0] - start_time) / ticks_per_step
                                    step = int(fstep)
                                    duration = (evtime - ninfo[0]) / ticks_per_step
                                    offset = fstep - step
                                    self.zynseq.libseq.addNote(step, note, ninfo[1], duration, offset)
                                    logging.debug(f"\tAdd Note {note}, {ninfo[1]} => {step} + {offset}, {duration}")
                                    note_on_info[note] = None
        # TODO Off pending notes?
        # Save state for undo/redo
        self.save_pattern_snapshot(now=True, force=True)
        # Clean SMF object
        zynsmf.libsmf.removeSmf(smf)
        # Refresh view
        self.redraw_pending = 4

    def export_smf(self, fname):
        fpath = f"{self.my_smf_dpath}/{fname}.mid"
        if os.path.exists(fpath):
            self.zyngui.show_confirm(f"Do you want to overwrite SMF file '{fname}'?",
                                     self.do_export_smf, fpath)
        else:
            self.do_export_smf(fpath)

    # Function to export pattern to SMF
    def do_export_smf(self, fpath):
        smf = zynsmf.libsmf.addSmf()
        tempo = self.zynseq.libseq.getTempo()
        zynsmf.libsmf.addTempo(smf, 0, tempo)
        ticks_per_step = zynsmf.libsmf.getTicksPerQuarterNote(smf) / self.n_steps_beat
        for step in range(self.n_steps):
            time = int(step * ticks_per_step)
            for note in range(128):
                duration = self.zynseq.libseq.getNoteDuration(step, note)
                if duration == 0.0:
                    continue
                duration = int(duration * ticks_per_step)
                velocity = self.zynseq.libseq.getNoteVelocity(step, note)
                zynsmf.libsmf.addNote(smf, 0, time, duration, self.channel, note, velocity)
        zynsmf.libsmf.setEndOfTrack(smf, 0, int(self.n_steps * ticks_per_step))
        zynsmf.save(smf, fpath)

    # Function to add program change at start of pattern
    def add_program_change(self, value):
        value -= 1
        if value < 0 or value > 127:
            self.zynseq.libseq.removeProgramChange(0, value)
        else:
            self.zynseq.libseq.addProgramChange(0, value)

    def toggle_midi_record(self, midi_record=None):
        if midi_record is None:
            midi_record = not self.midi_record
            self.midi_record = midi_record
        self.zynseq.libseq.enableMidiRecord(midi_record)
        self.save_pattern_snapshot(now=True, force=False)

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
            return 0
        self.piano_roll_drag_count += 1
        offset = int(DRAG_SENSIBILITY * (event.y - self.piano_roll_drag_start.y) / self.row_height)
        if offset == 0:
            return 0
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

    # Function to handle grid mouse drag
    # event: Mouse event
    def on_grid_wheel(self, event):
        if event.num == 4:
            self.set_grid_zoom(self.zoom + 1)
        else:
            self.set_grid_zoom(self.zoom - 1)

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

    def on_size(self, event=None):
        super().on_size()
        self.update_geometry()
        self.update_grid_position(True, True)
        self.redraw_pending = 4

    # Function to calculate variable gemoetry parameters
    def update_geometry(self):
        # Width & height
        self.grid_height = self.height - PLAYHEAD_HEIGHT
        self.grid_width = int(self.width * 0.91)
        self.total_width = self.n_steps * self.step_width
        self.total_height = 128 * self.row_height
        self.scroll_height = self.total_height - self.grid_height
        # Base cell size
        self.base_row_height = self.grid_height // self.DEFAULT_VIEW_ROWS
        if self.n_steps:
            self.base_step_width = self.grid_width // min(self.DEFAULT_VIEW_STEPS, self.n_steps)
        else:
            self.base_step_width = self.grid_width // self.DEFAULT_VIEW_STEPS
        # Font size
        self.fontsize_grid = self.row_height // 2
        if self.fontsize_grid > 20:
            self.fontsize_grid = 20  # Ugly font scale limiting
        self.grid_font = tkfont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize_grid)
        self.calculate_geometry_limits()
        self.update_scroll_regions()

    def calculate_geometry_limits(self):
        # Row height limits
        self.max_row_height = self.grid_height // 6
        self.min_row_height = self.grid_height // min(36, max(6, self.n_rows))

        # Step width limits
        self.max_step_width = self.grid_width // 8
        self.min_step_width = self.grid_width // min(64, max(8, self.n_steps))

        #logging.debug(f"N_STEPS={self.n_steps}")
        #logging.debug(f"ROW: MAX={self.max_row_height}, MIN={self.min_row_height}")
        #logging.debug(f"STEP: MAX={self.max_step_width}, MIN={self.min_step_width}")

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
        if self.n_steps < int(self.view_steps):
            self.step_offset = 0
        elif self.step_offset > self.n_steps - int(self.view_steps):
            self.step_offset = self.n_steps - int(self.view_steps)
        elif self.step_offset < 0:
            self.step_offset = 0
        if self.total_width > 0:
            xpos = self.step_offset * self.step_width / self.total_width
        else:
            xpos = 0
        self.grid_canvas.xview_moveto(xpos)
        self.play_canvas.xview_moveto(xpos)
        #logging.debug(f"OFFSET: {self.step_offset} (NSTEPS: {self.n_steps}, TOTAL WIDTH: {self.total_width})")
        #logging.debug(f"GRID X-SCROLL: {xpos}\n\n")

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
        if not step_width_changed:
            self.zoom = self.row_height - self.base_row_height
            #logging.debug(f"VZOOM! => {self.zoom}")
        elif not row_height_changed:
            self.zoom = self.step_width - self.base_step_width
            #logging.debug(f"HZOOM! => {self.zoom}")
        else:
            hzoom = self.step_width - self.base_step_width
            vzoom = self.row_height - self.base_row_height
            if abs(hzoom) > abs(vzoom):
                self.zoom = hzoom
            else:
                self.zoom = vzoom
            #logging.debug(f"ZOOM! => {self.zoom} (hzoom={hzoom}, vzoom={vzoom})")
        #self.zoom = new_zoom

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
        self.select_cell()
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
        self.view_rows = self.grid_height // self.row_height
        self.view_steps = self.grid_width // self.step_width

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

    def get_cell_pos(self, cell):
        x1 = int(cell[0] * self.step_width) + 1
        y1 = self.total_height - (cell[1] + 1) * self.row_height + 1
        return [x1, y1]

    # -------------------------------------------------------------------------
    # Drawing functions
    # -------------------------------------------------------------------------

    # Function to draw grid
    def draw_grid(self):
        if self.drawing:
            return
        self.drawing = True

        if self.n_steps == 0:
            self.redraw_pending = 0
            self.drawing = False
            return  # TODO: Should we clear grid?

        self.redraw_grid_pending()
        self.redraw_pending = 0
        self.select_cell()
        self.drawing = False

    def redraw_grid_pending(self):
        # Draw cells of grid
        # self.grid_canvas.itemconfig("gridcell", fill="black")
        if self.redraw_pending > 3:
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
                        beatnum = step // self.n_steps_beat
                        rest_beatnum = beatnum % self.bpb
                        if rest_beatnum == 0:
                            self.grid_canvas.create_line(xpos, 0, xpos, lh, fill=GRID_LINE_XTRONG, tags="gridvline")
                        else:
                            self.grid_canvas.create_line(xpos, 0, xpos, lh, fill=GRID_LINE_STRONG, tags="gridvline")
                        if step < self.n_steps:
                            if beatnum == 0:
                                anchor = tkinter.NW
                            else:
                                anchor = tkinter.N
                            self.play_canvas.create_text(xpos, -2, text=str(beatnum + 1), font=bnum_font, anchor=anchor,
                                                         fill=GRID_LINE_STRONG, tags="beatnum")
                    else:
                        self.grid_canvas.create_line(xpos, 0, xpos, lh, fill=GRID_LINE_WEAK, tags="gridvline")
                        self.play_canvas.create_line(xpos, 0, xpos, th, fill=PLAYHEAD_LINE, tags="beatnum")

    # Function to draw pianoroll content
    def draw_pianoroll(self):
        #self.piano_roll.delete(tkinter.ALL)
        pass

    def pianoroll_set_row(self, row, color=None):
        pass

    def pianoroll_note_on(self, note):
        pass

    def pianoroll_note_off(self, note):
        pass

    def draw_events(self):
        pass

    def draw_cp_events(self):
        pass

    def draw_event(self, evdata, cp=False, row=None):
        pass

    def draw_row(self, row):
        pass

    # Function to draw a grid cell
    # step: Step (column) index
    # row: Index of row
    def draw_cell(self, step, row):
        pass

    # Function to update selectedCell
    # step: Step (column) of selected cell (Optional - default to reselect current column)
    # row: Index of keymap to select (Optional - default to reselect current row).
    #      Maybe outside visible range to scroll display
    # plot: plot cursor (True by default)
    def select_cell(self, step=None, row=None):
        pass

    def hide_selected_cell(self):
        if self.rect_selected_cell:
            self.grid_canvas.delete(self.rect_selected_cell)
            self.rect_selected_cell = None

    # ---------------------------------------------------------------
    # Block edit functionality => Copy/paste block
    # ---------------------------------------------------------------

    def _move_cell(self, cell, dstep, drow):
        inrange = True
        if dstep:
            cell[0] += dstep
            if cell[0] >= self.n_steps:
                cell[0] = self.n_steps - 1
                inrange = False
            elif cell[0] < 0:
                cell[0] = 0
                inrange = False
        if drow:
            cell[1] += drow
            if cell[1] > 127:
                cell[1] = 127
                inrange = False
            elif cell[1] < 0:
                cell[1] = 0
                inrange = False
        return inrange

    def plot_select_block(self):
        # Plot rectangle
        coord = self.get_cell_pos(self.block_cell_start) + self.get_cell_pos(self.block_cell_end)
        if coord[2] >= coord[0]:
            coord[2] += self.step_width
        else:
            coord[0] +=  self.step_width
        if coord[3] >= coord[1]:
            coord[3] += self.row_height
        else:
            coord[1] += self.row_height
        if not self.rect_selected_block:
            self.rect_selected_block = self.grid_canvas.create_rectangle(coord, fill="", outline=SELECT_BORDER,
                                              width=self.select_thickness, tags="selected_block")
        else:
            self.grid_canvas.coords(self.rect_selected_block, coord)

    def start_select_block(self):
        self.clean_selected_events()
        self.block_copied = None
        self.block_cell_start = copy.copy(self.selected_cell)
        self.block_cell_end = copy.copy(self.selected_cell)
        self.select_block(0, 0)

    def end_select_block(self):
        self.clean_selected_events()
        self.block_copied = None
        self.set_edit_mode(EDIT_MODE_NONE)
        self.select_cell()

    def select_block(self, dstep, drow):
        # Move end position
        self._move_cell(self.block_cell_end, dstep, drow)
        # Hide cursor
        self.hide_selected_cell()
        # Position cursor (hidden)
        self.select_cell(self.block_cell_end[0], self.block_cell_end[1])
        # Plot
        self.plot_select_block()

    def select_block_all(self):
        # Get all events indexed by "step/note"" key
        self.selected_events = self.zynseq.get_pattern_selection(self.pattern, 0, self.n_steps, 0, 127)
        # Get row range
        row_min = 127
        row_max = 0
        for ev_key in self.selected_events:
            note = ev_key // zynseq.MAX_STEPS_PATTERN
            row = self.get_row_from_note(note)
            if row > row_max:
                row_max = row
            if row < row_min:
                row_min = row
        # Select minimum vertical area containing all notes
        self.block_cell_start = [0, row_max]
        self.block_cell_end = [self.n_steps - 1, row_min]
        # Plot
        self.plot_select_block()
        # Highlight selected notes color
        self.redraw_pending = 3

    def hide_selected_block(self):
        if self.rect_selected_block:
            self.grid_canvas.delete(self.rect_selected_block)
            self.rect_selected_block = None

    def clean_selected_events(self):
        if self.selected_events:
            self.selected_events = None
            self.redraw_pending = 3

    # End block selection
    def _end_block_selection(self):
        if self.block_cell_end[0] > self.block_cell_start[0]:
            step1 = self.block_cell_start[0]
            step2 = self.block_cell_end[0]
        else:
            step1 = self.block_cell_end[0]
            step2 = self.block_cell_start[0]
        if self.block_cell_end[1] >= self.block_cell_start[1]:
            row1 = self.block_cell_start[1]
            row2 = self.block_cell_end[1]
        else:
            row1 = self.block_cell_end[1]
            row2 = self.block_cell_start[1]
        self.block_cell_start = [step1, row1]
        self.block_cell_end = [step2, row2]

    def copy_block(self, cut=False):
        self._end_block_selection()
        # if cutting => save snapshot
        if cut:
            self.save_pattern_snapshot(True, False)
            self.selected_events = None
            self.changed = True
        # Copy/Cut subpattern to clipboard
        n = self.zynseq.libseq.copyPatternBuffer(self.pattern,
                                                 self.block_cell_start[0], self.block_cell_end[0],
                                                 self.get_evnum_from_row(self.block_cell_start[1]),
                                                 self.get_evnum_from_row(self.block_cell_end[1]),
                                                 cut)
        # If selection is empty => end select mode
        if n == 0:
            self.end_select_block()
            return
        # If selection is not empty => save block coordinates
        self.block_copied = [self.block_cell_start, self.block_cell_end]
        self.block_dstep = 0
        self.block_drow = 0
        # Hide select block and plot copied notes
        self.set_edit_mode(EDIT_MODE_BLOCK)
        self.hide_selected_block()
        self.draw_cp_events()
        # Redraw pattern notes
        if cut:
            self.redraw_pending = 3

    def select_block_events(self):
        self._end_block_selection()
        # Get selected events indexed by "step/note"" key
        self.selected_events = self.zynseq.get_pattern_selection(self.pattern,
                                           self.block_cell_start[0], self.block_cell_end[0],
                                           self.get_evnum_from_row(self.block_cell_start[1]),
                                           self.get_evnum_from_row(self.block_cell_end[1]))

        #logging.debug(f"SELECTED EVENTS => {self.selected_events}")

        # If selection is empty => end select mode
        #if not self.selected_events:
        #    self.end_select_block()
        #    return

        # Replot to highlight selected events
        self.redraw_pending = 3

    def select_all_events(self):
        # Get all events indexed by "step/note"" key
        self.selected_events = self.zynseq.get_pattern_selection(self.pattern, 0, self.n_steps, 0, 127)
        self.redraw_pending = 3

    def move_block(self, dstep, drow):
        # Calculate new position
        pos1 = copy.copy(self.block_cell_start)
        pos2 = copy.copy(self.block_cell_end)
        # Respect vertical limits, but allow horizontal overflow
        if self._move_cell(pos1, 0, drow) and self._move_cell(pos2, 0, drow):
            pos1[0] += dstep
            pos2[0] += dstep
            # Horizontal circular move
            if pos1[0] >= self.n_steps:
                pos1[0] -= self.n_steps
                pos2[0] -= self.n_steps
            elif pos2[0] < 0:
                pos1[0] += self.n_steps
                pos2[0] += self.n_steps
            self.block_cell_start = pos1
            self.block_cell_end = pos2
            # Calculate position offset => current position - copy position
            self.block_dstep = self.block_cell_start[0] - self.block_copied[0][0]
            self.block_drow = self.block_cell_start[1] - self.block_copied[0][1]
            # Redraw copied notes in the new position
            self.draw_cp_events()
            # Position cursor (hidden) to center view area (scroll)
            if dstep > 0:
                step = self.block_cell_end[0]
            else:
                step = self.block_cell_start[0]
            if drow > 0:
                row = self.block_cell_end[1]
            else:
                row = self.block_cell_start[1] + 1
            self.select_cell(step, row)

    def paste_block(self):
        # Save snapshot
        self.save_pattern_snapshot(True, False)
        # Paste buffer
        self.zynseq.libseq.pastePatternBuffer(self.pattern, self.block_dstep, 0.0, self.block_drow, False)  # truncate=False to use horizontal circular overflow
        self.changed = True
        self.redraw_pending = 3

    # -------------------------------------------------------------------------
    # Event management
    # -------------------------------------------------------------------------

    def plot_zctrls(self):
        self.swipe_update()

    # Function to toggle event
    # step: step number (column)
    # row: row index
    # Returns: Event number if event added else None
    def toggle_event(self, step, row):
        pass

    # Function to remove an event
    # step: step number (column)
    # row: row index
    def remove_event(self, step, row):
        pass

    # Function to refresh status
    def refresh_status(self):
        super().refresh_status()
        self.playstate = self.zynseq.libseq.getSequenceState(self.zynseq.scene, self.phrase, self.sequence) & 0xff
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

    # Function to handle zynpots value change
    #   i: Zynpot index [0..n]
    #   dval: Current value of zyncoder
    def zynpot_cb(self, i, dval):
        # This will be called in the child class
        #if super().zynpot_cb(i, dval):
        #    return True
        if i == self.ctrl_order[1]:
            #if self.edit_mode == EDIT_MODE_NONE:
            self.set_grid_zoom(self.zoom + dval)
            return True
        elif i == self.ctrl_order[2]:
            if self.edit_mode == EDIT_MODE_BLOCK:
                if self.block_copied:
                    self.move_block(0, -dval)
                else:
                    self.select_block(0, -dval)
                return True
            elif self.edit_mode == EDIT_MODE_NONE:
                self.select_cell(None, self.selected_cell[1] - dval)
                return True
        elif i == self.ctrl_order[3]:
            if self.edit_mode == EDIT_MODE_HISTORY:
                if dval > 0:
                    self.redo_pattern()
                else:
                    self.undo_pattern()
                return True
            elif self.edit_mode == EDIT_MODE_BLOCK:
                if self.block_copied:
                    self.move_block(dval, 0)
                else:
                    self.select_block(dval, 0)
                return True
            elif self.edit_mode == EDIT_MODE_NONE:
                self.select_cell(self.selected_cell[0] + dval, None)
                return True

    # Function to handle SELECT button press
    #   st: Button press duration [S=Short, B=Bold, L=Long]
    def switch_select(self, st='S'):
        if super().switch_select(st):
            return
        if st == "S":
            if self.edit_mode == EDIT_MODE_NONE:
                self.toggle_event(self.selected_cell[0], self.selected_cell[1])
            elif self.edit_mode == EDIT_MODE_BLOCK:
                if not self.block_copied:
                    self.copy_block(cut=False)
                else:
                    self.paste_block()
            else:
                self.set_edit_mode(EDIT_MODE_NONE)
        elif st == "B":
            if self.edit_mode == EDIT_MODE_NONE:
                if self.selected_events:
                    self.set_edit_mode(EDIT_MODE_MULTI)
                else:
                    self.set_edit_mode(EDIT_MODE_SINGLE)
            elif self.edit_mode == EDIT_MODE_BLOCK:
                if not self.block_copied:
                    self.select_block_events()
                if self.selected_events:
                    self.set_edit_mode(EDIT_MODE_MULTI)
                else:
                    self.set_edit_mode(EDIT_MODE_NONE)

    # Function to handle switch press
    #   i: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
    #   st: Press type [S=Short, B=Bold, L=Long]
    #   returns True if action fully handled or False if parent action should be triggered
    def switch(self, i, st):
        logging.debug(f"SWITCH {i} == {self.switch_i_block}")

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

        # Configured F button for block selection workflow
        elif i == self.switch_i_block:
            return self.cuia_v5_zynpot_switch([2, st])

        # ALT mode => Use configured F buttons as copy/paste buttons
        elif self.alt_mode and self.switch_i_clipboard is not None and i in self.switch_i_clipboard:
            index = self.switch_i_clipboard.index(i)
            if st == "S":
                self.paste_pattern(index)
                return True
            elif st == "B":
                self.copy_pattern(index)
                return True
        return False

    def cuia_v5_zynpot_switch(self, params):
        i = params[0]
        t = params[1].upper()
        if i == 0:
            if t == 'S' or t == 'B':
                self.zyngui.toggle_pated()
                return True
        elif i == 1:
            if t == 'S':
                self.reset_grid_zoom()
                return True
            elif t == 'B':
                self.menu_cb("Length", "Length")
        elif i == 2:
            if t == 'S':
                if self.edit_mode == EDIT_MODE_NONE:
                    self.set_edit_mode(EDIT_MODE_BLOCK)
                    return True
                elif self.edit_mode == EDIT_MODE_BLOCK:
                    if not self.block_copied:
                        self.copy_block(cut=True)
                    return True
            elif t == 'B':
                #self.select_all_events()
                #self.set_edit_mode(EDIT_MODE_MULTI)
                if self.edit_mode == EDIT_MODE_NONE:
                    self.set_edit_mode(EDIT_MODE_BLOCK)
                self.select_block_all()
                return True
        return False

    # Function to handle BACK button
    def back_action(self):
        if self.edit_mode == EDIT_MODE_NONE:
            if self.selected_events:
                self.clean_selected_events()
                return True
            else:
                self.zynseq.libseq.updateSequenceInfo()
                return super().back_action()
        elif self.edit_mode == EDIT_MODE_BLOCK:
            self.end_select_block()
            return True
        elif self.edit_mode == EDIT_MODE_MULTI:
            self.set_edit_mode(EDIT_MODE_NONE)
            return True
        else:
            self.set_edit_mode(EDIT_MODE_NONE)
            return True

    # CUIA Actions

    # Function to handle CUIA ARROW_RIGHT
    def arrow_right(self):
        if not self.param_editor_zctrl and ((self.alt_mode and self.edit_mode == EDIT_MODE_NONE) or self.edit_mode == EDIT_MODE_HISTORY):
            self.redo_pattern()
        else:
            self.zynpot_cb(self.ctrl_order[3], 1)

    # Function to handle CUIA ARROW_LEFT
    def arrow_left(self):
        if not self.param_editor_zctrl and ((self.alt_mode and self.edit_mode == EDIT_MODE_NONE) or self.edit_mode == EDIT_MODE_HISTORY):
            self.undo_pattern()
        else:
            self.zynpot_cb(self.ctrl_order[3], -1)

    # Function to handle CUIA ARROW_UP
    def arrow_up(self):
        if super().arrow_up():
            return
        elif (self.alt_mode and self.edit_mode == EDIT_MODE_NONE) or self.edit_mode == EDIT_MODE_HISTORY:
            self.redo_pattern_all()
        elif self.edit_mode in (EDIT_MODE_SINGLE, EDIT_MODE_MULTI):
            self.zynpot_cb(self.ctrl_order[2], 1)
        else:
            self.zynpot_cb(self.ctrl_order[2], -1)

    # Function to handle CUIA ARROW_DOWN
    def arrow_down(self):
        if super().arrow_down():
            return
        elif (self.alt_mode and self.edit_mode == EDIT_MODE_NONE) or self.edit_mode == EDIT_MODE_HISTORY:
            self.undo_pattern_all()
        elif self.edit_mode in (EDIT_MODE_SINGLE, EDIT_MODE_MULTI):
            self.zynpot_cb(self.ctrl_order[2], -1)
        else:
            self.zynpot_cb(self.ctrl_order[2], 1)

    def start_playback(self):
        # Set to start of pattern - work around for timebase issue in library.
        self.zynseq.libseq.setSequencePlayPosition(self.zynseq.scene, self.phrase, self.sequence, 0)
        self.zynseq.libseq.setPlayState(self.zynseq.scene, self.phrase, self.sequence, zynseq.SEQ_STARTING)

    def stop_playback(self):
        self.zynseq.libseq.setPlayState(self.zynseq.scene, self.phrase, self.sequence, zynseq.SEQ_STOPPED)

    def toggle_playback(self):
        if self.zynseq.libseq.getPlayState(self.zynseq.scene, self.phrase, self.sequence) == zynseq.SEQ_STOPPED:
            self.start_playback()
        else:
            self.stop_playback()

    def get_playback_status(self):
        return self.zynseq.libseq.getPlayState(self.zynseq.scene, self.phrase, self.sequence)

    # -------------------------------------------------------------------------
    # CUIA & LEDs methods
    # -------------------------------------------------------------------------

    def get_alt_mode(self):
        return self.alt_mode

    def cuia_toggle_alt_mode(self, params=None):
        self.alt_mode = not self.alt_mode
        return True

    def cuia_toggle_record(self, params=None):
        self.toggle_midi_record()
        return True

    def cuia_stop(self, params=None):
        self.stop_playback()
        return True

    def cuia_toggle_play(self, params=None):
        self.toggle_playback()
        return True

    def cuia_copy(self, params=None):
        self.copy_pattern(int(params[0]))
        return True

    def cuia_paste(self, params=None):
        self.paste_pattern(int(params[0]))
        return True

    def update_wsleds(self, leds):
        wsl = self.zyngui.wsleds

        # ALT mode
        if self.alt_mode:
            # ALT button
            wsl.set_led(leds[0], wsl.wscolor_active2)

            if self.wsleds_i_clipboard:
                # Copy/paste buttons
                for i, wsli in enumerate(self.wsleds_i_clipboard):
                    if self.clipboard[i] is not None:
                        if self.clipboard[i][2] == self.pattern:
                            wsl.blink(leds[wsli], wsl.wscolor_red)
                        else:
                            wsl.blink(leds[wsli], wsl.wscolor_active2)
                    else:
                        wsl.set_led(leds[wsli], wsl.wscolor_active2)

        # F3 => Block Selection
        if self.wsled_i_block is not None:
            if self.edit_mode == EDIT_MODE_BLOCK:
                if self.block_copied:
                    wsl.blink(leds[self.wsled_i_block], wsl.wscolor_active)
                else:
                    wsl.blink(leds[self.wsled_i_block], wsl.wscolor_active2)
            else:
                wsl.set_led(leds[self.wsled_i_block], wsl.wscolor_active2)

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
        elif pb_status == zynseq.SEQ_STARTING:
            wsl.set_led(leds[3], wsl.wscolor_yellow)
        elif pb_status in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPING_SYNC):
            wsl.set_led(leds[3], wsl.wscolor_red)
        elif pb_status == zynseq.SEQ_STOPPED:
            wsl.set_led(leds[3], wsl.wscolor_active2)
        # Arrow buttons
        if not self.param_editor_zctrl and ((self.alt_mode and self.edit_mode == EDIT_MODE_NONE) or self.edit_mode == EDIT_MODE_HISTORY):
            wsl.set_led(leds[4], wsl.wscolor_active2)
            wsl.set_led(leds[5], wsl.wscolor_active2)
            wsl.set_led(leds[6], wsl.wscolor_active2)
            wsl.set_led(leds[7], wsl.wscolor_active2)

# ------------------------------------------------------------------------------
