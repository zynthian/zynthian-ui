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
DEFAULT_BPM			= 120
DEFAULT_CLK_DIV		= 6
MAX_STEPS			= 64
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
HEADER_BACKGROUND	= zynthian_gui_config.color_header_bg
GRID_LINE			= zynthian_gui_config.color_tx
PLAYHEAD_HEIGHT		= 5
# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select
ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3
ENC_NOTE			= ENC_SNAPSHOT
ENC_STEP			= ENC_SELECT
ENC_VEL				= ENC_LAYER
ENC_DUR				= ENC_BACK
ENC_MENU			= ENC_LAYER


# List of permissible steps per beat (0 indicates custom)
STEPS_PER_BEAT = [0,1,2,3,4,6,8,12,24]

# Class implements step sequencer
class zynthian_gui_patterneditor():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		parent.setTitle("Pattern Editor")
		self.parent.addMenu({'Pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':1, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Steps per beat':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':len(STEPS_PER_BEAT), 'value':4, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Steps in pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':64, 'value':16, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Copy pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':1, 'onChange':self.onMenuChange,'onAssert':self.copyPattern}}})
		self.parent.addMenu({'Clear pattern':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':1, 'value':0, 'onChange':self.onMenuChange, 'onAssert':self.clearPattern}}})
		self.parent.addMenu({'Transpose pattern':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':2, 'value':1, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Tempo':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':999, 'value':120, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Vertical zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':127, 'value':16, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'MIDI channel':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'value':1, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Clocks per step':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':24, 'value':6, 'onChange':self.onMenuChange}}})

		self.zoom = 16 # Quantity of rows (notes) displayed in grid
		self.duration = 1 # Current note entry duration
		self.velocity = 100 # Current note entry velocity
		self.clearIndex = 0 # Index of pattern to clear
		self.copySource = 1 # Index of pattern to copy to
		self.sequence = 0 # Use sequence zero fo pattern editor sequence player
		self.pattern = 1 # Index of current pattern

		# Load sequencer library
		self.libseq = ctypes.CDLL(dirname(realpath(__file__))+"/../zynseq/build/libzynseq.so")
		self.libseq.init()
		self.stepWidth = 40 # Grid column width in pixels (default 40)
		self.keyOrigin = 60 # MIDI note number of top row in grid
		self.selectedCell = [0, self.keyOrigin] # Location of selected cell (step,note)
		#TODO: Get values from persistent storage
		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height
		self.selectThickness = 1 + int(self.width / 500)
		self.gridHeight = self.height - PLAYHEAD_HEIGHT
		self.gridWidth = int(self.width * 0.9)
		self.pianoRollWidth = self.width - self.gridWidth
		self.updateRowHeight()

		# Main Frame
		self.main_frame = self.parent.child_frame

		# Load pattern from file
		self.libseq.load(bytes(os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/sequences/patterns.zynseq", "utf-8"))
		# Draw pattern grid
		self.gridCanvas = tkinter.Canvas(self.main_frame, 
			width=self.gridWidth, 
			height=self.gridHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.gridCanvas.grid(row=0, column=1)
		# Draw pianoroll
		self.pianoRoll = tkinter.Canvas(self.main_frame,
			width=self.pianoRollWidth,
			height=self.zoom * self.rowHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.pianoRoll.grid(row=0, column=0)
		self.pianoRoll.bind("<ButtonPress-1>", self.onPianoRollDragStart)
		self.pianoRoll.bind("<ButtonRelease-1>", self.onPianoRollDragEnd)
		self.pianoRoll.bind("<B1-Motion>", self.onPianoRollDragMotion)
		# Draw playhead canvas
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
		self.playCanvas.grid(row=2, column=1)

		self.loadPattern(1)

		self.startPlayheadHandler()

		# Select a cell
		self.selectCell(0, self.keyOrigin + int(self.zoom / 2))

	# Function to draw play cursor - periodically checks for change in current step then redraws cursor if necessary
	def startPlayheadHandler(self):
		def onStep():
			playhead = 0
			while(not self.zyngui.exit_flag):
				step = self.libseq.getStep(self.sequence)
				if playhead != step:
					playhead = step
					if self.shown:
						# Draw play head cursor
						self.playCanvas.coords("playCursor", 1 + playhead * self.stepWidth, 0, 1 + playhead * self.stepWidth + self.stepWidth, PLAYHEAD_HEIGHT)
				sleep(0.1) #TODO It would be great if this could be event driven rather than poll every 100ms
		thread = threading.Thread(target=onStep, daemon=True)
		thread.start()

	# Function to print traceback
	#	TODO: Remove debug function (or move to other zynthian class)
	def debugTraceback(self):
		for trace in inspect.stack():
			print(trace.function)

	# Function to show GUI
	def show(self):
		if not self.shown:
			self.setupEncoders()
			self.shown=True
			self.main_frame.grid()

	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		print("setupEncoders")
		if zyncoder.lib_zyncoder:
			pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_NOTE]
			pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_NOTE]
			zyncoder.lib_zyncoder.setup_zyncoder(ENC_NOTE,pin_a,pin_b,0,0,None,self.selectedCell[1],127,0)
			pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_STEP]
			pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_STEP]
			zyncoder.lib_zyncoder.setup_zyncoder(ENC_STEP,pin_a,pin_b,0,0,None,self.selectedCell[0],self.libseq.getSteps() - 1,0)
			pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_VEL]
			pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_VEL]
			zyncoder.lib_zyncoder.setup_zyncoder(ENC_VEL,pin_a,pin_b,0,0,None,self.velocity,127,0)
			pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_DUR]
			pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_DUR]
			zyncoder.lib_zyncoder.setup_zyncoder(ENC_DUR,pin_a,pin_b,0,0,None,self.duration-1,16,0)

	# Function to hide GUI
	def hide(self):
		if self.shown:
			self.shown=False
			self.main_frame.grid_forget()
			self.savePatterns() #TODO: Find better time to save patterns

	# Function to handle start of pianoroll drag
	def onPianoRollDragStart(self, event):
		self.pianoRollDragStart = event

	# Function to handle pianoroll drag motion
	def onPianoRollDragMotion(self, event):
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
		closest = event.widget.find_closest(event.x, event.y)
		tags = self.gridCanvas.gettags(closest)
		step, note = tags[0].split(',')
		self.toggleEvent(int(step), self.keyOrigin + int(note))

	# Function to toggle note event
	#	step: step (column) index
	#	note: Note number
	def toggleEvent(self, step, note):
		if step < 0 or step >= self.libseq.getSteps():
			return
		if self.libseq.getNoteVelocity(step, note):
			self.removeEvent(step, note)
		else:
			self.addEvent(step, note)
			self.libseq.playNote(note, 100, self.libseq.getChannel(self.sequence), 100) # Play note when added

	# Function to remove an event
	#	step: step (column) index
	#	note: MIDI note number
	def removeEvent(self, step, note):
		self.libseq.removeNote(step, note)
		self.libseq.playNote(note, 0) # Silence note if sounding
		self.drawRow(note)
		self.selectCell(step, note)

	# Function to add an event
	#	step: step (column) index
	#	note: Note number
	def addEvent(self, step, note):
		self.libseq.addNote(step, note, self.velocity, self.duration)
		self.drawRow(note)
		self.selectCell(step, note)

	# Function to draw a grid row
	#	note: MIDI note for the row to draw
	def drawRow(self, note):
		self.gridCanvas.itemconfig("lastnotetext%d" % (note - self.keyOrigin), state="hidden")
		for step in range(self.libseq.getSteps()):
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
		if step < 0 or step >= self.libseq.getSteps() or note < self.keyOrigin or note >= self.keyOrigin + self.zoom:
			return
		row = note - self.keyOrigin
		velocityColour = self.libseq.getNoteVelocity(step, note)
		if velocityColour:
			velocityColour = 70 + velocityColour
		duration = self.libseq.getNoteDuration(step, note)
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
		if step + duration > self.libseq.getSteps():
			if duration > 1:
				self.gridCanvas.itemconfig("lastnotetext%d" % row, text="+%d" % (duration - self.libseq.getSteps() + step), state="normal")

	# Function to draw grid
	#	clearGrid: True to clear grid and create all new elements, False to reuse existing elements if they exist
	def drawGrid(self, clearGrid = False):
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(self.rowHeight * 0.5))
		if clearGrid:
			self.gridCanvas.delete(tkinter.ALL)
			self.stepWidth = (self.gridWidth - 2) / self.libseq.getSteps()
			self.drawPianoroll()
		# Draw cells of grid
		self.gridCanvas.itemconfig("gridcell", fill="black")
		for note in range(self.keyOrigin, self.keyOrigin + self.zoom):
			self.drawRow(note)
		# Delete existing note names
		self.pianoRoll.delete("notename")
		for note in range(self.keyOrigin, self.keyOrigin + self.zoom):
			# Update pianoroll keys
			key = note % 12
			row = note - self.keyOrigin
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
		if self.libseq.getStepsPerBeat():
			for step in range(0, self.libseq.getSteps() + 1, self.libseq.getStepsPerBeat()):
				self.gridCanvas.create_line(step * self.stepWidth + 1, 0, step * self.stepWidth + 1, self.zoom * self.rowHeight - 1, fill=GRID_LINE, tags=("gridline"))
		# Set z-order to allow duration to show
		if clearGrid:
			for step in range(self.libseq.getSteps()):
				self.gridCanvas.tag_lower("step%d"%step)

	# Function to draw pianoroll keys (does not fill key colour)
	def drawPianoroll(self):
		self.pianoRoll.delete(tkinter.ALL)
		for row in range(self.zoom):
			x1 = 0
			y1 = self.getCell(0, row, 1)[1] - 1
			x2 = self.pianoRollWidth
			y2 = y1 + self.rowHeight - 1
			id = "row%d" % (row)
			id = self.pianoRoll.create_rectangle(x1, y1, x2, y2, width=0, tags=id)

	# Function to update selectedCell
	#	step: Step (column) of selected cell
	#	note: Note number of selected cell
	def selectCell(self, step, note):
		# Skip hidden (overlapping) cells
		for previous in range(step - 1, -1, -1):
			prevDuration = self.libseq.getNoteDuration(previous, note)
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
		if step >= self.libseq.getSteps():
			step = self.libseq.getSteps() - 1
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
			duration = self.libseq.getNoteDuration(step, note)
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
			if zyncoder.lib_zyncoder:
				zyncoder.lib_zyncoder.set_value_zyncoder(ENC_NOTE, note)
				zyncoder.lib_zyncoder.set_value_zyncoder(ENC_STEP, step)

	# Function to save patterns to RIFF file
	def savePatterns(self):
		filename=os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/sequences/patterns.zynseq"
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		self.libseq.save(bytes(filename, "utf-8"));

	# Function to calculate row height
	def updateRowHeight(self):
		self.rowHeight = (self.gridHeight - 2) / self.zoom

	# Function to clear a pattern
	def clearPattern(self):
		self.libseq.clear()
		self.drawGrid(True)
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()

	# Function to copy pattern
	def copyPattern(self):
		self.libseq.copyPattern(self.copySource, self.pattern);
		self.loadPattern(self.pattern)

	# Function to handle menu editor change
	#	value: Menu item's value
	#	returns: String to populate menu editor label
	def onMenuChange(self, value):
#		self.parent.zyncoderMutex = True
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
#			self.parent.zyncoderMutex = False
			return "Clear pattern %d?" % (self.pattern)
		elif menuItem =='Copy pattern':
			self.loadPattern(value)
#			self.parent.zyncoderMutex = False
			return "Copy %d=>%d?" % (self.copySource, value)
		elif menuItem == 'Pattern':
			self.copySource = value
			self.clearIndex
			self.loadPattern(value)
		elif menuItem == 'Steps in pattern':
			self.libseq.setSteps(value)
			self.drawGrid(True)
			self.selectCell(self.selectedCell[0], self.selectedCell[1])
		elif menuItem == 'MIDI channel':
			self.libseq.setChannel(self.sequence, value - 1);
		elif menuItem == 'Transpose pattern':
			# zyncoders only support positive integers so must use offset
			if(value != 1):
				self.libseq.transpose(value - 1)
				self.parent.paramEditor['value'] = 1
				if zyncoder.lib_zyncoder:
					zyncoder.lib_zyncoder.set_value_zyncoder(ENC_MENU, 1)
					zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()
			self.drawGrid()
#			self.parent.zyncoderMutex = False
			return "Transpose pattern +/-"
		elif menuItem == 'Vertical zoom':
			self.zoom = value
			self.updateRowHeight()
			self.drawGrid(True)
		elif menuItem == 'Tempo':
			self.libseq.setTempo(value)
		elif menuItem == 'Clocks per step':
			self.libseq.setClockDivisor(value);
#			self.parent.zyncoderMutex = False
			return 'Clocks per step %d (%.2f BPM)' % (value, self.libseq.getTempo() * 24 / (value * self.libseq.getStepsPerBeat()))
		elif menuItem == 'Steps per beat':
			stepsPerBeat = STEPS_PER_BEAT[value]
			if stepsPerBeat:
				clocksPerStep = int(24 / stepsPerBeat)
				self.libseq.setClockDivisor(clocksPerStep)
			self.libseq.setStepsPerBeat(stepsPerBeat)
			self.parent.setParam('Clocks per step', 'value', clocksPerStep)
			self.drawGrid()
			value = stepsPerBeat
#		self.parent.zyncoderMutex = False
		return "%s: %d" % (menuItem, value)

	# Function to load new pattern
	#	index: Pattern index
	def loadPattern(self, index):
		self.libseq.clearSequence(self.sequence)
		self.pattern = index
		self.libseq.selectPattern(index)
		self.libseq.addPattern(self.sequence, 0, index)
		if self.selectedCell[0] >= self.libseq.getSteps():
			self.selectedCell[0] = self.libseq.getSteps() - 1
		self.drawGrid(True)
		self.playCanvas.coords("playCursor", 1, 0, 1 + self.stepWidth, PLAYHEAD_HEIGHT)
		self.parent.setParam('Steps in pattern', 'value', self.libseq.getSteps())
		self.parent.setParam('Pattern', 'value', index)
		self.parent.setParam('Tempo', 'value', self.libseq.getTempo())
		self.parent.setParam('Step per beat', 'value', self.libseq.getStepsPerBeat())
		self.parent.setParam('Clocks per step', 'value', self.libseq.getClockDivisor())
		self.parent.setTitle("Pattern Editor (%d)" % (self.pattern))

	def refresh_loading(self):
		pass

	# Function to handle zyncoder polling
	def zyncoder_read(self):
		if not self.shown:
			return
		if zyncoder.lib_zyncoder:
			value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_NOTE)
			if value != self.selectedCell[1]:
				self.selectCell(self.selectedCell[0], value)
			value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_STEP)
			if value != self.selectedCell[0]:
				self.selectCell(value, self.selectedCell[1])
			value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_VEL)
			if(value != self.velocity):
				self.velocity = value
				if self.libseq.getNoteDuration(self.selectedCell[0], self.selectedCell[1]):
					self.libseq.setNoteVelocity(self.selectedCell[0], self.selectedCell[1], value);
					self.drawCell(self.selectedCell[0], self.selectedCell[1]);
			value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_DUR)
			if value != self.duration-1:
				# zyncoder library does not permit minimum values :-( so offset duration by 1
				self.duration = value + 1
				if self.libseq.getNoteDuration(self.selectedCell[0], self.selectedCell[1]):
					self.addEvent(self.selectedCell[0], self.selectedCell[1])
				else:
					self.selectCell(self.selectedCell[0], self.selectedCell[1])
				self.drawGrid()

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
		if switch == ENC_NOTE:
			if self.libseq.getPlayMode(self.sequence):
				self.libseq.setPlayMode(self.sequence, 0) #STOP
			else:
				self.libseq.setPlayMode(self.sequence, 2) #LOOP
		elif switch == ENC_STEP:
			self.toggleEvent(self.selectedCell[0], self.selectedCell[1])
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
