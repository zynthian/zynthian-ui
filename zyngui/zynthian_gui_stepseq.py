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

import sys
import tkinter
import logging
import tkinter.font as tkFont
import jack
import json
import threading
from zyncoder import *

# Zynthian specific modules
from . import zynthian_gui_config

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer GUI Class
#------------------------------------------------------------------------------

# Local coonstants
STEP_MENU_PATTERN	= 0
STEP_MENU_VELOCITY	= 1
STEP_MENU_STEPS		= 2
STEP_MENU_MIDI		= 3
SELECT_BORDER		= '#ff8717'
PLAYHEAD_CURSOR		= '#cc701b'
CANVAS_BACKGROUND	= '#dddddd'
SELECT_THICKNESS	= 3

class zynthian_gui_stepseq():

	def __init__(self):
		self.clock = 0 # Count of MIDI clock pulses since last step [0..24]
		self.status = "STOP" # Play status [STOP | PLAY]
		self.playHead = 0 # Play head position in steps [0..gridColumns]
		self.pattern = 0 # Index of current pattern (zero indexed)
		# List of notes in selected pattern, indexed by step: each step is list of events, each event is list of (note,velocity)
		self.patterns = [] # List of patterns
		self.stepWidth = 40 # Grid column width in pixels (default 40)
		self.gridRows = 16 # Quantity of rows in grid (default 16)
		self.gridColumns = 16 # Quantity of columns in grid (default 16)
		self.keyOrigin = 60 # MIDI note number of top row in grid
		self.selectedCell = (self.playHead, self.keyOrigin) # Location of selected cell (step,note)
		self.menu = [{'title': 'Pattern', 'min': 1, 'max': 1, 'value': 1}, {'title': 'Velocity', 'min': 0, 'max': 127, 'value':100}, {'title': 'Steps', 'min': 2, 'max': 32, 'value': 16}, {'title': 'MIDI Channel', 'min': 1, 'max': 16, 'value': 1}] #TODO: Get values from persistent storage
		self.menuSelected = STEP_MENU_VELOCITY
		self.menuSelectMode = False # True to change selected menu value, False to change menu selection
		self.midiOutQueue = [] # List of events to be sent to MIDI output
		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height

		# Main Frame
		self.main_frame = tkinter.Frame(zynthian_gui_config.top,
			width=zynthian_gui_config.display_width,
			height=zynthian_gui_config.display_height,
			bg=CANVAS_BACKGROUND)

		logging.info("Starting PyStep...")
		# Load pattern from file
		try:
			#TODO: Get file from zynthian data path
			with open('pattern.json') as f:
				self.patterns = json.load(f)
		except:
			logging.warn('Failed to load pattern file')
			self.patterns = [[[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]]] # Default to empty 16 step pattern
		# Draw pattern grid
		self.trackHeight = 0.9 * self.height / (self.gridRows + 1)
		self.pianoRollWidth = self.width * 0.1
		self.gridCanvas = tkinter.Canvas(self.main_frame, width=self.width * 0.9, height=self.trackHeight * self.gridRows)
		self.gridCanvas.grid(row=1, column=1)
		# Draw title bar
		self.titleCanvas = tkinter.Canvas(self.main_frame, width=self.width, height=self.height * 0.1, bg="#70819e")
		self.titleCanvas.grid(row=0, column=0, columnspan=2)
		self.titleCanvas.create_text(2,2, anchor="nw", font=tkFont.Font(family="Times Roman", size=20), tags="lblPattern")
		lblMenu = self.titleCanvas.create_text(self.width - 2, 2, anchor="ne", font=tkFont.Font(family="Times Roman", size=16), tags="lblMenu")
		rectMenu = self.titleCanvas.create_rectangle(self.titleCanvas.bbox(lblMenu), fill="#70819e", width=0, tags="rectMenu")
		self.titleCanvas.tag_lower(rectMenu, lblMenu)
		self.menu[STEP_MENU_PATTERN]['max'] = len(self.patterns)
		if self.menu[STEP_MENU_PATTERN]['value'] > self.menu[STEP_MENU_PATTERN]['max']:
			self.menu[STEP_MENU_PATTERN]['value'] = self.menu[STEP_MENU_PATTERN]['max']
		self.refreshMenu()
		# Draw pianoroll
		self.pianoRoll = tkinter.Canvas(self.main_frame, width=self.pianoRollWidth, height=self.gridRows * self.trackHeight, bg="white")
		self.pianoRoll.grid(row=1, column=0)
		self.pianoRoll.bind("<ButtonPress-1>", self.pianoRollDragStart)
		self.pianoRoll.bind("<ButtonRelease-1>", self.pianoRollDragEnd)
		self.pianoRoll.bind("<B1-Motion>", self.pianoRollDragMotion)
		self.drawPianoroll()
		# Draw playhead
		self.playCanvas = tkinter.Canvas(self.main_frame, height=self.trackHeight / 2, bg=CANVAS_BACKGROUND)
		self.playCanvas.create_rectangle(0, 0, self.stepWidth, self.trackHeight / 2, fill=PLAYHEAD_CURSOR, state="hidden", width=0, tags="playCursor")
		self.playCanvas.grid(row=2, column=1)

		self.loadPattern(self.menu[STEP_MENU_PATTERN]['value'] - 1)

		# Set up JACK interface
		jackClient = jack.Client("zynthstep")
		self.midiInput = jackClient.midi_inports.register("input")
		self.midiOutput = jackClient.midi_outports.register("output")
		jackClient.set_process_callback(self.onJackProcess)
		jackClient.activate()
		#TODO: Remove auto test connection 
		try:
			jackClient.connect("a2j:MidiSport 2x2 [20] (capture): MidiSport 2x2 MIDI 1", "zynthstep:input")
			jackClient.connect("zynthstep:output", "ZynMidiRouter:main_in")
		except:
			logging.error("Failed to connect MIDI devices")

	def show(self):
		if not self.shown:
			self.shown=True
			self.main_frame.grid()
			# Set up encoders
			if zyncoder.lib_zyncoder:
				# Encoder 0 (Layer): Note
				pin_a=zynthian_gui_config.zyncoder_pin_a[0]
				pin_b=zynthian_gui_config.zyncoder_pin_b[0]
				zyncoder.lib_zyncoder.setup_zyncoder(0,pin_a,pin_b,0,0,None,self.selectedCell[1],127,0)
				# Encoder 2 (Snapshot): Step
				pin_a=zynthian_gui_config.zyncoder_pin_a[2]
				pin_b=zynthian_gui_config.zyncoder_pin_b[2]
				zyncoder.lib_zyncoder.setup_zyncoder(2,pin_a,pin_b,0,0,None,self.selectedCell[0],self.gridColumns-1,0)
				# Encoder 3 (Select): Menu
				pin_a=zynthian_gui_config.zyncoder_pin_a[3]
				pin_b=zynthian_gui_config.zyncoder_pin_b[3]
				zyncoder.lib_zyncoder.setup_zyncoder(3,pin_a,pin_b,0,0,None,self.menuSelected,len(self.menu) - 1,0)

	def hide(self):
		if self.shown:
			if self.menuSelectMode:
				self.toggleMenuMode()
			self.shown=False
			self.main_frame.grid_forget()

	# Function to handle start of pianoroll drag
	def pianoRollDragStart(self, event):
		self.pianoRollDragStartY = event.y

	# Function to handle pianoroll drag motion
	def pianoRollDragMotion(self, event):
		if event.y > self.pianoRollDragStartY + self.trackHeight and self.keyOrigin < 128 - self.gridRows:
			self.keyOrigin = self.keyOrigin + 1
			self.pianoRollDragStartY = event.y
			self.drawGrid()
		elif event.y < self.pianoRollDragStartY - self.trackHeight and self.keyOrigin > 0:
			self.keyOrigin = self.keyOrigin - 1
			self.pianoRollDragStartY = event.y
			self.drawGrid()

	# Function to handle end of pianoroll drag
	def pianoRollDragEnd(self, event):
		self.pianoRollDragStartY = None

	# Function to draw the play head cursor
	def drawPlayhead(self):
		self.playCanvas.coords("playCursor", 1 + self.playHead * self.stepWidth, 0, self.playHead * self.stepWidth + self.stepWidth, self.trackHeight / 2)

	# Function to handle mouse click / touch
	#   event: Mouse event
	def onCanvasClick(self, event):
		closest = event.widget.find_closest(event.x, event.y)
		tags = self.gridCanvas.gettags(closest)
		self.toggleEvent(int(tags[0].split(',')[0]), [self.keyOrigin + int(tags[0].split(',')[1]), self.menu[STEP_MENU_VELOCITY]['value']])

	# Function to toggle note event
	#   step: step (column) index
	#   note: note list [note, velocity]
	def toggleEvent(self, step, note):
		if step > self.gridRows or step > self.gridColumns:
			return
		found = False
		for event in self.patterns[self.pattern][step]:
			if event[0] == note[0]:
				self.patterns[self.pattern][step].remove(event)
				found = True
				break
		if not found and note[1]:
			self.patterns[self.pattern][step].append(note)
			self.noteOn(note)
			self.noteOffTimer = threading.Timer(0.1, self.noteOff, [note]).start()
		if note[0] >= self.keyOrigin and note[0] < self.keyOrigin + self.gridRows:
			self.selectCell(step, note[0])

	# Function to draw a grid cell
	#   step: Column index
	#   note: Row index
	def drawCell(self, col, row):
		if col >= self.gridColumns:
			return
		velocity = 255 # White
		for note in self.patterns[self.pattern][col]:
			if note[0] == self.keyOrigin + row:
				velocity = 255 - note[1] * 2
		fill = "#%02x%02x%02x" % (velocity, velocity, velocity)
		if self.selectedCell == (col, row + self.keyOrigin):
			outline = SELECT_BORDER
		elif velocity == 255:
			outline = CANVAS_BACKGROUND
		else:
			outline = 'black'
		cell = self.gridCanvas.find_withtag("%d,%d"%(col,row))
		if cell:
			# Update existing cell
			self.gridCanvas.itemconfig(cell, fill=fill, outline=outline)
		else:
			# Create new cell
			cell = self.gridCanvas.create_rectangle(SELECT_THICKNESS + col * self.stepWidth, (self.gridRows - row) * self.trackHeight, (col + 1) * self.stepWidth - SELECT_THICKNESS, (self.gridRows - row - 1) * self.trackHeight + SELECT_THICKNESS, fill=fill, outline=outline, tags=("%d,%d"%(col,row)), width=SELECT_THICKNESS)
			self.gridCanvas.tag_bind(cell, '<Button-1>', self.onCanvasClick)

	# Function to draw grid
	#   clearGrid: True to clear grid and create all new elements, False to reuse existing elements if they exist
	def drawGrid(self, clearGrid = False):
		if clearGrid:
			self.gridCanvas.delete(tkinter.ALL)
			self.stepWidth = self.width * 0.9 / self.gridColumns
		# Delete existing note names
		for item in self.pianoRoll.find_withtag("notename"):
			self.pianoRoll.delete(item)
		# Draw cells of grid
		for row in range(self.gridRows):
			for col in range(self.gridColumns):
				self.drawCell(col, row)
			# Update pianoroll keys
			key = (self.keyOrigin + row) % 12
			if key in (0,2,4,5,7,9,11):
				self.pianoRoll.itemconfig(row + 1, fill="white")
				if key == 0:
					self.pianoRoll.create_text((self.pianoRollWidth / 2, self.trackHeight * (self.gridRows - row - 0.5)), text="C%d (%d)" % ((self.keyOrigin + row) // 12 - 1, self.keyOrigin + row), tags="notename")
			else:
				self.pianoRoll.itemconfig(row + 1, fill="black")


	# Function to send MIDI note on
	#   note: List (MIDI note number, MIDI velocity)
	def noteOn(self, note):
		self.midiOutQueue.append((0x90 | (self.menu[STEP_MENU_MIDI]['value'] - 1), note[0], note[1]))

	# Function to send MIDI note off
	#   note: List (MIDI note number, MIDI velocity)
	def noteOff(self, note):
		self.midiOutQueue.append((0x80 | (self.menu[STEP_MENU_MIDI]['value'] - 1), note[0], note[1]))

	# Function to control play head
	#   command: Playhead command ["STOP" | "START" | "CONTINUE"]
	def setPlayState(self, command):
		if command == "START":
				logging.info("MIDI START")
				self.playHead = self.gridColumns - 1
				self.clock = 24
				self.status = "PLAY"
				self.playCanvas.coords("playCursor", 0, 0, self.stepWidth, self.trackHeight / 2)
				self.playCanvas.itemconfig("playCursor", state = 'normal')
		elif command == "CONTINUE":
				logging.info("MIDI CONTINUE")
				self.status = "PLAY"
				self.playCanvas.itemconfig("playCursor", state = 'normal')
		elif command == "STOP":
				logging.info("MIDI STOP")
				self.status = "STOP"
				self.playCanvas.itemconfig("playCursor", state = 'hidden')
				for note in self.patterns[self.pattern][self.playHead]:
					self.noteOff(note)


	# Function to handle JACK process events
	#   frames: Quantity of frames since last process event
	def onJackProcess(self, frames):
		for offset, data in self.midiInput.incoming_midi_events():
			if data[0] == b'\xf8':
				# MIDI Clock
				if self.status == "PLAY":
					self.clock = self.clock + 1
					if self.clock >= 6:
						# Time to process a time slot
						self.clock = 0
						for note in self.patterns[self.pattern][self.playHead]:
							self.noteOff(note)
						self.playHead = self.playHead + 1
						if self.playHead >= self.gridColumns:
							self.playHead = 0
						for note in self.patterns[self.pattern][self.playHead]:
							self.noteOn(note)
						self.drawPlayhead()
			elif data[0] == b'\xfa':
				# MIDI Start
				self.setPlayState("START")
			elif data[0] == b'\xfb':
				# Midi Continue
				self.setPlayState("CONTINUE")
			elif data[0] == b'\xfc':
				# MIDI Stop
				self.setPlayState("STOP")
		self.midiOutput.clear_buffer();
		for out in self.midiOutQueue:
			self.midiOutput.write_midi_event(0, out)
		self.midiOutQueue.clear()

	# Function to draw pianoroll keys (does not fill key colour)
	def drawPianoroll(self):
		for row in range(self.gridRows):
			y = self.trackHeight * (self.gridRows - row)
			self.pianoRoll.create_rectangle(0, y, self.pianoRollWidth, y - self.trackHeight)

	# Function to update selectedCell
	#   step: Step (column) of selected cell
	#   note: Note number of selected cell
	def selectCell(self, step, note):
		if step >= self.gridColumns or step < 0:
			return
		if note >= self.keyOrigin + self.gridRows:
			# Note is off top of display
			if note < 128:
				self.keyOrigin = note + 1 - self.gridRows
			else:
				self.keyOrigin = 128 - self.gridRows
			self.drawGrid()
		elif note < self.keyOrigin:
			self.keyOrigin = note
			self.drawGrid()
		else:
			previousSelected = self.selectedCell
			self.selectedCell = (step, note)
			self.drawCell(previousSelected[0], previousSelected[1]- self.keyOrigin) # Remove selection highlight
			self.drawCell(self.selectedCell[0], self.selectedCell[1] - self.keyOrigin)
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.set_value_zyncoder(0, note)
			zyncoder.lib_zyncoder.set_value_zyncoder(2, step)

	# Function to save pattern to json file
	def savePattern(self):
		with open('pattern.json', 'w') as f:
			json.dump(self.patterns, f)

	# Function to set menu value
	#   menuItem: Index of menu item
	#   value: Value to set menu item to
	def setMenuValue(self, menuItem, value):
		if menuItem >= len(self.menu):
			return
		if value < self.menu[menuItem]['min'] or value > self.menu[menuItem]['max']:
			return
		self.menu[menuItem]['value'] = value
		self.refreshMenu()
		if menuItem == STEP_MENU_VELOCITY:
			# Adjust velocity of selected cell
			currentStep = self.patterns[self.pattern][self.selectedCell[0]]
			for event in currentStep:
				if event[0] == self.selectedCell[1]:
					event[1] = value
					self.drawCell(self.selectedCell[0], self.selectedCell[1] - self.keyOrigin)
					return
		elif menuItem == STEP_MENU_PATTERN:
			self.loadPattern(value - 1)
		elif menuItem == STEP_MENU_STEPS:
			for step in range(self.gridColumns, value):
				self.patterns[self.pattern].append([])
			self.gridColumns = value
			self.drawGrid(True)

	# Function to toggle menu mode between menu selection and data entry
	def toggleMenuMode(self):
		self.menuSelectMode = not self.menuSelectMode
		if self.menuSelectMode:
			# Value edit mode
			self.titleCanvas.itemconfig("rectMenu", fill="#e8fc03")
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[3]
				pin_b=zynthian_gui_config.zyncoder_pin_b[3]
				zyncoder.lib_zyncoder.setup_zyncoder(3,pin_a,pin_b,0,0,None,self.menu[self.menuSelected]['value'],self.menu[self.menuSelected]['max'],0)
		else:
			# Menu item select mode
			self.titleCanvas.itemconfig("rectMenu", fill="#70819e")
			if self.menuSelected == STEP_MENU_STEPS:
				self.removeObsoleteSteps()
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[3]
				pin_b=zynthian_gui_config.zyncoder_pin_b[3]
				zyncoder.lib_zyncoder.setup_zyncoder(3,pin_a,pin_b,0,0,None,self.menuSelected,len(self.menu) - 1,0)
		self.refreshMenu()

	# Function to remove steps that are not within current display window
	def removeObsoleteSteps(self):
		self.patterns[self.pattern] = self.patterns[self.pattern][:self.gridColumns]

	# Function to update menu display
	def refreshMenu(self):
		self.titleCanvas.itemconfig("lblMenu", text="%s: %s" % (self.menu[self.menuSelected]['title'], self.menu[self.menuSelected]['value']))
		self.titleCanvas.coords("rectMenu", self.titleCanvas.bbox("lblMenu"))

	# Function to handle menu change
	#   value: New value
	def onMenuChange(self, value):
		if self.menuSelectMode:
			# Set menu value
			self.setMenuValue(self.menuSelected, value)
		elif value >= 0 and value < len(self.menu):
			self.menuSelected = value
			self.refreshMenu()
			if zyncoder.lib_zyncoder:
				pin_a=zynthian_gui_config.zyncoder_pin_a[3]
				pin_b=zynthian_gui_config.zyncoder_pin_b[3]
				zyncoder.lib_zyncoder.setup_zyncoder(3,pin_a,pin_b,0,0,None,self.menuSelected,len(self.menu) - 1,0)

	# Function to load new pattern
	def loadPattern(self, index):
		if index >= len(self.patterns) or index < 0:
			return
		self.pattern = index
		self.gridColumns = len(self.patterns[self.pattern])
		self.menu[STEP_MENU_STEPS]['value'] = self.gridColumns
		if self.playHead >= self.gridColumns:
			self.playHead = 0
		self.drawGrid(True)
		self.playCanvas.config(width=self.gridColumns * self.stepWidth)
		self.titleCanvas.itemconfig("lblPattern", text="Pattern: %d" % (self.pattern + 1))

	def refresh_loading(self):
		pass

	def zyncoder_read(self):
		if not self.shown:
			return
		if zyncoder.lib_zyncoder:
			# Read encoder 0 (Layer): Note
			val=zyncoder.lib_zyncoder.get_value_zyncoder(0)
			if val != self.selectedCell[1]:
				self.selectCell(self.selectedCell[0], val)
			# Read encoder 2 (Snapshot): Step
			val=zyncoder.lib_zyncoder.get_value_zyncoder(2)
			if val != self.selectedCell[0]:
				self.selectCell(val, self.selectedCell[1])
			# Read encoder 3 (Select): Menu
			val = zyncoder.lib_zyncoder.get_value_zyncoder(3)
			if self.menuSelectMode:
				# Change value
				if val != self.menu[self.menuSelected]['value']:
					self.onMenuChange(val)
			else:
				# Change menu
				if val != self.menuSelected:
					self.onMenuChange(val)

	def select_up(self):
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.set_value_zyncoder(3, zyncoder.lib_zyncoder.get_value_zyncoder(3) + 1)

	def select_down(self):
		if zyncoder.lib_zyncoder:
			value = zyncoder.lib_zyncoder.get_value_zyncoder(3)
			if value > 0:
				zyncoder.lib_zyncoder.set_value_zyncoder(3, value - 1)
				
	def switch_select(self, t):
		self.switch(3, t)

	def switch(self, switch, t):
		if switch == 0:
			#LAYER
			pass
		if switch == 1:
			#BACK
			pass
		if switch == 2:
			#SNAPSHOT
			self.toggleEvent(self.selectedCell[0], [self.selectedCell[1], self.menu[STEP_MENU_VELOCITY]['value']])
		if switch == 3:
			#SELECT
			if t == 'B' or self.menuSelectMode:
				self.toggleMenuMode()
			elif t == 'S':
				if self.status == "STOP":
					self.setPlayState("START")
				else:
					self.setPlayState("STOP")

#------------------------------------------------------------------------------
