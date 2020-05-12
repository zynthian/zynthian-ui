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
import tkinter
import logging
import threading
import tkinter.font as tkFont

# Zynthian specific modules
from . import zynthian_gui_config
from zyncoder import *

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Song Editor GUI Class
#------------------------------------------------------------------------------

# Local constants
SELECT_BORDER		= zynthian_gui_config.color_on
PLAYHEAD_CURSOR		= zynthian_gui_config.color_on
CANVAS_BACKGROUND	= zynthian_gui_config.color_panel_bg
CELL_BACKGROUND		= zynthian_gui_config.color_panel_bd
CELL_FOREGROUND		= zynthian_gui_config.color_panel_tx
GRID_LINE			= zynthian_gui_config.color_tx
PLAYHEAD_HEIGHT		= 20
# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select
ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3

# Class implements step sequencer song editor
class zynthian_gui_songeditor():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		parent.setTitle("Song Editor - work in progress")
		# Add menus
		self.parent.addMenu({'Song':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':1, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Copy song':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':1, 'onChange':self.onMenuChange,'onAssert':self.copySong}}})
		self.parent.addMenu({'Clear song':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':1, 'value':0, 'onChange':self.onMenuChange, 'onAssert':self.clearSong}}})
		self.parent.addMenu({'Transpose song':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':2, 'value':1, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Tempo':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':999, 'value':120, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Vertical zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'value':16, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Horizontal zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':128, 'value':64, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Clocks per division':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':24, 'value':6, 'onChange':self.onMenuChange}}})

		self.verticalZoom = 16 # Quantity of rows (tracks) displayed in grid
		self.horizontalZoom = 64 # Quantity of columns (clocks) displayed in grid
		self.copySource = 1 # Index of song to copy
		self.song = 1 # Index of current song
		self.rowOffset = 0 # Index of track within self.tracks of top row in grid
		self.colOffset = 0 # Index of clock cycle at left column in grid
		self.clockOrigin = 0 # Clock cycle of first column in grid
		self.selectedCell = [0, 0] # Location of selected cell (col,row)
		self.pattern = 1 # Index of current pattern to add to sequence
		self.tracks = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20] # Array of tracks: indicies of sequences
		self.duration = 128 #TODO Get duration from song sequences
		#TODO: Populate tracks from file
		self.trackDragStart = None
		self.timeDragStart = None

		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height
		self.selectThickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.gridHeight = self.height - PLAYHEAD_HEIGHT
		self.gridWidth = int(self.width * 0.9)
		self.trackTitleWidth = self.width - self.gridWidth
		self.updateCellSize()

		# Create main frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(column=0, row=1, sticky="nsew")

		# Create track titles canvas
		self.trackTitleCanvas = tkinter.Canvas(self.main_frame,
			width=self.trackTitleWidth,
			height=self.gridHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.trackTitleCanvas.bind("<ButtonPress-1>", self.onTrackDragStart)
		self.trackTitleCanvas.bind("<ButtonRelease-1>", self.onTrackDragEnd)
		self.trackTitleCanvas.bind("<B1-Motion>", self.onTrackDragMotion)
		self.trackTitleCanvas.grid(column=0, row=0)

		# Create grid canvas
		self.gridCanvas = tkinter.Canvas(self.main_frame, 
			width=self.gridWidth, 
			height=self.gridHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.gridCanvas.grid(column=1, row=0)

		# Create playhead canvas
		self.playCanvas = tkinter.Canvas(self.main_frame,
			width=self.gridWidth, 
			height=PLAYHEAD_HEIGHT,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.playCanvas.bind("<ButtonPress-1>", self.onTimeDragStart)
		self.playCanvas.bind("<ButtonRelease-1>", self.onTimeDragEnd)
		self.playCanvas.bind("<B1-Motion>", self.onTimeDragMotion)

		self.playCanvas.create_rectangle(0, 0, self.columnWidth, PLAYHEAD_HEIGHT,
			fill=PLAYHEAD_CURSOR,
			state="normal",
			width=0,
			tags="playCursor")
		self.playCanvas.grid(column=1, row=1)

		self.loadSong(1)

	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		self.parent.registerZyncoder(ENC_BACK, self)
		self.parent.registerZyncoder(ENC_SELECT, self)
		self.parent.registerZyncoder(ENC_SNAPSHOT, self)
		self.parent.registerZyncoder(ENC_LAYER, self)

	# Function to show GUI
	def show(self):
		self.main_frame.tkraise()
		self.setupEncoders()
		self.shown=True

	# Function to hide GUI
	def hide(self):
		self.shown=False
		self.parent.unregisterZyncoder(ENC_BACK)
		self.parent.unregisterZyncoder(ENC_SELECT)
		self.parent.unregisterZyncoder(ENC_SNAPSHOT)
		self.parent.unregisterZyncoder(ENC_LAYER)

	# Function to handle start of track drag
	def onTrackDragStart(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		if len(self.tracks) > self.verticalZoom:
			self.trackDragStart = event

	# Function to handle track drag motion
	def onTrackDragMotion(self, event):
		if not self.trackDragStart:
			return
		offset = int((event.y - self.trackDragStart.y) / self.rowHeight)
		if not offset:
			return
		self.trackDragStart.y = event.y
		pos = self.rowOffset - offset
		if pos < 0:
			pos = 0
		if pos + self.verticalZoom >= len(self.tracks):
			pos = len(self.tracks) - self.verticalZoom
		if self.rowOffset == pos:
			return
		self.rowOffset = pos
		self.drawGrid()
		row=self.selectedCell[1]
		if self.selectedCell[1] < self.rowOffset:
			row = self.rowOffset
		elif self.selectedCell[1] >= self.rowOffset + self.verticalZoom:
			row = self.rowOffset + self.verticalZoom - 1
		self.selectCell(self.selectedCell[0], row)

	# Function to handle end of track drag
	def onTrackDragEnd(self, event):
		self.trackDragStart = None

	# Function to handle start of time drag
	def onTimeDragStart(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		if self.duration > self.horizontalZoom:
			self.timeDragStart = event

	# Function to handle time drag motion
	def onTimeDragMotion(self, event):
		if not self.timeDragStart:
			return
		offset = int((self.timeDragStart.x - event.x) / self.columnWidth)
		if not offset:
			return
		self.timeDragStart.x = event.x
		pos = self.colOffset + offset
		if pos < 0:
			pos = 0
		if pos + self.horizontalZoom >= self.duration:
			pos = self.duration - self.horizontalZoom
		if self.colOffset == pos:
			return
		self.colOffset = pos
		self.drawGrid()
		col = self.selectedCell[0]
		if self.selectedCell[0] < self.colOffset:
			col = self.colOffset
		elif self.selectedCell[0] >= self.colOffset + self.horizontalZoom:
			col = self.colOffset + self.horizontalZoom - 1
		self.selectCell(col, self.selectedCell[1])

	# Function to handle end of time drag
	def onTimeDragEnd(self, event):
		self.timeDragStart = None

	# Function to handle mouse click / touch
	#	event: Mouse event
	def onCanvasClick(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		closest = event.widget.find_closest(event.x, event.y)
		tags = self.gridCanvas.gettags(closest)
		clock, track = tags[0].split(',')
		self.toggleEvent(int(clock), self.rowOffset + int(track))

	# Function to toggle note event
	#	clock: step clock(column) index
	#	track: Track number
	def toggleEvent(self, clock, track):
		if clock < 0:
			return
		if self.parent.libseq.getPattern(track, clock):
			self.removeEvent(clock, track)
		else:
			self.addEvent(clock, track)

	# Function to remove an event
	#	clock: clock (column) index
	#	track: Track number
	def removeEvent(self, clock, track):
		self.parent.libseq.removePattern(track, clock)
		self.drawRow(track)
		self.selectCell(clock, track)

	# Function to add an event
	#	clock: Clock (column) index
	#	track: Track number
	def addEvent(self, clock, track):
		self.parent.libseq.addPattern(track, clock, self.pattern)
		self.drawRow(track)
		self.selectCell(clock, track)

	# Function to draw a grid row
	#	row: Grid row to draw
	def drawRow(self, row):
		if row + self.rowOffset >= len(self.tracks):
			return
		self.trackTitleCanvas.itemconfig("rowtitle%d" % (row), text="Track %d" % (self.tracks[row + self.rowOffset]))
		self.gridCanvas.itemconfig("lastpatterntext%d" % (row), state="hidden")
		for clock in range(self.clockOrigin, self.clockOrigin + self.horizontalZoom):
			self.drawCell(clock, row + self.rowOffset)

	# Function to get cell coordinates
	#	col: Column index
	#	row: Row index
	#	duration: Duration of cell in clock cycles
	#	return: Coordinates required to draw cell
	def getCell(self, col, row, duration):
		x1 = col * self.columnWidth + 1
		y1 = self.rowHeight * row + 1
		x2 = x1 + self.columnWidth * duration - 1 
		y2 = y1 + self.rowHeight - 1
		return [x1, y1, x2, y2]

	# Function to draw a grid cell
	#	clock: Clock (column) index
	#	track: Track number
	def drawCell(self, clock, track):
		if clock < self.clockOrigin or clock >= self.clockOrigin + self.horizontalZoom or track < self.rowOffset or track >= self.rowOffset + self.verticalZoom:
			return
		col = clock + self.clockOrigin
		row = track + self.rowOffset
#		duration = self.parent.libseq.getPatternDuration(mypattern)
		duration = 1
		if not duration:
			duration = 1
		fillColour = CELL_BACKGROUND
		cell = self.gridCanvas.find_withtag("%d,%d"%(col,row))
		coord = self.getCell(clock, row, duration)
		if cell:
			# Update existing cell
			self.gridCanvas.itemconfig(cell, fill=fillColour)
			self.gridCanvas.coords(cell, coord)
		else:
			# Create new cell
			cell = self.gridCanvas.create_rectangle(coord, fill=fillColour, width=0, tags=("%d,%d"%(col,row), "gridcell", "clock%d"%clock))
			self.gridCanvas.tag_bind(cell, '<Button-1>', self.onCanvasClick)
		if clock + duration > self.horizontalZoom:
			if duration > 1:
				self.gridCanvas.itemconfig("lastpatterntext%d" % row, text="+%d" % (duration - self.parent.libseq.getDuration() + clock), state="normal")

	# Function to draw grid
	#	clearGrid: True to clear grid and create all new elements, False to reuse existing elements if they exist
	def drawGrid(self, clearGrid = False):
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		if clearGrid:
			self.gridCanvas.delete(tkinter.ALL)
			self.columnWidth = self.gridWidth / self.horizontalZoom
			self.trackTitleCanvas.delete("trackname")
		self.playCanvas.delete("timetext")
		# Draw cells of grid
		self.gridCanvas.itemconfig("gridcell", fill=CELL_BACKGROUND)
		for row in range(self.verticalZoom):
			if row >= len(self.tracks):
				break
			if clearGrid:
				self.trackTitleCanvas.create_text((0, self.rowHeight * (row + 0.5)), text="Track %d" % (self.tracks[row]), font=font, fill=CELL_FOREGROUND, tags=("rowtitle%d" % (row),"trackname"), anchor="w")
				self.gridCanvas.create_text(self.gridWidth - self.selectThickness, self.rowHeight * (self.rowHeight * int(row + 0.5)), state="hidden", tags=("lastpatterntext%d" % (row), "lastpatterntext"), font=font, anchor="e")
			self.drawRow(row)
		self.playCanvas.create_text(0 * self.columnWidth, PLAYHEAD_HEIGHT / 2, text="%d"%(self.colOffset), tags=("timetext"), anchor="w", fill=CELL_FOREGROUND)

		if clearGrid:
			for clock in range(self.horizontalZoom):
				self.gridCanvas.tag_lower("clock%d"%clock)

	# Function to update selectedCell
	#	clock: Clock (column) of selected cell (Optional - default to reselect current column)
	#	track: Track number of selected cell (Optional - default to reselect current =row)
	def selectCell(self, clock=None, track=None):
		redraw = False
		if not clock:
			clock = self.selectedCell[0]
		if not track:
			track = self.selectedCell[1]
		if clock < 0 or clock >= self.duration or track < 0 or track >= len(self.tracks):
			return
		# Skip hidden (overlapping) cells
#		for previous in range(clock - 1, -1, -1):
#			prevDuration = self.parent.libseq.getSteps(previous, track)
#			if not prevDuration:
#				continue
#			if prevDuration > clock - previous:
#				if clock > self.selectedCell[0]:
#					clock = previous + prevDuration
#				else:
#					clock = previous
#				break
#		if clock >= self.duration:
#			clock = self.duration - 1
#		if clock < 0:
#			clock = 0;
		self.selectedCell = [clock, track]
		if clock >= self.colOffset + self.horizontalZoom:
			# time is off right of display
			self.colOffset = clock - self.horizontalZoom + 1
			redraw = True
		elif clock < self.colOffset:
			# time is off left of display
			self.colOffset = clock
			redraw = True
		if track >= self.rowOffset + self.verticalZoom:
			# track is off bottom of display
			self.rowOffset = track - self.verticalZoom + 1
			redraw = True
		elif track < self.rowOffset:
			self.rowOffset = track
			redraw = True
		if redraw:
			self.drawGrid(True)
#		duration = self.parent.libseq.getPatternLength(clock, track)
		duration = 1
		if not duration:
			duration = self.duration
		coord = self.getCell(clock - self.colOffset, track - self.rowOffset, duration)
		coord[0] = coord[0] - 1
		coord[1] = coord[1] - 1
		coord[2] = coord[2]
		coord[3] = coord[3]
		cell = self.gridCanvas.find_withtag("selection")
		if not cell:
			cell = self.gridCanvas.create_rectangle(coord, fill="", outline=SELECT_BORDER, width=self.selectThickness, tags="selection")
		else:
			self.gridCanvas.coords(cell, coord)
		self.gridCanvas.tag_raise(cell)

	# Function to calculate cell size
	def updateCellSize(self):
		self.rowHeight = (self.gridHeight - 2) / self.verticalZoom
		self.columnWidth = self.gridWidth / self.horizontalZoom
		self.fontsize = int(self.rowHeight * 0.5)
		if self.fontsize > 20:
			self.fontsize = 20 # Ugly font scale limiting

	# Function to clear a pattern
	def clearSong(self):
		self.parent.libseq.clearSong()
		self.drawGrid(True)
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()
		self.selectCell(0,0)

	# Function to copy pattern
	def copySong(self):
		self.parent.libseq.copySong(self.copySource, self.song);
		self.loadSong(self.song)

	# Function to handle menu editor change
	#	value: Menu item's value
	#	returns: String to populate menu editor label
	def onMenuChange(self, value):
		menuItem = self.parent.paramEditor['menuitem']
		if value < self.parent.paramEditor['min']:
			value = self.parent.paramEditor['min']
		if value > self.parent.paramEditor['max']:
			value = self.parent.paramEditor['max']
		self.parent.paramEditor['value'] = value
		if menuItem == 'Song':
			self.song = value
			self.copySource = value
			self.parent.setParam('Copy song', 'value', value)
			self.loadSong(value)
		elif menuItem == 'Clear song':
			return "Clear song %d?" % (self.song)
		elif menuItem =='Copy song':
			self.loadSong(value)
			return "Copy %d=>%d?" % (self.copySource, value)
		elif menuItem == 'Transpose song':
			if(value != 1):
				for seq in self.tracks:
					self.parent.libseq.transposeSong(seq)
				self.parent.paramEditor['value'] = 1
				if zyncoder.lib_zyncoder:
					zyncoder.lib_zyncoder.zynmidi_send_all_notes_off() #TODO: Use libseq - also, just send appropriate note off
			self.drawGrid()
			self.selectCell()
			return "Transpose song +/-"
		elif menuItem == 'Vertical zoom':
			self.verticalZoom = value
			self.updateCellSize()
			self.drawGrid(True)
			self.selectCell()
			self.parent.setParam(menuItem, 'value', value)
		elif menuItem == 'Horizontal zoom':
			self.horizontalZoom = value
			self.updateCellSize()
			self.drawGrid(True)
			self.selectCell()
			self.parent.setParam(menuItem, 'value', value)
		elif menuItem == 'Tempo':
			self.parent.libseq.setTempo(value)
			self.parent.setParam(menuItem, 'value', value)
		elif menuItem == 'Clocks per division':
			#TODO: Implement clocks per division
			self.parent.setParam(menuItem, 'value', value)
		return "%s: %d" % (menuItem, value)

	# Function to load new pattern
	#	index: Pattern index
	def loadSong(self, index):
		self.song = index
		#TODO: Update from file
		self.drawGrid(True)
		self.selectCell(0,0)
		self.parent.setParam('Vertical zoom', 'max', len(self.tracks))
		self.parent.setParam('Horizontal zoom', 'max', self.duration)

	def refresh_loading(self):
		pass

	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def onZyncoder(self, encoder, value):
		if encoder == ENC_BACK:
			# BACK encoder adjusts track selection
			track = self.selectedCell[1] + value
			self.selectCell(self.selectedCell[0], track)
		elif encoder == ENC_SELECT:
			# SELECT encoder adjusts time selection
			clock = self.selectedCell[0] + value
			self.selectCell(clock, self.selectedCell[1])

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
