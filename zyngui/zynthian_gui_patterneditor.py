 
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

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_layer
from zyncoder import *

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
# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select
ENC_LAYER           = 0
ENC_BACK            = 1
ENC_SNAPSHOT        = 2
ENC_SELECT          = 3

# List of permissible steps per beat
STEPS_PER_BEAT = [0,1,2,3,4,6,8,12,24]

# Class implements step sequencer pattern editor
class zynthian_gui_patterneditor():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent

		self.zoom = 16 # Quantity of rows (notes) displayed in grid
		self.duration = 1 # Current note entry duration
		self.velocity = 100 # Current note entry velocity
		self.copySource = 1 # Index of pattern to copy
		#TODO: Use song operations rather than sequence
		self.song = 0 # Use song zero for pattern editor sequnce player
		self.sequence = parent.libseq.getSequence(self.song, 0) # Sequence used for pattern editor sequence player
		self.stepWidth = 40 # Grid column width in pixels
		self.keyMapOffset = 60 # MIDI note number of bottom row in grid
		self.selectedCell = [0, 0] # Location of selected cell (column,row)
		self.dragVelocity = False # True indicates drag will adjust velocity and duration
		self.dragStartVelocity = None # Velocity value at start of drag
		self.gridDragStart = None # Coordinates at start of grid drag
		self.keymap = [] # Array of {"note":MIDI_NOTE_NUMBER, "name":"key name","colour":"key colour"} name and colour are optional
		self.notes = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
		#TODO: Get values from persistent storage
		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration
		self.cells = [] # Array of cells indices

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height
		self.selectThickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.gridHeight = self.height - PLAYHEAD_HEIGHT
		self.gridWidth = int(self.width * 0.9)
		self.pianoRollWidth = self.width - self.gridWidth
		self.updateRowHeight()

		# Main Frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(row=1, column=0, sticky="nsew")

		# Create pattern grid canvas
		self.gridCanvas = tkinter.Canvas(self.main_frame, 
			width=self.gridWidth, 
			height=self.gridHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.gridCanvas.grid(row=0, column=1)

		# Create velocity level indicator canvas
		self.velocityCanvas = tkinter.Canvas(self.main_frame,
			width=self.pianoRollWidth,
			height=PLAYHEAD_HEIGHT,
			bg=CELL_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.velocityCanvas.create_rectangle(0, 0, self.pianoRollWidth * self.velocity / 127, PLAYHEAD_HEIGHT, fill='yellow', tags="velocityIndicator", width=0)
		self.velocityCanvas.grid(column=0, row=2)

		# Create pianoroll canvas
		self.pianoRoll = tkinter.Canvas(self.main_frame,
			width=self.pianoRollWidth,
			height=self.gridHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.pianoRoll.grid(row=0, column=0)
		self.pianoRoll.bind("<ButtonPress-1>", self.onPianoRollPress)
		self.pianoRoll.bind("<ButtonRelease-1>", self.onPianoRollRelease)
		self.pianoRoll.bind("<B1-Motion>", self.onPianoRollMotion)

		# Create playhead canvas
		self.playCanvas = tkinter.Canvas(self.main_frame,
			width=self.gridWidth, 
			height=PLAYHEAD_HEIGHT,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.playCanvas.create_rectangle(0, 0, self.stepWidth, PLAYHEAD_HEIGHT,
			fill=PLAYHEAD_CURSOR,
			state="normal",
			width=0,
			tags="playCursor")
		self.playCanvas.grid(column=1, row=2)

		self.parent.libseq.setPlayMode(self.sequence, zynthian_gui_config.SEQ_LOOP)

		self.playhead = 0
#		self.startPlayheadHandler()

		# Select a cell
		self.selectCell(0, self.keyMapOffset)

	# Function to draw play cursor - periodically checks for change in current step then redraws cursor if necessary
	#TODO: Remove thread handling playhead (now using refresh_status)
	def startPlayheadHandler(self):
		def onStep():
			playhead = 0
			while(not self.zyngui.exit_flag):
				step = self.parent.libseq.getStep(self.sequence)
				if playhead != step:
					playhead = step
					if self.shown:
						# Draw play head cursor
						self.playCanvas.coords("playCursor", 1 + playhead * self.stepWidth, 0, 1 + playhead * self.stepWidth + self.stepWidth, PLAYHEAD_HEIGHT)
				sleep(0.1) #TODO It would be great if this could be event driven rather than poll every 100ms
		thread = threading.Thread(target=onStep, daemon=True)
		thread.start()

	#Function to set values of encoders
	#   note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		self.parent.registerZyncoder(ENC_BACK, self)
		self.parent.registerZyncoder(ENC_SELECT, self)
		self.parent.registerZyncoder(ENC_SNAPSHOT, self)
		self.parent.registerZyncoder(ENC_LAYER, self)

	# Function to show GUI
	#   params: Pattern parameters to edit {'pattern':x, 'channel':x}
	def show(self, params=None):
		try:
			pattern = params['pattern']
			channel = params['channel']
		except:
			pattern = 1
			channel = 1
		self.parent.libseq.setChannel(self.sequence, channel)
		self.loadPattern(pattern)
		self.setupEncoders()
		self.main_frame.tkraise()
		self.parent.setTitle("Pattern Editor (%d)" % (self.pattern))
		self.parent.libseq.setPlayState(self.sequence, zynthian_gui_config.SEQ_PLAYING)
		self.shown=True

	# Function to hide GUI
	def hide(self):
		self.shown=False
		self.parent.unregisterZyncoder(ENC_BACK)
		self.parent.unregisterZyncoder(ENC_SELECT)
		self.parent.unregisterZyncoder(ENC_SNAPSHOT)
		self.parent.unregisterZyncoder(ENC_LAYER)
		self.parent.libseq.setPlayState(self.sequence, zynthian_gui_config.SEQ_STOPPED)
		self.parent.zyngui.zyntransport.transport_stop() #TODO: Stopping transport due to jack_transport restarting if locate called

	# Function to add menus
	def populateMenu(self):
		self.parent.addMenu({'Pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'getValue':self.getPattern, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Input channel':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':16, 'getValue':self.getInputChannel, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Steps per beat':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':len(STEPS_PER_BEAT)-1, 'getValue':self.parent.libseq.getStepsPerBeat, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Steps in pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':64, 'getValue':self.parent.libseq.getSteps, 'onChange':self.onMenuChange, 'onAssert':self.assertSteps}}})
		self.parent.addMenu({'Copy pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'getValue':self.getCopySource, 'onChange':self.onMenuChange,'onAssert':self.copyPattern}}})
		self.parent.addMenu({'Clear pattern':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':1, 'value':0, 'onChange':self.onMenuChange, 'onAssert':self.clearPattern}}})
		if self.parent.libseq.getScale():
			self.parent.addMenu({'Transpose pattern':{'method':self.parent.showParamEditor, 'params':{'min':-1, 'max':1, 'value':0, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Vertical zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':127, 'getValue':self.getVerticalZoom, 'onChange':self.onMenuChange, 'onAssert':self.assertZoom}}})
		self.parent.addMenu({'Clocks per step':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':24, 'getValue':self.parent.libseq.getClocksPerStep, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Tempo':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':999, 'getValue':self.parent.zyngui.zyntransport.get_tempo, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Scale':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':self.getScales(), 'getValue':self.parent.libseq.getScale, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Tonic':{'method':self.parent.showParamEditor, 'params':{'min':-1, 'max':12, 'getValue':self.parent.libseq.getTonic, 'onChange':self.onMenuChange}}})

	# Function to get quantity of scales
	#	returns: Quantity of available scales
	def getScales(self):
		data = []
		with open("/zynthian/zynthian-my-data/sequences/scales.json") as json_file:
			data = json.load(json_file)
		return len(data)

	# Function to assert zoom level
	def assertZoom(self):
		self.updateRowHeight()
		self.drawGrid(True)
		self.selectCell()

	# Function to populate keymap array
	#	returns Name of scale / map
	def loadKeymap(self):
		scale = self.parent.libseq.getScale()
		tonic = self.parent.libseq.getTonic()
		name = None
		self.keymap = []
		if scale == 0:
			# Map
			path = None
			for layer in self.zyngui.screens['layer'].layers:
				if layer.midi_chan == self.parent.libseq.getChannel(self.sequence):
					path = layer.get_presetpath()
					break
			if path:
				path = path.split('#')[1]
				with open("/zynthian/zynthian-my-data/sequences/keymaps.json") as json_file:
					data = json.load(json_file)
				if path in data:
					name = data[path]
					xml = minidom.parse("/zynthian/zynthian-my-data/sequences/%s.midnam" % (name))
					notes = xml.getElementsByTagName('Note')
					self.scale = []
					for note in notes:
						self.keymap.append({'note':int(note.attributes['Number'].value), 'name':note.attributes['Name'].value})
		if name == None: # Not found map
			# Scale
			if scale > 0:
				scale = scale - 1
			self.parent.libseq.setScale(scale + 1) # Use chromatic scale if map not found
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
				with open("/zynthian/zynthian-my-data/sequences/scales.json") as json_file:
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
		self.drawGrid()
		self.selectCell(0, int(len(self.keymap) / 2))
		return name

	# Function to handle start of pianoroll drag
	def onPianoRollPress(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		self.pianoRollDragStart = event
		index = self.keyMapOffset + self.zoom - int(event.y / self.rowHeight) - 1
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		self.parent.libseq.playNote(note, 100, self.parent.libseq.getChannel(self.sequence), 200)

	# Function to handle pianoroll drag motion
	def onPianoRollMotion(self, event):
		if not self.pianoRollDragStart:
			return
		offset = int((event.y - self.pianoRollDragStart.y) / self.rowHeight)
		if offset == 0:
			return
		self.keyMapOffset = self.keyMapOffset + offset
		if self.keyMapOffset < 0:
			self.keyMapOffset = 0
		if self.keyMapOffset > len(self.keymap) - self.zoom:
			self.keyMapOffset = len(self.keymap) - self.zoom

		self.pianoRollDragStart = event
		self.drawGrid()

		if self.selectedCell[1] < self.keyMapOffset:
			self.selectedCell[1] = self.keyMapOffset
		elif self.selectedCell[1] >= self.keyMapOffset + self.zoom:
			self.selectedCell[1] = self.keyMapOffset + self.zoom - 1
		self.selectCell()

	# Function to handle end of pianoroll drag
	def onPianoRollRelease(self, event):
		self.pianoRollDragStart = None


	# Function to handle grid mouse down
	#	event: Mouse event
	def onGridPress(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		if self.parent.paramEditorItem != None:
			self.parent.hideParamEditor()
			return
		self.gridDragStart = event
		try:
			col,row = self.gridCanvas.gettags(self.gridCanvas.find_withtag(tkinter.CURRENT))[0].split(',')
		except:
			return
		note = self.keymap[self.keyMapOffset + int(row)]["note"]
		step = int(col)
		if step < 0 or step >= self.parent.libseq.getSteps():
			return
		self.dragStartVelocity = self.parent.libseq.getNoteVelocity(step, note)
		if not self.dragStartVelocity:
			self.parent.libseq.playNote(note, 100, self.parent.libseq.getChannel(self.sequence), 200)
		self.selectCell(int(col), self.keyMapOffset + int(row))

	# Function to handle grid mouse release
	#	event: Mouse event
	def onGridRelease(self, event):
		if not self.gridDragStart:
			return
		if not self.dragVelocity:
			self.toggleEvent(self.selectedCell[0], self.selectedCell[1])
		self.dragVelocity = False
		self.gridDragStart = None

	# Function to handle grid mouse drag
	#	event: Mouse event
	def onGridDrag(self, event):
		if not self.gridDragStart:
			return
		step = self.selectedCell[0]
		index = self.selectedCell[1]
		note = self.keymap[index]['note']
		velocity = self.parent.libseq.getNoteVelocity(step, note)
		duration = self.parent.libseq.getNoteDuration(step, note)
		x1 = self.selectedCell[0] * self.stepWidth
		x2 = (self.selectedCell[0] + duration) * self.stepWidth
		x3 = (self.selectedCell[0] + 1) * self.stepWidth
		y1 = self.gridHeight - (self.selectedCell[1] - self.keyMapOffset) * self.rowHeight
		y2 = self.gridHeight - (self.selectedCell[1] - self.keyMapOffset + 1) * self.rowHeight
		if velocity:
			value = 0
			if event.x > x2:
				self.duration = self.duration + 1
				self.addEvent(step, index)
				self.dragVelocity = True
			elif duration > 1 and event.x < x2 - self.stepWidth:
				self.duration = self.duration - 1
				self.addEvent(step, index)
				self.dragVelocity = True
			elif event.y < y2:
				value = (self.gridDragStart.y - event.y) / self.rowHeight
			elif event.y > y1:
				value = (self.gridDragStart.y - event.y) / self.rowHeight
			if value:
				self.dragVelocity = True
				self.velocity = int(self.dragStartVelocity + value * self.height / 100)
				if self.velocity > 127:
					self.velocity = 127
					return
				if self.velocity < 1:
					self.velocity = 1
					return
				self.velocityCanvas.coords("velocityIndicator", 0, 0, self.pianoRollWidth * self.velocity / 127, PLAYHEAD_HEIGHT)
				if self.parent.libseq.getNoteDuration(self.selectedCell[0], note):
					self.parent.libseq.setNoteVelocity(self.selectedCell[0], note, self.velocity)
					self.drawCell(self.selectedCell[0], index)
		else:
			if event.x < x1:
				self.selectCell(self.selectedCell[0] - 1, None)
			elif event.x > x3:
				self.selectCell(self.selectedCell[0] + 1, None)
			elif event.y < y2:
				self.selectCell(None, self.selectedCell[1] + 1)
				self.parent.libseq.playNote(self.keymap[self.selectedCell[1]]["note"], 100, self.parent.libseq.getChannel(self.sequence), 200)
			elif event.y > y1:
				self.selectCell(None, self.selectedCell[1] - 1)
				self.parent.libseq.playNote(self.keymap[self.selectedCell[1]]["note"], 100, self.parent.libseq.getChannel(self.sequence), 200)

	# Function to toggle note event
	#	step: step (column) index
	#	index: key map index
	def toggleEvent(self, step, index):
		if step < 0 or step >= self.parent.libseq.getSteps() or index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		if self.parent.libseq.getNoteVelocity(step, note):
			self.removeEvent(step, index)
		else:
			self.addEvent(step, index)

	# Function to remove an event
	#	step: step (column) index
	#	index: keymap index
	def removeEvent(self, step, index):
		if index >= len(self.keymap):
			return
		note = self.keymap[index]['note']
		self.parent.libseq.removeNote(step, note)
		self.parent.libseq.playNote(note, 0) # Silence note if sounding
		self.drawRow(index)
		self.selectCell(step, index)

	# Function to add an event
	#	step: step (column) index
	#	index: keymap index
	def addEvent(self, step, index):
		note = self.keymap[index]["note"]
		self.parent.libseq.addNote(step, note, self.velocity, self.duration)
		self.drawRow(index)
		self.selectCell(step, index)

	# Function to draw a grid row
	#	index: keymap index
	def drawRow(self, index):
		row = index - self.keyMapOffset
		self.gridCanvas.itemconfig("lastnotetext%d" % (row), state="hidden")
		for step in range(self.parent.libseq.getSteps()):
			self.drawCell(step, row)

	# Function to get cell coordinates
	#   col: Column index
	#   row: Row index
	#   duration: Duration of cell in steps
	#   return: Coordinates required to draw cell
	def getCell(self, col, row, duration):
		x1 = col * self.stepWidth + 1
		y1 = (self.zoom - row - 1) * self.rowHeight + 1
		x2 = x1 + self.stepWidth * duration - 1 
		y2 = y1 + self.rowHeight - 1
		return [x1, y1, x2, y2]

	# Function to draw a grid cell
	#	step: Step (column) index
	#	row: Index of row
	def drawCell(self, step, row):
		cellIndex = row * self.parent.libseq.getSteps() + step # Cells are stored in array sequentially: 1st row, 2nd row...
		if cellIndex >= len(self.cells):
			return
		note = self.keymap[row + self.keyMapOffset]["note"]
		velocityColour = self.parent.libseq.getNoteVelocity(step, note)
		if velocityColour:
			velocityColour = 70 + velocityColour
		elif self.parent.libseq.getScale() == 1:
			# Draw tramlines for white notes in chromatic scale
			key = note % 12
			if key in (0,2,4,5,7,9,11): # White notes
#			if key in (1,3,6,8,10): # Black notes
				velocityColour += 30
		else:
			# Draw tramlines for odd rows in other scales and maps
			if (row + self.keyMapOffset) % 2:
				velocityColour += 30
		duration = self.parent.libseq.getNoteDuration(step, note)
		if not duration:
			duration = 1
		fillColour = "#%02x%02x%02x" % (velocityColour, velocityColour, velocityColour)
		cell = self.cells[cellIndex]
		coord = self.getCell(step, row, duration)
		if cell:
			# Update existing cell
			self.gridCanvas.itemconfig(cell, fill=fillColour)
			self.gridCanvas.coords(cell, coord)
		else:
			# Create new cell
			cell = self.gridCanvas.create_rectangle(coord, fill=fillColour, width=0, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step))
			self.gridCanvas.tag_bind(cell, '<ButtonPress-1>', self.onGridPress)
			self.gridCanvas.tag_bind(cell, '<ButtonRelease-1>', self.onGridRelease)
			self.gridCanvas.tag_bind(cell, '<B1-Motion>', self.onGridDrag)
			self.cells[cellIndex] = cell
		if step + duration > self.parent.libseq.getSteps():
			if duration > 1:
				self.gridCanvas.itemconfig("lastnotetext%d" % row, text="+%d" % (duration - self.parent.libseq.getSteps() + step), state="normal")

	# Function to draw grid
	#   clearGrid: True to clear grid and create all new elements, False to reuse existing elements if they exist
	def drawGrid(self, clearGrid = False):
		if self.parent.libseq.getSteps() == 0:
			return #TODO: Should we clear grid?
		if self.keyMapOffset > len(self.keymap) - self.zoom:
			self.keyMapOffset = len(self.keymap) - self.zoom
		if self.keyMapOffset < 0:
			self.keyMapOffset = 0
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		if clearGrid:
			self.gridCanvas.delete(tkinter.ALL)
			self.stepWidth = (self.gridWidth - 2) / self.parent.libseq.getSteps()
			self.drawPianoroll()
			self.cells = [None] * self.zoom * self.parent.libseq.getSteps()
		# Draw cells of grid
		self.gridCanvas.itemconfig("gridcell", fill="black")
		# Redraw gridlines
		self.gridCanvas.delete("gridline")
		if self.parent.libseq.getStepsPerBeat():
			for step in range(0, self.parent.libseq.getSteps() + 1, self.parent.libseq.getStepsPerBeat()):
				self.gridCanvas.create_line(step * self.stepWidth, 0, step * self.stepWidth, self.zoom * self.rowHeight - 1, fill=GRID_LINE, tags=("gridline"))
		# Delete existing note names
		self.pianoRoll.delete("notename")
		for row in range(0, self.zoom):
			index = row + self.keyMapOffset
			if(index >= len(self.keymap)):
				break
			self.drawRow(index)
			# Update pianoroll keys
			if clearGrid:
				# Create last note labels in grid
				self.gridCanvas.create_text(self.gridWidth - self.selectThickness, self.fontsize, state="hidden", tags=("lastnotetext%d" % (row), "lastnotetext"), font=font, anchor="e")
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
			if self.keymap[index]['note'] % 12 == self.parent.libseq.getTonic():
				self.gridCanvas.create_line(0, (self.zoom - row) * self.rowHeight, self.gridWidth, (self.zoom - row) * self.rowHeight, fill=GRID_LINE, tags=("gridline"))
		# Set z-order to allow duration to show
		if clearGrid:
			for step in range(self.parent.libseq.getSteps()):
				self.gridCanvas.tag_lower("step%d"%step)
		self.gridCanvas.tag_raise("selection")

	# Function to draw pianoroll key outlines (does not fill key colour)
	def drawPianoroll(self):
		self.pianoRoll.delete(tkinter.ALL)
		for row in range(self.zoom):
			x1 = 0
			y1 = self.getCell(0, row, 1)[1]
			x2 = self.pianoRollWidth
			y2 = y1 + self.rowHeight - 1
			id = "row%d" % (row)
			id = self.pianoRoll.create_rectangle(x1, y1, x2, y2, width=0, tags=id)

	# Function to update selectedCell
	#	step: Step (column) of selected cell (Optional - default to reselect current column)
	#	index: Index of keymap to select (Optional - default to reselect current row) Maybe outside visible range to scroll display
	def selectCell(self, step=None, index=None):
		if len(self.keymap) == 0:
			return
		redraw = False
		if step == None:
			step = self.selectedCell[0]
		if index == None:
			index = self.selectedCell[1]
		if step < 0:
			step = 0
		if step >= self.parent.libseq.getSteps():
			step = self.parent.libseq.getSteps() - 1
		if index >= len(self.keymap):
			index = len(self.keymap) - 1
		if index >= self.keyMapOffset + self.zoom:
			# Note is off top of display
			self.keyMapOffset = index - self.zoom + 1
			redraw = True
		if index < 0:
			index = 0
		if index < self.keyMapOffset:
			# Note is off bottom of display
			self.keyMapOffset = index
			redraw = True
		if redraw:
			self.drawGrid()
		row = index - self.keyMapOffset
		note = self.keymap[index]['note']
		# Skip hidden (overlapping) cells
		for previous in range(step - 1, -1, -1):
			prevDuration = self.parent.libseq.getNoteDuration(previous, note)
			if not prevDuration:
				continue
			if prevDuration > step - previous:
				if step > self.selectedCell[0]:
					step = previous + prevDuration
				else:
					step = previous
				break
		if step < 0:
			step = 0;
		if step >= self.parent.libseq.getSteps():
			step = self.parent.libseq.getSteps() - 1
		self.selectedCell = [step, index]
		cell = self.gridCanvas.find_withtag("selection")
		duration = self.parent.libseq.getNoteDuration(step, row)
		if not duration:
			duration = self.duration
		coord = self.getCell(step, row, duration)
		coord[0] = coord[0] - 1
		coord[1] = coord[1] - 1
		coord[2] = coord[2]
		coord[3] = coord[3]
		if not cell:
			cell = self.gridCanvas.create_rectangle(coord, fill="", outline=SELECT_BORDER, width=self.selectThickness, tags="selection")
		else:
			self.gridCanvas.coords(cell, coord)
		self.gridCanvas.tag_raise(cell)

	# Function to calculate row height
	def updateRowHeight(self):
		self.rowHeight = (self.gridHeight - 2) / self.zoom
		self.fontsize = int(self.rowHeight * 0.5)
		if self.fontsize > 20:
			self.fontsize = 20 # Ugly font scale limiting

	# Function to clear a pattern
	def clearPattern(self):
		self.parent.libseq.clear()
		self.drawGrid(True)
		self.selectCell()
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()

	# Function to copy pattern
	def copyPattern(self):
		self.parent.libseq.copyPattern(self.copySource, self.pattern);
		self.loadPattern(self.pattern)

	# Function to get pattern index
	def getPattern(self):
		return self.pattern

	# Function to get pattern index
	def getInputChannel(self):
		channel = self.parent.libseq.getInputChannel() + 1
		if channel > 16:
			channel = 0
		return channel

	# Function to get copy source
	def getCopySource(self):
		return self.copySource

	# Function to get vertical zoom
	def getVerticalZoom(self):
		return self.zoom

	# Function to assert steps in pattern
	def assertSteps(self):
		self.parent.libseq.setSteps(self.parent.getParam('Steps in pattern', 'value'))
		self.drawGrid(True)
		self.selectCell()

	# Function to handle menu editor change
	#   params: Menu item's parameters
	#   returns: String to populate menu editor label
	#   note: params is a dictionary with required fields: min, max, value
	def onMenuChange(self, params):
		menuItem = self.parent.paramEditorItem
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		params['value'] = value
		if menuItem == 'Pattern':
			self.pattern = value
			self.copySource = value
			self.loadPattern(value)
		elif menuItem == 'Input channel':
			if value == 0:
				self.parent.libseq.setInputChannel(0xFF)
				return 'Input channel: None'
			self.parent.libseq.setInputChannel(value - 1)
		elif menuItem == 'Clear pattern':
			return "Clear pattern %d?" % (self.pattern)
		elif menuItem =='Copy pattern':
			self.loadPattern(value)
			return "Copy %d=>%d?" % (self.copySource, value)
		elif menuItem == 'Transpose pattern':
			if self.parent.libseq.getScale() == 0:
				self.parent.hideParamEditor()
				return
			if self.parent.libseq.getScale() > 1:
				# Only allow transpose when showing chromatic scale
				self.parent.libseq.setScale(1)
				self.loadKeymap()
				self.drawGrid()
			if (value != 0 and self.parent.libseq.getScale()):
				self.parent.libseq.transpose(value)
				self.parent.setParam(menuItem, 'value', 0)
				self.keyMapOffset = self.keyMapOffset + value
				if self.keyMapOffset > 128 - self.zoom:
					self.keyMapOffset = 128 - self.zoom
				elif self.keyMapOffset < 0:
					self.keyMapOffset = 0
				else:
					self.selectedCell[1] = self.selectedCell[1] + value
				self.drawGrid()
				self.selectCell()
			return "Transpose +/-"
		elif menuItem == 'Vertical zoom':
			self.zoom = value
		elif menuItem == 'Clocks per step':
			self.parent.libseq.setClocksPerStep(value);
		elif menuItem == 'Steps per beat':
			stepsPerBeat = STEPS_PER_BEAT[value]
			if stepsPerBeat:
				clocksPerStep = int(24 / stepsPerBeat)
				self.parent.libseq.setClocksPerStep(clocksPerStep)
			else:
				clocksPerStep = 0
				self.parent.libseq.setClocksPerStep(24)
			self.parent.libseq.setStepsPerBeat(stepsPerBeat)
			self.drawGrid()
			self.selectCell()
			value = stepsPerBeat
		elif menuItem == 'Tempo':
			self.parent.zyngui.zyntransport.set_tempo(value)
		elif menuItem == 'Scale':
			self.parent.libseq.setScale(value)
			name = self.loadKeymap()
			return "Keymap: %s" % (name)
		elif menuItem == 'Tonic':
			if value < 0:
				value = 11
			if value > 11:
				value = 0
			self.parent.setParam('Tonic', 'value', value)
			offset = value - self.parent.libseq.getTonic()
			self.parent.libseq.setTonic(value)
			if self.parent.getParam('Scale', 'value'):
				for key in self.keymap:
					note = key['note'] + offset
					key['note'] = note
					key['name'] = "%s%d" % (self.notes[note % 12], note // 12)
			self.drawGrid()
			return "Tonic: %s" % (self.notes[value])
		return "%s: %d" % (menuItem, value)

	# Function to load new pattern
	#   index: Pattern index
	def loadPattern(self, index):
		self.sequence = self.parent.libseq.getSequence(self.song, 0)
		self.parent.libseq.clearSequence(self.sequence)
		self.pattern = index
		self.parent.libseq.selectPattern(index)
		self.parent.libseq.addPattern(self.sequence, 0, index)
		if self.selectedCell[0] >= self.parent.libseq.getSteps():
			self.selectedCell[0] = self.parent.libseq.getSteps() - 1
		self.loadKeymap()
		self.drawGrid(True)
		self.selectCell()
		self.playCanvas.coords("playCursor", 1, 0, 1 + self.stepWidth, PLAYHEAD_HEIGHT)
		self.parent.setTitle("Pattern Editor (%d)" % (self.pattern))

	# Function called when new file loaded from disk
	def onLoad(self):
		self.loadPattern(self.pattern)
		#TODO: Should we select pattern 1?

	# Function to refresh display
	def refresh_status(self):
		step = self.parent.libseq.getStep(self.sequence)
		if self.playhead != step:
			self.playhead = step
			if self.shown:
				# Draw play head cursor
				self.playCanvas.coords("playCursor", 1 + self.playhead * self.stepWidth, 0, 1 + self.playhead * 	self.stepWidth + self.stepWidth, PLAYHEAD_HEIGHT)
		if self.parent.libseq.isModified():
			self.drawGrid();

	# Function to handle zyncoder value change
	#   encoder: Zyncoder index [0..4]
	#   value: Current value of zyncoder
	def onZyncoder(self, encoder, value):
		if encoder == ENC_BACK:
			# BACK encoder adjusts note selection
			self.selectCell(None, self.selectedCell[1] - value)
		elif encoder == ENC_SELECT:
			pass
			# SELECT encoder adjusts step selection
			self.selectCell(self.selectedCell[0] + value, None)
		elif encoder == ENC_SNAPSHOT:
			# SNAPSHOT encoder adjusts velocity
			self.velocity = self.velocity + value
			if self.velocity > 127:
				self.velocity = 127
				return
			if self.velocity < 1:
				self.velocity = 1
				return
			self.velocityCanvas.coords("velocityIndicator", 0, 0, self.pianoRollWidth * self.velocity / 127, PLAYHEAD_HEIGHT)
			note = self.keymap[self.selectedCell[1]]["note"]
			if self.parent.libseq.getNoteDuration(self.selectedCell[0], note):
				self.parent.libseq.setNoteVelocity(self.selectedCell[0], note, self.velocity)
				self.drawCell(self.selectedCell[0], self.selectedCell[1])
		elif encoder == ENC_LAYER:
			# LAYER encoder adjusts duration
			if value > 0:
				self.duration = self.duration + 1
			if value < 0:
				self.duration = self.duration - 1
			if self.duration > self.parent.libseq.getSteps():
				self.duration = self.parent.libseq.getSteps()
				return
			if self.duration < 1:
				self.duration = 1
				return
			if self.parent.libseq.getNoteDuration(self.selectedCell[0], self.selectedCell[1]):
				self.addEvent(self.selectedCell[0], self.selectedCell[1])
			else:
				self.selectCell()

	# Function to handle switch press
	#   switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#   type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#   returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
		elif switch == ENC_SELECT:
			self.toggleEvent(self.selectedCell[0], self.selectedCell[1])
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------