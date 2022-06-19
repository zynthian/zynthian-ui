#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pattern Editor Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#
#******************************************************************************
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
#******************************************************************************

import os
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

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern Editor GUI Class
#------------------------------------------------------------------------------

# Local constants
SELECT_BORDER       = zynthian_gui_config.color_on
PLAYHEAD_CURSOR     = zynthian_gui_config.color_on
CANVAS_BACKGROUND   = zynthian_gui_config.color_panel_bg
CELL_BACKGROUND     = zynthian_gui_config.color_panel_bd
CELL_FOREGROUND     = zynthian_gui_config.color_panel_tx
GRID_LINE           = zynthian_gui_config.color_tx_off
PLAYHEAD_HEIGHT     = 5
CONFIG_ROOT         = "/zynthian/zynthian-data/zynseq"

EDIT_MODE_NONE		= 0 # Edit mode disabled
EDIT_MODE_SINGLE	= 1 # Edit mode enabled for selected note
EDIT_MODE_ALL		= 2 # Edit mode enabled for all notes

# List of permissible steps per beat
STEPS_PER_BEAT = [1,2,3,4,6,8,12,24]
INPUT_CHANNEL_LABELS = ['OFF','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16']
NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

# Class implements step sequencer pattern editor
class zynthian_gui_patterneditor(zynthian_gui_base.zynthian_gui_base):

	# Function to initialise class
	def __init__(self):

		self.buttonbar_config = [
			(zynthian_gui_config.ENC_LAYER, 'MENU\n(main menu)'),
			None,
			None,
			(zynthian_gui_config.ENC_SNAPSHOT, 'PLAY'),
		]
		super().__init__()

		os.makedirs(CONFIG_ROOT, exist_ok=True) #TODO: Do we want/need these dirs?

		self.edit_mode = EDIT_MODE_NONE # Enable encoders to adjust duration and velocity
		self.zoom = 16 # Quantity of rows (notes) displayed in grid
		self.duration = 1.0 # Current note entry duration
		self.velocity = 100 # Current note entry velocity
		self.copy_source = 1 # Index of pattern to copy
		self.bank = 0 # Bank used for pattern editor sequence player
		self.pattern = 0 # Pattern to edit
		self.sequence = 0 # Sequence used for pattern editor sequence player
		self.step_width = 40 # Grid column width in pixels
		self.keymap_offset = 60 # MIDI note number of bottom row in grid
		self.selected_cell = [0, 0] # Location of selected cell (column,row)
		self.drag_velocity = False # True indicates drag will adjust velocity
		self.drag_duration = False # True indicates drag will adjust duration
		self.drag_start_velocity = None # Velocity value at start of drag
		self.grid_drag_start = None # Coordinates at start of grid drag
		self.keymap = [] # Array of {"note":MIDI_NOTE_NUMBER, "name":"key name","colour":"key colour"} name and colour are optional
		#TODO: Get values from persistent storage
		self.cells = [] # Array of cells indices
		self.redraw_pending = 4 # What to redraw: 0=nothing, 1=selected cell, 2=selected row, 3=refresh grid, 4=rebuild grid
		self.title = "Pattern 0"
		self.channel = 0
		self.drawing = False # mutex to avoid mutliple concurrent] screen draws


		# Geometry vars
		self.select_thickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.grid_height = self.height - PLAYHEAD_HEIGHT - self.buttonbar_height - zynthian_gui_config.topbar_height
		self.grid_width = int(self.width * 0.9)
		self.piano_roll_width = self.width - self.grid_width
		self.update_row_height()

		self.seq_frame = tkinter.Frame(self.main_frame)
		self.seq_frame.grid(row=1)
		# Create pattern grid canvas
		self.grid_canvas = tkinter.Canvas(self.seq_frame,
			width=self.grid_width,
			height=self.grid_height,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.grid_canvas.grid(column=1, row=0)

		# Create velocity level indicator canvas
		self.velocity_canvas = tkinter.Canvas(self.seq_frame,
			width=self.piano_roll_width,
			height=PLAYHEAD_HEIGHT,
			bg=CELL_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.velocity_canvas.create_rectangle(0, 0, self.piano_roll_width * self.velocity / 127, PLAYHEAD_HEIGHT, fill='yellow', tags="velocityIndicator", width=0)
		self.velocity_canvas.grid(column=0, row=2)

		# Create pianoroll canvas
		self.piano_roll = tkinter.Canvas(self.seq_frame,
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
		self.play_canvas = tkinter.Canvas(self.seq_frame,
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
		self.play_canvas.grid(column=1, row=2)

		self.playhead = 0
#		self.startPlayheadHandler()

		# Init touchbar
		self.init_buttonbar()

		# Select a cell
		self.select_cell(0, self.keymap_offset)


	# Function to get name of this view
	def get_name(self):
		return "pattern editor"


	def play_note(self, note):
		if self.zyngui.zynseq.libseq.getPlayState(self.bank, self.sequence) == zynthian_gui_config.SEQ_STOPPED:
			self.zyngui.zynseq.libseq.playNote(note, self.velocity, self.channel, int(200 * self.duration))


	#Function to set values of encoders
	def setup_zynpots(self):
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_LAYER, 0)
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_BACK, 0)
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_SNAPSHOT, 0)
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_SELECT, 0)


	# Function to show GUI
	def show(self):
		self.zyngui.zynseq.libseq.setGroup(self.bank, self.sequence, 0xFF)
		self.copy_source = self.pattern
		self.setup_zynpots()
		if not self.param_editor_zctrl:
			self.set_title("Pattern {}".format(self.pattern))
		self.zyngui.zynseq.libseq.setPlayMode(self.bank, self.sequence, zynthian_gui_config.SEQ_LOOP)
		self.zyngui.zynseq.libseq.enableMidiInput(True)
		super().show()


	# Function to enable note duration/velocity direct edit mode
	#	mode: Edit mode to enable [EDIT_MODE_NONE | EDIT_MODE_SINGLE | EDIT_MODE_ALL]
	def enable_edit(self, mode):
		self.edit_mode = mode
		if mode == EDIT_MODE_SINGLE:
			self.set_title("Note Parameters", zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)
		elif mode == EDIT_MODE_ALL:
			self.set_title("Note Parameters ALL", zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)
		else:
			self.set_title("Pattern {}".format(self.pattern), zynthian_gui_config.color_panel_tx, zynthian_gui_config.color_header_bg)


	# Function to hide GUI
	def hide(self):
		super().hide()
		self.zyngui.zynseq.libseq.setPlayState(self.bank, self.sequence, zynthian_gui_config.SEQ_STOPPED)
		self.zyngui.zynseq.libseq.enableMidiInput(False)
		self.enable_edit(EDIT_MODE_NONE)
		self.zyngui.zynseq.libseq.setRefNote(self.keymap_offset)


	# Function to add menus
	def show_menu(self):
		self.disable_param_editor()
		options = OrderedDict()
		options['Tempo'] = 1
		options['Beats per bar'] = 1
		if self.zyngui.zynseq.libseq.isMetronomeEnabled():
			options['[X] Metronome'] = 1
		else:
			options['[  ] Metronome'] = 1
		options['Metronome volume'] = 1
		options['Beats in pattern'] = 1
		options['Steps per beat'] = 1
		options['Copy pattern'] = 1
		options['Clear pattern'] = 1
		options['Transpose pattern'] = 1
		options['Vertical zoom'] = 1
		options['Scale'] = 1
		options['Tonic'] = 1
		options['Rest note'] = 1
		#options['Add program change'] = 1
		options['Input channel'] = 1
		options['Export to SMF'] = 1
		self.zyngui.screens['option'].config("Pattern Editor Menu", options, self.menu_cb)
		self.zyngui.show_screen('option')


	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()


	def menu_cb(self, option, params):
		if option == 'Tempo':
			self.enable_param_editor(self, 'tempo', 'Tempo', {'value_min':10, 'value_max':420, 'value_default':120, 'is_integer':False, 'nudge_factor':0.1, 'value':self.zyngui.zynseq.libseq.getTempo()})
		elif option == 'Beats per bar':
			self.enable_param_editor(self, 'bpb', 'Beats per bar', {'value_min':1, 'value_max':64, 'value_default':4, 'value':self.zyngui.zynseq.libseq.getBeatsPerBar()})
		elif option == '[  ] Metronome':
			self.zyngui.zynseq.libseq.enableMetronome(True)
		elif option == '[X] Metronome':
			self.zyngui.zynseq.libseq.enableMetronome(False)
		elif option == 'Metronome volume':
			self.enable_param_editor(self, 'metro_vol', 'Metro volume', {'value_min':0, 'value_max':100, 'value_default':100, 'value':int(100*self.zyngui.zynseq.libseq.getMetronomeVolume())})
		elif option == 'Beats in pattern':
			self.enable_param_editor(self, 'bip', 'Beats in pattern', {'value_min':1, 'value_max':64, 'value_default':4, 'value':self.zyngui.zynseq.libseq.getBeatsInPattern()}, self.assert_beats_in_pattern)
		elif option == 'Steps per beat':
			self.enable_param_editor(self, 'spb', 'Steps per beat', {'ticks':STEPS_PER_BEAT, 'value_default':3, 'value':self.zyngui.zynseq.libseq.getStepsPerBeat()}, self.assert_steps_per_beat)
		elif option == 'Copy pattern':
			self.copy_source = self.pattern
			self.enable_param_editor(self, 'copy', 'Copy pattern to', {'value_min':1, 'value_max':zynthian_gui_config.SEQ_MAX_PATTERNS, 'value':self.pattern}, self.copy_pattern)
		elif option == 'Clear pattern':
			self.clear_pattern()
		elif option == 'Transpose pattern':
			self.enable_param_editor(self, 'transpose', 'Transpose', {'value_min':-1, 'value_max':1, 'labels':['down','down/up','up'], 'value':0})
		elif option == 'Vertical zoom':
			self.enable_param_editor(self, 'vzoom', 'Vertical zoom', {'value_min':1, 'value_max':127, 'value_default':16, 'value':self.zoom})
		elif option == 'Scale':
			self.enable_param_editor(self, 'scale', 'Scale', {'labels':self.get_scales(), 'value':self.zyngui.zynseq.libseq.getScale()})
		elif option == 'Tonic':
			self.enable_param_editor(self, 'tonic', 'Tonic', {'labels':NOTE_NAMES, 'value':self.zyngui.zynseq.libseq.getTonic()})
		elif option == 'Rest note':
			labels = ['None']
			for note in range(128):
				labels.append("{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1))
			value = self.zyngui.zynseq.libseq.getInputRest() + 1
			if value > 128:
				value = 0
			options = {'labels':labels, 'value':value}
			self.enable_param_editor(self, 'rest', 'Rest', options)
		elif option == 'Add program change':
			self.enable_param_editor(self, 'prog_change', 'Program', {'value_max':128, 'value':self.get_program_change()}, self.add_program_change)
		elif option == 'Input channel':
			self.enable_param_editor(self, 'in_chan', 'Input Chan', {'labels':INPUT_CHANNEL_LABELS, 'value': self.get_input_channel()})
		elif option == 'Export to SMF':
			self.export_smf()


	def send_controller_value(self, zctrl):
		if zctrl.symbol == 'tempo':
			self.zyngui.zynseq.libseq.setTempo(zctrl.value)
		if zctrl.symbol == 'metro_vol':
			self.zyngui.zynseq.libseq.setMetronomeVolume(zctrl.value / 100.0)
		if zctrl.symbol == 'bpb':
			self.zyngui.zynseq.libseq.setBeatsPerBar(zctrl.value)
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
				self.zyngui.zynseq.libseq.setInputRest(128)
			else:
				self.zyngui.zynseq.libseq.setInputRest(zctrl.value - 1)
		elif zctrl.symbol == 'in_chan':
			self.zyngui.zynseq.libseq.setInputChannel(zctrl.value - 1)
    			

	# Function to transpose pattern
	def transpose(self, offset):
		if (offset != 0):
			if self.zyngui.zynseq.libseq.getScale():
				# Only allow transpose when showing chromatic scale
				self.zyngui.zynseq.libseq.setScale(0)
				self.load_keymap()
			
			self.zyngui.zynseq.libseq.transpose(offset)
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
	#	scale: Index of scale to load
	#	Returns: name of scale 
	def set_scale(self, scale):
		self.zyngui.zynseq.libseq.setScale(scale)
		name = self.load_keymap()
		self.redraw_pending = 3
		return name


	# Function to set tonic (root note) of scale
	#	tonic: Scale root note
	def set_tonic(self, tonic):
		self.zyngui.zynseq.libseq.setTonic(tonic)
		self.load_keymap()
		self.redraw_pending = 3


	# Function to export pattern to SMF
	def export_smf(self):
		smf = zynsmf.libsmf.addSmf()
		tempo = self.zyngui.zynseq.libseq.getTempo()
		zynsmf.libsmf.addTempo(smf, 0, tempo)
		ticks_per_step = zynsmf.libsmf.getTicksPerQuarterNote(smf) / self.zyngui.zynseq.libseq.getStepsPerBeat()
		for step in range(self.zyngui.zynseq.libseq.getSteps()):
			time = int(step * ticks_per_step)
			for note in range(128):
				duration = self.zyngui.zynseq.libseq.getNoteDuration(step, note)
				if duration == 0.0:
					continue
				duration = int(duration * ticks_per_step)
				velocity = self.zyngui.zynseq.libseq.getNoteVelocity(step, note)
				zynsmf.libsmf.addNote(smf, 0, time, duration, self.channel, note, velocity)
		zynsmf.libsmf.setEndOfTrack(smf, 0, int(self.zyngui.zynseq.libseq.getSteps() * ticks_per_step))
		zynsmf.save(smf, "/zynthian/zynthian-my-data/capture/pattern{}_{}.mid".format(self.pattern, datetime.now()))


	# Function to assert steps per beat
	def assert_steps_per_beat(self, value):
		self.zyngui.show_confirm("Changing steps per beat may alter timing and/or lose notes?", self.do_steps_per_beat, value)


	# Function to actually change steps per beat
	def do_steps_per_beat(self, value):
		self.zyngui.zynseq.libseq.setStepsPerBeat(value)
		self.redraw_pending = 4


	# Function to assert beats in pattern
	def assert_beats_in_pattern(self, value):
		if self.zyngui.zynseq.libseq.getLastStep() >= self.zyngui.zynseq.libseq.getStepsPerBeat() * value:
			self.zyngui.show_confirm("Reducing beats in pattern will truncate pattern", self.set_beats_in_pattern, value)
		else:
			self.set_beats_in_pattern(value)

	# Function to assert beats in pattern
	def set_beats_in_pattern(self, value):
		self.zyngui.zynseq.libseq.setBeatsInPattern(value)
		self.redraw_pending = 4


	# Function to get the index of the closest steps per beat in array of allowed values
	#	returns: Index of closest allowed value
	def get_steps_per_beat_index(self):
		steps_per_beat = self.zyngui.zynseq.libseq.getStepsPerBeat()
		for index in range(len(STEPS_PER_BEAT)):
			if STEPS_PER_BEAT[index] >= steps_per_beat:
				return index
		return index


	# Function to get list of scales
	#	returns: List of available scales
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
		self.update_row_height()
		self.redraw_pending = 4
		self.select_cell()


	# Function to populate keymap array
	#	returns Name of scale / map
	def load_keymap(self):
		try:
			base_note = int(self.keymap[self.keymap_offset]['note'])
		except:
			base_note = 60
		scale = self.zyngui.zynseq.libseq.getScale()
		tonic = self.zyngui.zynseq.libseq.getTonic()
		name = None
		self.keymap = []
		if scale == 0:
			# Map
			path = None
			for layer in self.zyngui.screens['layer'].layers:
				if layer.midi_chan == self.channel:
					path = layer.get_presetpath()
					break
			if path:
				path = path.split('#')[1]
				try:
					with open(CONFIG_ROOT + "/keymaps.json") as json_file:
						data = json.load(json_file)
					if path in data:
						name = data[path]
						xml = minidom.parse(CONFIG_ROOT + "/%s.midnam" % (name))
						notes = xml.getElementsByTagName('Note')
						self.scale = []
						for note in notes:
							self.keymap.append({'note':int(note.attributes['Number'].value), 'name':note.attributes['Name'].value})
				except:
					logging.warning("Unable to load keymaps.json")
		if name == None: # Not found map
			# Scale
			self.zyngui.zynseq.libseq.setScale(scale) # Use chromatic scale if map not found
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
					if note <= base_note:
						self.keymap_offset = len(self.keymap) - 1
						self.selected_cell[1] = self.keymap_offset
				name = "Chromatic"
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
						if note <= base_note:
							self.keymap_offset = len(self.keymap) - 1
							self.selected_cell[1] = self.keymap_offset
				name = data[scale]['name']
		return name


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
	#	event: Mouse event
	def on_grid_press(self, event):
		if self.param_editor_zctrl:
			self.disable_param_editor()
		self.grid_drag_start = event
		try:
			col,row = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))[0].split(',')
		except:
			return
		note = self.keymap[self.keymap_offset + int(row)]["note"]
		step = int(col)
		if step < 0 or step >= self.zyngui.zynseq.libseq.getSteps():
			return
		self.drag_start_velocity = self.zyngui.zynseq.libseq.getNoteVelocity(step, note)
		self.drag_start_duration = self.zyngui.zynseq.libseq.getNoteDuration(step, note)
		self.drag_start_step = int(event.x / self.step_width)
		if not self.drag_start_velocity:
			self.play_note(note)
		self.select_cell(int(col), self.keymap_offset + int(row))


	# Function to handle grid mouse release
	#	event: Mouse event
	def on_grid_release(self, event):
		if not self.grid_drag_start:
			return
		if not (self.drag_velocity or self.drag_duration):
			self.toggle_event(self.selected_cell[0], self.selected_cell[1])
		self.drag_velocity = False
		self.drag_duration = False
		self.grid_drag_start = None


	# Function to handle grid mouse drag
	#	event: Mouse event
	def on_grid_drag(self, event):
		if not self.grid_drag_start:
			return
		step = self.selected_cell[0]
		index = self.selected_cell[1]
		note = self.keymap[index]['note']
		if self.drag_start_velocity:
			# Selected cell has a note so we want to adjust its velocity or duration
			if not self.drag_velocity and not self.drag_duration and (event.x > (self.drag_start_step + 1) * self.step_width or event.x < self.drag_start_step * self.step_width):
				self.drag_duration = True
			if not self.drag_duration and not self.drag_velocity and (event.y > self.grid_drag_start.y + self.row_height / 2 or event.y < self.grid_drag_start.y - self.row_height / 2):
				self.drag_velocity = True
			value = 0
			if self.drag_velocity:
				value = (self.grid_drag_start.y - event.y) / self.row_height
				if value:
					self.velocity = int(self.drag_start_velocity + value * self.height / 100)
					if self.velocity > 127:
						self.velocity = 127
						return
					if self.velocity < 1:
						self.velocity = 1
						return
					self.velocity_canvas.coords("velocityIndicator", 0, 0, self.piano_roll_width * self.velocity / 127, PLAYHEAD_HEIGHT)
					if self.zyngui.zynseq.libseq.getNoteDuration(self.selected_cell[0], note):
						self.zyngui.zynseq.libseq.setNoteVelocity(self.selected_cell[0], note, self.velocity)
						self.draw_cell(self.selected_cell[0], index - self.keymap_offset)
			if self.drag_duration:
				value = int(event.x / self.step_width) - self.drag_start_step
				duration = self.drag_start_duration + value
				if duration != self.duration and duration > 0:
					self.duration = duration
					self.add_event(step, index) # Change length by adding event over previous one
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


	# Function to toggle note event
	#	step: step (column) index
	#	index: key map index
	# 	Returns: Note if note added else None
	def toggle_event(self, step, index):
		if step < 0 or step >= self.zyngui.zynseq.libseq.getSteps() or index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		if self.zyngui.zynseq.libseq.getNoteVelocity(step, note):
			self.remove_event(step, index)
		else:
			self.add_event(step, index)
			return note


	# Function to remove an event
	#	step: step (column) index
	#	index: keymap index
	def remove_event(self, step, index):
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		self.zyngui.zynseq.libseq.removeNote(step, note)
		self.zyngui.zynseq.libseq.playNote(note, 0, self.channel) # Silence note if sounding
		self.draw_row(index)
		self.select_cell(step, index)


	# Function to add an event
	#	step: step (column) index
	#	index: keymap index
	def add_event(self, step, index):
		note = self.keymap[index]["note"]
		self.zyngui.zynseq.libseq.addNote(step, note, self.velocity, self.duration)
		self.draw_row(index)
		self.select_cell(step, index)


	# Function to draw a grid row
	#	index: keymap index
	#	colour: Black, white or None (default) to not care
	def draw_row(self, index, white=None):
		row = index - self.keymap_offset
		self.grid_canvas.itemconfig("lastnotetext%d" % (row), state="hidden")
		for step in range(self.zyngui.zynseq.libseq.getSteps()):
			self.draw_cell(step, row, white)


	# Function to get cell coordinates
	#   col: Column index
	#   row: Row index
	#   duration: Duration of cell in steps
	#   return: Coordinates required to draw cell
	def get_cell(self, col, row, duration):
		x1 = col * self.step_width + 1
		y1 = (self.zoom - row - 1) * self.row_height + 1
		x2 = x1 + self.step_width * duration - 1
		y2 = y1 + self.row_height - 1
		return [x1, y1, x2, y2]


	# Function to draw a grid cell
	#	step: Step (column) index
	#	row: Index of row
	#	white: True for white notes
	def draw_cell(self, step, row, white=None):
		self.zyngui.zynseq.libseq.isPatternModified() # Flush modified flag to avoid refresh redrawing whole grid
		cellIndex = row * self.zyngui.zynseq.libseq.getSteps() + step # Cells are stored in array sequentially: 1st row, 2nd row...
		if cellIndex >= len(self.cells):
			return
		note = self.keymap[row + self.keymap_offset]["note"]
		cell = self.cells[cellIndex]
		if white is None:
			if cell:
				white =  "white" in self.grid_canvas.gettags(cell)
			else:
				white = True
		
		velocity_colour = self.zyngui.zynseq.libseq.getNoteVelocity(step, note)
		if velocity_colour:
			velocity_colour += 70
		else:
			velocity_colour = 30 * int(white)

		duration = self.zyngui.zynseq.libseq.getNoteDuration(step, note)
		if not duration:
			duration = 1.0
		fill_colour = "#%02x%02x%02x" % (velocity_colour, velocity_colour, velocity_colour)
		coord = self.get_cell(step, row, duration)
		if cell:
			# Update existing cell
			if white:
				self.grid_canvas.itemconfig(cell, fill=fill_colour, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step, "white"))
			else:
				self.grid_canvas.itemconfig(cell, fill=fill_colour, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step))
			self.grid_canvas.coords(cell, coord)
		else:
			# Create new cell
			if white:
				cell = self.grid_canvas.create_rectangle(coord, fill=fill_colour, width=0, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step, "white"))
			else:
				cell = self.grid_canvas.create_rectangle(coord, fill=fill_colour, width=0, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step))
			self.grid_canvas.tag_bind(cell, '<ButtonPress-1>', self.on_grid_press)
			self.grid_canvas.tag_bind(cell, '<ButtonRelease-1>', self.on_grid_release)
			self.grid_canvas.tag_bind(cell, '<B1-Motion>', self.on_grid_drag)
			self.cells[cellIndex] = cell
		if step + duration > self.zyngui.zynseq.libseq.getSteps():
			self.grid_canvas.itemconfig("lastnotetext%d" % row, text="+%d" % (duration - self.zyngui.zynseq.libseq.getSteps() + step), state="normal")


	# Function to draw grid
	def draw_grid(self):
		if self.drawing:
			return
		self.drawing = True
		redraw_pending = self.redraw_pending
		self.redraw_pending = 0
		if len(self.cells) != self.zoom * self.zyngui.zynseq.libseq.getSteps():
			redraw_pending = 4
		if self.zyngui.zynseq.libseq.getSteps() == 0:
			self.drawing = False
			return #TODO: Should we clear grid?
		if self.keymap_offset > len(self.keymap) - self.zoom:
			self.keymap_offset = len(self.keymap) - self.zoom
		if self.keymap_offset < 0:
			self.keymap_offset = 0
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		if redraw_pending == 4:
			self.grid_canvas.delete(tkinter.ALL)
			self.step_width = (self.grid_width - 2) / self.zyngui.zynseq.libseq.getSteps()
			self.draw_pianoroll()
			self.cells = [None] * self.zoom * self.zyngui.zynseq.libseq.getSteps()
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)

		# Draw cells of grid
		self.grid_canvas.itemconfig("gridcell", fill="black")
		if redraw_pending > 2:
			# Redraw gridlines
			self.grid_canvas.delete("gridline")
			if self.zyngui.zynseq.libseq.getStepsPerBeat():
				for step in range(0, self.zyngui.zynseq.libseq.getSteps() + 1, self.zyngui.zynseq.libseq.getStepsPerBeat()):
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
				self.grid_canvas.create_text(self.grid_width - self.select_thickness, int(self.row_height * (self.zoom - row - 0.5)), state="hidden", tags=("lastnotetext%d" % (row), "lastnotetext"), font=font, anchor="e")

				fill = "black"
				# Update pianoroll keys
				id = "row%d" % (row)
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
				if self.keymap[index]['note'] % 12 == self.zyngui.zynseq.libseq.getTonic():
					self.grid_canvas.create_line(0, (self.zoom - row) * self.row_height, self.grid_width, (self.zoom - row) * self.row_height, fill=GRID_LINE, tags=("gridline"))
				# Draw row of note cells
				self.draw_row(index, colour=="white")

		# Set z-order to allow duration to show
		if redraw_pending > 2:
			for step in range(self.zyngui.zynseq.libseq.getSteps()):
				self.grid_canvas.tag_lower("step%d"%step)
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
			id = "row%d" % (row)
			id = self.piano_roll.create_rectangle(x1, y1, x2, y2, width=0, tags=id)


	# Function to update selectedCell
	#	step: Step (column) of selected cell (Optional - default to reselect current column)
	#	index: Index of keymap to select (Optional - default to reselect current row) Maybe outside visible range to scroll display
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
		if step >= self.zyngui.zynseq.libseq.getSteps():
			step = self.zyngui.zynseq.libseq.getSteps() - 1
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
			prev_duration = ceil(self.zyngui.zynseq.libseq.getNoteDuration(previous, note))
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
		if step >= self.zyngui.zynseq.libseq.getSteps():
			step = self.zyngui.zynseq.libseq.getSteps() - 1
		self.selected_cell = [int(step), index]
		cell = self.grid_canvas.find_withtag("selection")
		duration = self.zyngui.zynseq.libseq.getNoteDuration(step, row)
		if not duration:
			duration = self.duration
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
		self.zyngui.show_confirm("Clear pattern %d?"%(self.pattern), self.do_clear_pattern)


	# Function to actually clear pattern
	def do_clear_pattern(self, params=None):
		self.zyngui.zynseq.libseq.clear()
		self.redraw_pending = 3
		self.select_cell()
		if self.zyngui.zynseq.libseq.getPlayState(self.bank, self.sequence, 0) != zynthian_gui_config.SEQ_STOPPED:
			self.zyngui.zynseq.libseq.sendMidiCommand(0xB0 | self.channel, 123, 0) # All notes off


	# Function to copy pattern
	def copy_pattern(self, value):
		if self.zyngui.zynseq.libseq.getLastStep() == -1:
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
		self.zyngui.zynseq.libseq.copyPattern(self.copy_source, dest_pattern)
		self.pattern = dest_pattern
		self.load_pattern(self.pattern)
		self.copy_source = self.pattern
		#TODO: Update arranger when it is refactored
		#self.zyngui.screen['arranger'].pattern = self.pattern
		#self.zyngui.screen['arranger'].pattern_canvas.itemconfig("patternIndicator", text="{}".format(self.pattern))


	# Function to get program change at start of pattern
	# returns: Program change number (1..128) or 0 for none
	def get_program_change(self):
		program = self.zyngui.zynseq.libseq.getProgramChange(0) + 1
		if program > 128:
			program = 0
		return program


	# Function to add program change at start of pattern
	def add_program_change(self, value):
		self.zyngui.zynseq.libseq.addProgramChange(0, value)


	# Function to get MIDI channel listening
	# returns: MIDI channel ((1..16) or 0 for none
	def get_input_channel(self):
		channel = self.zyngui.zynseq.libseq.getInputChannel() + 1
		if channel > 16:
			channel = 0
		return channel


	# Function to load new pattern
	#   index: Pattern index
	def load_pattern(self, index):
		steps = self.zyngui.zynseq.libseq.getSteps()
		self.zyngui.zynseq.libseq.clearSequence(self.bank, self.sequence)
		self.zyngui.zynseq.libseq.setChannel(self.bank, self.sequence, 0, self.channel)
		self.pattern = index
		self.zyngui.zynseq.libseq.selectPattern(index)
		self.zyngui.zynseq.libseq.addPattern(self.bank, self.sequence, 0, 0, index)
		if self.selected_cell[0] >= self.zyngui.zynseq.libseq.getSteps():
			self.selected_cell[0] = int(self.zyngui.zynseq.libseq.getSteps()) - 1
		self.keymap_offset = self.zyngui.zynseq.libseq.getRefNote()
		keymap_len = len(self.keymap)
		self.load_keymap()
		if self.redraw_pending < 4:
			if self.zyngui.zynseq.libseq.getSteps() != steps or len(self.keymap) != keymap_len:
				self.redraw_pending = 4
			else:
				self.redraw_pending = 3
		if self.keymap_offset >= len(self.keymap):
			self.keymap_offset = len(self.keymap) // 2 - self.zoom // 2
		self.draw_grid()
		self.select_cell(0, int(self.keymap_offset + self.zoom / 2))
		self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)
		self.set_title("Pattern {}".format(self.pattern))


	# Function to refresh status
	def refresh_status(self, status):
		super().refresh_status(status)
		step = self.zyngui.zynseq.libseq.getPatternPlayhead(self.bank, self.sequence, 0)
		if self.playhead != step:
			self.playhead = step
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)
		if self.zyngui.zynseq.libseq.isPatternModified() and self.redraw < 3:
			self.redraw_pending = 3
		if self.redraw_pending:
			self.draw_grid()


	# Function to handle zynpots value change
	#   i: Zynpot index [0..n]
	#   dval: Current value of zyncoder
	def zynpot_cb(self, i, dval):
		if super().zynpot_cb(i, dval):
			return
		if i == zynthian_gui_config.ENC_BACK:
			if self.edit_mode == EDIT_MODE_SINGLE:
				self.velocity = self.velocity + dval
				if self.velocity > 127:
					self.velocity = 127
					return
				if self.velocity < 1:
					self.velocity = 1
					return
				self.velocity_canvas.coords("velocityIndicator", 0, 0, self.piano_roll_width * self.velocity / 127, PLAYHEAD_HEIGHT)
				note = self.keymap[self.selected_cell[1]]["note"]
				if self.zyngui.zynseq.libseq.getNoteDuration(self.selected_cell[0], note):
					self.zyngui.zynseq.libseq.setNoteVelocity(self.selected_cell[0], note, self.velocity)
					self.draw_cell(self.selected_cell[0], self.selected_cell[1])
				self.set_title("Velocity: %d" % (self.velocity), None, None, 2)
			elif self.edit_mode == EDIT_MODE_ALL:
				self.zyngui.zynseq.libseq.changeVelocityAll(dval)
				self.set_title("ALL Velocity", None, None, 2)
			else:
				self.select_cell(None, self.selected_cell[1] - dval)

		elif i == zynthian_gui_config.ENC_SELECT:
			if self.edit_mode == EDIT_MODE_SINGLE:
				if dval > 0:
					self.duration = self.duration + 1
				if dval < 0:
					self.duration = self.duration - 1
				if self.duration > self.zyngui.zynseq.libseq.getSteps():
					self.duration = self.zyngui.zynseq.libseq.getSteps()
					return
				if self.duration < 1:
					self.duration = 1
					return
				note = self.keymap[self.selected_cell[1]]["note"]
				if self.zyngui.zynseq.libseq.getNoteDuration(self.selected_cell[0], note):
					self.add_event(self.selected_cell[0], note)
				else:
					self.select_cell()
				self.set_title("Duration: %0.1f steps" % (self.duration), None, None, 2)
			elif self.edit_mode == EDIT_MODE_ALL:
				if dval > 0:
					self.zyngui.zynseq.libseq.changeDurationAll(1)
				if dval < 0:
					self.zyngui.zynseq.libseq.changeDurationAll(-1)
				self.set_title("ALL DURATION", None, None, 2)
			else:
				self.select_cell(self.selected_cell[0] + dval, None)

		elif i == zynthian_gui_config.ENC_SNAPSHOT:
			if self.edit_mode == EDIT_MODE_SINGLE:
				if dval > 0:
					self.duration = self.duration + 0.1
				if dval < 0:
					self.duration = self.duration - 0.1
				if self.duration > self.zyngui.zynseq.libseq.getSteps():
					self.duration = self.zyngui.zynseq.libseq.getSteps()
					return
				if self.duration < 0.1:
					self.duration = 0.1
					return
				note = self.keymap[self.selected_cell[1]]["note"]
				if self.zyngui.zynseq.libseq.getNoteDuration(self.selected_cell[0], note):
					self.add_event(self.selected_cell[0], note)
				else:
					self.select_cell()
				self.set_title("Duration: %0.1f steps" % (self.duration), None, None, 2)
			elif self.edit_mode == EDIT_MODE_ALL:
				if dval > 0:
					self.zyngui.zynseq.libseq.changeDurationAll(0.1)
				if dval < 0:
					self.zyngui.zynseq.libseq.changeDurationAll(-0.1)
				self.set_title("ALL DURATION", None, None, 2)
			else:
				self.zyngui.zynseq.nudge_tempo(dval)
				self.set_title("Tempo: {:.1f}".format(self.zyngui.zynseq.get_tempo()), None, None, 2)


	# Function to handle switch press
	#   switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#   type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#   returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if super().switch(switch, type):
			return True
		if switch == zynthian_gui_config.ENC_SELECT:
			if type == "S":
				note = self.toggle_event(self.selected_cell[0], self.selected_cell[1])
				if note:
					self.play_note(note)
			elif type == "B":
				if self.edit_mode == EDIT_MODE_NONE:
					self.enable_edit(EDIT_MODE_SINGLE)
				else:
					self.enable_edit(EDIT_MODE_ALL)
			return True
		elif switch == zynthian_gui_config.ENC_SNAPSHOT:
			if type == "B":
				self.zyngui.zynseq.libseq.setTransportToStartOfBar()
				return True
			if self.zyngui.zynseq.libseq.getPlayState(self.bank, self.sequence) == zynthian_gui_config.SEQ_STOPPED:
				self.zyngui.zynseq.libseq.setPlayState(self.bank, self.sequence, zynthian_gui_config.SEQ_STARTING)
			else:
				self.zyngui.zynseq.libseq.setPlayState(self.bank, self.sequence, zynthian_gui_config.SEQ_STOPPED)
			return True
		elif switch == zynthian_gui_config.ENC_BACK:
			if self.edit_mode:
				self.enable_edit(EDIT_MODE_NONE)
				if type == 'S':
					return True
		elif switch == zynthian_gui_config.ENC_LAYER and type == 'S':
			self.show_menu()
			return True
		return False


	#	CUIA Actions
	# Function to handle CUIA ARROW_RIGHT
	def arrow_right(self):
		self.zynpot_cb(zynthian_gui_config.ENC_SELECT, 1)

	# Function to handle CUIA ARROW_LEFT
	def arrow_left(self):
		self.zynpot_cb(zynthian_gui_config.ENC_SELECT, -1)


	# Function to handle CUIA ARROW_UP
	def arrow_up(self):
		self.zynpot_cb(zynthian_gui_config.ENC_BACK, -1)


	# Function to handle CUIA ARROW_DOWN
	def arrow_down(self):
		self.zynpot_cb(zynthian_gui_config.ENC_BACK, 1)


#------------------------------------------------------------------------------
