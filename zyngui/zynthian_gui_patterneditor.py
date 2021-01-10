#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Step-Sequencer Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2020 Brian Walton <brian@riban.co.uk>
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
import time
import ctypes
from os.path import dirname, realpath, basename
from mido import MidiFile

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_layer
from . import zynthian_gui_stepsequencer
from zyngui.zynthian_gui_fileselector import zynthian_gui_fileselector

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
# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select
ENC_LAYER           = 0
ENC_BACK            = 1
ENC_SNAPSHOT        = 2
ENC_SELECT          = 3

# List of permissible steps per beat
STEPS_PER_BEAT = [1,2,3,4,6,8,12,24]


# Class implements step sequencer pattern editor
class zynthian_gui_patterneditor():
	#TODO: Inherit child views from superclass

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		self.libseq = parent.zyngui.libseq

		os.makedirs(CONFIG_ROOT, exist_ok=True)

		self.edit_mode = False # True to enable encoders to adjust duration and velocity
		self.zoom = 16 # Quantity of rows (notes) displayed in grid
		self.duration = 1 # Current note entry duration
		self.velocity = 100 # Current note entry velocity
		self.copySource = 1 # Index of pattern to copy
		#TODO: Use song operations rather than sequence
		self.sequence = self.libseq.getSequence(0, 0) # Sequence used for pattern editor sequence player (track 0 in song 0)
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

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height
		self.select_thickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.grid_height = self.height - PLAYHEAD_HEIGHT
		self.grid_width = int(self.width * 0.9)
		self.pianoroll_width = self.width - self.grid_width
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
		self.velocityCanvas = tkinter.Canvas(self.main_frame,
			width=self.pianoroll_width,
			height=PLAYHEAD_HEIGHT,
			bg=CELL_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.velocityCanvas.create_rectangle(0, 0, self.pianoroll_width * self.velocity / 127, PLAYHEAD_HEIGHT, fill='yellow', tags="velocityIndicator", width=0)
		self.velocityCanvas.grid(column=0, row=2)

		# Create pianoroll canvas
		self.pianoRoll = tkinter.Canvas(self.main_frame,
			width=self.pianoroll_width,
			height=self.grid_height,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.pianoRoll.grid(row=0, column=0)
		self.pianoRoll.bind("<ButtonPress-1>", self.on_pianoroll_press)
		self.pianoRoll.bind("<ButtonRelease-1>", self.on_pianoroll_release)
		self.pianoRoll.bind("<B1-Motion>", self.on_pianoroll_motion)

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

		self.libseq.setPlayMode(self.sequence, zynthian_gui_stepsequencer.SEQ_LOOP)

		self.playhead = 0
#		self.startPlayheadHandler()

		# Select a cell
		self.select_cell(0, self.keymap_offset)


	# Function to get name of this view
	def get_name(self):
		return "pattern editor"
	

	# Function called when new file loaded
	def on_load(self):
		pass


	#Function to set values of encoders
	#   note: Call after other routine uses one or more encoders
	def setup_encoders(self):
		self.parent.register_zyncoder(ENC_BACK, self)
		self.parent.register_zyncoder(ENC_SELECT, self)
		self.parent.register_zyncoder(ENC_LAYER, self)
		self.parent.register_switch(ENC_SELECT, self, "SB")
		self.parent.register_switch(ENC_SNAPSHOT, self, "SB")


	# Function to show GUI
	#   params: Pattern parameters to edit {'pattern':x, 'channel':x}
	def show(self, params=None):
		try:
			self.load_pattern(params['pattern'])
			self.libseq.setChannel(self.sequence, params['channel'])
			self.libseq.setTransportToStartOfBar()
		except:
			pass # Probably already populated and just returning from menu action or similar
		self.copySource = self.pattern
		self.setup_encoders()
		self.main_frame.tkraise()
		self.parent.set_title("Pattern %d" % (self.pattern))
		self.shown=True


	# Function to hide GUI
	def hide(self):
		self.shown=False
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.ENC_BACK)
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.ENC_SELECT)
		self.parent.unregister_zyncoder(zynthian_gui_stepsequencer.ENC_LAYER)
		self.parent.unregister_switch(zynthian_gui_stepsequencer.ENC_SELECT, "SB")
		self.parent.unregister_switch(zynthian_gui_stepsequencer.ENC_SNAPSHOT, "SB")
		self.libseq.setPlayState(self.sequence, zynthian_gui_stepsequencer.SEQ_STOPPED)


	# Function to add menus
	def populate_menu(self):
		self.parent.add_menu({'Pattern':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':999, 'get_value':self.get_pattern, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Beats in pattern':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':16, 'get_value':self.libseq.getBeatsInPattern, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Steps per beat':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':len(STEPS_PER_BEAT)-1, 'get_value':self.get_steps_per_beat_index, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Beat type':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':64, 'get_value':self.libseq.getBeatType, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Copy pattern':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':1999, 'get_value':self.get_copy_source, 'on_change':self.on_menu_change,'on_assert':self.copy_pattern}}})
		self.parent.add_menu({'Clear pattern':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':1, 'value':0, 'on_change':self.on_menu_change, 'on_assert':self.clear_pattern}}})
		if self.libseq.getScale():
			self.parent.add_menu({'Transpose pattern':{'method':self.parent.show_param_editor, 'params':{'min':-1, 'max':1, 'value':0, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Vertical zoom':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':127, 'get_value':self.get_vertical_zoom, 'on_change':self.on_menu_change, 'on_assert':self.assert_zoom}}})
		self.parent.add_menu({'Scale':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':self.get_scales(), 'get_value':self.libseq.getScale, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Tonic':{'method':self.parent.show_param_editor, 'params':{'min':-1, 'max':12, 'get_value':self.libseq.getTonic, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Import':{'method':self.select_import}})
		self.parent.add_menu({'Input channel':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':16, 'get_value':self.get_input_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Rest note':{'method':self.parent.show_param_editor, 'params':{'min':-1, 'max':128, 'get_value':self.libseq.getInputRest, 'on_change':self.on_menu_change}}})


	# Function to set edit mode
	def enable_edit(self, enable):
		if enable:
			self.edit_mode = True
			self.parent.register_switch(ENC_BACK, self)
			self.parent.set_title("Note Parameters (%d)" % (self.pattern), zynthian_gui_config.color_header_bg, zynthian_gui_config.color_panel_tx)
		else:
			self.edit_mode = False
			self.parent.unregister_switch(ENC_BACK)
			self.parent.set_title("Pattern %d" % (self.pattern), zynthian_gui_config.color_panel_tx, zynthian_gui_config.color_header_bg)


	# Function to get the index of the closest steps per beat in array of allowed values
	#	returns: Index of closest allowed value
	def get_steps_per_beat_index(self):
		stepsPerBeat = self.libseq.getStepsPerBeat()
		for index in range(len(STEPS_PER_BEAT)):
			if STEPS_PER_BEAT[index] >= stepsPerBeat:
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
		scale = self.libseq.getScale()
		tonic = self.libseq.getTonic()
		name = None
		self.keymap = []
		if scale == 0:
			# Map
			path = None
			for layer in self.zyngui.screens['layer'].layers:
				if layer.midi_chan == self.libseq.getChannel(self.sequence):
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
			self.libseq.setScale(scale + 1) # Use chromatic scale if map not found
			if scale == 0:
				for note in range(0,128):
					newEntry = {"note":note}
					key = note % 12
					if key in (1,3,6,8,10): # Black notes
						newEntry.update({"colour":"black"})
					if key == 0: # 'C'
						newEntry.update({"name":"C%d" % (note // 12 - 1)})
					self.keymap.append(newEntry)
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
				name = data[scale]['name']
		self.select_cell(0, int(len(self.keymap) / 2))
		return name


	# Function to handle start of pianoroll drag
	def on_pianoroll_press(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hideMenu()
			return
		self.pianoRollDragStart = event
		index = self.keymap_offset + self.zoom - int(event.y / self.rowHeight) - 1
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		self.libseq.playNote(note, 100, self.libseq.getChannel(self.sequence), 200)


	# Function to handle pianoroll drag motion
	def on_pianoroll_motion(self, event):
		if not self.pianoRollDragStart:
			return
		offset = int((event.y - self.pianoRollDragStart.y) / self.rowHeight)
		if offset == 0:
			return
		self.keymap_offset = self.keymap_offset + offset
		if self.keymap_offset < 0:
			self.keymap_offset = 0
		if self.keymap_offset > len(self.keymap) - self.zoom:
			self.keymap_offset = len(self.keymap) - self.zoom

		self.pianoRollDragStart = event
		self.redraw_pending = 1

		if self.selected_cell[1] < self.keymap_offset:
			self.selected_cell[1] = self.keymap_offset
		elif self.selected_cell[1] >= self.keymap_offset + self.zoom:
			self.selected_cell[1] = self.keymap_offset + self.zoom - 1
		self.select_cell()


	# Function to handle end of pianoroll drag
	def on_pianoroll_release(self, event):
		self.pianoRollDragStart = None


	# Function to handle grid mouse down
	#	event: Mouse event
	def on_grid_press(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hideMenu()
			return
		if self.parent.param_editor_item != None:
			self.parent.hideParamEditor()
			return
		self.grid_drag_start = event
		try:
			col,row = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))[0].split(',')
		except:
			return
		note = self.keymap[self.keymap_offset + int(row)]["note"]
		step = int(col)
		if step < 0 or step >= self.libseq.getSteps():
			return
		self.drag_start_velocity = self.libseq.getNoteVelocity(step, note)
		self.dragStartDuration = self.libseq.getNoteDuration(step, note)
		self.dragStartStep = int(event.x / self.step_width)
		if not self.drag_start_velocity:
			self.libseq.playNote(note, 100, self.libseq.getChannel(self.sequence), 200)
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
			if not self.drag_velocity and not self.drag_duration and (event.x > (self.dragStartStep + 1) * self.step_width or event.x < self.dragStartStep * self.step_width):
				self.drag_duration = True
			if not self.drag_duration and not self.drag_velocity and (event.y > self.grid_drag_start.y + self.rowHeight / 2 or event.y < self.grid_drag_start.y - self.rowHeight / 2):
				self.drag_velocity = True
			value = 0
			if self.drag_velocity:
				value = (self.grid_drag_start.y - event.y) / self.rowHeight
				if value:
					self.velocity = int(self.drag_start_velocity + value * self.height / 100)
					if self.velocity > 127:
						self.velocity = 127
						return
					if self.velocity < 1:
						self.velocity = 1
						return
					self.velocityCanvas.coords("velocityIndicator", 0, 0, self.pianoroll_width * self.velocity / 127, PLAYHEAD_HEIGHT)
					if self.libseq.getNoteDuration(self.selected_cell[0], note):
						self.libseq.setNoteVelocity(self.selected_cell[0], note, self.velocity)
						self.draw_cell(self.selected_cell[0], index)
			if self.drag_duration:
				value = int(event.x / self.step_width) - self.dragStartStep
				duration = self.dragStartDuration + value
				if duration != self.duration and duration > 0:
					self.duration = duration
					self.add_event(step, index) # Change length by adding event over previous one
		else:
			# Clicked on empty cell so want to add a new note by dragging towards the desired cell
			x1 = self.selected_cell[0] * self.step_width # x pos of start of event
			x3 = (self.selected_cell[0] + 1) * self.step_width # x pos right of event's first cell
			y1 = self.grid_height - (self.selected_cell[1] - self.keymap_offset) * self.rowHeight # y pos of top of selected row
			y2 = self.grid_height - (self.selected_cell[1] - self.keymap_offset + 1) * self.rowHeight # y pos of bottom of selected row
			if event.x < x1:
				self.select_cell(self.selected_cell[0] - 1, None)
			elif event.x > x3:
				self.select_cell(self.selected_cell[0] + 1, None)
			elif event.y < y2:
				self.select_cell(None, self.selected_cell[1] + 1)
				self.libseq.playNote(self.keymap[self.selected_cell[1]]["note"], 100, self.libseq.getChannel(self.sequence), 200)
			elif event.y > y1:
				self.select_cell(None, self.selected_cell[1] - 1)
				self.libseq.playNote(self.keymap[self.selected_cell[1]]["note"], 100, self.libseq.getChannel(self.sequence), 200)


	# Function to toggle note event
	#	step: step (column) index
	#	index: key map index
	def toggle_event(self, step, index, playnote=False):
		if step < 0 or step >= self.libseq.getSteps() or index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		if self.libseq.getNoteVelocity(step, note):
			self.remove_event(step, index)
		else:
			self.add_event(step, index)
			if playnote:
				self.libseq.playNote(note, 100, self.libseq.getChannel(self.sequence), 200)


	# Function to remove an event
	#	step: step (column) index
	#	index: keymap index
	def remove_event(self, step, index):
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		self.libseq.removeNote(step, note)
		self.libseq.playNote(note, 0) # Silence note if sounding
		self.draw_row(index)
		self.select_cell(step, index)


	# Function to add an event
	#	step: step (column) index
	#	index: keymap index
	def add_event(self, step, index):
		note = self.keymap[index]["note"]
		self.libseq.addNote(step, note, self.velocity, self.duration)
		self.draw_row(index)
		self.select_cell(step, index)


	# Function to draw a grid row
	#	index: keymap index
	def draw_row(self, index):
		row = index - self.keymap_offset
		self.grid_canvas.itemconfig("lastnotetext%d" % (row), state="hidden")
		for step in range(self.libseq.getSteps()):
			self.draw_cell(step, row)


	# Function to get cell coordinates
	#   col: Column index
	#   row: Row index
	#   duration: Duration of cell in steps
	#   return: Coordinates required to draw cell
	def get_cell(self, col, row, duration):
		x1 = col * self.step_width + 1
		y1 = (self.zoom - row - 1) * self.rowHeight + 1
		x2 = x1 + self.step_width * duration - 1 
		y2 = y1 + self.rowHeight - 1
		return [x1, y1, x2, y2]


	# Function to draw a grid cell
	#	step: Step (column) index
	#	row: Index of row
	def draw_cell(self, step, row):
		cellIndex = row * self.libseq.getSteps() + step # Cells are stored in array sequentially: 1st row, 2nd row...
		if cellIndex >= len(self.cells):
			return
		note = self.keymap[row + self.keymap_offset]["note"]
		velocityColour = self.libseq.getNoteVelocity(step, note)
		if velocityColour:
			velocityColour = 70 + velocityColour
		elif self.libseq.getScale() == 1:
			# Draw tramlines for white notes in chromatic scale
			key = note % 12
			if key in (0,2,4,5,7,9,11): # White notes
#			if key in (1,3,6,8,10): # Black notes
				velocityColour += 30
		else:
			# Draw tramlines for odd rows in other scales and maps
			if (row + self.keymap_offset) % 2:
				velocityColour += 30
		duration = self.libseq.getNoteDuration(step, note)
		if not duration:
			duration = 1
		fillColour = "#%02x%02x%02x" % (velocityColour, velocityColour, velocityColour)
		cell = self.cells[cellIndex]
		coord = self.get_cell(step, row, duration)
		if cell:
			# Update existing cell
			self.grid_canvas.itemconfig(cell, fill=fillColour)
			self.grid_canvas.coords(cell, coord)
		else:
			# Create new cell
			cell = self.grid_canvas.create_rectangle(coord, fill=fillColour, width=0, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step))
			self.grid_canvas.tag_bind(cell, '<ButtonPress-1>', self.on_grid_press)
			self.grid_canvas.tag_bind(cell, '<ButtonRelease-1>', self.on_grid_release)
			self.grid_canvas.tag_bind(cell, '<B1-Motion>', self.on_grid_drag)
			self.cells[cellIndex] = cell
		if step + duration > self.libseq.getSteps():
			if duration > 1:
				self.grid_canvas.itemconfig("lastnotetext%d" % row, text="+%d" % (duration - self.libseq.getSteps() + step), state="normal")


	# Function to draw grid
	def draw_grid(self):
		clearGrid = (self.redraw_pending == 2)
		self.redraw_pending = 0
		if self.libseq.getSteps() == 0:
			return #TODO: Should we clear grid?
		if self.keymap_offset > len(self.keymap) - self.zoom:
			self.keymap_offset = len(self.keymap) - self.zoom
		if self.keymap_offset < 0:
			self.keymap_offset = 0
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		if clearGrid:
			self.grid_canvas.delete(tkinter.ALL)
			self.step_width = (self.grid_width - 2) / self.libseq.getSteps()
			self.draw_pianoroll()
			self.cells = [None] * self.zoom * self.libseq.getSteps()
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)
		# Draw cells of grid
		self.grid_canvas.itemconfig("gridcell", fill="black")
		# Redraw gridlines
		self.grid_canvas.delete("gridline")
		if self.libseq.getStepsPerBeat():
			for step in range(0, self.libseq.getSteps() + 1, self.libseq.getStepsPerBeat()):
				self.grid_canvas.create_line(step * self.step_width, 0, step * self.step_width, self.zoom * self.rowHeight - 1, fill=GRID_LINE, tags=("gridline"))
		# Delete existing note names
		self.pianoRoll.delete("notename")
		for row in range(0, self.zoom):
			index = row + self.keymap_offset
			if(index >= len(self.keymap)):
				break
			self.draw_row(index)
			# Update pianoroll keys
			if clearGrid:
				# Create last note labels in grid
				self.grid_canvas.create_text(self.grid_width - self.select_thickness, self.fontsize, state="hidden", tags=("lastnotetext%d" % (row), "lastnotetext"), font=font, anchor="e")
			id = "row%d" % (row)
			try:
				name = self.keymap[index]["name"]
			except:
				name = None
			try:
				colour = self.keymap[index]["colour"]
			except:
				colour = "white"
			self.pianoRoll.itemconfig(id, fill=colour)
			if name:
				self.pianoRoll.create_text((2, self.rowHeight * (self.zoom - row - 0.5)), text=name, font=font, anchor="w", fill=CANVAS_BACKGROUND, tags="notename")
			if self.keymap[index]['note'] % 12 == self.libseq.getTonic():
				self.grid_canvas.create_line(0, (self.zoom - row) * self.rowHeight, self.grid_width, (self.zoom - row) * self.rowHeight, fill=GRID_LINE, tags=("gridline"))
		# Set z-order to allow duration to show
		if clearGrid:
			for step in range(self.libseq.getSteps()):
				self.grid_canvas.tag_lower("step%d"%step)
		self.select_cell()


	# Function to draw pianoroll key outlines (does not fill key colour)
	def draw_pianoroll(self):
		self.pianoRoll.delete(tkinter.ALL)
		for row in range(self.zoom):
			x1 = 0
			y1 = self.get_cell(0, row, 1)[1]
			x2 = self.pianoroll_width
			y2 = y1 + self.rowHeight - 1
			id = "row%d" % (row)
			id = self.pianoRoll.create_rectangle(x1, y1, x2, y2, width=0, tags=id)


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
		if step >= self.libseq.getSteps():
			step = self.libseq.getSteps() - 1
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
		for previous in range(step - 1, -1, -1):
			prevDuration = self.libseq.getNoteDuration(previous, note)
			if not prevDuration:
				continue
			if prevDuration > step - previous:
				if step > self.selected_cell[0]:
					step = previous + prevDuration
				else:
					step = previous
				break
		if step < 0:
			step = 0
		if step >= self.libseq.getSteps():
			step = self.libseq.getSteps() - 1
		self.selected_cell = [step, index]
		cell = self.grid_canvas.find_withtag("selection")
		duration = self.libseq.getNoteDuration(step, row)
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
		self.rowHeight = (self.grid_height - 2) / self.zoom
		self.fontsize = int(self.rowHeight * 0.5)
		if self.fontsize > 20:
			self.fontsize = 20 # Ugly font scale limiting


	# Function to clear a pattern
	def clear_pattern(self):
		self.libseq.clear()
		self.redraw_pending = 2
		self.select_cell()
		if self.zyngui.lib_zyncoder:
			self.zyngui.lib_zyncoder.zynmidi_send_all_notes_off()


	# Function to copy pattern
	def copy_pattern(self):
		self.libseq.copyPattern(self.copySource, self.pattern)
		self.load_pattern(self.pattern)
		self.copySource = self.pattern


	# Function to get pattern index
	def get_pattern(self):
		return self.pattern


	# Function to get pattern index
	def get_input_channel(self):
		channel = self.libseq.getInputChannel() + 1
		if channel > 16:
			channel = 0
		return channel


	# Function to get copy source
	def get_copy_source(self):
		return self.copySource


	# Function to get vertical zoom
	def get_vertical_zoom(self):
		return self.zoom


	# Function to handle menu editor change
	#   params: Menu item's parameters
	#   returns: String to populate menu editor label
	#   note: params is a dictionary with required fields: min, max, value
	def on_menu_change(self, params):
		menuItem = self.parent.param_editor_item
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		params['value'] = value
		if menuItem == 'Pattern':
			self.pattern = value
			self.copySource = value
			self.load_pattern(value)
		elif menuItem == 'Clear pattern':
			return "Clear pattern %d?" % (self.pattern)
		elif menuItem =='Copy pattern':
			self.load_pattern(value)
			return "Copy %d=>%d?" % (self.copySource, value)
		elif menuItem == 'Transpose pattern':
			if self.libseq.getScale() == 0:
				self.parent.hideParamEditor()
				return
			if self.libseq.getScale() > 1:
				# Only allow transpose when showing chromatic scale
				self.libseq.setScale(1)
				self.load_keymap()
				self.redraw_pending = 1
			if (value != 0 and self.libseq.getScale()):
				self.libseq.transpose(value)
				self.parent.set_param(menuItem, 'value', 0)
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
		elif menuItem == 'Vertical zoom':
			self.zoom = value
		elif menuItem == 'Beats in pattern':
			self.libseq.setBeatsInPattern(value)
			self.redraw_pending = 2
		elif menuItem == 'Steps per beat':
			stepsPerBeat = STEPS_PER_BEAT[value]
			self.libseq.setStepsPerBeat(stepsPerBeat)
			self.redraw_pending = 2
			value = stepsPerBeat
		elif menuItem == 'Beat type':
			prevVal = self.libseq.getBeatType()
			if prevVal > value:
				value = prevVal >> 1
			self.libseq.setBeatType(value)
			self.redraw_pending = 2
			value = self.libseq.getBeatType()
			self.parent.set_param('Beat type', 'value', value)
		elif menuItem == 'Scale':
			self.libseq.setScale(value)
			name = self.load_keymap()
			self.redraw_pending = 1
			return "Keymap: %s" % (name)
		elif menuItem == 'Tonic':
			if value < 0:
				value = 11
			if value > 11:
				value = 0
			self.parent.set_param('Tonic', 'value', value)
			offset = value - self.libseq.getTonic()
			self.libseq.setTonic(value)
			if self.parent.get_param('Scale', 'value'):
				for key in self.keymap:
					note = key['note'] + offset
					key['note'] = note
					key['name'] = "%s%d" % (self.notes[note % 12], note // 12)
			self.redraw_pending = 1
			return "Tonic: %s" % (self.notes[value])
		elif menuItem == 'Input channel':
			if value == 0:
				self.libseq.setInputChannel(0xFF)
				return 'Input channel: None'
			self.libseq.setInputChannel(value - 1)
		elif menuItem == 'Rest note':
			if value < 0 or value > 127:
				value = 128
			self.libseq.setInputRest(value)
			if value > 127:
				return "Rest note: None"
			return "Rest note: %s%d(%d)" % (['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][value%12],int(value/12)-1, value)
		return "%s: %d" % (menuItem, value)


	# Function to load new pattern
	#   index: Pattern index
	def load_pattern(self, index):
		self.libseq.clearSequence(self.sequence)
		self.pattern = index
		self.libseq.selectPattern(index)
		self.libseq.addPattern(self.sequence, 0, index)
		if self.selected_cell[0] >= self.libseq.getSteps():
			self.selected_cell[0] = self.libseq.getSteps() - 1
		self.load_keymap()
		self.redraw_pending = 2
		self.select_cell()
		self.play_canvas.coords("playCursor", 1, 0, 1 + self.step_width, PLAYHEAD_HEIGHT)
		self.parent.set_title("Pattern %d" % (self.pattern))


	# Function to select .mid file to import
	def select_import(self, params):
		zynthian_gui_fileselector(self.parent, self.import_mid, zynthian_gui_stepsequencer.os.environ.get('ZYNTHIAN_MY_DATA_DIR',"/zynthian/zynthian-my-data") + "/capture", "mid", None, True)


	# Function to import patterns from .mid file
	#	filename: Full path and filename of midi file from which to import
	def import_mid(self, filename):
		# Open file
		try:
			mid = MidiFile(filename)
		except:
			logging.warning("Unable to open file %s for import", filename)
			return

		# Extract first tempo from file
		tempo = 60000000/120
		for msg in mid:
			if msg.type == "set_tempo":
				tempo = msg.tempo
				break
		if tempo == None:
			logging.warning("Cannot find tempo marker within %s. Assuming 120 BPM.", filename)
			return
		
		# Iterate through events in file matching current pattern MIDI channel
		pattern = self.pattern
		self.libseq.selectPattern(pattern)
		self.libseq.clear()
		notes = [{'step':0, 'velocity':0} for i in range(127)]
		offset = 0
		sec_per_beat = tempo / 1000000
		steps_per_beat = self.libseq.getStepsPerBeat()
		sec_per_step = sec_per_beat / steps_per_beat
		step = 0
		max_steps = self.libseq.getSteps()
		beats = self.libseq.getBeatsInPattern()
		channel = self.get_input_channel()
		populated_pattern = False
		for msg in mid:
			offset += msg.time
			step = int(offset / sec_per_step) % max_steps
			this_pattern = pattern + int(int(offset / sec_per_step) / max_steps)
			if this_pattern > self.pattern:
				if populated_pattern:
					populated_pattern = False
					self.pattern = this_pattern
					self.libseq.selectPattern(this_pattern)
					self.libseq.clear()
					self.libseq.setBeatsInPattern(beats)
					self.libseq.setStepsPerBeat(steps_per_beat)
			if msg.type != 'note_on' and msg.type != 'note_off' or msg.channel != channel: continue
			populated_pattern = True
			if msg.type == 'note_on' and msg.velocity:
				notes[msg.note]['step'] = step
				notes[msg.note]['velocity'] = msg.velocity
			elif msg.type == 'note_off' or msg.type == 'note_on' and msg.velocity == 0:
				duration = step - notes[msg.note]['step'] + 1
				if duration < 0:
					duration += max_steps
				self.libseq.addNote(step, msg.note, notes[msg.note]['velocity'], duration)
		self.load_pattern(pattern) # Reload our starting pattern in the editor


	# Function to refresh display
	def refresh_status(self):
		step = self.libseq.getStep(self.sequence)
		if self.playhead != step:
			self.playhead = step
			self.play_canvas.coords("playCursor", 1 + self.playhead * self.step_width, 0, 1 + self.playhead * self.step_width + self.step_width, PLAYHEAD_HEIGHT)
		if self.redraw_pending or self.libseq.isPatternModified():
			self.draw_grid()


	# Function to handle zyncoder value change
	#   encoder: Zyncoder index [0..4]
	#   value: Current value of zyncoder
	def on_zyncoder(self, encoder, value):
		if encoder == ENC_BACK:
			if self.edit_mode:
				self.velocity = self.velocity + value
				if self.velocity > 127:
					self.velocity = 127
					return
				if self.velocity < 1:
					self.velocity = 1
					return
				self.velocityCanvas.coords("velocityIndicator", 0, 0, self.pianoroll_width * self.velocity / 127, PLAYHEAD_HEIGHT)
				note = self.keymap[self.selected_cell[1]]["note"]
				if self.libseq.getNoteDuration(self.selected_cell[0], note):
					self.libseq.setNoteVelocity(self.selected_cell[0], note, self.velocity)
					self.draw_cell(self.selected_cell[0], self.selected_cell[1])
			else:
				self.select_cell(None, self.selected_cell[1] - value)
		elif encoder == ENC_SELECT:
			if self.edit_mode:
				if value > 0:
					self.duration = self.duration + 1
				if value < 0:
					self.duration = self.duration - 1
				if self.duration > self.libseq.getSteps():
					self.duration = self.libseq.getSteps()
					return
				if self.duration < 1:
					self.duration = 1
					return
				if self.libseq.getNoteDuration(self.selected_cell[0], self.selected_cell[1]):
					self.add_event(self.selected_cell[0], self.selected_cell[1])
				else:
					self.select_cell()
			else:
				self.select_cell(self.selected_cell[0] + value, None)


	# Function to handle switch press
	#   switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#   type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#   returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if switch == ENC_SELECT:
			if self.edit_mode:
				self.enable_edit(False)
				return True
			if type == "S":
				self.toggle_event(self.selected_cell[0], self.selected_cell[1], True)
			else:
				self.enable_edit(True)
			return True
		elif switch == ENC_SNAPSHOT:
			if type == "B":
				self.libseq.setTransportToStartOfBar()
				return True
			self.libseq.togglePlayState(self.sequence)
			return True
		elif switch == ENC_BACK:
			self.enable_edit(False)
			return True
		return False
#------------------------------------------------------------------------------
