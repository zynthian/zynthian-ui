#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pattern Editor Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
import json
import tkinter
import logging
from math import ceil
from queue import Queue
from xml.dom import minidom
from datetime import datetime
import tkinter.font as tkFont

# Zynthian specific modules
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq
from zynlibs.zynsmf import zynsmf
from . import zynthian_gui_base
from zyngui import zynthian_gui_config
from zyngui.multitouch import MultitouchTypes


# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern Editor GUI Class
# ------------------------------------------------------------------------------

# Local constants
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bd
GRID_LINE_WEAK		= zynthian_gui_config.color_panel_bg
GRID_LINE_STRONG	= zynthian_gui_config.color_tx_off
PLAYHEAD_BACKGROUND	= zynthian_gui_config.color_variant(zynthian_gui_config.color_panel_bd, 40)
PLAYHEAD_LINE 		= zynthian_gui_config.color_tx_off
PLAYHEAD_HEIGHT		= 12
CONFIG_ROOT			= "/zynthian/zynthian-data/zynseq"

DEFAULT_VZOOM		= 16
DEFAULT_HZOOM		= 16
DRAG_SENSIBILITY	= 1.5
SAVE_SNAPSHOT_DELAY	= 5

EDIT_MODE_NONE		= 0  # Edit mode disabled
EDIT_MODE_SINGLE	= 1  # Edit mode enabled for selected note
EDIT_MODE_ALL		= 2  # Edit mode enabled for all notes
EDIT_MODE_SCALE		= 3  # Edit mode enabled for all notes
EDIT_PARAM_DUR		= 0  # Edit note duration
EDIT_PARAM_VEL		= 1  # Edit note velocity
EDIT_PARAM_OFFSET	= 2  # Edit note offset
EDIT_PARAM_STUT_CNT	= 3  # Edit note stutter count
EDIT_PARAM_STUT_DUR	= 4  # Edit note stutter duration
EDIT_PARAM_CHANCE	= 5  # Edit note play chance
EDIT_PARAM_LAST		= 5  # Index of last parameter

# List of permissible steps per beat
STEPS_PER_BEAT = [1, 2, 3, 4, 6, 8, 12, 24]
INPUT_CHANNEL_LABELS = ['OFF', 'ANY', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# -----------------------------------------------------------------------------
# Class implements step sequencer pattern editor
# -----------------------------------------------------------------------------


class zynthian_gui_patterneditor(zynthian_gui_base.zynthian_gui_base):

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

		self.status_canvas.bind("<ButtonRelease-1>", self.cb_status_release)

		self.ctrl_order = zynthian_gui_config.layout['ctrl_order']

		self.title = "Pattern 0"
		self.edit_mode = EDIT_MODE_NONE  # Enable encoders to adjust note parameters
		self.edit_param = EDIT_PARAM_DUR  # Parameter to adjust in parameter edit mode
		self.vzoom = DEFAULT_VZOOM  # Quantity of rows (notes) displayed in grid
		self.hzoom = DEFAULT_HZOOM  # Quantity of columns (steps) displayed in grid
		self.duration = 1.0  # Current note entry duration
		self.velocity = 100  # Current note entry velocity
		self.copy_source = 1  # Index of pattern to copy
		self.bank = None  # Bank used for pattern editor sequence player
		self.pattern = 0  # Pattern to edit
		self.sequence = None  # Sequence used for pattern editor sequence player
		self.last_play_mode = zynseq.SEQ_LOOP
		self.playhead = 0
		self.playstate = zynseq.SEQ_STOPPED
		self.n_steps = 0  # Number of steps in current pattern
		self.n_steps_beat = 0  # Number of steps per beat (current pattern)
		self.keymap_offset = 60  # MIDI note number of bottom row in grid
		self.step_offset = 0  # Step number of left column in grid
		self.selected_cell = [0, 60]  # Location of selected cell (column,row)
		self.keymap = []  # Array of {"note":MIDI_NOTE_NUMBER, "name":"key name","colour":"key colour"} name and colour are optional
		self.reload_keymap = False  # Signal keymap needs reloading
		self.cells = []  # Array of cells indices
		self.redraw_pending = 4  # What to redraw: 0=nothing, 1=selected cell, 2=selected row, 3=refresh grid, 4=rebuild grid
		self.rows_pending = Queue()
		self.channel = 0
		self.drawing = False  # mutex to avoid concurrent screen draws
		self.changed = False
		self.changed_ts = 0

		self.swiping = 0
		self.swipe_friction = 0.8
		self.swipe_step_dir = 0
		self.swipe_row_dir = 0
		self.swipe_step_speed = 0
		self.swipe_row_speed = 0
		self.swipe_step_offset = 0
		self.swipe_row_offset = 0
		self.grid_drag_start = None  # Coordinates at start of grid drag
		self.drag_start_velocity = None  # Velocity value at start of drag
		self.drag_note = False  # True if dragging note in grid
		self.drag_velocity = False  # True indicates drag will adjust velocity
		self.drag_duration = False  # True indicates drag will adjust duration

		# Geometry vars
		self.select_thickness = 1 + int(self.width / 500)  # Scale thickness of select border based on screen resolution
		self.grid_height = self.height - PLAYHEAD_HEIGHT
		self.grid_width = int(self.width * 0.91)
		self.piano_roll_width = self.width - self.grid_width
		self.row_height = (self.grid_height - 2) // self.vzoom
		self.step_width = (self.grid_width - 2) // self.hzoom

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

		# Create velocity level indicator canvas
		self.velocity_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_roll_width,
			height=PLAYHEAD_HEIGHT,
			bg=PLAYHEAD_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.velocity_canvas.create_rectangle(0, 0, self.piano_roll_width * self.velocity / 127, PLAYHEAD_HEIGHT, fill='yellow', tags="velocityIndicator", width=0)
		self.velocity_canvas.grid(column=0, row=1)

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

		self.zynseq.libseq.setPlayMode(0, 0, zynseq.SEQ_LOOP)

		# Load pattern 1 so that the editor has a default known state
		self.load_pattern(1)

	# Function to get name of this view
	def get_name(self):
		return "pattern editor"

	def play_note(self, note):
		if self.zynseq.libseq.getPlayState(self.bank, self.sequence) == zynseq.SEQ_STOPPED:
			self.zynseq.libseq.playNote(note, self.velocity, self.channel, int(200 * self.duration))

	# Function to set values of encoders
	def setup_zynpots(self):
		lib_zyncore.setup_behaviour_zynpot(0, 0)
		lib_zyncore.setup_behaviour_zynpot(1, 0)
		lib_zyncore.setup_behaviour_zynpot(2, 0)
		lib_zyncore.setup_behaviour_zynpot(3, 0)

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
				self.set_title(f"Pattern {self.pattern} ({title})")
			else:
				self.set_title(f"Pattern {self.pattern}")
		self.last_play_mode = self.zynseq.libseq.getPlayMode(self.bank, self.sequence)
		if self.last_play_mode not in (zynseq.SEQ_LOOP,zynseq.SEQ_LOOPALL):
			self.zynseq.libseq.setPlayMode(self.bank, self.sequence, zynseq.SEQ_LOOP)

		# Set active the first chain with pattern's MIDI chan
		try:
			chain_id = self.zyngui.chain_manager.midi_chan_2_chain_ids[self.channel][0]
			self.zyngui.chain_manager.set_active_chain_by_id(chain_id)
		except:
			logging.error(f"Couldn't set active chain to channel {self.channel}.")

		return True

	# Function to enable note duration/velocity direct edit mode
	# mode: Edit mode to enable [EDIT_MODE_NONE | EDIT_MODE_SINGLE | EDIT_MODE_ALL]
	def enable_edit(self, mode):
		self.edit_mode = mode
		if mode == EDIT_MODE_SINGLE:
			self.set_title("Note Parameters", zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)
			self.set_edit_title()
		elif mode == EDIT_MODE_ALL:
			self.set_title("Note Parameters ALL", zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)
			self.set_edit_title()
		else:
			self.set_title("Pattern {}".format(self.pattern), zynthian_gui_config.color_panel_tx, zynthian_gui_config.color_header_bg)
			self.init_buttonbar()

	# Function to hide GUI
	def hide(self):
		if not self.shown:
			return
		super().hide()
		if self.bank == 0 and self.sequence == 0:
			self.zynseq.libseq.setPlayState(self.bank, self.sequence, zynseq.SEQ_STOPPED)
		self.toggle_midi_record(False)
		self.enable_edit(EDIT_MODE_NONE)
		self.zynseq.libseq.setRefNote(self.keymap_offset)
		self.zynseq.libseq.setPlayMode(self.bank, self.sequence, self.last_play_mode)
		self.zynseq.libseq.enableMidiRecord(False)
		self.zyngui.alt_mode = False

	# Function to add menus
	def show_menu(self):
		self.disable_param_editor()
		options = {}
		extra_options = not zynthian_gui_config.check_wiring_layout(["Z2", "V5"])

		# Global Options
		if not zynthian_gui_config.check_wiring_layout(["V5"]):
			options['Grid zoom'] = 'Grid zoom'
		if extra_options:
			options['Tempo'] = 'Tempo'
		if not zynthian_gui_config.check_wiring_layout(["Z2"]):
			options['Arranger'] = 'Arranger'
		options['Beats per Bar ({})'.format(self.zynseq.libseq.getBeatsPerBar())] = 'Beats per bar'

		# Pattern Options
		options['> PATTERN OPTIONS'] = None
		options['Beats in pattern ({})'.format(self.zynseq.libseq.getBeatsInPattern())] = 'Beats in pattern'
		options['Steps/Beat ({})'.format(self.n_steps_beat)] = 'Steps per beat'
		options['Swing Divisor ({})'.format(self.zynseq.libseq.getSwingDiv())] = 'Swing Divisor'
		options['Swing Amount ({}%)'.format(int(100.0 * self.zynseq.libseq.getSwingAmount()))] = 'Swing Amount'
		options['Time Humanization ({})'.format(int(500.0 * self.zynseq.libseq.getHumanTime()))] = 'Time Humanization'
		options['Velocity Humanization ({})'.format(int(self.zynseq.libseq.getHumanVelo()))] = 'Velocity Humanization'
		options['Note Play Chance ({}%)'.format(int(100.0 * self.zynseq.libseq.getPlayChance()))] = 'Note Play Chance'
		scales = self.get_scales()
		options['Scale ({})'.format(scales[self.zynseq.libseq.getScale()])] = 'Scale'
		options['Tonic ({})'.format(NOTE_NAMES[self.zynseq.libseq.getTonic()])] = 'Tonic'
		note = self.zynseq.libseq.getInputRest()
		if note < 128:
			options['Rest note ({}{})'.format(NOTE_NAMES[note % 12], note // 12 - 1)] = 'Rest note'
		else:
			options['Rest note (None)'] = 'Rest note'

		# Pattern Edit
		options['> PATTERN EDIT'] = None
		#options['Add program change'] = 'Add program change'
		if extra_options:
			if self.zynseq.libseq.isMidiRecord():
				options['\u2612 Record from MIDI'] = 'Record MIDI'
			else:
				options['\u2610 Record from MIDI'] = 'Record MIDI'
		if self.zynseq.libseq.getQuantizeNotes():
			options['\u2612 Quantized recording'] = 'Quantized recording'
		else:
			options['\u2610 Quantized recording'] = 'Quantized recording'
		options['Transpose pattern'] = 'Transpose pattern'
		options['Copy pattern'] = 'Copy pattern'
		options['Load pattern'] = 'Load pattern'
		options['Save pattern'] = 'Save pattern'
		options['Clear pattern'] = 'Clear pattern'
		options['Export to SMF'] = 'Export to SMF'

		self.zyngui.screens['option'].config("Pattern Editor Menu", options, self.menu_cb)
		self.zyngui.show_screen('option')

	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()

	def get_note_from_row(self, row):
		return self.keymap[row]["note"]

	def menu_cb(self, option, params):
		if params == 'Grid zoom':
			self.toggle_grid_scale()
		elif params == 'Tempo':
			self.zyngui.show_screen('tempo')
		elif params == 'Arranger':
			self.zyngui.show_screen('arranger')
		elif params == 'Beats per bar':
			self.enable_param_editor(self, 'bpb', {'name': 'Beats per bar', 'value_min': 1, 'value_max': 64, 'value_default': 4, 'value': self.zynseq.libseq.getBeatsPerBar()})

		elif params == 'Beats in pattern':
			self.enable_param_editor(self, 'bip', {'name': 'Beats in pattern', 'value_min': 1, 'value_max': 64, 'value_default': 4, 'value': self.zynseq.libseq.getBeatsInPattern()}, self.assert_beats_in_pattern)
		elif params == 'Steps per beat':
			self.enable_param_editor(self, 'spb', {'name': 'Steps per beat', 'ticks': STEPS_PER_BEAT, 'value_default': 3, 'value': self.n_steps_beat}, self.assert_steps_per_beat)

		elif params == 'Swing Divisor':
			self.enable_param_editor(self, 'swing_div', {'name': 'Swing Divisor', 'value_min': 1, 'value_max': self.n_steps_beat, 'value_default': 1, 'value': self.zynseq.libseq.getSwingDiv()})

		elif params == 'Swing Amount':
			self.enable_param_editor(self, 'swing_amount', {'name': 'Swing Amount', 'value_min': 0, 'value_max': 100, 'value_default': 0, 'value': int(100.0 * self.zynseq.libseq.getSwingAmount())})

		elif params == 'Time Humanization':
			self.enable_param_editor(self, 'human_time', {'name': 'Time Humanization', 'value_min': 0, 'value_max': 100, 'value_default': 0, 'value': int(500.0 * self.zynseq.libseq.getHumanTime())})

		elif params == 'Velocity Humanization':
			self.enable_param_editor(self, 'human_velo', {'name': 'Velocity Humanization', 'value_min': 0, 'value_max': 100, 'value_default': 0, 'value': int(self.zynseq.libseq.getHumanVelo())})

		elif params == 'Note Play Chance':
			self.enable_param_editor(self, 'play_chance', {'name': 'Note Play Chance', 'value_min': 0, 'value_max': 100, 'value_default': 0, 'value': int(100.0 * self.zynseq.libseq.getPlayChance())})

		elif params == 'Scale':
			self.enable_param_editor(self, 'scale', {'name': 'Scale', 'labels': self.get_scales(), 'value': self.zynseq.libseq.getScale()})
		elif params == 'Tonic':
			self.enable_param_editor(self, 'tonic', {'name': 'Tonic', 'labels': NOTE_NAMES, 'value': self.zynseq.libseq.getTonic()})
		elif params == 'Rest note':
			labels = ['None']
			for note in range(128):
				labels.append("{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1))
			value = self.zynseq.libseq.getInputRest() + 1
			if value > 128:
				value = 0
			self.enable_param_editor(self, 'rest', {'name': 'Rest', 'labels': labels, 'value': value})
		elif params == 'Add program change':
			self.enable_param_editor(self, 'prog_change', {'name': 'Program', 'value_max': 128, 'value': self.get_program_change()}, self.add_program_change)

		elif params == 'Record MIDI':
			self.toggle_midi_record()
		elif params == 'Quantized recording':
			self.zynseq.libseq.setQuantizeNotes(not self.zynseq.libseq.getQuantizeNotes())
		elif params == 'Transpose pattern':
			self.enable_param_editor(self, 'transpose', {'name': 'Transpose', 'value_min': -1, 'value_max': 1, 'labels': ['down','down/up','up'], 'value': 0})
		elif params == 'Copy pattern':
			self.copy_source = self.pattern
			self.enable_param_editor(self, 'copy', {'name': 'Copy pattern to', 'value_min': 1, 'value_max': zynseq.SEQ_MAX_PATTERNS, 'value': self.pattern}, self.copy_pattern)
		elif params == 'Load pattern':
			self.zyngui.screens['option'].config_file_list("Load pattern", [self.patterns_dpath, self.my_patterns_dpath], "*.zpat", self.load_pattern_file)
			self.zyngui.show_screen('option')
		elif params == 'Save pattern':
			self.zyngui.show_keyboard(self.save_pattern_file, "pat#{}".format(self.pattern))
		elif params == 'Clear pattern':
			self.clear_pattern()
		elif params == 'Export to SMF':
			self.zyngui.show_keyboard(self.export_smf, "pat#{}".format(self.pattern))

	def save_pattern_file(self, fname):
		self.zynseq.save_pattern(self.pattern, "{}/{}.zpat".format(self.my_patterns_dpath, fname))

	def load_pattern_file(self, fname, fpath):
		if not self.zynseq.is_pattern_empty(self.pattern):
			self.zyngui.show_confirm("Do you want to overwrite pattern '{}'?".format(self.pattern), self.do_load_pattern_file, fpath)
		else:
			self.do_load_pattern_file(fpath)

	def do_load_pattern_file(self, fpath):
		self.zynseq.load_pattern(self.pattern, fpath)
		self.changed = False
		self.redraw_pending = 3

	def clean_pattern_snapshots(self):
		self.zynseq.libseq.resetPatternSnapshots()

	# If changed, save snapshot:
	#  + right now, if force=True
	#  + each loop, if playing
	#  + each SAVE_SNAPSHOT_DELAY seconds, if stopped
	def save_pattern_snapshot(self, force=True):
		if self.changed:
			if force or (self.playstate != zynseq.SEQ_STOPPED and self.playhead == 0):
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
		self.save_pattern_snapshot()
		if self.zynseq.libseq.undoPattern():
			self.redraw_pending = 3

	def redo_pattern(self):
		if not self.changed and self.zynseq.libseq.redoPattern():
			self.redraw_pending = 3

	def undo_pattern_all(self):
		self.save_pattern_snapshot()
		if self.zynseq.libseq.undoPatternAll():
			self.redraw_pending = 3

	def redo_pattern_all(self):
		if not self.changed and self.zynseq.libseq.redoPatternAll():
			self.redraw_pending = 3

	def toggle_midi_record(self, midi_record=None):
		if midi_record is None:
			midi_record = not self.zynseq.libseq.isMidiRecord()
		self.zynseq.libseq.enableMidiRecord(midi_record)
		self.save_pattern_snapshot()

	def send_controller_value(self, zctrl):
		if zctrl.symbol == 'tempo':
			self.zynseq.libseq.setTempo(zctrl.value)
		elif zctrl.symbol == 'bpb':
			self.zynseq.libseq.setBeatsPerBar(zctrl.value)
		elif zctrl.symbol == 'swing_amount':
			self.zynseq.libseq.setSwingAmount(zctrl.value/100.0)
		elif zctrl.symbol == 'swing_div':
			self.zynseq.libseq.setSwingDiv(zctrl.value)
		elif zctrl.symbol == 'human_time':
			self.zynseq.libseq.setHumanTime(zctrl.value / 500.0)
		elif zctrl.symbol == 'human_velo':
			self.zynseq.libseq.setHumanVelo(1.0 * zctrl.value)
		elif zctrl.symbol == 'play_chance':
			self.zynseq.libseq.setPlayChance(zctrl.value / 100.0)
		elif zctrl.symbol == 'transpose':
			self.transpose(zctrl.value)
			zctrl.set_value(0)
		elif zctrl.symbol == 'copy':
			self.load_pattern(zctrl.value)
		elif zctrl.symbol == 'scale':
			self.set_scale(zctrl.value)
		elif zctrl.symbol == 'tonic':
			self.set_tonic(zctrl.value)
		elif zctrl.symbol == 'rest':
			if zctrl.value == 0:
				self.zynseq.libseq.setInputRest(128)
			else:
				self.zynseq.libseq.setInputRest(zctrl.value - 1)

	# Function to transpose pattern
	def transpose(self, offset):
		if offset != 0:
			self.save_pattern_snapshot()
			if self.zynseq.libseq.getScale():
				# Change to chromatic scale to transpose
				self.zynseq.libseq.setScale(0)
				self.load_keymap()
			self.zynseq.libseq.transpose(offset)
			self.changed = True
			self.set_keymap_offset(self.keymap_offset + offset)
			self.selected_cell[1] = self.selected_cell[1] + offset
			self.redraw_pending = 3
			self.select_cell()

	# Function to set musical scale
	# scale: Index of scale to load
	# Returns: name of scale
	def set_scale(self, scale):
		self.zynseq.libseq.setScale(scale)
		self.reload_keymap = True
		self.redraw_pending = 3

	# Function to set tonic (root note) of scale
	# tonic: Scale root note
	def set_tonic(self, tonic):
		self.zynseq.libseq.setTonic(tonic)
		self.reload_keymap = True
		self.redraw_pending = 3

	# Function to export pattern to SMF
	def export_smf(self, fname):
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
		zynsmf.save(smf, "{}/{}.mid".format(self.my_captures_dpath, fname))

	# Function to assert steps per beat
	def assert_steps_per_beat(self, value):
		self.zyngui.show_confirm("Changing steps per beat may alter timing and/or lose notes?", self.do_steps_per_beat, value)

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
			self.zyngui.show_confirm("Reducing beats in pattern will truncate pattern", self.set_beats_in_pattern, value)
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
	# returns: Index of closest allowed value
	def get_steps_per_beat_index(self):
		steps_per_beat = self.zynseq.libseq.getStepsPerBeat()
		for index in range(len(STEPS_PER_BEAT)):
			if STEPS_PER_BEAT[index] >= steps_per_beat:
				return index
		return index

	# Function to get list of scales
	# returns: List of available scales
	def get_scales(self):
		# Load scales
		data = []
		try:
			with open(CONFIG_ROOT + "/scales.json") as json_file:
				data = json.load(json_file)
		except:
			logging.warning("Unable to open scales.json")
		res = []
		# Look for a custom keymap, defaults to chromatic
		custom_keymap = self.get_custom_keymap()
		if custom_keymap:
			res.append(f"Custom - {custom_keymap}")
		else:
			res.append(f"Custom - None")
		for scale in data:
			res.append(scale['name'])
		return res

	# Search for a custom map
	def get_custom_keymap(self):
		synth_proc = self.zyngui.chain_manager.get_synth_processor(self.channel)
		if synth_proc:
			map_name = None
			preset_path = synth_proc.get_presetpath()
			try:
				with open(CONFIG_ROOT + "/keymaps.json") as json_file:
					data = json.load(json_file)
					for pat in data:
						if pat in preset_path:
							map_name = data[pat]
							break
				if map_name:
					keymap_fpath = CONFIG_ROOT + f"/{map_name}.midnam"
					if os.path.isfile(keymap_fpath):
						return map_name
					else:
						logging.warning(f"Keymap file {keymap_fpath} doesn't exist.")
			except:
				logging.warning("Unable to load keymaps.json")
		else:
			logging.info(f"MIDI channel {self.channel} has not synth processors.")

	# Function to populate keymap array
	# returns Name of scale / map
	def load_keymap(self):
		self.keymap = []
		scale = self.zynseq.libseq.getScale()
		tonic = self.zynseq.libseq.getTonic()

		# Try to load custom keymap
		if scale == 0:
			map_name = self.get_custom_keymap()
			if map_name:
				keymap_fpath = CONFIG_ROOT + f"/{map_name}.midnam"
				logging.info(f"Loading keymap {map_name} for MIDI channel {self.channel}...")
				try:
					xml = minidom.parse(keymap_fpath)
					notes = xml.getElementsByTagName('Note')
					for note in notes:
						self.keymap.append({'note':int(note.attributes['Number'].value), 'name':note.attributes['Name'].value})
					return map_name
				except Exception as e:
					logging.error(f"Can't load '{keymap_fpath}' => {e}")

		# Not custom map loaded => Load scale

		# Load specific scale
		if scale > 1:
			try:
				with open(CONFIG_ROOT + "/scales.json") as json_file:
					data = json.load(json_file)
				if scale <= len(data):
					scale -= 1  # Offset by -1 because the 0 is used for custom keymap
					for octave in range(0, 9):
						for offset in data[scale]['scale']:
							note = tonic + offset + octave * 12
							if note > 127:
								break
							self.keymap.append({"note": note, "name": "{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1)})
					return data[scale]['name']
			except Exception as e:
				logging.error(f"Can't load 'scales.json' => {e}")

		# Load chromatic scale
		for note in range(0, 128):
			new_entry = {"note": note}
			key = note % 12
			if key in (1, 3, 6, 8, 10):  # Black notes
				new_entry.update({"colour": "black"})
			else:
				new_entry.update({"colour": "white"})
			if key == 0:  # 'C'
				new_entry.update({"name": "C{}".format(note // 12 - 1)})
			self.keymap.append(new_entry)
		return "Chromatic"

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
		self.set_keymap_offset(self.keymap_offset + offset)
		if self.selected_cell[1] < self.keymap_offset:
			self.selected_cell[1] = self.keymap_offset
		elif self.selected_cell[1] >= self.keymap_offset + self.vzoom:
			self.selected_cell[1] = self.keymap_offset + self.vzoom - 1
		self.select_cell()

	# Function to handle end of pianoroll drag
	def on_pianoroll_release(self, event):
		# Play note if not drag action
		if self.piano_roll_drag_start and self.piano_roll_drag_count == 0:
			row = int((self.total_height - self.piano_roll.canvasy(event.y)) / self.row_height)
			if row < len(self.keymap):
				note = self.keymap[row]['note']
				self.play_note(note)
		# Swipe
		elif self.swiping:
			dts = (event.time - self.piano_roll_drag_start.time)/1000
			self.swipe_nudge(dts)

		self.piano_roll_drag_start = None
		self.piano_roll_drag_count = 0

	# Function to handle mouse wheel over pianoroll
	def on_pianoroll_wheel(self, event):
		if event.num == 4:
			# Scroll up
			if self.keymap_offset + self.vzoom < len(self.keymap):
				self.set_keymap_offset(self.keymap_offset + 1)
				if self.selected_cell[1] < self.keymap_offset:
					self.select_cell(self.selected_cell[0], self.keymap_offset)
		else:
			# Scroll down
			if self.keymap_offset > 0:
				self.set_keymap_offset(self.keymap_offset - 1)
				if self.selected_cell[1] >= self.keymap_offset + self.vzoom:
					self.select_cell(self.selected_cell[0], self.keymap_offset + self.vzoom - 1)

	# Function to handle grid mouse down
	# event: Mouse event
	def on_grid_press(self, event):
		if self.param_editor_zctrl:
			self.disable_param_editor()

		# Select cell
		row = int((self.total_height - self.grid_canvas.canvasy(event.y)) / self.row_height)
		step = int(self.grid_canvas.canvasx(event.x) / self.step_width)
		try:
			note = self.keymap[row]['note']
		except:
			return
		start_step = self.zynseq.libseq.getNoteStart(step, note)
		if start_step >= 0:
			step = start_step
		if step < 0 or step >= self.n_steps:
			return
		self.select_cell(step, row)

		# Start drag state variables
		self.swiping = False
		self.grid_drag_start = event
		self.grid_drag_count = 0
		self.swipe_step_speed = 0
		self.swipe_row_speed = 0
		self.swipe_step_dir = 0
		self.swipe_row_dir = 0
		self.drag_note = False
		self.drag_velocity = False
		self.drag_duration = False
		self.drag_start_step = step
		self.drag_start_velocity = self.zynseq.libseq.getNoteVelocity(step, note)
		self.drag_start_duration = self.zynseq.libseq.getNoteDuration(step, note)

	# Function to handle grid mouse drag
	# event: Mouse event
	def on_grid_drag(self, event):
		if not self.grid_drag_start:
			return
		self.grid_drag_count += 1

		if self.drag_note:
			step = self.selected_cell[0]
			row = self.selected_cell[1]
			note = self.keymap[row]['note']
			sel_duration = self.zynseq.libseq.getNoteDuration(step, note)
			sel_velocity = self.zynseq.libseq.getNoteVelocity(step, note)

			if self.drag_start_velocity:
				# Selected cell has a note so we want to adjust its velocity or duration
				if not self.drag_velocity and not self.drag_duration and (event.x > (self.drag_start_step + 1) * self.step_width or event.x < self.drag_start_step * self.step_width):
					self.drag_duration = True
				if not self.drag_duration and not self.drag_velocity and (event.y > self.grid_drag_start.y + self.row_height / 2 or event.y < self.grid_drag_start.y - self.row_height / 2):
					self.drag_velocity = True
				if self.drag_velocity:
					value = (self.grid_drag_start.y - event.y) / self.row_height
					if value:
						velocity = int(self.drag_start_velocity + value * self.height / 100)
						if 1 <= velocity <= 127:
							self.set_velocity_indicator(velocity)
							if sel_duration and velocity != sel_velocity:
								self.zynseq.libseq.setNoteVelocity(step, note, velocity)
								self.draw_cell(step, row)
				if self.drag_duration:
					duration = int(event.x / self.step_width) - self.drag_start_step
					if duration > 0 and duration != sel_duration:
						self.add_event(step, row, sel_velocity, duration)
					else:
						#self.duration = duration
						pass
			else:
				# Clicked on empty cell so want to add a new note by dragging towards the desired cell
				x1 = self.selected_cell[0] * self.step_width  # x pos of start of event
				x2 = x1 + self.step_width  # x pos right of event's first cell
				y1 = self.total_height - self.selected_cell[1] * self.row_height  # y pos of bottom of selected row
				y2 = y1 - self.row_height  # y pos of top of selected row
				event_x = self.grid_canvas.canvasx(event.x)
				event_y = self.grid_canvas.canvasy(event.y)
				if event_x < x1:
					self.select_cell(self.selected_cell[0] - 1, None)
				elif event_x > x2:
					self.select_cell(self.selected_cell[0] + 1, None)
				elif event_y > y1:
					self.select_cell(None, self.selected_cell[1] - 1)
					self.play_note(self.keymap[self.selected_cell[1]]["note"])
				elif event_y < y2:
					self.select_cell(None, self.selected_cell[1] + 1)
					self.play_note(self.keymap[self.selected_cell[1]]["note"])
		else:
			step_offset = int(DRAG_SENSIBILITY * (self.grid_drag_start.x - event.x) / self.step_width)
			row_offset = int(DRAG_SENSIBILITY * (event.y - self.grid_drag_start.y) / self.row_height)
			if step_offset == 0 and row_offset == 0:
				if self.grid_drag_count < 2 and (event.time - self.grid_drag_start.time) > 800:
					self.drag_note = True
				return
			self.swiping = True
			self.grid_drag_start = event
			if step_offset:
				self.swipe_step_dir = step_offset
				self.set_step_offset(self.step_offset + step_offset)
			if row_offset:
				self.swipe_row_dir = row_offset
				self.set_keymap_offset(self.keymap_offset + row_offset)
				if self.selected_cell[1] < self.keymap_offset:
					self.selected_cell[1] = self.keymap_offset
				elif self.selected_cell[1] >= self.keymap_offset + self.vzoom:
					self.selected_cell[1] = self.keymap_offset + self.vzoom - 1
			self.select_cell()

	# Function to handle grid mouse release
	# event: Mouse event
	def on_grid_release(self, event):
		# No drag actions
		if self.grid_drag_start:
			dts = event.time - self.grid_drag_start.time
			if self.grid_drag_count == 0:
				# Bold click without drag
				if (dts) > 800:
					if self.edit_mode == EDIT_MODE_NONE:
						self.enable_edit(EDIT_MODE_SINGLE)
					else:
						self.enable_edit(EDIT_MODE_ALL)
				# Short click without drag: Add/remove single note
				else:
					step = self.selected_cell[0]
					row = self.selected_cell[1]
					self.toggle_event(step, row)
					if not self.drag_start_velocity:
						note = self.keymap[row]['note']
						self.play_note(note)
			# End drag action
			elif self.drag_note:
				if not self.drag_start_velocity:
					step = self.selected_cell[0]
					row = self.selected_cell[1]
					#note = self.keymap[row]['note']
					self.add_event(step, row, self.velocity, self.duration)
			# Swipe
			elif self.swiping:
				self.swipe_nudge(dts/1000)

		# Reset drag state variables
		self.grid_drag_start = None
		self.grid_drag_count = 0
		self.drag_note = False
		self.drag_velocity = False
		self.drag_duration = False
		self.drag_start_step = None
		self.drag_start_velocity = None
		self.drag_start_duration = None

	def on_gesture(self, gtype, value):
		if gtype == MultitouchTypes.GESTURE_H_DRAG:
			value = int(-0.1 * value)
			self.set_step_offset(self.step_offset + value)
			self.select_cell()
		elif gtype == MultitouchTypes.GESTURE_V_DRAG:
			value = int(0.1 * value)
			self.set_keymap_offset(self.keymap_offset + value)
			if self.selected_cell[1] < self.keymap_offset:
				self.selected_cell[1] = self.keymap_offset
			elif self.selected_cell[1] >= self.keymap_offset + self.vzoom:
				self.selected_cell[1] = self.keymap_offset + self.vzoom - 1
			self.select_cell()
		elif gtype in (MultitouchTypes.GESTURE_H_PINCH, MultitouchTypes.GESTURE_V_PINCH):
			value = int(0.1 * value)
			self.set_grid_scale(value, value)

	def plot_zctrls(self):
		self.swipe_update()

	def swipe_nudge(self, dts):
		kt = 0.5 * min(0.05 * DRAG_SENSIBILITY / dts, 8)
		self.swipe_step_speed += kt * self.swipe_step_dir
		self.swipe_row_speed += kt * self.swipe_row_dir
		#logging.debug(f"KT={kt} => SWIPE_STEP_SPEED = {self.swipe_step_speed}, SWIPE_ROW_SPEED = {self.swipe_row_speed}")

	# Update swipe scroll
	def swipe_update(self):
		select_cell = False
		if self.swipe_step_speed:
			#logging.debug(f"SWIPE_UPDATE_STEP => {self.swipe_step_speed}")
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
			#logging.debug(f"SWIPE_UPDATE_ROW => {self.swipe_row_speed}")
			self.swipe_row_offset += self.swipe_row_speed
			self.swipe_row_speed *= self.swipe_friction
			if abs(self.swipe_row_speed) < 0.2:
				self.swipe_row_speed = 0
				self.swipe_row_offset = 0
			if abs(self.swipe_row_offset) > 1:
				self.keymap_offset += int(self.swipe_row_offset)
				self.swipe_row_offset -= int(self.swipe_row_offset)
				self.set_keymap_offset(self.keymap_offset)
				if self.selected_cell[1] < self.keymap_offset:
					self.selected_cell[1] = self.keymap_offset
				elif self.selected_cell[1] >= self.keymap_offset + self.vzoom:
					self.selected_cell[1] = self.keymap_offset + self.vzoom - 1
				select_cell = True
		if select_cell:
			self.select_cell()

	# Function to adjust velocity indicator
	# velocity: Note velocity to indicate
	def set_velocity_indicator(self, velocity):
		self.velocity_canvas.coords("velocityIndicator", 0, 0, self.piano_roll_width * velocity / 127, PLAYHEAD_HEIGHT)

	# Function to toggle note event
	# step: step number (column)
	# row: keymap index
	# Returns: Note if note added else None
	def toggle_event(self, step, row):
		if step < 0 or step >= self.n_steps or row >= len(self.keymap):
			return
		note = self.keymap[row]['note']
		start_step = self.zynseq.libseq.getNoteStart(step, note)
		if start_step >= 0:
			self.remove_event(start_step, row)
		else:
			self.add_event(step, row, self.velocity, self.duration)
			return note

	# Function to remove an event
	# step: step number (column)
	# row: keymap index
	def remove_event(self, step, row):
		if row >= len(self.keymap):
			return
		note = self.keymap[row]['note']
		self.zynseq.libseq.removeNote(step, note)
		self.zynseq.libseq.playNote(note, 0, self.channel) # Silence note if sounding
		self.changed = True
		self.drawing = True
		self.draw_row(row)
		self.drawing = False
		self.select_cell(step, row)

	# Function to add an event
	# step: step number (column)
	# row: keymap index
	# vel: velocity (0-127)
	# dur: duration (in steps)
	# offset: offset of start of event (0..0.99)
	def add_event(self, step, row, vel, dur, offset=0.0):
		note = self.keymap[row]["note"]
		self.zynseq.libseq.addNote(step, note, vel, dur, offset)
		self.changed = True
		self.drawing = True
		self.draw_row(row)
		self.drawing = False
		self.select_cell(step, row)

	# Function to draw a grid row
	# row: Row number (keymap index)
	# colour: Black, white or None (default) to not care
	def draw_row(self, row, white=None):
		self.grid_canvas.itemconfig(f"lastnotetext{row}", state="hidden")
		for step in range(self.n_steps):
			self.draw_cell(step, row, white)

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

	# Function to draw a grid cell
	# step: Step (column) index
	# row: Index of row
	# white: True for white notes
	def draw_cell(self, step, row, white=None):
		self.zynseq.libseq.isPatternModified()  # Flush modified flag to avoid refresh redrawing whole grid => Is this OK?
		cellIndex = row * self.n_steps + step  # Cells are stored in array sequentially: 1st row, 2nd row...
		if cellIndex >= len(self.cells):
			return
		note = self.keymap[row]["note"]
		cell = self.cells[cellIndex]
		if white is None:
			if cell:
				white = "white" in self.grid_canvas.gettags(cell)
			else:
				white = True
		
		velocity_colour = self.zynseq.libseq.getNoteVelocity(step, note)
		if velocity_colour:
			velocity_colour += 70
			duration = self.zynseq.libseq.getNoteDuration(step, note)
			offset = self.zynseq.libseq.getNoteOffset(step, note)
			fill_colour = f"#{velocity_colour:02x}{velocity_colour:02x}{velocity_colour:02x}"
		else:
			self.grid_canvas.delete(cell)
			self.cells[cellIndex] = None
			return

		coord = self.get_cell(step, row, duration, offset)
		if white:
			cell_tags = ("%d,%d" % (step, row), "gridcell", "step%d" % step, "white")
		else:
			cell_tags = ("%d,%d" % (step, row), "gridcell", "step%d" % step)

		if cell:
			# Update existing cell
			self.grid_canvas.itemconfig(cell, fill=fill_colour, tags=cell_tags)
			self.grid_canvas.coords(cell, coord)
		else:
			# Create new cell
			cell = self.grid_canvas.create_rectangle(coord, fill=fill_colour, width=0, tags=cell_tags)
			self.cells[cellIndex] = cell

		if step + duration > self.n_steps:
			self.grid_canvas.itemconfig("lastnotetext%d" % row, text="+%d" % (duration - self.n_steps + step), state="normal")

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

		if len(self.cells) != len(self.keymap) * self.n_steps:
			redraw_pending = 4
			self.grid_canvas.delete(tkinter.ALL)
			self.draw_pianoroll()
			self.cells = [None] * len(self.keymap) * self.n_steps
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.step_width * (self.playhead + 1), PLAYHEAD_HEIGHT)

		grid_font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize_grid)
		bnum_font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=PLAYHEAD_HEIGHT-2)

		# Draw cells of grid
		#self.grid_canvas.itemconfig("gridcell", fill="black")
		if redraw_pending > 3:
			# Redraw gridlines
			self.grid_canvas.delete("gridline")
			self.play_canvas.delete("beatnum")
			if self.n_steps_beat:
				lh = 128 * self.row_height - 1
				th = int(0.7 * PLAYHEAD_HEIGHT)
				for step in range(0, self.n_steps + 1):
					xpos = step * self.step_width
					if step % self.n_steps_beat == 0:
						self.grid_canvas.create_line(xpos, 0, xpos, lh, fill=GRID_LINE_STRONG, tags="gridline")
						if step < self.n_steps:
							beatnum = 1 + step // self.n_steps_beat
							if beatnum == 1:
								anchor = "nw"
							else:
								anchor = "n"
							self.play_canvas.create_text((xpos, -2), text=str(beatnum), font=bnum_font, anchor=anchor, fill=GRID_LINE_STRONG, tags="beatnum")

					else:
						self.grid_canvas.create_line(xpos, 0, xpos, lh, fill=GRID_LINE_WEAK, tags="gridline")
						self.play_canvas.create_line(xpos, 0, xpos, th, fill=PLAYHEAD_LINE, tags="beatnum")

		if redraw_pending > 1:
			# Delete existing note names from piano roll
			self.piano_roll.delete("notename")

			if redraw_pending > 2:
				row_min = 0
				row_max = len(self.keymap)
			else:
				row_min = self.selected_cell[1]
				row_max = self.selected_cell[1]

			for row in range(row_min, row_max):
				# Create last note labels in grid
				self.grid_canvas.create_text(self.total_width - self.select_thickness, int(self.row_height * (row - 0.5)), state="hidden", tags=(f"lastnotetext{row}", "lastnotetext", "gridcell"), font=grid_font, anchor="e")

				fill = "black"
				# Update pianoroll keys
				id = f"row{row}"
				try:
					name = self.keymap[row]["name"]
				except:
					name = None
				if "colour" in self.keymap[row]:
					colour = self.keymap[row]["colour"]
				elif name and "#" in name:
					colour = "black"
					fill = "white"
				else:
					colour = "white"
					fill = CANVAS_BACKGROUND
				self.piano_roll.itemconfig(id, fill=colour)
				#name = str(row)
				ypos = self.total_height - row * self.row_height
				if name:
					self.piano_roll.create_text((2, ypos - 0.5 * self.row_height), text=name, font=grid_font, anchor="w", fill=fill, tags="notename")
				if self.keymap[row]['note'] % 12 == self.zynseq.libseq.getTonic():
					self.grid_canvas.create_line(0, ypos, self.total_width, ypos, fill=GRID_LINE_STRONG, tags="gridline")
				else:
					self.grid_canvas.create_line(0, ypos, self.total_width, ypos, fill=GRID_LINE_WEAK, tags="gridline")
				# Draw row of note cells
				self.draw_row(row, (colour == "white"))

		# Set z-order to allow duration to show
		if redraw_pending > 2:
			for step in range(self.n_steps):
				self.grid_canvas.tag_lower(f"step{step}")
		self.select_cell()
		self.drawing = False

	# Function to draw pianoroll key outlines (does not fill key colour)
	def draw_pianoroll(self):
		self.piano_roll.delete(tkinter.ALL)
		for row in range(0, len(self.keymap)):
			x1 = 0
			y1 = self.total_height - (row + 1) * self.row_height + 1
			x2 = self.piano_roll_width
			y2 = y1 + self.row_height - 1
			tags = f"row{row}"
			self.piano_roll.create_rectangle(x1, y1, x2, y2, width=0, tags=tags)

	# Function to set kaymap offset and move grid view accordingly
	# offset: Keymap Offset (note at bottom row)
	def set_keymap_offset(self, offset=None):
		if offset is not None:
			self.keymap_offset = offset
		if self.keymap_offset > len(self.keymap) - self.vzoom:
			self.keymap_offset = len(self.keymap) - self.vzoom
		elif self.keymap_offset < 0:
			self.keymap_offset = 0
		ypos = (self.scroll_height - self.keymap_offset * self.row_height) / self.total_height
		self.grid_canvas.yview_moveto(ypos)
		self.piano_roll.yview_moveto(ypos)
		#logging.debug(f"OFFSET: {self.keymap_offset} (keymap length: {len(self.keymap)})")
		#logging.debug(f"GRID Y-SCROLL: {ypos}\n\n")

	# Function to set step offset and move grid view accordingly
	# offset: Step Offset (step at left column)
	def set_step_offset(self, offset=None):
		if offset is not None:
			self.step_offset = offset
		if self.step_offset > self.n_steps - self.hzoom:
			self.step_offset = self.n_steps - self.hzoom
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

	def set_grid_scale(self, step_width_inc=0, row_height_inc=0):
		# Check step width limits
		step_width = self.step_width + step_width_inc
		if step_width < max(10, self.grid_width // self.n_steps):
			step_width = max(10, self.grid_width // self.n_steps)
		elif step_width > self.grid_width // 8:
			step_width = self.grid_width // 8
		# Check row height limits
		row_height = self.row_height + row_height_inc
		if row_height < self.grid_height // 36:
			row_height = self.grid_height // 36
		elif row_height > self.grid_height // 6:
			row_height = self.grid_height // 6
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
			return
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
		# Update grid position
		if step_width_changed:
			self.set_step_offset()
		if row_height_changed:
			self.set_keymap_offset()
		self.vzoom = self.grid_height // self.row_height
		self.hzoom = self.grid_width // self.step_width

	def reset_grid_scale(self):
		self.vzoom = DEFAULT_VZOOM
		self.hzoom = DEFAULT_HZOOM
		self.row_height = (self.grid_height - 2) // self.vzoom
		self.step_width = (self.grid_width - 2) // self.hzoom
		w = self.total_width
		h = self.total_height
		self.update_geometry()
		xscale = self.total_width / w
		yscale = self.total_height / h
		self.grid_canvas.scale("all", 0, 0, xscale, yscale)
		self.play_canvas.scale("all", 0, 0, xscale, 1.0)
		self.piano_roll.scale("all", 0, 0, 1.0, yscale)
		self.set_keymap_offset()
		self.set_step_offset()
		#self.redraw_pending = 4
		if self.edit_mode == EDIT_MODE_SCALE:
			self.edit_mode = EDIT_MODE_NONE

	# Function to calculate variable gemoetry parameters
	def update_geometry(self):
		# Y-axis calculations
		self.total_height = 128 * self.row_height
		self.scroll_height = self.total_height - self.grid_height

		# X-axis calculations
		self.total_width = self.n_steps * self.step_width

		# Font size calculation
		self.fontsize_grid = self.row_height // 2
		if self.fontsize_grid > 20:
			self.fontsize_grid = 20  # Ugly font scale limiting

		# Update scrollregion in canvas
		if self.total_width > 0:
			self.grid_canvas.config(scrollregion=(0, 0, self.total_width, self.total_height))
			self.piano_roll.config(scrollregion=(0, 0, self.piano_roll_width, self.total_height))
			self.play_canvas.config(scrollregion=(0, 0, self.total_width, PLAYHEAD_HEIGHT))
			#logging.debug(f"GRID SCROLLREGION: {self.total_width} x {self.total_height}")

	# Function to update selectedCell
	# step: Step (column) of selected cell (Optional - default to reselect current column)
	# row: Index of keymap to select (Optional - default to reselect current row) Maybe outside visible range to scroll display
	def select_cell(self, step=None, row=None):
		if not self.keymap:
			return

		# Check row boundaries
		if row == None:
			row = self.selected_cell[1]
		if row < 0:
			row = 0
		elif row >= len(self.keymap):
			row = len(self.keymap) - 1
		# Check keymap offset
		if row >= self.keymap_offset + self.vzoom:
			# Note is off top of display
			self.set_keymap_offset(row - self.vzoom + 1)
		elif row < self.keymap_offset:
			# Note is off bottom of display
			self.set_keymap_offset(row)
		#if redraw and self.redraw_pending < 1:
		#	self.redraw_pending = 3
		note = self.keymap[row]['note']

		# Check column boundaries
		if step == None:
			step = self.selected_cell[0]
		if step < 0:
			step = 0
		elif step >= self.n_steps:
			step = self.n_steps - 1
		# Skip hidden (overlapping) cells
		for previous in range(int(step) - 1, -1, -1):
			prev_duration = ceil(self.zynseq.libseq.getNoteDuration(previous, note))
			if not prev_duration:
				continue
			if prev_duration > step - previous:
				if step > self.selected_cell[0]:
					step = previous + prev_duration
				else:
					step = previous
				break
		# Re-check column boundaries
		if step < 0:
			step = 0
		elif step >= self.n_steps:
			step = self.n_steps - 1
		# Check step offset
		if step >= self.step_offset + self.hzoom:
			# Step is off right of display
			self.set_step_offset(step - self.hzoom + 1)
		elif step < self.step_offset:
			# Step is off left of display
			self.set_step_offset(step)
		self.selected_cell = [int(step), row]
		# Duration & velocity
		duration = self.zynseq.libseq.getNoteDuration(step, note)
		offset = self.zynseq.libseq.getNoteOffset(step, note)
		if duration:
			velocity = self.zynseq.libseq.getNoteVelocity(step, note)
		else:
			duration = self.duration
			velocity = self.velocity
		self.set_velocity_indicator(velocity)
		# Position selector cell-frame
		coord = self.get_cell(step, row, duration, offset)
		coord[0] -= 1
		coord[1] -= 1
		cell = self.grid_canvas.find_withtag("selection")
		if not cell:
			cell = self.grid_canvas.create_rectangle(coord, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")
		else:
			self.grid_canvas.coords(cell, coord)
		self.grid_canvas.tag_raise(cell)

	# Function to clear a pattern
	def clear_pattern(self, params=None):
		self.zyngui.show_confirm(f"Clear pattern {self.pattern}?", self.do_clear_pattern)

	# Function to actually clear pattern
	def do_clear_pattern(self, params=None):
		self.save_pattern_snapshot()
		self.zynseq.libseq.clear()
		self.changed = True
		self.redraw_pending = 3
		self.select_cell()
		if self.zynseq.libseq.getPlayState(self.bank, self.sequence, 0) != zynseq.SEQ_STOPPED:
			self.zynseq.libseq.sendMidiCommand(0xB0 | self.channel, 123, 0)  # All notes off

	# Function to copy pattern
	def copy_pattern(self, value):
		if self.zynseq.libseq.getLastStep() == -1:
			self.do_copy_pattern(value)
		else:
			self.zyngui.show_confirm("Overwrite pattern {} with content from pattern {}?".format(value, self.copy_source),
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
		#self.zyngui.screen['arranger'].pattern = self.pattern
		#self.zyngui.screen['arranger'].pattern_canvas.itemconfig("patternIndicator", text="{}".format(self.pattern))

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

	# Function to load new pattern
	# index: Pattern index
	def load_pattern(self, index):
		self.zynseq.libseq.setRefNote(self.keymap_offset)
		if self.bank == 0 and self.sequence == 0:
			self.zynseq.libseq.setChannel(self.bank, self.sequence, 0, self.channel)
		self.zynseq.libseq.selectPattern(index)
		self.pattern = index

		n_steps = self.zynseq.libseq.getSteps()
		n_steps_beat = self.zynseq.libseq.getStepsPerBeat()
		keymap_len = len(self.keymap)
		self.load_keymap()
		if n_steps != self.n_steps or n_steps_beat != self.n_steps_beat or len(self.keymap) != keymap_len:
			self.n_steps = n_steps
			self.n_steps_beat = n_steps_beat
			self.step_offset = 0
			self.update_geometry()
			self.redraw_pending = 4
			keymap_len = len(self.keymap)
		else:
			self.redraw_pending = 3

		if self.selected_cell[0] >= n_steps:
			self.selected_cell[0] = int(n_steps) - 1
		self.keymap_offset = self.zynseq.libseq.getRefNote()
		if self.keymap_offset >= keymap_len:
			self.keymap_offset = (keymap_len - self.vzoom) // 2
			self.selected_cell[1] = self.keymap_offset + self.vzoom // 2
		if self.duration > n_steps:
			self.duration = 1
		self.draw_grid()
		self.select_cell()
		self.set_keymap_offset()
		self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)
		self.set_title("Pattern {}".format(self.pattern))

	# Function to refresh status
	def refresh_status(self):
		super().refresh_status()
		self.playstate = self.zynseq.libseq.getSequenceState(self.bank, self.sequence) & 0xff
		step = self.zynseq.libseq.getPatternPlayhead()
		if self.playhead != step:
			self.playhead = step
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.step_width * (self.playhead + 1), PLAYHEAD_HEIGHT)
		if (self.reload_keymap or self.zynseq.libseq.isPatternModified()) and self.redraw_pending < 3:
			self.redraw_pending = 3
		if self.reload_keymap:
			self.load_keymap()
			self.reload_keymap = False
			self.set_keymap_offset()
		if self.redraw_pending:
			self.draw_grid()
		if not self.drawing:
			pending_rows = set()
			while not self.rows_pending.empty():
				pending_rows.add(self.rows_pending.get_nowait())
			while len(pending_rows):
				self.draw_row(pending_rows.pop(), None)
		self.save_pattern_snapshot(force=False)

	# Function to handle MIDI notes (only used to refresh screen - actual MIDI input handled by lib)
	def midi_note(self, note):
		self.changed = True
		self.rows_pending.put_nowait(note)

	def set_edit_title(self):
		step = self.selected_cell[0]
		note = self.get_note_from_row(self.selected_cell[1])
		delta = "1"
		zynpot = 2
		if self.edit_mode == EDIT_MODE_ALL:
			if self.edit_param == EDIT_PARAM_DUR:
				delta = "0.1"
				zynpot = 1
				self.set_title("Duration ALL")
			elif self.edit_param == EDIT_PARAM_VEL:
				self.set_title("Velocity ALL")
			elif self.edit_param == EDIT_PARAM_STUT_CNT:
				self.set_title("Stutter count ALL")
			elif self.edit_param == EDIT_PARAM_STUT_DUR:
				self.set_title("Stutter duration ALL")
		else:
			if self.edit_param == EDIT_PARAM_DUR:
				sel_duration = self.zynseq.libseq.getNoteDuration(step, note)
				if sel_duration > 0:
					duration = sel_duration
				else:
					duration = self.duration
				self.set_title(f"Duration: {duration:0.1f} steps")
				delta = "0.1"
				zynpot = 1
			elif self.edit_param == EDIT_PARAM_VEL:
				sel_velocity = self.zynseq.libseq.getNoteVelocity(step, note)
				if sel_velocity > 0:
					velocity = sel_velocity
				else:
					velocity = self.velocity
				self.set_title(f"Velocity: {velocity}")
			elif self.edit_param == EDIT_PARAM_OFFSET:
				self.set_title(f"Offset: {round(100 * self.zynseq.libseq.getNoteOffset(step, note))}%")
			elif self.edit_param == EDIT_PARAM_STUT_CNT:
				self.set_title(f"Stutter count: {self.zynseq.libseq.getStutterCount(step, note)}")
			elif self.edit_param == EDIT_PARAM_STUT_DUR:
				self.set_title(f"Stutter duration: {self.zynseq.libseq.getStutterDur(step, note)}")
			elif self.edit_param == EDIT_PARAM_CHANCE:
				self.set_title(f"Play chance: {self.zynseq.libseq.getNotePlayChance(step, note)}%")

		self.init_buttonbar([(f"ZYNPOT {zynpot},-1", f"-{delta}"),(f"ZYNPOT {zynpot},+1", f"+{delta}"),("ZYNPOT 3,-1", "PREV\nPARAM"),("ZYNPOT 3,+1", "NEXT\nPARAM"),(3,"OK")])

	# Function to handle zynpots value change
	#   i: Zynpot index [0..n]
	#   dval: Current value of zyncoder
	def zynpot_cb(self, i, dval):
		if super().zynpot_cb(i, dval):
			return

		if i == self.ctrl_order[0] and zynthian_gui_config.transport_clock_source <= 1:
			self.zynseq.update_tempo()
			self.zynseq.nudge_tempo(dval)
			self.set_title("Tempo: {:.1f}".format(self.zynseq.get_tempo()), None, None, 2)

		elif i == self.ctrl_order[1]:
			if self.edit_mode == EDIT_MODE_SINGLE:
				if self.edit_param == EDIT_PARAM_DUR:
					step = self.selected_cell[0]
					index = self.selected_cell[1]
					note = self.keymap[index]['note']
					sel_duration = self.zynseq.libseq.getNoteDuration(step, note)
					if sel_duration > 0:
						duration = sel_duration
					else:
						duration = self.duration
					duration += 0.1 * dval
					max_duration = self.n_steps
					if duration > max_duration or duration < 0.05:
						return
					if sel_duration:
						sel_velocity = self.zynseq.libseq.getNoteVelocity(step, note)
						sel_offset = self.zynseq.libseq.getNoteOffset(step, note)
						self.add_event(step, self.selected_cell[1], sel_velocity, duration, sel_offset)
					else:
						self.duration = duration
						self.select_cell()
					self.set_edit_title()
			elif self.edit_mode == EDIT_MODE_ALL:
				if self.edit_param == EDIT_PARAM_DUR:
					self.zynseq.libseq.changeDurationAll(dval * 0.1)
					self.redraw_pending = 3
			else:
				self.set_grid_scale(dval, dval)
				#patnum = self.pattern + dval
				#if patnum > 0:
				#	self.pattern = patnum
				#	self.load_pattern(self.pattern)

		elif i == self.ctrl_order[2]:
			if self.edit_mode == EDIT_MODE_SINGLE:
				step = self.selected_cell[0]
				index = self.selected_cell[1]
				note = self.keymap[index]['note']
				sel_duration = self.zynseq.libseq.getNoteDuration(step, note)
				if self.edit_param == EDIT_PARAM_DUR:
					if sel_duration > 0:
						duration = sel_duration
					else:
						duration = self.duration
					duration += dval
					max_duration = self.n_steps
					if duration > max_duration or duration < 0.05:
						return
					if sel_duration:
						sel_velocity = self.zynseq.libseq.getNoteVelocity(step, note)
						sel_offset = self.zynseq.libseq.getNoteOffset(step, note)
						self.add_event(step, index, sel_velocity, duration, sel_offset)
					else:
						self.duration = duration
						self.select_cell()
				elif self.edit_param == EDIT_PARAM_VEL:
					if sel_duration:
						sel_velocity = self.zynseq.libseq.getNoteVelocity(step, note)
						velocity = sel_velocity
					else:
						velocity = self.velocity
					velocity += dval
					if velocity > 127 or velocity < 1:
						return
					self.set_velocity_indicator(velocity)
					if sel_duration and velocity != sel_velocity:
						self.zynseq.libseq.setNoteVelocity(step, note, velocity)
						self.draw_cell(step, index - self.keymap_offset)
					else:
						self.velocity = velocity
						self.select_cell()
				elif self.edit_param == EDIT_PARAM_OFFSET:
					val = round(100 * self.zynseq.libseq.getNoteOffset(step, note)) + dval
					if val > 99:
						val = 99
					elif val < 0:
						val = 0
					self.zynseq.libseq.setNoteOffset(step, note, val/100.0)
					self.draw_row(index)
				elif self.edit_param == EDIT_PARAM_STUT_CNT:
					val = self.zynseq.libseq.getStutterCount(step, note) + dval
					if val < 0:
						val = 0
					self.zynseq.libseq.setStutterCount(step, note, val)
					self.draw_cell(step, note - self.keymap_offset)
				elif self.edit_param == EDIT_PARAM_STUT_DUR:
					val = self.zynseq.libseq.getStutterDur(step, note) + dval
					if val < 1:
						val = 1
					self.zynseq.libseq.setStutterDur(step, note, val)
					self.draw_cell(step, note - self.keymap_offset)
				elif self.edit_param == EDIT_PARAM_CHANCE:
					val = self.zynseq.libseq.getNotePlayChance(step, note) + dval
					if val < 0:
						val = 0
					elif val > 100:
						val = 100
					self.zynseq.libseq.setNotePlayChance(step, note, val)
					self.draw_cell(step, note - self.keymap_offset)
				self.set_edit_title()
			elif self.edit_mode == EDIT_MODE_ALL:
				if self.edit_param == EDIT_PARAM_DUR:
					if dval > 0:
						self.zynseq.libseq.changeDurationAll(1)
					if dval < 0:
						self.zynseq.libseq.changeDurationAll(-1)
					self.redraw_pending = 3
				elif self.edit_param == EDIT_PARAM_VEL:
					self.zynseq.libseq.changeVelocityAll(dval)
					self.redraw_pending = 3
				elif self.edit_param == EDIT_PARAM_STUT_CNT:
					self.zynseq.libseq.changeStutterCountAll(dval)
					self.redraw_pending = 3
				elif self.edit_param == EDIT_PARAM_STUT_DUR:
					self.zynseq.libseq.changeStutterDurAll(dval)
					self.redraw_pending = 3
			else:
				self.select_cell(None, self.selected_cell[1] - dval)

		elif i == self.ctrl_order[3]:
			if self.edit_mode == EDIT_MODE_SINGLE or self.edit_mode == EDIT_MODE_ALL:
				self.edit_param += dval
				if self.edit_param < 0:
					self.edit_param = 0
				if self.edit_param > EDIT_PARAM_LAST:
					self.edit_param = EDIT_PARAM_LAST
				self.set_edit_title()
			elif self.edit_mode == EDIT_MODE_SCALE:
				self.set_grid_scale(dval, dval)
			else:
				self.select_cell(self.selected_cell[0] + dval, None)

	# Function to handle SELECT button press
	# type: Button press duration ["S"=Short, "B"=Bold, "L"=Long]
	def switch_select(self, type='S'):
		if super().switch_select(type):
			return
		if type == "S":
			if self.edit_mode == EDIT_MODE_NONE:
				note = self.toggle_event(self.selected_cell[0], self.selected_cell[1])
				if note:
					self.play_note(note)
			else:
				self.enable_edit(EDIT_MODE_NONE)
		elif type == "B":
			if self.edit_mode == EDIT_MODE_NONE:
				self.enable_edit(EDIT_MODE_SINGLE)
			elif self.edit_mode == EDIT_MODE_SINGLE:
				self.enable_edit(EDIT_MODE_ALL)

	# Function to handle switch press
	#   i: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#   type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#   returns True if action fully handled or False if parent action should be triggered
	def switch(self, i, type):
		if i == 2:
			if type == 'S':
				self.cuia_toggle_play()
			elif type == 'B':
				self.cuia_toggle_record()
			return True
		return False

	# Function to handle BACK button
	def back_action(self):
		if self.edit_mode == EDIT_MODE_NONE:
			return super().back_action()
		self.enable_edit(EDIT_MODE_NONE)
		return True

	# CUIA Actions

	# Function to toggle grid scale mode
	def toggle_grid_scale(self):
		if self.edit_mode == EDIT_MODE_NONE:
			self.edit_mode = EDIT_MODE_SCALE
			self.set_title("Grid zoom", zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)
		elif self.edit_mode == EDIT_MODE_SCALE:
			self.edit_mode = EDIT_MODE_NONE
			self.set_title("Pattern {}".format(self.pattern), zynthian_gui_config.color_panel_tx, zynthian_gui_config.color_header_bg)


	# Function to handle CUIA ARROW_RIGHT
	def arrow_right(self):
		if self.zyngui.alt_mode:
			self.redo_pattern()
		else:
			self.zynpot_cb(self.ctrl_order[3], 1)

	# Function to handle CUIA ARROW_LEFT
	def arrow_left(self):
		if self.zyngui.alt_mode:
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

	# Default status area release callback
	def cb_status_release(self, params=None):
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
