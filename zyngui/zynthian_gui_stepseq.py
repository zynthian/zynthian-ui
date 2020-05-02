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
from zyngine import zynthian_engine_transport as zyntransport

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer GUI Class
#------------------------------------------------------------------------------

# Local constants
DEFAULT_BPM			= 120
DEFAULT_CLK_DIV		= 6
MAX_PATTERNS		= 999
MAX_STEPS			= 64
MENU_PATTERN		= 0
MENU_VELOCITY		= 1
MENU_DURATION		= 2
MENU_STEPS			= 3
MENU_COPY			= 4
MENU_CLEAR			= 5
MENU_TRANSPOSE		= 6
MENU_MIDI			= 7
MENU_TEMPO			= 8
MENU_CLOCKDIV		= 9
MENU_GRID			= 10
MENU_ROWS			= 11
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
ENC_MENU			= ENC_LAYER
ENC_NOTE			= ENC_SNAPSHOT
ENC_STEP			= ENC_SELECT

# Class implements step sequencer
class zynthian_gui_stepseq():

	# Function to initialise class
	def __init__(self):
		# Load sequencer library
		self.libseq = ctypes.CDLL(dirname(realpath(__file__))+"/../zynseq/build/libzynseq.so")
		self.libseq.init()
		self.sequence = 0 # Use sequence zero fo pattern editor sequence player
		self.pattern = 0 # Index of current pattern (zero indexed)
		self.stepWidth = 40 # Grid column width in pixels (default 40)
		self.keyOrigin = 60 # MIDI note number of top row in grid
		self.selectedCell = [0, self.keyOrigin] # Location of selected cell (step,note)
		#TODO: Get values from persistent storage
		self.menu = [{'title': 'Pattern', 'min': 1, 'max': MAX_PATTERNS, 'value': 1}, \
			{'title': 'Velocity', 'min': 1, 'max': 127, 'value':100}, \
			{'title': 'Duration', 'min': 1, 'max': 64, 'value':1}, \
			{'title': 'Steps', 'min': 2, 'max': MAX_STEPS, 'value': 16}, \
			{'title': 'Copy pattern', 'min': 1, 'max': MAX_PATTERNS, 'value': 1}, \
			{'title': 'Clear pattern', 'min': 1, 'max': MAX_PATTERNS, 'value': 1}, \
			{'title': 'Transpose', 'min': 0, 'max': 2, 'value': 1}, \
			{'title': 'MIDI Channel', 'min': 1, 'max': 16, 'value': 1}, \
			{'title': 'Tempo', 'min': 0, 'max': 999, 'value': DEFAULT_BPM},
			{'title': 'Clock divisor', 'min': 1, 'max': 24, 'value': DEFAULT_CLK_DIV},
			{'title': 'Grid lines', 'min': 0, 'max': 16, 'value': 0},
			{'title': 'Zoom', 'min': 1, 'max': 100, 'value': 16}]
		self.menuSelected = MENU_VELOCITY
		self.menuSelectMode = False # True to change selected menu value, False to change menu selection
		self.zyncoderMutex = False # Flag to avoid reading encoders whilst processing changes
		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height
		self.selectThickness = 1 + int(self.width / 500)
		self.titlebarHeight = int(self.height * 0.1)
		self.gridHeight = self.height - self.titlebarHeight - PLAYHEAD_HEIGHT
		self.gridWidth = int(self.width * 0.9)
		self.pianoRollWidth = self.width - self.gridWidth
		self.updateRowHeight()

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width=self.width,
			height=self.height,
			bg=CANVAS_BACKGROUND)

		# Load pattern from file
		self.libseq.load(bytes(os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/sequences/patterns.zynseq", "utf-8"))
		# Draw pattern grid
		self.gridCanvas = tkinter.Canvas(self.main_frame, 
			width=self.gridWidth, 
			height=self.gridHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.gridCanvas.grid(row=1, column=1)
		# Draw title bar
		self.titleCanvas = tkinter.Canvas(self.main_frame, 
			width=self.width, 
			height=self.titlebarHeight, 
			bg=HEADER_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.titleCanvas.grid(row=0, column=0, columnspan=2)
		lblMenu = self.titleCanvas.create_text(2, int(self.height * 0.05),
			width = self.width * 0.95,
			anchor="w",
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="lblMenu")
		rectMenu = self.titleCanvas.create_rectangle(self.titleCanvas.bbox(lblMenu),
			fill=zynthian_gui_config.color_header_bg,
			width=0,
			tags="rectMenu")
		self.titleCanvas.tag_lower(rectMenu, lblMenu)
		self.titleCanvas.create_text(self.width - 2, int(self.height * 0.05),
			anchor="e", 
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.height * 0.05)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="lblPattern")
		self.refreshMenu()
		# Bind user input to GUI
#		self.titleCanvas.tag_bind("lblMenu", "<ButtonPress-1>", self.onMenuClick)
		self.titleCanvas.bind("<ButtonPress-1>", self.onTitleClick)
		# Draw pianoroll
		self.pianoRoll = tkinter.Canvas(self.main_frame,
			width=self.pianoRollWidth,
			height=self.getMenuValue(MENU_ROWS) * self.rowHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.pianoRoll.grid(row=1, column=0)
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

		self.loadPattern(self.getMenuValue(MENU_PATTERN) - 1)

		self.startPlayheadHandler()

		# Select a cell
		self.selectCell(0, self.keyOrigin + int(self.getMenuValue(MENU_ROWS) / 2))

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
			self.shown=True
			self.main_frame.grid()
			# Set up encoders
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_BACK]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_BACK]
#				zyncoder.lib_zyncoder.setup_zyncoder(ENC_BACK,pin_a,pin_b,0,0,None,0,127,0)
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_MENU]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_MENU]
				zyncoder.lib_zyncoder.setup_zyncoder(ENC_MENU,pin_a,pin_b,0,0,None,self.menuSelected,len(self.menu) - 1,0)
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_NOTE]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_NOTE]
				zyncoder.lib_zyncoder.setup_zyncoder(ENC_NOTE,pin_a,pin_b,0,0,None,self.selectedCell[1],127,0)
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_STEP]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_STEP]
				zyncoder.lib_zyncoder.setup_zyncoder(ENC_STEP,pin_a,pin_b,0,0,None,self.selectedCell[0],self.libseq.getSteps() - 1,0)

	# Function to hide GUI
	def hide(self):
		if self.shown:
			if self.menuSelectMode:
				self.toggleMenuMode(False)
			self.shown=False
			self.main_frame.grid_forget()
			self.savePatterns() #TODO: Find better time to save patterns

	# Function to handle start of pianoroll drag
	def onPianoRollDragStart(self, event):
		self.pianoRollDragStart = event

	# Function to handle pianoroll drag motion
	def onPianoRollDragMotion(self, event):
		if event.y > self.pianoRollDragStart.y + self.rowHeight and self.keyOrigin < 128 - self.getMenuValue(MENU_ROWS):
			self.keyOrigin = self.keyOrigin + 1
			self.pianoRollDragStart.y = event.y
			self.drawGrid()
		elif event.y < self.pianoRollDragStart.y - self.rowHeight and self.keyOrigin > 0:
			self.keyOrigin = self.keyOrigin - 1
			self.pianoRollDragStart.y = event.y
			self.drawGrid()
		elif event.x < self.pianoRollDragStart.x - self.pianoRollWidth / 2:
			if self.menuSelectMode:
				self.toggleMenuMode(False) # Disable data entry before exit
			else:
				self.zyngui.show_screen(self.zyngui.active_screen)
			return
		if self.selectedCell[1] < self.keyOrigin:
			self.selectedCell[1] = self.keyOrigin
		elif self.selectedCell[1] >= self.keyOrigin + self.getMenuValue(MENU_ROWS):
			self.selectedCell[1] = self.keyOrigin + self.getMenuValue(MENU_ROWS) - 1
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
		velocity = self.getMenuValue(MENU_VELOCITY)
		duration = self.getMenuValue(MENU_DURATION)
		self.libseq.addNote(step, note, velocity, duration)
		self.drawRow(note)
		self.selectCell(step, note)

	# Function to draw a grid row
	#	note: MIDI note for the row to draw
	def drawRow(self, note):
		self.gridCanvas.itemconfig("lastnotetext%d" % (note - self.keyOrigin), state="hidden")
		for step in range(self.libseq.getSteps()):
			self.drawCell(step, note)

	# Function to get cell coordinates
	def getCell(self, col, row, duration):
		x1 = col * self.stepWidth + 1
		y1 = (self.getMenuValue(MENU_ROWS) - row - 1) * self.rowHeight + 1
		x2 = x1 + self.stepWidth * duration - 1 
		y2 = y1 + self.rowHeight - 1
		return [x1, y1, x2, y2]

	# Function to draw a grid cell
	#	step: Step (column) index
	#	note: Note number
	def drawCell(self, step, note):
		if step < 0 or step >= self.libseq.getSteps() or note < self.keyOrigin or note >= self.keyOrigin + self.getMenuValue(MENU_ROWS):
			return
		row = note - self.keyOrigin
		velocityColour = self.libseq.getNoteVelocity(step, note)
		if velocityColour:
			velocityColour = 70 + velocityColour
		duration = self.libseq.getNoteDuration(step, note)
		if not duration:
			duration = 1
		fill = "#%02x%02x%02x" % (velocityColour, velocityColour, velocityColour)
		cell = self.gridCanvas.find_withtag("%d,%d"%(step,row))
		coord = self.getCell(step, row, duration)
		if cell:
			# Update existing cell
			self.gridCanvas.itemconfig(cell, fill=fill)
			self.gridCanvas.coords(cell, coord)
		else:
			# Create new cell
			cell = self.gridCanvas.create_rectangle(coord, fill=fill, width=0, tags=("%d,%d"%(step,row), "gridcell", "step%d"%step))
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
		for note in range(self.keyOrigin, self.keyOrigin + self.getMenuValue(MENU_ROWS)):
			self.drawRow(note)
		# Delete existing note names
		self.pianoRoll.delete("notename")
		for note in range(self.keyOrigin, self.keyOrigin + self.getMenuValue(MENU_ROWS)):
			# Update pianoroll keys
			key = note % 12
			row = note - self.keyOrigin
			if clearGrid:
				# Create last note labels in grid
				self.gridCanvas.create_text(self.gridWidth - self.selectThickness, self.rowHeight * (self.getMenuValue(MENU_ROWS) - row - 0.5), state="hidden", tags=("lastnotetext%d" % (row), "lastnotetext"), font=font, anchor="e")
			id = "row%d" % (row)
			if key in (0,2,4,5,7,9,11):
				self.pianoRoll.itemconfig(id, fill="white")
				if key == 0:
					self.pianoRoll.create_text((self.pianoRollWidth / 2, self.rowHeight * (self.getMenuValue(MENU_ROWS) - row - 0.5)), text="C%d (%d)" % ((self.keyOrigin + row) // 12 - 1, self.keyOrigin + row), font=font, fill=CANVAS_BACKGROUND, tags="notename")
			else:
				self.pianoRoll.itemconfig(id, fill="black")
		# Redraw gridlines
		self.gridCanvas.delete("gridline")
		if self.getMenuValue(MENU_GRID):
			for step in range(0, self.libseq.getSteps() + 1, self.getMenuValue(MENU_GRID)):
				self.gridCanvas.create_line(step * self.stepWidth + 1, 0, step * self.stepWidth + 1, self.getMenuValue(MENU_ROWS) * self.rowHeight - 1, fill=GRID_LINE, tags=("gridline"))
		# Set z-order to allow duration to show
		if clearGrid:
			for step in range(self.libseq.getSteps()):
				self.gridCanvas.tag_lower("step%d"%step)

	# Function to draw pianoroll keys (does not fill key colour)
	def drawPianoroll(self):
		self.pianoRoll.delete(tkinter.ALL)
		for row in range(self.getMenuValue(MENU_ROWS)):
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
		if note >= self.keyOrigin + self.getMenuValue(MENU_ROWS):
			# Note is off top of display
			if note < 128:
				self.keyOrigin = note + 1 - self.getMenuValue(MENU_ROWS)
			else:
				self.keyOrigin = 128 - self.getMenuValue(MENU_ROWS)
			self.drawGrid()
		elif note < self.keyOrigin:
			self.keyOrigin = note
			self.drawGrid()
		else:
			cell = self.gridCanvas.find_withtag("selection")
			row = note - self.keyOrigin
			duration = self.libseq.getNoteDuration(step, note)
			if not duration:
				duration = self.getMenuValue(MENU_DURATION)
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

	# Function to save patterns to json file
	def savePatterns(self):
		filename=os.environ.get("ZYNTHIAN_MY_DATA_DIR", "/zynthian/zynthian-my-data") + "/sequences/patterns.zynseq"
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		self.libseq.save(bytes(filename, "utf-8"));

	# Function to transform menu value
	#	menuItem: Index of menu item
	#	value: Value to transform
	#	returns: Transformed menu item value
	def transformMenuValue(self, menuItem, value):
		if menuItem == MENU_GRID and self.getMenuValue(menuItem) == 0:
			return "None"
		elif menuItem == MENU_TRANSPOSE:
			return "Up/Down"
		elif menuItem == MENU_COPY:
			return "%d => %d" % (self.getMenuValue(MENU_PATTERN), self.pattern + 1)
		else:
			return self.menu[menuItem]['value']

	# Function to update menu display
	def refreshMenu(self):
		self.titleCanvas.itemconfig("lblMenu", text="%s: %s" % (self.menu[self.menuSelected]['title'], self.getMenuValue(self.menuSelected, False)))
		self.titleCanvas.coords("rectMenu", self.titleCanvas.bbox("lblMenu"))

	# Function to get menu value
	#	menuItem: Index of menu item
	#	raw: True to return raw number, False to return transformed value
	#	returns: Value of menu item
	def getMenuValue(self, menuItem, raw = True):
		value = 0
		try:
			value = self.menu[menuItem]['value']
		except:
			logging.error("Failed to get menu value for menu item %d", menuItem)
		if raw:
			return value
		return self.transformMenuValue(menuItem, value)

	# Function to set menu value
	#	menuItem: Index of menu item
	#	value: Value to set menu item to
	#	refresh: True to refresh grid
	def setMenuValue(self, menuItem, value, refresh = True):
		if menuItem >= len(self.menu) or value < self.menu[menuItem]['min'] or value > self.menu[menuItem]['max']:
			return
		self.menu[menuItem]['value'] = value
		if menuItem == MENU_VELOCITY:
			# Adjust velocity of selected cell
			if self.libseq.getNoteDuration(self.selectedCell[0], self.selectedCell[1]):
				self.libseq.setNoteVelocity(self.selectedCell[0], self.selectedCell[1], value);
				self.drawCell(self.selectedCell[0], self.selectedCell[1]);
		elif menuItem == MENU_DURATION:
			if self.libseq.getNoteDuration(self.selectedCell[0], self.selectedCell[1]):
				self.addEvent(self.selectedCell[0], self.selectedCell[1])
			else:
				self.selectCell(self.selectedCell[0], self.selectedCell[1])
		elif menuItem == MENU_PATTERN or menuItem == MENU_COPY:
			self.menu[MENU_COPY]['value'] = value# update copy pattern index  when pattern value changes
			self.menu[MENU_CLEAR]['value'] = value# update clear pattern index when pattern value changes
			self.loadPattern(value - 1)
		elif menuItem == MENU_STEPS:
			self.libseq.setSteps(value)
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_STEP]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_STEP]
				zyncoder.lib_zyncoder.setup_zyncoder(ENC_STEP,pin_a,pin_b,0,0,None,self.selectedCell[0],MAX_STEPS,0)
			self.drawGrid(True)
			self.selectCell(self.selectedCell[0], self.selectedCell[1])
			self.menu[MENU_DURATION]['max'] = value;
		elif menuItem == MENU_MIDI:
			self.libseq.setChannel(self.sequence, value - 1);
		elif menuItem == MENU_TRANSPOSE:
			# zyncoders only support positive integers so must use offset
			self.libseq.transpose(self.getMenuValue(MENU_TRANSPOSE) - 1)
			if zyncoder.lib_zyncoder:
				zyncoder.lib_zyncoder.set_value_zyncoder(ENC_MENU, 1)
				zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()
			self.drawGrid()
		elif menuItem == MENU_ROWS:
			# Zoom
			self.updateRowHeight()
			self.drawGrid(True)
		elif menuItem == MENU_TEMPO:
			#self.zyngui.zyntransport.tempo(value)
			self.libseq.setTempo(value)
		elif menuItem == MENU_GRID:
			self.drawGrid()

	# Function to calculate row height
	def updateRowHeight(self):
		self.rowHeight = (self.gridHeight - 2) / self.getMenuValue(MENU_ROWS)

	# Function to clear a pattern
	#	pattern: Index of the pattern to clear
	def clearPattern(self, pattern):
		self.libseq.clear()
		self.drawGrid(True)
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()

	# Function to copy pattern
	#	source: Index of pattern to copy from
	#	dest: Index of pattern to copy to
	def copyPattern(self, source, dest):
		#TODO: Handle zero based 
		self.libseq.copyPattern(source, dest);
		if dest == self.pattern:
			self.loadPattern(dest)

	# Function to toggle menu mode between menu selection and data entry
	#	assertChange: True to assert changes, False to cancel changes
	def toggleMenuMode(self, assertChange = True):
		self.zyncoderMutex = True
		self.menuSelectMode = not self.menuSelectMode
		if self.menuSelectMode:
			# Entered value edit mode
			self.titleCanvas.itemconfig("rectMenu", fill=zynthian_gui_config.color_ctrl_bg_on)
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_MENU]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_MENU]
				zyncoder.lib_zyncoder.setup_zyncoder_with_min(ENC_MENU,pin_a,pin_b,0,0,None,self.getMenuValue(self.menuSelected),self.menu[self.menuSelected]['min'],self.menu[self.menuSelected]['max'],0)
		else:
			# Exit value edit mode
			self.titleCanvas.itemconfig("rectMenu", fill=zynthian_gui_config.color_header_bg)
			if assertChange:
				if self.menuSelected == MENU_COPY:
					self.copyPattern(self.getMenuValue(MENU_PATTERN) - 1, self.pattern)
					self.setMenuValue(MENU_PATTERN, self.pattern + 1)
			elif self.menuSelected == MENU_STEPS:
				#TODO: Undo changes to pattern length (used to work but now updating pattern immediately)
				pass
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_MENU]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_MENU]
				zyncoder.lib_zyncoder.setup_zyncoder(ENC_MENU,pin_a,pin_b,0,0,None,self.menuSelected,len(self.menu) - 1,0)
		self.refreshMenu()
		self.zyncoderMutex = False

	# Function to handle menu change
	#	value: New value
	def onMenuChange(self, value):
		self.menuModeMutex = True
		if self.menuSelectMode:
			# Set menu value
			self.setMenuValue(self.menuSelected, value)
			self.refreshMenu()
		elif value >= 0 and value < len(self.menu):
			# Select menu
			self.menuSelected = value
			self.refreshMenu()
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_MENU]
				pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_MENU]
				zyncoder.lib_zyncoder.setup_zyncoder(ENC_MENU,pin_a,pin_b,0,0,None,self.menuSelected,len(self.menu) - 1,0)
		self.menuModeMutex = False

	# Function to handle title bar click
	def onTitleClick(self, event):
		if self.menuSelectMode:
			self.toggleMenuMode(False) # Disable data entry before exit
		else:
			self.zyngui.show_screen(self.zyngui.active_screen)

	# Function to handle title bar click
	def onMenuClick(self, event):
		if self.menuSelectMode:
			self.toggleMenuMode(False) # Disable data entry before exit
		else:
			self.zyngui.show_screen(self.zyngui.active_screen)

	# Function to load new pattern
	def loadPattern(self, index):
		zyncoderMutex = True
		self.libseq.clearSequence(self.sequence)
		self.pattern = index
		self.libseq.selectPattern(index)
		self.libseq.addPattern(self.sequence, 0, index)
		if self.selectedCell[0] >= self.libseq.getSteps():
			self.selectedCell[0] = self.libseq.getSteps() - 1
		self.titleCanvas.itemconfig("lblPattern", text="%d" % (self.pattern + 1))
		self.setMenuValue(MENU_STEPS, self.libseq.getSteps())
		if zyncoder.lib_zyncoder:
			pin_a=zynthian_gui_config.zyncoder_pin_a[ENC_STEP]
			pin_b=zynthian_gui_config.zyncoder_pin_b[ENC_STEP]
			zyncoder.lib_zyncoder.setup_zyncoder(ENC_STEP,pin_a,pin_b,0,0,None,self.selectedCell[0],self.libseq.getSteps() - 1,0)
		zyncoderMutex = False
		self.drawGrid()
		self.playCanvas.coords("playCursor", 1, 0, 1 + self.stepWidth, PLAYHEAD_HEIGHT)

	def refresh_loading(self):
		pass

	# Function to handle zyncoder polling
	def zyncoder_read(self):
		if not self.shown or self.zyncoderMutex:
			return
		if zyncoder.lib_zyncoder:
			val=zyncoder.lib_zyncoder.get_value_zyncoder(ENC_NOTE)
			if val != self.selectedCell[1]:
				self.selectCell(self.selectedCell[0], val)
			val=zyncoder.lib_zyncoder.get_value_zyncoder(ENC_STEP)
			if val != self.selectedCell[0]:
				self.selectCell(val, self.selectedCell[1])
			val = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_MENU)
			if self.menuSelectMode:
				# Change value
				if val != self.getMenuValue(self.menuSelected):
					self.onMenuChange(val)
			else:
				# Change menu
				if  val != self.menuSelected:
					self.onMenuChange(val)

	# Function to handle CUIA SELECT_UP command
	def select_up(self):
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SELECT, zyncoder.lib_zyncoder.get_value_zyncoder(ENC_SELECT) + 1)

	# Function to handle CUIA SELECT_DOWN command
	def select_down(self):
		if zyncoder.lib_zyncoder:
			value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_SELECT)
			if value > 0:
				zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SELECT, value - 1)

	# Function to handle CUIA LAYER_UP command
	def layer_up(self):
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_LAYER, zyncoder.lib_zyncoder.get_value_zyncoder(ENC_LAYER) + 1)

	# Function to handle CUIA LAYER_DOWN command
	def layer_down(self):
		if zyncoder.lib_zyncoder:
			value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_LAYER)
			if value > 0:
				zyncoder.lib_zyncoder.set_value_zyncoder(ENC_LAYER, value - 1)

	# Function to handle CUIA SNAPSHOT_UP command
	def snapshot_up(self):
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SNAPSHOT, zyncoder.lib_zyncoder.get_value_zyncoder(ENC_SNAPSHOT) + 1)

	# Function to handle CUIA SNAPSHOT_DOWN command
	def snapshot_down(self):
		if zyncoder.lib_zyncoder:
			value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_SNAPSHOT)
			if value > 0:
				zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SNAPSHOT, value - 1)

	# Function to handle CUIA SELECT command
	def switch_select(self, t):
		self.switch(3, t)

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
		if switch == ENC_BACK:
			if self.menuSelectMode:
				self.toggleMenuMode(False) # Disable data entry before exit
			else:
				return False
		elif switch == ENC_MENU:
			if self.menuSelected == MENU_CLEAR:
				if type == "B":
					self.clearPattern(self.pattern)
					self.loadPattern(self.pattern)
			else:
				self.toggleMenuMode()
		elif switch == ENC_NOTE:
			if self.libseq.getPlayMode(self.sequence):
				self.libseq.setPlayMode(self.sequence, 0) #STOP
			else:
				self.libseq.setPlayMode(self.sequence, 2) #LOOP
		elif switch == ENC_STEP:
			self.toggleEvent(self.selectedCell[0], self.selectedCell[1])
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
