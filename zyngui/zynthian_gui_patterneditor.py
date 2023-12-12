#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pattern Editor Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
from queue import Queue
import tkinter
import logging
import tkinter.font as tkFont
import json
from xml.dom import minidom
from datetime import datetime
from math import ceil
from collections import OrderedDict

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zynlibs.zynsmf import zynsmf
from . import zynthian_gui_base
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq


# ------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern Editor GUI Class
# ------------------------------------------------------------------------------

# Local constants
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
CELL_BACKGROUND		= zynthian_gui_config.color_panel_bd
CELL_FOREGROUND		= zynthian_gui_config.color_panel_tx
GRID_LINE			= zynthian_gui_config.color_tx_off
PLAYHEAD_HEIGHT		= 5
CONFIG_ROOT			= "/zynthian/zynthian-data/zynseq"

EDIT_MODE_NONE		= 0  # Edit mode disabled
EDIT_MODE_SINGLE	= 1  # Edit mode enabled for selected note
EDIT_MODE_ALL		= 2  # Edit mode enabled for all notes
EDIT_PARAM_DUR		= 0  # Edit note duration
EDIT_PARAM_VEL		= 1  # Edit note velocity
EDIT_PARAM_STUT_CNT	= 2  # Edit note stutter count
EDIT_PARAM_STUT_DUR	= 3  # Edit note stutter duration
EDIT_PARAM_LAST		= 3  # Index of last parameter

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
		os.makedirs(CONFIG_ROOT, exist_ok=True) #TODO: Do we want/need these dirs?
		self.zynseq_dpath = os.environ.get('ZYNTHIAN_DATA_DIR', "/zynthian/zynthian-data") + "/zynseq"
		self.patterns_dpath = self.zynseq_dpath + "/patterns"
		self.my_zynseq_dpath = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/zynseq"
		self.my_patterns_dpath = self.my_zynseq_dpath + "/patterns"
		self.my_captures_dpath = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"
		self.zynseq = self.zyngui.state_manager.zynseq

		self.status_canvas.bind("<ButtonRelease-1>", self.cb_status_release)

		self.ctrl_order = zynthian_gui_config.layout['ctrl_order']

		self.edit_mode = EDIT_MODE_NONE # Enable encoders to adjust duration and velocity
		self.edit_param = EDIT_PARAM_DUR # Parameter to adjust in parameter edit mode
		self.zoom = 16 # Quantity of rows (notes) displayed in grid
		self.duration = 1.0 # Current note entry duration
		self.velocity = 100 # Current note entry velocity
		self.copy_source = 1 # Index of pattern to copy
		self.bank = None # Bank used for pattern editor sequence player
		self.pattern = 0 # Pattern to edit
		self.sequence = None # Sequence used for pattern editor sequence player
		self.last_play_mode = zynseq.SEQ_LOOP
		self.n_steps = 0 # Number of steps in current pattern
		self.n_steps_beat = 0 # Number of steps per beat (current pattern)
		self.step_width = 40 # Grid column width in pixels
		self.keymap_offset = 60 # MIDI note number of bottom row in grid
		self.selected_cell = [0, 60] # Location of selected cell (column,row)
		self.drag_velocity = False # True indicates drag will adjust velocity
		self.drag_duration = False # True indicates drag will adjust duration
		self.drag_start_velocity = None # Velocity value at start of drag
		self.drag_note = False # True if dragging note in grid
		self.grid_drag_start = None # Coordinates at start of grid drag
		self.keymap = []  # Array of {"note":MIDI_NOTE_NUMBER, "name":"key name","colour":"key colour"} name and colour are optional
		# TODO: Get values from persistent storage
		self.cells = []  # Array of cells indices
		self.redraw_pending = 4  # What to redraw: 0=nothing, 1=selected cell, 2=selected row, 3=refresh grid, 4=rebuild grid
		self.rows_pending = Queue()
		self.title = "Pattern 0"
		self.channel = 0
		self.drawing = False  # mutex to avoid mutliple concurrent] screen draws
		self.reload_keymap = False  # Signal keymap needs reloading

		# Geometry vars
		self.select_thickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.grid_height = self.height - PLAYHEAD_HEIGHT
		self.grid_width = int(self.width * 0.9)
		self.piano_roll_width = self.width - self.grid_width
		self.update_row_height()

		# Create pattern grid canvas
		self.grid_canvas = tkinter.Canvas(self.main_frame,
			width=self.grid_width,
			height=self.grid_height,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.grid_canvas.grid(column=1, row=0)
		self.grid_canvas.tag_bind("gridcell", '<ButtonPress-1>', self.on_grid_press)
		self.grid_canvas.tag_bind("gridcell", '<ButtonRelease-1>', self.on_grid_release)
		self.grid_canvas.tag_bind("gridcell", '<B1-Motion>', self.on_grid_drag)

		# Create velocity level indicator canvas
		self.velocity_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_roll_width,
			height=PLAYHEAD_HEIGHT,
			bg=CELL_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.velocity_canvas.create_rectangle(0, 0, self.piano_roll_width * self.velocity / 127, PLAYHEAD_HEIGHT, fill='yellow', tags="velocityIndicator", width=0)
		self.velocity_canvas.grid(column=0, row=1)

		# Create pianoroll canvas
		self.piano_roll = tkinter.Canvas(self.main_frame,
			width=self.piano_roll_width,
			height=self.grid_height,
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
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.play_canvas.create_rectangle(0, 0, self.step_width, PLAYHEAD_HEIGHT,
			fill=PLAYHEAD_CURSOR,
			state="normal",
			width=0,
			tags="playCursor")
		self.play_canvas.grid(column=1, row=1)

		self.playhead = 0
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
				if preset_name:
					title = preset_name.replace("_", " ")
				else:
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

		# Set active the chain with pattern's MIDI chan
		try:
			chain_id = self.zyngui.chain_manager.midi_chan_2_chain_id[self.channel]
			self.zyngui.chain_manager.set_active_chain_by_id(chain_id)
		except:
			logging.error(f"Couldn't set active chain to channel {self.channel}.")

		zoom = self.zynseq.libseq.getVerticalZoom()
		if zoom != self.zoom:
			self.set_vzoom(zoom)

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

	# Function to add menus
	def show_menu(self):
		self.disable_param_editor()
		options = OrderedDict()
		extra_options = not zynthian_gui_config.check_wiring_layout(["Z2", "V5"])

		# Global Options
		if extra_options:
			options['Tempo'] = 'Tempo'
		if not zynthian_gui_config.check_wiring_layout(["Z2"]):
			options['Arranger'] = 'Arranger'
		options['Beats per bar ({})'.format(self.zynseq.libseq.getBeatsPerBar())] = 'Beats per bar'

		# Pattern Options
		options['> PATTERN OPTIONS'] = None
		options['Beats in pattern ({})'.format(self.zynseq.libseq.getBeatsInPattern())] = 'Beats in pattern'
		options['Steps per beat ({})'.format(self.n_steps_beat)] = 'Steps per beat'
		options['Vertical zoom ({})'.format(self.zoom)] = 'Vertical zoom'
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
				options['\u2612 Record from MIDI'] = 'midi_record'
			else:
				options['\u2610 Record from MIDI'] = 'midi_record'
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
		if params == 'Tempo':
			self.zyngui.show_screen('tempo')
		elif params == 'Arranger':
			self.zyngui.show_screen('arranger')
		elif params == 'Beats per bar':
			self.enable_param_editor(self, 'bpb', 'Beats per bar', {'value_min':1, 'value_max':64, 'value_default':4, 'value':self.zynseq.libseq.getBeatsPerBar()})
		elif params == 'Beats in pattern':
			self.enable_param_editor(self, 'bip', 'Beats in pattern', {'value_min':1, 'value_max':64, 'value_default':4, 'value':self.zynseq.libseq.getBeatsInPattern()}, self.assert_beats_in_pattern)
		elif params == 'Steps per beat':
			self.enable_param_editor(self, 'spb', 'Steps per beat', {'ticks': STEPS_PER_BEAT, 'value_default': 3, 'value': self.n_steps_beat}, self.assert_steps_per_beat)
		elif params == 'Copy pattern':
			self.copy_source = self.pattern
			self.enable_param_editor(self, 'copy', 'Copy pattern to', {'value_min':1, 'value_max':zynseq.SEQ_MAX_PATTERNS, 'value':self.pattern}, self.copy_pattern)
		elif params == 'Load pattern':
			self.zyngui.screens['option'].config_file_list("Load pattern", [self.patterns_dpath, self.my_patterns_dpath], "*.zpat", self.load_pattern_file)
			self.zyngui.show_screen('option')
		elif params == 'Save pattern':
			self.zyngui.show_keyboard(self.save_pattern_file, "pat#{}".format(self.pattern))
		elif params == 'Clear pattern':
			self.clear_pattern()
		elif params == 'Transpose pattern':
			self.enable_param_editor(self, 'transpose', 'Transpose', {'value_min':-1, 'value_max':1, 'labels':['down','down/up','up'], 'value':0})
		elif params == 'Vertical zoom':
			self.enable_param_editor(self, 'vzoom', 'Vertical zoom', {'value_min':1, 'value_max':127, 'value_default':16, 'value':self.zoom})
		elif params == 'Scale':
			self.enable_param_editor(self, 'scale', 'Scale', {'labels':self.get_scales(), 'value':self.zynseq.libseq.getScale()})
		elif params == 'Tonic':
			self.enable_param_editor(self, 'tonic', 'Tonic', {'labels':NOTE_NAMES, 'value':self.zynseq.libseq.getTonic()})
		elif params == 'Rest note':
			labels = ['None']
			for note in range(128):
				labels.append("{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1))
			value = self.zynseq.libseq.getInputRest() + 1
			if value > 128:
				value = 0
			options = {'labels':labels, 'value':value}
			self.enable_param_editor(self, 'rest', 'Rest', options)
		elif params == 'Add program change':
			self.enable_param_editor(self, 'prog_change', 'Program', {'value_max':128, 'value':self.get_program_change()}, self.add_program_change)
		elif params == 'midi_record':
			self.toggle_midi_record()
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
		self.redraw_pending = 3

	def toggle_midi_record(self, midi_record=None):
		if midi_record is None:
			midi_record = not self.zynseq.libseq.isMidiRecord()
		self.zynseq.libseq.enableMidiRecord(midi_record)
		if midi_record:
			self.zynseq.libseq.snapshotPattern(self.pattern)
		else:
			self.zynseq.libseq.resetPatternSnapshot()

	def send_controller_value(self, zctrl):
		if zctrl.symbol == 'tempo':
			self.zynseq.libseq.setTempo(zctrl.value)
		elif zctrl.symbol == 'metro_vol':
			self.zynseq.libseq.setMetronomeVolume(zctrl.value / 100.0)
		elif zctrl.symbol == 'bpb':
			self.zynseq.libseq.setBeatsPerBar(zctrl.value)
		elif zctrl.symbol == 'copy':
			self.load_pattern(zctrl.value)
		elif zctrl.symbol == 'transpose':
			self.transpose(zctrl.value)
			zctrl.set_value(0)
		elif zctrl.symbol == 'vzoom':
			self.set_vzoom(zctrl.value)
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
		if (offset != 0):
			if self.zynseq.libseq.getScale():
				# Only allow transpose when showing chromatic scale
				self.zynseq.libseq.setScale(0)
				self.load_keymap()
			
			self.zynseq.libseq.transpose(offset)
			self.keymap_offset = self.keymap_offset + offset
			if self.keymap_offset > 128 - self.zoom:
				self.keymap_offset = 128 - self.zoom
			elif self.keymap_offset < 0:
				self.keymap_offset = 0
			else:
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
		self.n_steps_beat = self.zynseq.libseq.getStepsPerBeat()
		self.n_steps = self.zynseq.libseq.getSteps()
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
		self.n_steps = self.zynseq.libseq.getSteps()
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
		data = []
		try:
			with open(CONFIG_ROOT + "/scales.json") as json_file:
				data = json.load(json_file)
		except:
			logging.warning("Unable to open scales.json")
		res = []
		for scale in data:
			res.append(scale['name'])
		return res

	# Function to set vertical zoom
	def set_vzoom(self, value):
		self.zoom = value
		self.zynseq.libseq.setVerticalZoom(value)
		self.update_row_height()
		self.redraw_pending = 4
		self.select_cell()

	# Function to populate keymap array
	# returns Name of scale / map
	def load_keymap(self):
		map_name = None
		self.keymap = []
		scale = self.zynseq.libseq.getScale()
		tonic = self.zynseq.libseq.getTonic()

		if scale == 0:
			# Search for a map
			synth_proc = self.zyngui.chain_manager.get_synth_processor(self.channel)
			if synth_proc:
				path = synth_proc.get_presetpath()
			else:
				path = None

			if path:
				try:
					with open(CONFIG_ROOT + "/keymaps.json") as json_file:
						data = json.load(json_file)
						for pat in data:
							if pat in path:
								map_name = data[pat]
								break
				except:
					logging.warning("Unable to load keymaps.json")

				if map_name:
					logging.info("Loading keymap {} for MIDI channel {}...".format(map_name, self.channel))
					try:
						xml = minidom.parse(CONFIG_ROOT + f"/{map_name}.midnam")
						notes = xml.getElementsByTagName('Note')
						for note in notes:
							self.keymap.append({'note':int(note.attributes['Number'].value), 'name':note.attributes['Name'].value})
					except Exception as e:
						logging.error("Can't load midnam file => {}".format(e))

			else:
				logging.info("MIDI channel {} has not synth processors.".format(self.channel))

		# Not found map
		if map_name is None:
			try:
				base_note = int(self.keymap[self.keymap_offset]['note'])
			except:
				base_note = 60

			# Scale
			self.zynseq.libseq.setScale(scale) # Use chromatic scale if map not found
			if scale == 0:
				for note in range(0,128):
					new_entry = {"note":note}
					key = note % 12
					if key in (1,3,6,8,10): # Black notes
						new_entry.update({"colour":"black"})
					else:
						new_entry.update({"colour":"white"})
					if key == 0: # 'C'
						new_entry.update({"name":"C{}".format(note // 12 - 1)})
					self.keymap.append(new_entry)
				map_name = "Chromatic"
			else:
				with open(CONFIG_ROOT + "/scales.json") as json_file:
					data = json.load(json_file)
				if len(data) <= scale:
					scale = 0
				for octave in range(0,9):
					for offset in data[scale]['scale']:
						note = tonic + offset + octave * 12
						if note > 127:
							break
						self.keymap.append({"note":note, "name":"{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1)})
				map_name = data[scale]['name']

		return map_name

	# Function to handle start of pianoroll drag
	def on_pianoroll_press(self, event):
		self.piano_roll_drag_start = event
		index = self.keymap_offset + self.zoom - int(event.y / self.row_height) - 1
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		self.play_note(note)

	# Function to handle pianoroll drag motion
	def on_pianoroll_motion(self, event):
		if not self.piano_roll_drag_start:
			return
		offset = int((event.y - self.piano_roll_drag_start.y) / self.row_height)
		if offset == 0:
			return
		self.keymap_offset = self.keymap_offset + offset
		if self.keymap_offset < 0:
			self.keymap_offset = 0
		if self.keymap_offset > len(self.keymap) - self.zoom:
			self.keymap_offset = len(self.keymap) - self.zoom

		self.piano_roll_drag_start = event
		self.redraw_pending = 3

		if self.selected_cell[1] < self.keymap_offset:
			self.selected_cell[1] = self.keymap_offset
		elif self.selected_cell[1] >= self.keymap_offset + self.zoom:
			self.selected_cell[1] = self.keymap_offset + self.zoom - 1
		self.select_cell()

	# Function to handle end of pianoroll drag
	def on_pianoroll_release(self, event):
		self.piano_roll_drag_start = None

	# Function to handle mouse wheel over pianoroll
	def on_pianoroll_wheel(self, event):
		if event.num == 4:
			# Scroll up
			if self.keymap_offset + self.zoom < len(self.keymap):
				self.keymap_offset += 1
				self.redraw_pending = 3
				if self.selected_cell[1] < self.keymap_offset:
					self.select_cell(self.selected_cell[0], self.keymap_offset)
		else:
			# Scroll down
			if self.keymap_offset:
				self.keymap_offset -= 1
				self.redraw_pending = 3
				if self.selected_cell[1] >= self.keymap_offset + self.zoom:
					self.select_cell(self.selected_cell[0], self.keymap_offset + self.zoom - 1)

	# Function to handle grid mouse down
	# event: Mouse event
	def on_grid_press(self, event):
		if self.param_editor_zctrl:
			self.disable_param_editor()
		self.grid_drag_start = event
		step = int(event.x / self.step_width)
		row = self.zoom - int(event.y / self.row_height) - 1
		note = self.keymap[self.keymap_offset + int(row)]["note"]
		if step < 0 or step >= self.n_steps:
			return
		start_step = self.zynseq.libseq.getNoteStart(step, note)
		self.drag_start_step = step
		if start_step >= 0:
			step = start_step
		self.select_cell(step, self.keymap_offset + int(row))
		self.drag_start_velocity = self.zynseq.libseq.getNoteVelocity(step, note)
		self.drag_start_duration = self.zynseq.libseq.getNoteDuration(step, note)
		if not self.drag_start_velocity:
			self.play_note(note)
			self.drag_note = True

	# Function to handle grid mouse release
	# event: Mouse event
	def on_grid_release(self, event):
		if not self.grid_drag_start:
			return
		if not self.drag_note and event.time - self.grid_drag_start.time > 800:
			# Bold click
			if self.edit_mode == EDIT_MODE_NONE:
				self.enable_edit(EDIT_MODE_SINGLE)
			else:
				self.enable_edit(EDIT_MODE_ALL)
		else:
			self.toggle_event(self.selected_cell[0], self.selected_cell[1])
		self.drag_velocity = False
		self.drag_duration = False
		self.drag_note = False
		self.grid_drag_start = None

	# Function to handle grid mouse drag
	# event: Mouse event
	def on_grid_drag(self, event):
		if not self.grid_drag_start:
			return
		step = self.selected_cell[0]
		index = self.selected_cell[1]
		note = self.keymap[index]['note']
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
					if velocity >= 1 and velocity <= 127:
						self.set_velocity_indicator(velocity)
						if sel_duration and velocity != sel_velocity:
							self.zynseq.libseq.setNoteVelocity(step, note, velocity)
							self.draw_cell(step, index - self.keymap_offset)
			if self.drag_duration:
				duration = int(event.x / self.step_width) - self.drag_start_step
				if duration > 0 and duration != sel_duration:
					self.add_event(step, index, sel_velocity, duration)
				else:
					#self.duration = duration
					pass
		else:
			# Clicked on empty cell so want to add a new note by dragging towards the desired cell
			x1 = self.selected_cell[0] * self.step_width # x pos of start of event
			x3 = (self.selected_cell[0] + 1) * self.step_width # x pos right of event's first cell
			y1 = self.grid_height - (self.selected_cell[1] - self.keymap_offset) * self.row_height # y pos of top of selected row
			y2 = self.grid_height - (self.selected_cell[1] - self.keymap_offset + 1) * self.row_height # y pos of bottom of selected row
			if event.x < x1:
				self.select_cell(self.selected_cell[0] - 1, None)
			elif event.x > x3:
				self.select_cell(self.selected_cell[0] + 1, None)
			elif event.y < y2:
				self.select_cell(None, self.selected_cell[1] + 1)
				self.play_note(self.keymap[self.selected_cell[1]]["note"])
			elif event.y > y1:
				self.select_cell(None, self.selected_cell[1] - 1)
				self.play_note(self.keymap[self.selected_cell[1]]["note"])

	# Function to adjust velocity indicator
	# velocity: Note velocity to indicate
	def set_velocity_indicator(self, velocity):
		self.velocity_canvas.coords("velocityIndicator", 0, 0, self.piano_roll_width * velocity / 127, PLAYHEAD_HEIGHT)

	# Function to toggle note event
	# step: step (column) index
	# index: key map index
	# Returns: Note if note added else None
	def toggle_event(self, step, index):
		if step < 0 or step >= self.n_steps or index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		start_step = self.zynseq.libseq.getNoteStart(step, note)
		if start_step >= 0:
			self.remove_event(start_step, index)
		else:
			self.add_event(step, index, self.velocity, self.duration)
			return note

	# Function to remove an event
	# step: step (column) index
	# index: keymap index
	def remove_event(self, step, index):
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		self.zynseq.libseq.removeNote(step, note)
		self.zynseq.libseq.playNote(note, 0, self.channel) # Silence note if sounding
		self.draw_row(index)
		self.select_cell(step, index)

	# Function to add an event
	# step: step (column) index
	# index: keymap index
	# vel: velocity (0-127)
	# dur: duration (in steps)
	def add_event(self, step, index, vel, dur):
		note = self.keymap[index]["note"]
		self.zynseq.libseq.addNote(step, note, vel, dur)
		self.draw_row(index)
		self.select_cell(step, index)

	# Function to draw a grid row
	# index: keymap index
	# colour: Black, white or None (default) to not care
	def draw_row(self, index, white=None):
		row = index - self.keymap_offset
		self.grid_canvas.itemconfig(f"lastnotetext{row}", state="hidden")
		for step in range(self.n_steps):
			self.draw_cell(step, row, white)

	# Function to get cell coordinates
	# col: Column index
	# row: Row index
	# duration: Duration of cell in steps
	# return: Coordinates required to draw cell
	def get_cell(self, col, row, duration):
		x1 = col * self.step_width + 1
		y1 = (self.zoom - row - 1) * self.row_height + 1
		x2 = x1 + self.step_width * duration - 1
		y2 = y1 + self.row_height - 1
		return [x1, y1, x2, y2]

	# Function to draw a grid cell
	# step: Step (column) index
	# row: Index of row
	# white: True for white notes
	def draw_cell(self, step, row, white=None):
		self.zynseq.libseq.isPatternModified() # Flush modified flag to avoid refresh redrawing whole grid
		cellIndex = row * self.n_steps + step  # Cells are stored in array sequentially: 1st row, 2nd row...
		if cellIndex >= len(self.cells):
			return
		note = self.keymap[row + self.keymap_offset]["note"]
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
		else:
			velocity_colour = 30 * int(white)
			duration = 1.0
		fill_colour = f"#{velocity_colour:02x}{velocity_colour:02x}{velocity_colour:02x}"

		if not duration:
			duration = 1.0

		coord = self.get_cell(step, row, duration)
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
		if len(self.cells) != self.zoom * self.n_steps:
			redraw_pending = 4
		if self.n_steps == 0:
			self.drawing = False
			return #TODO: Should we clear grid?
		if self.keymap_offset > len(self.keymap) - self.zoom:
			self.keymap_offset = len(self.keymap) - self.zoom
		if self.keymap_offset < 0:
			self.keymap_offset = 0
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		if redraw_pending == 4:
			self.grid_canvas.delete(tkinter.ALL)
			self.step_width = (self.grid_width - 2) / self.n_steps
			self.draw_pianoroll()
			self.cells = [None] * self.zoom * self.n_steps
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)

		# Draw cells of grid
		#self.grid_canvas.itemconfig("gridcell", fill="black")
		if redraw_pending > 2:
			# Redraw gridlines
			self.grid_canvas.delete("gridline")
			if self.n_steps_beat:
				for step in range(0, self.n_steps + 1, self.n_steps_beat):
					self.grid_canvas.create_line(step * self.step_width, 0, step * self.step_width, self.zoom * self.row_height - 1, fill=GRID_LINE, tags=("gridline"))

		if redraw_pending > 1:
			# Delete existing note names from piano roll
			self.piano_roll.delete("notename")

			if redraw_pending > 2:
				row_min = 0
				row_max = self.zoom
			else:
				row_min = self.selected_cell[1]
				row_max = self.selected_cell[1]
			for row in range(row_min, row_max):
				index = row + self.keymap_offset
				if(index >= len(self.keymap)):
					break

				# Create last note labels in grid
				self.grid_canvas.create_text(self.grid_width - self.select_thickness, int(self.row_height * (self.zoom - row - 0.5)), state="hidden", tags=(f"lastnotetext{row}", "lastnotetext", "gridcell"), font=font, anchor="e")

				fill = "black"
				# Update pianoroll keys
				id = f"row{row}"
				try:
					name = self.keymap[index]["name"]
				except:
					name = None
				if "colour" in self.keymap[index]:
					colour = self.keymap[index]["colour"]
				elif name and "#" in name:
					colour = "black"
					fill = "white"
				else:
					colour = "white"
					fill = CANVAS_BACKGROUND
				self.piano_roll.itemconfig(id, fill=colour)
				if name:
					self.piano_roll.create_text((2, self.row_height * (self.zoom - row - 0.5)), text=name, font=font, anchor="w", fill=fill, tags="notename")
				if self.keymap[index]['note'] % 12 == self.zynseq.libseq.getTonic():
					self.grid_canvas.create_line(0, (self.zoom - row) * self.row_height, self.grid_width, (self.zoom - row) * self.row_height, fill=GRID_LINE, tags=("gridline"))
				# Draw row of note cells
				self.draw_row(index, (colour == "white"))

		# Set z-order to allow duration to show
		if redraw_pending > 2:
			for step in range(self.n_steps):
				self.grid_canvas.tag_lower(f"step{step}")
		self.select_cell()
		self.drawing = False

	# Function to draw pianoroll key outlines (does not fill key colour)
	def draw_pianoroll(self):
		self.piano_roll.delete(tkinter.ALL)
		for row in range(self.zoom):
			x1 = 0
			y1 = self.get_cell(0, row, 1)[1]
			x2 = self.piano_roll_width
			y2 = y1 + self.row_height - 1
			id = f"row{row}"
			id = self.piano_roll.create_rectangle(x1, y1, x2, y2, width=0, tags=id)

	# Function to update selectedCell
	# step: Step (column) of selected cell (Optional - default to reselect current column)
	# index: Index of keymap to select (Optional - default to reselect current row) Maybe outside visible range to scroll display
	def select_cell(self, step=None, index=None):
		if not self.keymap:
			return
		redraw = False
		if step == None:
			step = self.selected_cell[0]
		if index == None:
			index = self.selected_cell[1]
		if step < 0:
			step = 0
		if step >= self.n_steps:
			step = self.n_steps - 1
		if index >= len(self.keymap):
			index = len(self.keymap) - 1
		if index >= self.keymap_offset + self.zoom:
			# Note is off top of display
			self.keymap_offset = index - self.zoom + 1
			redraw = True
		if index < 0:
			index = 0
		if index < self.keymap_offset:
			# Note is off bottom of display
			self.keymap_offset = index
			redraw = True
		if redraw and self.redraw_pending < 1:
			self.redraw_pending = 3
		row = index - self.keymap_offset
		note = self.keymap[index]['note']
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
		if step < 0:
			step = 0
		if step >= self.n_steps:
			step = self.n_steps - 1
		self.selected_cell = [int(step), index]
		cell = self.grid_canvas.find_withtag("selection")
		duration = self.zynseq.libseq.getNoteDuration(step, note)
		if duration:
			velocity = self.zynseq.libseq.getNoteVelocity(step, note)
		else:
			duration = self.duration
			velocity = self.velocity
		self.set_velocity_indicator(velocity)
		coord = self.get_cell(step, row, duration)
		coord[0] = coord[0] - 1
		coord[1] = coord[1] - 1
		coord[2] = coord[2]
		coord[3] = coord[3]
		if not cell:
			cell = self.grid_canvas.create_rectangle(coord, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")
		else:
			self.grid_canvas.coords(cell, coord)
		self.grid_canvas.tag_raise(cell)

	# Function to calculate row height
	def update_row_height(self):
		self.row_height = (self.grid_height - 2) / self.zoom
		self.fontsize = int(self.row_height * 0.5)
		if self.fontsize > 20:
			self.fontsize = 20 # Ugly font scale limiting

	# Function to clear a pattern
	def clear_pattern(self, params=None):
		self.zyngui.show_confirm(f"Clear pattern {self.pattern}?", self.do_clear_pattern)

	# Function to actually clear pattern
	def do_clear_pattern(self, params=None):
		self.zynseq.libseq.clear()
		self.redraw_pending = 3
		self.select_cell()
		if self.zynseq.libseq.getPlayState(self.bank, self.sequence, 0) != zynseq.SEQ_STOPPED:
			self.zynseq.libseq.sendMidiCommand(0xB0 | self.channel, 123, 0) # All notes off

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
		#TODO: Update arranger when it is refactored
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
		if self.bank == 0 and self.sequence == 0:
			self.zynseq.libseq.setChannel(self.bank, self.sequence, 0, self.channel)
		self.pattern = index
		self.zynseq.libseq.selectPattern(index)
		n_steps = self.zynseq.libseq.getSteps()
		self.n_steps_beat = self.zynseq.libseq.getStepsPerBeat()
		if self.selected_cell[0] >= n_steps:
			self.selected_cell[0] = int(n_steps) - 1
		self.keymap_offset = self.zynseq.libseq.getRefNote()
		keymap_len = len(self.keymap)
		self.load_keymap()
		if self.redraw_pending < 4:
			if n_steps != self.n_steps or len(self.keymap) != keymap_len:
				self.n_steps = n_steps
				self.redraw_pending = 4
			else:
				self.redraw_pending = 3
		if self.keymap_offset >= len(self.keymap):
			self.keymap_offset = len(self.keymap) // 2 - self.zoom // 2
		self.selected_cell = [0, int(self.keymap_offset)]# + self.zoom / 2))
		if self.duration > n_steps:
			self.duration = 1
		self.draw_grid()
		self.select_cell(0, int(self.keymap_offset + self.zoom / 2))
		self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)
		self.set_title("Pattern {}".format(self.pattern))

	# Function to refresh status
	def refresh_status(self):
		super().refresh_status()
		step = self.zynseq.libseq.getPatternPlayhead()
		if self.playhead != step:
			self.playhead = step
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)
		if (self.reload_keymap or self.zynseq.libseq.isPatternModified()) and self.redraw_pending < 3:
			self.redraw_pending = 3
		if self.reload_keymap:
			self.load_keymap()
			self.reload_keymap = False
		if self.redraw_pending:
			self.draw_grid()
		pending_rows = set()
		while not self.rows_pending.empty():
			pending_rows.add(self.rows_pending.get_nowait())
		while len(pending_rows):
			self.draw_row(pending_rows.pop(), None)

	# Function to handle MIDI notes (only used to refresh screen - actual MIDI input handled by lib)
	def midi_note(self, note):
		if note >= self.keymap_offset and note < self.keymap_offset + self.zoom:
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
			elif self.edit_param == EDIT_PARAM_STUT_CNT:
				self.set_title(f"Stutter count: {self.zynseq.libseq.getStutterCount(step, note)}")
			elif self.edit_param == EDIT_PARAM_STUT_DUR:
				self.set_title(f"Stutter duration: {self.zynseq.libseq.getStutterDur(step, note)}")
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
						self.add_event(step, self.selected_cell[1], sel_velocity, duration)
					else:
						self.duration = duration
						self.select_cell()
					self.set_edit_title()
			elif self.edit_mode == EDIT_MODE_ALL:
				if self.edit_param == EDIT_PARAM_DUR:
					self.zynseq.libseq.changeDurationAll(dval * 0.1)
					self.redraw_pending = 3
			else:
				patnum = self.pattern + dval
				if patnum > 0:
					self.pattern = patnum
					self.load_pattern(self.pattern)

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
						self.add_event(step, index, sel_velocity, duration)
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
			else:
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
		if self.zynseq.libseq.isMidiRecord():
			self.zynseq.libseq.undoPattern()
			self.redraw_pending = 3
		elif self.edit_mode == EDIT_MODE_NONE:
			return super().back_action()
		self.enable_edit(EDIT_MODE_NONE)
		return True

	# CUIA Actions

	# Function to handle CUIA ARROW_RIGHT
	def arrow_right(self):
		self.zynpot_cb(self.ctrl_order[3], 1)

	# Function to handle CUIA ARROW_LEFT
	def arrow_left(self):
		self.zynpot_cb(self.ctrl_order[3], -1)

	# Function to handle CUIA ARROW_UP
	def arrow_up(self):
		if self.param_editor_zctrl:
			self.zynpot_cb(self.ctrl_order[3], 1)
		else:
			self.zynpot_cb(self.ctrl_order[2], -1)

	# Function to handle CUIA ARROW_DOWN
	def arrow_down(self):
		if self.param_editor_zctrl:
			self.zynpot_cb(self.ctrl_order[3], -1)
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

	# Setup CUIA methods
	cuia_toggle_record = toggle_midi_record
	cuia_stop = stop_playback
	cuia_toggle_play = toggle_playback

	def get_playback_status(self):
		return self.zynseq.libseq.getPlayState(self.bank, self.sequence)

	def update_wsleds(self, wsleds):
		wsl = self.zyngui.wsleds
		# REC button:
		if self.zynseq.libseq.isMidiRecord():
			wsl.wsleds.setPixelColor(wsleds[0], wsl.wscolor_red)
		else:
			wsl.wsleds.setPixelColor(wsleds[0], wsl.wscolor_active2)
		# STOP button
		wsl.wsleds.setPixelColor(wsleds[1], wsl.wscolor_active2)
		# PLAY button:
		pb_status = self.zyngui.screens['pattern_editor'].get_playback_status()
		if pb_status == zynseq.SEQ_PLAYING:
			wsl.wsleds.setPixelColor(wsleds[2], wsl.wscolor_green)
		elif pb_status in (zynseq.SEQ_STARTING, zynseq.SEQ_RESTARTING):
			wsl.wsleds.setPixelColor(wsleds[2], wsl.wscolor_yellow)
		elif pb_status in (zynseq.SEQ_STOPPING, zynseq.SEQ_STOPPINGSYNC):
			wsl.wsleds.setPixelColor(wsleds[2], wsl.wscolor_red)
		elif pb_status == zynseq.SEQ_STOPPED:
			wsl.wsleds.setPixelColor(wsleds[2], wsl.wscolor_active2)

	# Default status area release callback
	def cb_status_release(self, params=None):
		self.toggle_playback()

# ------------------------------------------------------------------------------
