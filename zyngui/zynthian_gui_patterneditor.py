#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2022 Brian Walton <brian@riban.co.uk>
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

import inspect
import sys
import os
import tkinter
import logging
import tkinter.font as tkFont
import json
from xml.dom import minidom
import threading
from time import sleep
from datetime import datetime
import time
import ctypes
from math import ceil
from os.path import dirname, realpath, basename
from zynlibs.zynsmf import zynsmf # Python wrapper for zynsmf (ensures initialised and wraps load() function)
from zynlibs.zynsmf.zynsmf import libsmf # Direct access to shared library

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_layer
from zyngui import zynthian_gui_stepsequencer
from zyngui.zynthian_gui_fileselector import zynthian_gui_fileselector
from zynlibs.zynseq import zynseq
from zynlibs.zynseq.zynseq import libseq
from zynlibs.zynsmf import zynsmf
from zynlibs.zynsmf.zynsmf import libsmf

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


# Class implements step sequencer pattern editor
class zynthian_gui_patterneditor():
	#TODO: Inherit child views from superclass

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent

		os.makedirs(CONFIG_ROOT, exist_ok=True)

		self.edit_mode = EDIT_MODE_NONE # Enable encoders to adjust duration and velocity
		self.zoom = 16 # Quantity of rows (notes) displayed in grid
		self.duration = 1.0 # Current note entry duration
		self.velocity = 100 # Current note entry velocity
		self.copy_source = 1 # Index of pattern to copy
		self.bank = 0 # Bank used for pattern editor sequence player
		self.sequence = 0 # Sequence used for pattern editor sequence player
		self.step_width = 40 # Grid column width in pixels
		self.keymap_offset = 60 # MIDI note number of bottom row in grid
		self.selected_cell = [0, 0] # Location of selected cell (column,row)
		self.drag_velocity = False # True indicates drag will adjust velocity
		self.drag_duration = False # True indicates drag will adjust duration
		self.drag_start_velocity = None # Velocity value at start of drag
		self.grid_drag_start = None # Coordinates at start of grid drag
		self.keymap = [] # Array of {"note":MIDI_NOTE_NUMBER, "name":"key name","colour":"key colour"} name and colour are optional
		self.notes = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
		#TODO: Get values from persistent storage
		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration
		self.cells = [] # Array of cells indices
		self.redraw_pending = 0 # What to redraw: 0=nothing, 1=existing elements, 2=recreate grid
		self.title = "Pattern 0"
		self.channel = 0


		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height
		self.select_thickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.grid_height = self.height - PLAYHEAD_HEIGHT
		self.grid_width = int(self.width * 0.9)
		self.piano_roll_width = self.width - self.grid_width
		self.update_row_height()

		# Main Frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(row=1, column=0, sticky="nsew")

		# Create pattern grid canvas
		self.grid_canvas = tkinter.Canvas(self.main_frame,
			width=self.grid_width,
			height=self.grid_height,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.grid_canvas.grid(row=0, column=1)

		# Create velocity level indicator canvas
		self.velocity_canvas = tkinter.Canvas(self.main_frame,
			width=self.piano_roll_width,
			height=PLAYHEAD_HEIGHT,
			bg=CELL_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.velocity_canvas.create_rectangle(0, 0, self.piano_roll_width * self.velocity / 127, PLAYHEAD_HEIGHT, fill='yellow', tags="velocityIndicator", width=0)
		self.velocity_canvas.grid(column=0, row=2)

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
		self.play_canvas.grid(column=1, row=2)

		self.playhead = 0
#		self.startPlayheadHandler()

		# Select a cell
		self.select_cell(0, self.keymap_offset)


	# Function to get name of this view
	def get_name(self):
		return "pattern editor"


	def play_note(self, note):
		if libseq.getPlayState(self.bank, self.sequence) == zynthian_gui_stepsequencer.SEQ_STOPPED:
			libseq.playNote(note, self.velocity, self.channel, int(200 * self.duration))


	#Function to set values of encoders
	#   note: Call after other routine uses one or more encoders
	def setup_encoders(self):
		self.parent.register_zyncoder(zynthian_gui_config.ENC_BACK, self)
		self.parent.register_zyncoder(zynthian_gui_config.ENC_SELECT, self)
		self.parent.register_zyncoder(zynthian_gui_config.ENC_LAYER, self)
		self.parent.register_switch(zynthian_gui_config.ENC_SELECT, self, "SB")
		self.parent.register_switch(zynthian_gui_config.ENC_SNAPSHOT, self, "SB")


	# Function to show GUI
	#   params: Pattern parameters to edit {'pattern':x, 'channel':x, 'pad':x (optional)}
	def show(self, params=None):
		try:
			self.channel = params['channel']
			self.load_pattern(params['pattern'])
			self.title = "Pattern %d" % (params['pattern'])
			self.title = "Pattern %d (Seq: %s)" % (params['pattern'], params['name'])
		except:
			pass # Probably already populated and just returning from menu action or similar
		libseq.setGroup(self.bank, self.sequence, 0xFF)
		self.copy_source = self.pattern
		self.setup_encoders()
		self.main_frame.tkraise()
		self.parent.set_title(self.title)
		libseq.setPlayMode(self.bank, self.sequence, zynthian_gui_stepsequencer.SEQ_LOOP)
		libseq.enableMidiInput(True)
		self.shown=True


	# Function to hide GUI
	def hide(self):
		self.shown=False
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.zynthian_gui_config.ENC_BACK)
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.zynthian_gui_config.ENC_SELECT)
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.zynthian_gui_config.ENC_LAYER)
		self.parent.unregister_switch(zynthian_gui_stepsequencer.zynthian_gui_config.ENC_SELECT, "SB")
		self.parent.unregister_switch(zynthian_gui_stepsequencer.zynthian_gui_config.ENC_SNAPSHOT, "SB")
		libseq.setPlayState(self.bank, self.sequence, zynthian_gui_stepsequencer.SEQ_STOPPED)
		libseq.enableMidiInput(False)
		self.enable_edit(EDIT_MODE_NONE)
		libseq.setRefNote(self.keymap_offset)


	# Function to add menus
	def populate_menu(self):
		self.parent.add_menu({'Beats in pattern':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':16, 'get_value':libseq.getBeatsInPattern, 'on_change':self.on_menu_change, 'on_assert': self.assert_beats_in_pattern}}})
		self.parent.add_menu({'Steps per beat':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':len(STEPS_PER_BEAT)-1, 'get_value':self.get_steps_per_beat_index, 'on_change':self.on_menu_change, 'on_assert':self.assert_steps_per_beat}}})
		self.parent.add_menu({'-------------------':{}})
		self.parent.add_menu({'Copy pattern':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':64872, 'get_value':self.get_pattern, 'on_change':self.on_menu_change,'on_assert':self.copy_pattern,'on_cancel':self.cancel_copy}}})
		self.parent.add_menu({'Clear pattern':{'method':self.clear_pattern}})
		if libseq.getScale():
			self.parent.add_menu({'Transpose pattern':{'method':self.parent.show_param_editor, 'params':{'min':-1, 'max':1, 'value':0, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'-------------------':{}})
		self.parent.add_menu({'Vertical zoom':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':127, 'get_value':self.get_vertical_zoom, 'on_change':self.on_menu_change, 'on_assert':self.assert_zoom}}})
		self.parent.add_menu({'Scale':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':self.get_scales(), 'get_value':libseq.getScale, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Tonic':{'method':self.parent.show_param_editor, 'params':{'min':-1, 'max':12, 'get_value':libseq.getTonic, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Rest note':{'method':self.parent.show_param_editor, 'params':{'min':-1, 'max':128, 'get_value':libseq.getInputRest, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Program change':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':128, 'get_value':self.get_program_change, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Input channel':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':16, 'get_value':self.get_input_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Export to SMF':{'method':self.export_smf}})


	# Function to export pattern to SMF
	def export_smf(self, params):
		smf = libsmf.addSmf()
		tempo = libseq.getTempo()
		libsmf.addTempo(smf, 0, tempo)
		ticks_per_step = libsmf.getTicksPerQuarterNote(smf) / libseq.getStepsPerBeat()
		for step in range(libseq.getSteps()):
			time = int(step * ticks_per_step)
			for note in range(128):
				duration = libseq.getNoteDuration(step, note)
				if duration == 0.0:
					continue
				duration = int(duration * ticks_per_step)
				velocity = libseq.getNoteVelocity(step, note)
				libsmf.addNote(smf, 0, time, duration, self.channel, note, velocity)
		libsmf.setEndOfTrack(smf, 0, int(libseq.getSteps() * ticks_per_step))
		zynsmf.save(smf, "/zynthian/zynthian-my-data/capture/pattern%d_%s.mid"%(self.pattern, datetime.now()))


	# Function to set edit mode
	def enable_edit(self, mode):
		if mode <= EDIT_MODE_ALL:
			self.edit_mode = mode
			if mode:
				self.parent.register_switch(zynthian_gui_config.ENC_BACK, self)
				self.parent.register_zyncoder(zynthian_gui_config.ENC_SNAPSHOT, self)
				self.parent.register_zyncoder(zynthian_gui_config.ENC_LAYER, self)
				if mode == EDIT_MODE_SINGLE:
					self.parent.set_title("Note Parameters", zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)
				else:
					self.parent.set_title("Note Parameters ALL", zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)

			else:
				self.parent.unregister_switch(zynthian_gui_config.ENC_BACK)
				self.parent.unregister_zyncoder(zynthian_gui_config.ENC_SNAPSHOT)
				self.parent.unregister_zyncoder(zynthian_gui_config.ENC_LAYER)
				self.parent.set_title(self.title, zynthian_gui_config.color_panel_tx, zynthian_gui_config.color_header_bg)


	# Function to assert steps per beat
	def assert_steps_per_beat(self):
		self.zyngui.show_confirm("Changing steps per beat may alter timing and/or lose notes?", self.do_steps_per_beat)


	# Function to actually change steps per beat
	def do_steps_per_beat(self, params=None):
		libseq.setStepsPerBeat(STEPS_PER_BEAT[self.parent.get_param('Steps per beat', 'value')])
		self.redraw_pending = 2


	# Function to assert beats in pattern
	def assert_beats_in_pattern(self):
		value = self.parent.get_param('Beats in pattern', 'value')
		if libseq.getLastStep() >= libseq.getStepsPerBeat() * value:
			self.zyngui.show_confirm("Reducing beats in pattern will truncate pattern", self.set_beats_in_pattern)
		else:
			self.set_beats_in_pattern()

	# Function to assert beats in pattern
	def set_beats_in_pattern(self, params=None):
		libseq.setBeatsInPattern(self.parent.get_param('Beats in pattern', 'value'))
		self.redraw_pending = 2


	# Function to get the index of the closest steps per beat in array of allowed values
	#	returns: Index of closest allowed value
	def get_steps_per_beat_index(self):
		steps_per_beat = libseq.getStepsPerBeat()
		for index in range(len(STEPS_PER_BEAT)):
			if STEPS_PER_BEAT[index] >= steps_per_beat:
				return index
		return index


	# Function to get quantity of scales
	#	returns: Quantity of available scales
	def get_scales(self):
		data = []
		try:
			with open(CONFIG_ROOT + "/scales.json") as json_file:
				data = json.load(json_file)
		except:
			logging.warning("Unable to open scales.json")
		return len(data)


	# Function to assert zoom level
	def assert_zoom(self):
		self.update_row_height()
		self.redraw_pending = 2
		self.select_cell()


	# Function to populate keymap array
	#	returns Name of scale / map
	def load_keymap(self):
		try:
			base_note = int(self.keymap[self.keymap_offset]['note'])
		except:
			base_note = 60
		scale = libseq.getScale()
		tonic = libseq.getTonic()
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
			if scale > 0:
				scale = scale - 1
			libseq.setScale(scale + 1) # Use chromatic scale if map not found
			if scale == 0:
				for note in range(0,128):
					new_entry = {"note":note}
					key = note % 12
					if key in (1,3,6,8,10): # Black notes
						new_entry.update({"colour":"black"})
					if key == 0: # 'C'
						new_entry.update({"name":"C%d" % (note // 12 - 1)})
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
						self.keymap.append({"note":note, "name":"%s%d"%(self.notes[note % 12],note // 12 - 1)})
						if note <= base_note:
							self.keymap_offset = len(self.keymap) - 1
							self.selected_cell[1] = self.keymap_offset
				name = data[scale]['name']
		return name


	# Function to handle start of pianoroll drag
	def on_pianoroll_press(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hide_menu()
			return
		self.piano_roll_drag_start = event
		index = self.keymap_offset + self.zoom - int(event.y / self.row_height) - 1
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		libseq.playNote(note, 100, self.channel, 200)


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
		self.redraw_pending = 1

		if self.selected_cell[1] < self.keymap_offset:
			self.selected_cell[1] = self.keymap_offset
		elif self.selected_cell[1] >= self.keymap_offset + self.zoom:
			self.selected_cell[1] = self.keymap_offset + self.zoom - 1
		self.select_cell()


	# Function to handle end of pianoroll drag
	def on_pianoroll_release(self, event):
		self.piano_roll_drag_start = None


	# Function to handle grid mouse down
	#	event: Mouse event
	def on_grid_press(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hide_menu()
			return
		if self.parent.param_editor_item != None:
			self.parent.hide_param_editor()
			return
		self.grid_drag_start = event
		try:
			col,row = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))[0].split(',')
		except:
			return
		note = self.keymap[self.keymap_offset + int(row)]["note"]
		step = int(col)
		if step < 0 or step >= libseq.getSteps():
			return
		self.drag_start_velocity = libseq.getNoteVelocity(step, note)
		self.drag_start_duration = libseq.getNoteDuration(step, note)
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
					if libseq.getNoteDuration(self.selected_cell[0], note):
						libseq.setNoteVelocity(self.selected_cell[0], note, self.velocity)
						self.draw_cell(self.selected_cell[0], index)
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
		if step < 0 or step >= libseq.getSteps() or index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		if libseq.getNoteVelocity(step, note):
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
		libseq.removeNote(step, note)
		libseq.playNote(note, 0, self.channel) # Silence note if sounding
		self.draw_row(index)
		self.select_cell(step, index)


	# Function to add an event
	#	step: step (column) index
	#	index: keymap index
	def add_event(self, step, index):
		note = self.keymap[index]["note"]
		libseq.addNote(step, note, self.velocity, self.duration)
		self.draw_row(index)
		self.select_cell(step, index)


	# Function to draw a grid row
	#	index: keymap index
	def draw_row(self, index):
		row = index - self.keymap_offset
		self.grid_canvas.itemconfig("lastnotetext%d" % (row), state="hidden")
		for step in range(libseq.getSteps()):
			self.draw_cell(step, row)


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
	def draw_cell(self, step, row):
		libseq.isPatternModified() # Avoid refresh redrawing whole grid
		cellIndex = row * libseq.getSteps() + step # Cells are stored in array sequentially: 1st row, 2nd row...
		if cellIndex >= len(self.cells):
			return
		note = self.keymap[row + self.keymap_offset]["note"]
		velocity_colour = libseq.getNoteVelocity(step, note)
		if velocity_colour:
			velocity_colour = 70 + velocity_colour
		elif libseq.getScale() == 1:
			# Draw tramlines for white notes in chromatic scale
			key = note % 12
			if key in (0,2,4,5,7,9,11): # White notes
#			if key in (1,3,6,8,10): # Black notes
				velocity_colour += 30
		else:
			# Draw tramlines for odd rows in other scales and maps
			if (row + self.keymap_offset) % 2:
				velocity_colour += 30
		duration = libseq.getNoteDuration(step, note)
		if not duration:
			duration = 1.0
		fill_colour = "#%02x%02x%02x" % (velocity_colour, velocity_colour, velocity_colour)
		cell = self.cells[cellIndex]
		coord = self.get_cell(step, row, duration)
		if cell:
			# Update existing cell
			self.grid_canvas.itemconfig(cell, fill=fill_colour)
			self.grid_canvas.coords(cell, coord)
		else:
			# Create new cell
			cell = self.grid_canvas.create_rectangle(coord, fill=fill_colour, width=0, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step))
			self.grid_canvas.tag_bind(cell, '<ButtonPress-1>', self.on_grid_press)
			self.grid_canvas.tag_bind(cell, '<ButtonRelease-1>', self.on_grid_release)
			self.grid_canvas.tag_bind(cell, '<B1-Motion>', self.on_grid_drag)
			self.cells[cellIndex] = cell
		if step + duration > libseq.getSteps():
			self.grid_canvas.itemconfig("lastnotetext%d" % row, text="+%d" % (duration - libseq.getSteps() + step), state="normal")


	# Function to draw grid
	def draw_grid(self):
		clear_grid = (self.redraw_pending == 2)
		self.redraw_pending = 0
		if libseq.getSteps() == 0:
			return #TODO: Should we clear grid?
		if self.keymap_offset > len(self.keymap) - self.zoom:
			self.keymap_offset = len(self.keymap) - self.zoom
		if self.keymap_offset < 0:
			self.keymap_offset = 0
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		if clear_grid:
			self.grid_canvas.delete(tkinter.ALL)
			self.step_width = (self.grid_width - 2) / libseq.getSteps()
			self.draw_pianoroll()
			self.cells = [None] * self.zoom * libseq.getSteps()
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)
		# Draw cells of grid
		self.grid_canvas.itemconfig("gridcell", fill="black")
		# Redraw gridlines
		self.grid_canvas.delete("gridline")
		if libseq.getStepsPerBeat():
			for step in range(0, libseq.getSteps() + 1, libseq.getStepsPerBeat()):
				self.grid_canvas.create_line(step * self.step_width, 0, step * self.step_width, self.zoom * self.row_height - 1, fill=GRID_LINE, tags=("gridline"))
		# Delete existing note names
		self.piano_roll.delete("notename")
		for row in range(0, self.zoom):
			index = row + self.keymap_offset
			if(index >= len(self.keymap)):
				break
			if clear_grid:
				# Create last note labels in grid
				self.grid_canvas.create_text(self.grid_width - self.select_thickness, int(self.row_height * (self.zoom - row - 0.5)), state="hidden", tags=("lastnotetext%d" % (row), "lastnotetext"), font=font, anchor="e")
			self.draw_row(index)
			# Update pianoroll keys
			id = "row%d" % (row)
			try:
				name = self.keymap[index]["name"]
			except:
				name = None
			try:
				colour = self.keymap[index]["colour"]
			except:
				colour = "white"
			self.piano_roll.itemconfig(id, fill=colour)
			if name:
				self.piano_roll.create_text((2, self.row_height * (self.zoom - row - 0.5)), text=name, font=font, anchor="w", fill=CANVAS_BACKGROUND, tags="notename")
			if self.keymap[index]['note'] % 12 == libseq.getTonic():
				self.grid_canvas.create_line(0, (self.zoom - row) * self.row_height, self.grid_width, (self.zoom - row) * self.row_height, fill=GRID_LINE, tags=("gridline"))
		# Set z-order to allow duration to show
		if clear_grid:
			for step in range(libseq.getSteps()):
				self.grid_canvas.tag_lower("step%d"%step)
		self.select_cell()


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
		if len(self.keymap) == 0:
			return
		redraw = False
		if step == None:
			step = self.selected_cell[0]
		if index == None:
			index = self.selected_cell[1]
		if step < 0:
			step = 0
		if step >= libseq.getSteps():
			step = libseq.getSteps() - 1
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
		if redraw:
			self.redraw_pending = 1
		row = index - self.keymap_offset
		note = self.keymap[index]['note']
		# Skip hidden (overlapping) cells
		for previous in range(int(step) - 1, -1, -1):
			prev_duration = ceil(libseq.getNoteDuration(previous, note))
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
		if step >= libseq.getSteps():
			step = libseq.getSteps() - 1
		self.selected_cell = [int(step), index]
		cell = self.grid_canvas.find_withtag("selection")
		duration = libseq.getNoteDuration(step, row)
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
		libseq.clear()
		self.redraw_pending = 2
		self.select_cell()
		if libseq.getPlayState(self.bank, self.sequence, 0) != zynthian_gui_stepsequencer.SEQ_STOPPED:
			libseq.sendMidiCommand(0xB0 | self.channel, 123, 0) # All notes off


	# Function to copy pattern
	def copy_pattern(self):
		if libseq.getLastStep() == -1:
			self.do_copy_pattern(self.pattern)
		else:
			self.zyngui.show_confirm("Overwrite pattern %d with content from pattern %d?"%(self.pattern, self.copy_source), self.do_copy_pattern, self.pattern)
		self.load_pattern(self.copy_source)


	# Function to cancel copy pattern operation
	def cancel_copy(self):
		self.load_pattern(self.copy_source)


	# Function to actually copy pattern
	def do_copy_pattern(self, dest_pattern):
		libseq.copyPattern(self.copy_source, dest_pattern)
		self.pattern = dest_pattern
		self.load_pattern(self.pattern)
		self.copy_source = self.pattern
		self.parent.arranger.pattern = self.pattern
		self.parent.arranger.pattern_canvas.itemconfig("patternIndicator", text="%d"%(self.pattern))
		self.title = "Pattern %d" % (self.pattern)
		self.parent.set_title(self.title)


	# Function to get pattern index
	def get_pattern(self):
		return self.pattern


	# Function to get program change at start of pattern
	# returns: Program change number (1..128) or 0 for none
	def get_program_change(self):
		program = libseq.getProgramChange(0) + 1
		if program > 128:
			program = 0
		return program


	# Function to get MIDI channel listening
	# returns: MIDI channel ((1..16) or 0 for none
	def get_input_channel(self):
		channel = libseq.getInputChannel() + 1
		if channel > 16:
			channel = 0
		return channel


	# Function to get vertical zoom
	def get_vertical_zoom(self):
		return self.zoom


	# Function to handle menu editor change
	#   params: Menu item's parameters
	#   returns: String to populate menu editor label
	#   note: params is a dictionary with required fields: min, max, value
	def on_menu_change(self, params):
		menu_item = self.parent.param_editor_item
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		params['value'] = value
		if menu_item == 'Pattern':
			self.pattern = value
			self.copy_source = value
			self.load_pattern(value)
		elif menu_item =='Copy pattern':
			self.load_pattern(value)
			return "Copy %d => %d ?" % (self.copy_source, value)
		elif menu_item == 'Transpose pattern':
			if libseq.getScale() == 0:
				self.parent.hide_param_editor()
				return
			if libseq.getScale() > 1:
				# Only allow transpose when showing chromatic scale
				libseq.setScale(1)
				self.load_keymap()
				self.redraw_pending = 1
			if (value != 0 and libseq.getScale()):
				libseq.transpose(value)
				self.parent.set_param(menu_item, 'value', 0)
				self.keymap_offset = self.keymap_offset + value
				if self.keymap_offset > 128 - self.zoom:
					self.keymap_offset = 128 - self.zoom
				elif self.keymap_offset < 0:
					self.keymap_offset = 0
				else:
					self.selected_cell[1] = self.selected_cell[1] + value
				self.redraw_pending = 1
				self.select_cell()
			return "Transpose +/-"
		elif menu_item == 'Vertical zoom':
			self.zoom = value
		elif menu_item == 'Steps per beat':
			steps_per_beat = STEPS_PER_BEAT[value]
#			libseq.setStepsPerBeat(steps_per_beat)
			self.redraw_pending = 2
			value = steps_per_beat
		elif menu_item == 'Scale':
			libseq.setScale(value)
			name = self.load_keymap()
			self.redraw_pending = 1
			return "Keymap: %s" % (name)
		elif menu_item == 'Tonic':
			if value < 0:
				value = 11
			if value > 11:
				value = 0
			self.parent.set_param('Tonic', 'value', value)
			offset = value - libseq.getTonic()
			libseq.setTonic(value)
			self.load_keymap()
			self.redraw_pending = 1
			return "Tonic: %s" % (self.notes[value])
		elif menu_item == 'Program change':
			if value == 0:
				libseq.removeProgramChange(0)
				return 'Program change: None'
			else:
				libseq.addProgramChange(0, value - 1)
		elif menu_item == 'Input channel':
			if value == 0:
				libseq.setInputChannel(0xFF)
				return 'Input channel: None'
			libseq.setInputChannel(value - 1)
		elif menu_item == 'Rest note':
			if value < 0 or value > 127:
				value = 128
			libseq.setInputRest(value)
			if value > 127:
				return "Rest note: None"
			return "Rest note: %s%d(%d)" % (['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][value%12],int(value/12)-1, value)
		return "%s: %d" % (menu_item, value)


	# Function to load new pattern
	#   index: Pattern index
	def load_pattern(self, index):
		libseq.clearSequence(self.bank, self.sequence)
		libseq.setChannel(self.bank, self.sequence, 0, self.channel)
		self.pattern = index
		libseq.selectPattern(index)
		libseq.addPattern(self.bank, self.sequence, 0, 0, index)
		if self.selected_cell[0] >= libseq.getSteps():
			self.selected_cell[0] = int(libseq.getSteps()) - 1
		self.keymap_offset = libseq.getRefNote()
		self.load_keymap()
		self.redraw_pending = 2
		self.select_cell(0, int(self.keymap_offset + self.zoom / 2))
		self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)


	# Function to refresh display
	def refresh_status(self):
		step = libseq.getPatternPlayhead(self.bank, self.sequence, 0)
		if self.playhead != step:
			self.playhead = step
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)
		if self.redraw_pending or libseq.isPatternModified():
			self.draw_grid()


	# Function to handle zynpots value change
	#   i: Zynpot index [0..n]
	#   dval: Current value of zyncoder
	def zynpot_cb(self, i, dval):
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
				if libseq.getNoteDuration(self.selected_cell[0], note):
					libseq.setNoteVelocity(self.selected_cell[0], note, self.velocity)
					self.draw_cell(self.selected_cell[0], self.selected_cell[1])
				self.parent.set_title("Velocity: %d" % (self.velocity), None, None, 2)
			elif self.edit_mode == EDIT_MODE_ALL:
				libseq.changeVelocityAll(dval)
				self.parent.set_title("ALL Velocity", None, None, 2)
			else:
				self.select_cell(None, self.selected_cell[1] - dval)

		elif i == zynthian_gui_config.ENC_SELECT:
			if self.edit_mode == EDIT_MODE_SINGLE:
				if dval > 0:
					self.duration = self.duration + 1
				if dval < 0:
					self.duration = self.duration - 1
				if self.duration > libseq.getSteps():
					self.duration = libseq.getSteps()
					return
				if self.duration < 1:
					self.duration = 1
					return
				note = self.keymap[self.selected_cell[1]]["note"]
				if libseq.getNoteDuration(self.selected_cell[0], note):
					self.add_event(self.selected_cell[0], note)
				else:
					self.select_cell()
				self.parent.set_title("Duration: %0.1f steps" % (self.duration), None, None, 2)
			elif self.edit_mode == EDIT_MODE_ALL:
				if dval > 0:
					libseq.changeDurationAll(1)
				if dval < 0:
					libseq.changeDurationAll(-1)
				self.parent.set_title("ALL DURATION", None, None, 2)
			else:
				self.select_cell(self.selected_cell[0] + dval, None)

		elif i == zynthian_gui_config.ENC_SNAPSHOT:
			if self.edit_mode == EDIT_MODE_SINGLE:
				if dval > 0:
					self.duration = self.duration + 0.1
				if dval < 0:
					self.duration = self.duration - 0.1
				if self.duration > libseq.getSteps():
					self.duration = libseq.getSteps()
					return
				if self.duration < 0.1:
					self.duration = 0.1
					return
				note = self.keymap[self.selected_cell[1]]["note"]
				if libseq.getNoteDuration(self.selected_cell[0], note):
					self.add_event(self.selected_cell[0], note)
				else:
					self.select_cell()
				self.parent.set_title("Duration: %0.1f steps" % (self.duration), None, None, 2)
			elif self.edit_mode == EDIT_MODE_ALL:
				if dval > 0:
					libseq.changeDurationAll(0.1)
				if dval < 0:
					libseq.changeDurationAll(-0.1)
				self.parent.set_title("ALL DURATION", None, None, 2)

#		elif encoder == zynthian_gui_config.ENC_LAYER and not self.parent.lst_menu.winfo_viewable():
			# Show menu
#			self.parent.toggle_menu()
#			return


	# Function to handle switch press
	#   switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#   type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#   returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if self.parent.lst_menu.winfo_viewable():
			return False
		if self.parent.param_editor_item:
			return False
		if switch == zynthian_gui_config.ENC_SELECT:
			if type == "S":
				if self.edit_mode:
					self.enable_edit(EDIT_MODE_NONE)
					return True
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
				libseq.setTransportToStartOfBar()
				return True
			if libseq.getPlayState(self.bank, self.sequence) == zynthian_gui_stepsequencer.SEQ_STOPPED:
				libseq.setPlayState(self.bank, self.sequence, zynthian_gui_stepsequencer.SEQ_STARTING)
			else:
				libseq.setPlayState(self.bank, self.sequence, zynthian_gui_stepsequencer.SEQ_STOPPED)
			return True
		elif switch == zynthian_gui_config.ENC_BACK:
			self.enable_edit(EDIT_MODE_NONE)
			return True
		return False


#------------------------------------------------------------------------------
