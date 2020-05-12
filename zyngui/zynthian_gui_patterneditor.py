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
import threading
from time import sleep
import ctypes
from os.path import dirname, realpath

# Zynthian specific modules
from . import zynthian_gui_config
from zyncoder import *

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Pattern Editor GUI Class
#------------------------------------------------------------------------------

# Local constants
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
CELL_BACKGROUND		= zynthian_gui_config.color_panel_bd
CELL_FOREGROUND		= zynthian_gui_config.color_panel_tx
GRID_LINE			= zynthian_gui_config.color_tx
PLAYHEAD_HEIGHT		= 5
# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select
ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3

# List of permissible steps per beat
STEPS_PER_BEAT = [0,1,2,3,4,6,8,12,24]

# Class implements step sequencer pattern editor
class zynthian_gui_patterneditor():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		parent.setTitle("Pattern Editor")
		# Add menus
		self.parent.addMenu({'Pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':1, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Steps per beat':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':len(STEPS_PER_BEAT), 'value':4, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Steps in pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':64, 'value':16, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Copy pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':1, 'onChange':self.onMenuChange,'onAssert':self.copyPattern}}})
		self.parent.addMenu({'Clear pattern':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':1, 'value':0, 'onChange':self.onMenuChange, 'onAssert':self.clearPattern}}})
		self.parent.addMenu({'Transpose pattern':{'method':self.parent.showParamEditor, 'params':{'min':-1, 'max':1, 'value':0, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Tempo':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':999, 'value':120, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Vertical zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':127, 'value':16, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'MIDI channel':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'value':1, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Clocks per step':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':24, 'value':6, 'onChange':self.onMenuChange}}})

		self.zoom = 16 # Quantity of rows (notes) displayed in grid
		self.duration = 1 # Current note entry duration
		self.velocity = 100 # Current note entry velocity
		self.copySource = 1 # Index of pattern to copy
		self.sequence = 0 # Use sequence zero fo pattern editor sequence player
		self.pattern = 1 # Index of current pattern

		self.stepWidth = 40 # Grid column width in pixels
		self.keyOrigin = 60 # MIDI note number of bottom row in grid
		self.selectedCell = [0, self.keyOrigin] # Location of selected cell (step,note)
		#TODO: Get values from persistent storage
		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

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
		self.pianoRoll.bind("<ButtonPress-1>", self.onPianoRollDragStart)
		self.pianoRoll.bind("<ButtonRelease-1>", self.onPianoRollDragEnd)
		self.pianoRoll.bind("<B1-Motion>", self.onPianoRollDragMotion)

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

		self.loadPattern(1)

		self.startPlayheadHandler()

		# Select a cell
		self.selectCell(0, self.keyOrigin + int(self.zoom / 2))

	# Function to draw play cursor - periodically checks for change in current step then redraws cursor if necessary
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
	#	note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		self.parent.registerZyncoder(ENC_BACK, self)
		self.parent.registerZyncoder(ENC_SELECT, self)
		self.parent.registerZyncoder(ENC_SNAPSHOT, self)
		self.parent.registerZyncoder(ENC_LAYER, self)

	# Function to show GUI
	def show(self):
		self.setupEncoders()
		self.main_frame.tkraise()
		self.shown=True

	# Function to hide GUI
	def hide(self):
		self.shown=False
		self.parent.unregisterZyncoder(ENC_BACK)
		self.parent.unregisterZyncoder(ENC_SELECT)
		self.parent.unregisterZyncoder(ENC_SNAPSHOT)
		self.parent.unregisterZyncoder(ENC_LAYER)
		self.savePatterns() #TODO: Find better time to save patterns

	# Function to handle start of pianoroll drag
	def onPianoRollDragStart(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		self.pianoRollDragStart = event
		keyboardPlayNote =  self.keyOrigin + self.zoom - int(event.y / self.rowHeight) - 1
		self.parent.libseq.playNote(keyboardPlayNote, 100, self.parent.libseq.getChannel(0), 200)

	# Function to handle pianoroll drag motion
	def onPianoRollDragMotion(self, event):
		if not self.pianoRollDragStart:
			return
		if event.y > self.pianoRollDragStart.y + self.rowHeight and self.keyOrigin < 128 - self.zoom:
			self.keyOrigin = self.keyOrigin + 1
			self.pianoRollDragStart.y = event.y
			self.drawGrid()
		elif event.y < self.pianoRollDragStart.y - self.rowHeight and self.keyOrigin > 0:
			self.keyOrigin = self.keyOrigin - 1
			self.pianoRollDragStart.y = event.y
			self.drawGrid()
		if self.selectedCell[1] < self.keyOrigin:
			self.selectedCell[1] = self.keyOrigin
		elif self.selectedCell[1] >= self.keyOrigin + self.zoom:
			self.selectedCell[1] = self.keyOrigin + self.zoom - 1
		self.selectCell(self.selectedCell[0], self.selectedCell[1])

	# Function to handle end of pianoroll drag
	def onPianoRollDragEnd(self, event):
		self.pianoRollDragStart = None

	# Function to handle mouse click / touch
	#	event: Mouse event
	def onCanvasClick(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		closest = event.widget.find_closest(event.x, event.y)
		tags = self.gridCanvas.gettags(closest)
		step, note = tags[0].split(',')
		self.toggleEvent(int(step), self.keyOrigin + int(note))

	# Function to toggle note event
	#	step: step (column) index
	#	note: Note number
	def toggleEvent(self, step, note):
		if step < 0 or step >= self.parent.libseq.getSteps():
			return
		if self.parent.libseq.getNoteVelocity(step, note):
			self.removeEvent(step, note)
		else:
			self.addEvent(step, note)
			self.parent.libseq.playNote(note, 100, self.parent.libseq.getChannel(self.sequence), 100) # Play note when added

	# Function to remove an event
	#	step: step (column) index
	#	note: MIDI note number
	def removeEvent(self, step, note):
		self.parent.libseq.removeNote(step, note)
		self.parent.libseq.playNote(note, 0) # Silence note if sounding
		self.drawRow(note)
		self.selectCell(step, note)

	# Function to add an event
	#	step: step (column) index
	#	note: Note number
	def addEvent(self, step, note):
		self.parent.libseq.addNote(step, note, self.velocity, self.duration)
		self.drawRow(note)
		self.selectCell(step, note)

	# Function to draw a grid row
	#	note: MIDI note for the row to draw
	def drawRow(self, note):
		self.gridCanvas.itemconfig("lastnotetext%d" % (note - self.keyOrigin), state="hidden")
		for step in range(self.parent.libseq.getSteps()):
			self.drawCell(step, note)

	# Function to get cell coordinates
	#	col: Column index
	#	row: Row index
	#	duration: Duration of cell in steps
	#	return: Coordinates required to draw cell
	def getCell(self, col, row, duration):
		x1 = col * self.stepWidth + 1
		y1 = (self.zoom - row - 1) * self.rowHeight + 1
		x2 = x1 + self.stepWidth * duration - 1 
		y2 = y1 + self.rowHeight - 1
		return [x1, y1, x2, y2]

	# Function to draw a grid cell
	#	step: Step (column) index
	#	note: Note number
	def drawCell(self, step, note):
		if step < 0 or step >= self.parent.libseq.getSteps() or note < self.keyOrigin or note >= self.keyOrigin + self.zoom:
			return
		row = note - self.keyOrigin
		velocityColour = self.parent.libseq.getNoteVelocity(step, note)
		if velocityColour:
			velocityColour = 70 + velocityColour
		else:
			key = note % 12
			if key in (0,2,4,5,7,9,11): # White notes
#			if key in (1,3,6,8,10): # Black notes
				velocityColour += 30
		duration = self.parent.libseq.getNoteDuration(step, note)
		if not duration:
			duration = 1
		fillColour = "#%02x%02x%02x" % (velocityColour, velocityColour, velocityColour)
		cell = self.gridCanvas.find_withtag("%d,%d"%(step,row))
		coord = self.getCell(step, row, duration)
		if cell:
			# Update existing cell
			self.gridCanvas.itemconfig(cell, fill=fillColour)
			self.gridCanvas.coords(cell, coord)
		else:
			# Create new cell
			cell = self.gridCanvas.create_rectangle(coord, fill=fillColour, width=0, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step))
			self.gridCanvas.tag_bind(cell, '<Button-1>', self.onCanvasClick)
		if step + duration > self.parent.libseq.getSteps():
			if duration > 1:
				self.gridCanvas.itemconfig("lastnotetext%d" % row, text="+%d" % (duration - self.parent.libseq.getSteps() + step), state="normal")

	# Function to draw grid
	#	clearGrid: True to clear grid and create all new elements, False to reuse existing elements if they exist
	def drawGrid(self, clearGrid = False):
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.rowHeight * 0.5))
		if clearGrid:
			self.gridCanvas.delete(tkinter.ALL)
			self.stepWidth = (self.gridWidth - 2) / self.parent.libseq.getSteps()
			self.drawPianoroll()
		# Draw cells of grid
		self.gridCanvas.itemconfig("gridcell", fill="black")
		# Delete existing note names
		self.pianoRoll.delete("notename")
		for note in range(self.keyOrigin, self.keyOrigin + self.zoom):
			# Update pianoroll keys
			key = note % 12
			row = note - self.keyOrigin
			self.drawRow(note)
			if clearGrid:
				# Create last note labels in grid
				self.gridCanvas.create_text(self.gridWidth - self.selectThickness, self.rowHeight * (self.zoom - row - 0.5), state="hidden", tags=("lastnotetext%d" % (row), "lastnotetext"), font=font, anchor="e")
			id = "row%d" % (row)
			if key in (0,2,4,5,7,9,11):
				self.pianoRoll.itemconfig(id, fill="white")
				if key == 0:
					self.pianoRoll.create_text((self.pianoRollWidth / 2, self.rowHeight * (self.zoom - row - 0.5)), text="C%d (%d)" % ((self.keyOrigin + row) // 12 - 1, self.keyOrigin + row), font=font, fill=CANVAS_BACKGROUND, tags="notename")
			else:
				self.pianoRoll.itemconfig(id, fill="black")
		# Redraw gridlines
		self.gridCanvas.delete("gridline")
		if self.parent.libseq.getStepsPerBeat():
			for step in range(0, self.parent.libseq.getSteps() + 1, self.parent.libseq.getStepsPerBeat()):
				self.gridCanvas.create_line(step * self.stepWidth, 0, step * self.stepWidth, self.zoom * self.rowHeight - 1, fill=GRID_LINE, tags=("gridline"))
		# Set z-order to allow duration to show
		if clearGrid:
			for step in range(self.parent.libseq.getSteps()):
				self.gridCanvas.tag_lower("step%d"%step)

	# Function to draw pianoroll keys (does not fill key colour)
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
	#	step: Step (column) of selected cell
	#	note: Note number of selected cell
	def selectCell(self, step, note):
		if step < 0 or step > self.parent.libseq.getSteps():
			return
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
		self.selectedCell = [step, note]
		if note >= self.keyOrigin + self.zoom:
			# Note is off top of display
			if note < 128:
				self.keyOrigin = note + 1 - self.zoom
			else:
				self.keyOrigin = 128 - self.zoom
			self.drawGrid()
		elif note < self.keyOrigin:
			self.keyOrigin = note
			self.drawGrid()
		else:
			cell = self.gridCanvas.find_withtag("selection")
			row = note - self.keyOrigin
			duration = self.parent.libseq.getNoteDuration(step, note)
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

	# Function to save patterns to RIFF file
	def savePatterns(self):
		filename=os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/sequences/patterns.zynseq"
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		self.parent.libseq.save(bytes(filename, "utf-8"));

	# Function to calculate row height
	def updateRowHeight(self):
		self.rowHeight = (self.gridHeight - 2) / self.zoom

	# Function to clear a pattern
	def clearPattern(self):
		self.parent.libseq.clear()
		self.drawGrid(True)
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()

	# Function to copy pattern
	def copyPattern(self):
		self.parent.libseq.copyPattern(self.copySource, self.pattern);
		self.loadPattern(self.pattern)

	# Function to handle menu editor change
	#	value: Menu item's value
	#	returns: String to populate menu editor label
	def onMenuChange(self, value):
		#TODO: Implement acccess to paramEditor
		menuItem = self.parent.paramEditor['menuitem']
		if value < self.parent.paramEditor['min']:
			value = self.parent.paramEditor['min']
		if value > self.parent.paramEditor['max']:
			value = self.parent.paramEditor['max']
		self.parent.paramEditor['value'] = value
		if menuItem == 'Pattern':
			self.pattern = value
			self.copySource = value
			self.parent.setParam('Copy pattern', 'value', value)
			self.loadPattern(value)
		elif menuItem == 'Clear pattern':
			return "Clear pattern %d?" % (self.pattern)
		elif menuItem =='Copy pattern':
			self.loadPattern(value)
			return "Copy %d=>%d?" % (self.copySource, value)
		elif menuItem == 'Steps in pattern':
			self.parent.libseq.setSteps(value)
			self.parent.setParam(menuItem, 'value', self.parent.libseq.getSteps())
			self.drawGrid(True)
			self.selectCell(self.selectedCell[0], self.selectedCell[1])
		elif menuItem == 'MIDI channel':
			self.parent.libseq.setChannel(self.sequence, value - 1);
			self.parent.setParam(menuItem, 'value', self.parent.libseq.getChannel(self.sequence))
		elif menuItem == 'Transpose pattern':
			if(value != 0):
				self.parent.libseq.transpose(value)
				self.parent.paramEditor['value'] = 0
				if zyncoder.lib_zyncoder:
					zyncoder.lib_zyncoder.zynmidi_send_all_notes_off() #TODO: Use libseq - also, just send appropriate note off
			self.drawGrid()
			return "Transpose pattern +/-"
		elif menuItem == 'Vertical zoom':
			self.zoom = value
			self.updateRowHeight()
			self.drawGrid(True)
			self.parent.setParam(menuItem, 'value', value)
		elif menuItem == 'Tempo':
			self.parent.libseq.setTempo(value)
			self.parent.setParam(menuItem, 'value', value)
		elif menuItem == 'Clocks per step':
			self.parent.libseq.setClockDivisor(value);
			self.parent.setParam(menuItem, 'value', value)
			return 'Clocks per step %d (%.2f BPM)' % (value, self.parent.libseq.getTempo() * 24 / (value * self.parent.libseq.getStepsPerBeat()))
		elif menuItem == 'Steps per beat':
			stepsPerBeat = STEPS_PER_BEAT[value]
			if stepsPerBeat:
				clocksPerStep = int(24 / stepsPerBeat)
				self.parent.libseq.setClockDivisor(clocksPerStep)
			else:
				clocksPerStep = 0
				self.parent.libseq.setClockDivisor(24)
			self.parent.libseq.setStepsPerBeat(stepsPerBeat)
			self.parent.setParam('Clocks per step', 'value', clocksPerStep)
			self.drawGrid()
			self.parent.setParam(menuItem, 'value', value)
			value = stepsPerBeat
		return "%s: %d" % (menuItem, value)

	# Function to load new pattern
	#	index: Pattern index
	def loadPattern(self, index):
		self.parent.libseq.clearSequence(self.sequence)
		self.pattern = index
		self.parent.libseq.selectPattern(index)
		self.parent.libseq.addPattern(self.sequence, 0, index)
		if self.selectedCell[0] >= self.parent.libseq.getSteps():
			self.selectedCell[0] = self.parent.libseq.getSteps() - 1
		self.drawGrid(True)
		self.playCanvas.coords("playCursor", 1, 0, 1 + self.stepWidth, PLAYHEAD_HEIGHT)
		self.parent.setParam('Steps in pattern', 'value', self.parent.libseq.getSteps())
		self.parent.setParam('Pattern', 'value', index)
		self.parent.setParam('Tempo', 'value', self.parent.libseq.getTempo())
		self.parent.setParam('Step per beat', 'value', self.parent.libseq.getStepsPerBeat())
		self.parent.setParam('Clocks per step', 'value', self.parent.libseq.getClockDivisor())
		self.parent.setTitle("Pattern Editor (%d)" % (self.pattern))

	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def onZyncoder(self, encoder, value):
		if encoder == ENC_BACK:
			# BACK encoder adjusts note selection
			note = self.selectedCell[1] - value
			self.selectCell(self.selectedCell[0], note)
		elif encoder == ENC_SELECT:
			# SELECT encoder adjusts step selection
			step = self.selectedCell[0] + value
			self.selectCell(step, self.selectedCell[1])
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
			if self.parent.libseq.getNoteDuration(self.selectedCell[0], self.selectedCell[1]):
				self.parent.libseq.setNoteVelocity(self.selectedCell[0], self.selectedCell[1], self.velocity)
				self.drawCell(self.selectedCell[0], self.selectedCell[1])
		elif encoder == ENC_LAYER:
			# LAYER encoder adjusts duration
			self.duration = self.duration + value
			if self.duration > 16:
				self.duration = 16
				return
			if self.duration < 1:
				self.duration = 1
				return
			if self.parent.libseq.getNoteDuration(self.selectedCell[0], self.selectedCell[1]):
				self.addEvent(self.selectedCell[0], self.selectedCell[1])
			else:
				self.selectCell(self.selectedCell[0], self.selectedCell[1])

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
		if switch == ENC_SNAPSHOT:
			if self.parent.libseq.getPlayMode(self.sequence):
				self.parent.libseq.setPlayMode(self.sequence, 0) #STOP
			else:
				self.parent.libseq.setPlayMode(self.sequence, 2) #LOOP
		elif switch == ENC_SELECT:
			self.toggleEvent(self.selectedCell[0], self.selectedCell[1])
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
