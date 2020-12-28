#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Step-Sequencer Class
# 
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2020 Brian Walton <brian@riban.co.uk>
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
from PIL import Image, ImageTk
from time import monotonic, sleep
from threading import Timer
import traceback

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
		self.libseq = parent.zyngui.libseq

		#TODO: Put colours in a common file
		self.playModes = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all', 'Oneshot sync', 'Loop sync']
		self.padColourDisabled = 'grey'
		self.padColourStarting = 'orange'
		self.padColourPlaying = 'green'
		self.padColourStopping = 'red'
		self.padColourStoppedEven = 'purple'
		self.padColourStoppedOdd = 'blue'

		self.verticalZoom = 4 # Quantity of rows (tracks) displayed in grid
		self.horizontalZoom = 8 # Quantity of columns (time divisions) displayed in grid
		self.copySource = 1 # Index of song to copy (add 1000 for pad editor)
		self.rowOffset = 0 # Index of track at top row in grid
		self.colOffset = 0 # Index of time division at left column in grid
		self.selectedCell = [0, 0] # Location of selected cell (time div,track)
		self.pattern = 1 # Index of current pattern to add to sequence
		self.position = 0 # Current playhead position
		self.gridTimer = Timer(0.5, self.onGridTimer) # Grid press and hold timer
		self.editorMode = 0 # Editor mode [0: Song, 1: Pads]
		self.song = 1 # Index of song being edited (1000 * editorMode + libseq.getSong)
		self.trigger = 60 # MIDI note number to set trigger
		#TODO: Populate tracks from file
		self.trackDragStart = None # Set to loaction of mouse during drag
		self.timeDragStart = None # Set to time of click to test for bold click
		self.gridDragStart = None # Set to location of click during drag
		self.clocksPerDivision = 24
		self.icon = [tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage()]
		self.cells = [[None] * 2 for _ in range(self.verticalZoom * self.horizontalZoom)] # 2D array of cells 0:cell, 1:cell label
		self.redraw_pending = 0

		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height
		self.timebaseTrackHeight = int(self.height / 10)
		self.smallFontSize = int(self.timebaseTrackHeight / 3);
		self.selectThickness = 1 + int(self.width / 500) # Scale thickness of select border based on screen resolution
		self.gridHeight = self.height - self.timebaseTrackHeight
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
		self.trackTitleCanvas.grid(column=1, row=0)

		# Create grid canvas
		self.gridCanvas = tkinter.Canvas(self.main_frame, 
			width=self.gridWidth, 
			height=self.gridHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.gridCanvas.grid(column=2, row=0)
		self.gridCanvas.bind("<ButtonPress-1>", self.parent.hideMenu)

		# Create pattern entry indicator
		self.patternCanvas = tkinter.Canvas(self.main_frame,
			width=self.trackTitleWidth,
			height=self.timebaseTrackHeight,
			bg=CELL_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.patternCanvas.create_text(self.trackTitleWidth / 2, self.timebaseTrackHeight / 2, tags="patternIndicator", fill='white', text='%d'%(self.pattern), font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=int(0.9 * self.timebaseTrackHeight)))
		self.patternCanvas.grid(column=1, row=1)
		self.patternCanvas.bind('<ButtonPress-1>', self.onPatternClick)

		# Create timebase track canvas
		self.timebasetrackCanvas = tkinter.Canvas(self.main_frame,
			width=self.gridWidth, 
			height=self.timebaseTrackHeight,
			bg=CANVAS_BACKGROUND,
			bd=0,
			highlightthickness=0)
		self.timebasetrackCanvas.bind("<ButtonPress-1>", self.onTimeDragStart)
		self.timebasetrackCanvas.bind("<ButtonRelease-1>", self.onTimeDragEnd)
		self.timebasetrackCanvas.bind("<B1-Motion>", self.onTimeDragMotion)
		self.timebasetrackCanvas.grid(column=2, row=1)


	# Function to load and resize icons
	def loadIcons(self):
		if self.rowHeight > self.trackTitleWidth / 3:
			iconHeight = self.trackTitleWidth / 3
		else:
			iconHeight = self.rowHeight
		iconsize = (int(iconHeight), int(iconHeight))
		img = (Image.open("/zynthian/zynthian-ui/icons/endnoline.png").resize(iconsize))
		self.icon[1] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loop.png").resize(iconsize))
		self.icon[2] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/end.png").resize(iconsize))
		self.icon[3] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loopstop.png").resize(iconsize))
		self.icon[4] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/end.png").resize(iconsize))
		self.icon[5] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loopstop.png").resize(iconsize))
		self.icon[6] = ImageTk.PhotoImage(img)

	# Function to register encoders
	def setupEncoders(self):
		self.parent.registerZyncoder(ENC_BACK, self)
		self.parent.registerZyncoder(ENC_SELECT, self)
		self.parent.registerZyncoder(ENC_LAYER, self)
		self.parent.registerSwitch(ENC_SELECT, self, 'S')
		self.parent.registerSwitch(ENC_SELECT, self, 'B')

	# Function to populate menu
	def populateMenu(self):
		# Only show song editor menu entries if we have a song selected
		self.parent.addMenu({'Copy song':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':self.copySource, 'onChange':self.onMenuChange,'onAssert':self.copySong}}})
		self.parent.addMenu({'Clear song':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':1, 'value':0, 'onChange':self.onMenuChange, 'onAssert':self.clearSong}}})
		self.parent.addMenu({'Vertical zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':64, 'value':self.verticalZoom, 'onChange':self.onMenuChange,'onAssert':self.assertAndRedraw}}})
		self.parent.addMenu({'Horizontal zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999 
		, 'value':64, 'onChange':self.onMenuChange,'onAssert':self.assertAndRedraw}}})
		self.parent.addMenu({'MIDI channel':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'getValue':self.getTrackChannel, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Tracks':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':64, 'getValue':self.getTracks, 'onChange':self.onMenuChange, 'onAssert':self.setTracks}}})
		self.parent.addMenu({'Tempo':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':999, 'getValue':self.getTempo, 'onChange':self.onMenuChange, 'onAssert':self.assertTempo}}})
		self.parent.addMenu({'Bar / sync':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'getValue':self.getBeatsPerBar, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Group':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':25, 'getValue':self.getGroup, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Mode':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':len(self.playModes)-1, 'getValue':self.getMode, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Trigger':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':128, 'getValue':self.getTrigger, 'onChange':self.onMenuChange, 'onAssert':self.setTrigger}}})
		self.parent.addMenu({'Pattern':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'getValue':self.getPattern, 'onChange':self.onMenuChange}}})

	# Function to show GUI
	#	song: Song to show
	def show(self, params=None):
		if params != None:
			self.editorMode = params
		self.main_frame.tkraise()
		self.selectSong()
#		self.redraw_pending = 2
		self.setupEncoders()

	# Function to hide GUI
	def hide(self):
		#TODO: Move unregisterZyncoder to panel manager
		self.parent.unregisterZyncoder(ENC_BACK)
		self.parent.unregisterZyncoder(ENC_SELECT)
		self.parent.unregisterZyncoder(ENC_LAYER)
#		self.libseq.solo(self.song, 0, False)

	# Function to get tempo at current cursor position
	def getTempo(self):
		return self.libseq.getTempo(self.song, self.selectedCell[0] * self.clocksPerDivision)

	# Function to assert zoom changes and redraw screen
	def assertAndRedraw(self):
		self.updateCellSize()
		self.redraw_pending = 2

	# Function to assert tempo change
	def assertTempo(self):
		value = self.parent.getParam('Tempo', 'value')
		if self.position == self.selectedCell[0]:
			self.libseq.setTempo(value)
		#TODO: Need to use measure + tick to set tempo - and all other song timebase operations
		self.libseq.addTempo(self.song, value, self.selectedCell[0] * self.clocksPerDivision)
		self.redraw_pending = 1

	# Function to get group of selected track
	def getGroup(self):
		sequence = self.libseq.getSequence(self.song, self.selectedCell[1])
		return int(self.libseq.getGroup(sequence))

	# Function to get play mode of selected track
	def getMode(self):
		sequence = self.libseq.getSequence(self.song, self.selectedCell[1])
		return int(self.libseq.getPlayMode(sequence))

	# Function to get trigger note of selected track
	def getTrigger(self):
		sequence = self.libseq.getSequence(self.song, self.selectedCell[1])
		trigger = int(self.libseq.getTriggerNote(sequence))
		if trigger > 127:
			trigger = 128
		return trigger

	# Function to set trigger note of selected track
	def setTrigger(self):
		sequence = self.libseq.getSequence(self.song, self.selectedCell[1])
		self.libseq.setTriggerNote(sequence, self.trigger);
		self.redraw_pending = 1

	# Function to get bar duration
	def getBeatsPerBar(self):
		#TODO: Do we want beats per bar at cursor or play position?
		return int(self.libseq.getBeatsPerBar(self.song, self.song_position))

	# Function to get pattern (to add to song)
	def getPattern(self):
		return self.pattern

	# Function to set pattern (to add to song)
	def setPattern(self, pattern):
		if pattern < 1:
			self.pattern = 1
		else:
			self.pattern = pattern
		self.patternCanvas.itemconfig("patternIndicator", text="%d"%(self.pattern))
		self.parent.setParam('Pattern', 'value', self.pattern)
		self.selectCell()


	# Function to set quantity of tracks in song
	#	tracks: Quantity of tracks in song
	#	Note: Tracks will be deleted from or added to end of track list as necessary
	def setTracks(self):
		tracks = self.parent.getParam('Tracks', 'value')
		# Remove surplus tracks
		while self.libseq.getTracks(self.song) > tracks:
			self.libseq.removeTrack(self.song, tracks)
		# Add extra tracks
		while self.libseq.getTracks(self.song) < tracks:
			track = self.libseq.addTrack(self.song)
			sequence = self.libseq.getSequence(self.song, track)
			if self.editorMode:
				self.libseq.setGroup(sequence, int(track / 4))
				self.libseq.setChannel(sequence, int(track / 4))
				self.libseq.setPlayMode(sequence, 6)
			else:
				if track < 26:
					self.libseq.setGroup(sequence, track)
				if track <= 16:
					self.libseq.setChannel(sequence, track)
				self.libseq.setPlayMode(sequence, 1)
		self.redraw_pending = 2

	# Function to get quantity of tracks in song
	#	returns: Quantity of tracks in song
	def getTracks(self):
		return self.libseq.getTracks(self.song)

	# Function to handle start of track drag
	def onTrackDragStart(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		if self.libseq.getTracks(self.song) > self.verticalZoom:
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
		if pos + self.verticalZoom >= self.libseq.getTracks(self.song):
			pos = self.libseq.getTracks(self.song) - self.verticalZoom
		if self.rowOffset == pos:
			return
		self.rowOffset = pos
		self.redraw_pending = 1
		track=self.selectedCell[1]
		if self.selectedCell[1] < self.rowOffset:
			track = self.rowOffset
		elif self.selectedCell[1] >= self.rowOffset + self.verticalZoom:
			track = self.rowOffset + self.verticalZoom - 1
		self.selectCell(self.selectedCell[0], track)

	# Function to handle end of track drag
	def onTrackDragEnd(self, event):
		self.trackDragStart = None

	# Function to handle start of time drag
	def onTimeDragStart(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
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
		if self.colOffset == pos:
			return
		self.colOffset = pos
		self.redraw_pending = 1
		col = self.selectedCell[0]
		duration = int(self.libseq.getPatternLength(self.pattern) / self.clocksPerDivision)
		if self.selectedCell[0] < self.colOffset:
			self.selectCell(self.colOffset, self.selectedCell[1])
		elif self.selectedCell[0] > self.colOffset + self.horizontalZoom  - duration:
			self.selectCell(self.colOffset + self.horizontalZoom - duration, self.selectedCell[1])
		else:
			self.selectCell()

	# Function to handle end of time drag
	def onTimeDragEnd(self, event):
		self.timeDragStart = None

	# Function to handle grid mouse press
	#	event: Mouse event
	def onGridPress(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		if self.parent.paramEditorItem != None:
			self.parent.hideParamEditor()
			return

		self.gridDragStart = event

		self.gridTimer = Timer(0.4, self.onGridTimer)
		self.gridTimer.start()
		tags = self.gridCanvas.gettags(self.gridCanvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		col, row = tags[0].split(',')
		self.selectCell(self.colOffset + int(col), self.rowOffset + int(row), False)

	# Function to handle grid mouse release
	#	event: Mouse event
	def onGridRelease(self, event):
		self.gridTimer.cancel()
		if not self.gridDragStart:
			return
		self.gridDragStart = None

		self.toggleEvent(self.selectedCell[0], self.selectedCell[1])

	# Function to handle grid mouse motion
	#	event: Mouse event
	def onGridMotion(self, event):
		if self.gridDragStart == None:
			return
		col = self.colOffset + int(event.x / self.columnWidth)
		row = self.rowOffset + int(event.y / self.rowHeight)
		if col != self.selectedCell[0] or row != self.selectedCell[1]:
			self.gridTimer.cancel()
			self.gridDragStart.x = event.x
			self.gridDragStart.y = event.y
			self.selectCell(col, row, False)

	# Function to handle grid press and hold
	def onGridTimer(self):
		self.gridDragStart = None
		self.showPatternEditor()

	# Function to show pattern editor
	def showPatternEditor(self):
		track = self.rowOffset + self.selectedCell[1]
		time = self.selectedCell[0] * self.clocksPerDivision # time in clock cycles
		sequence = self.libseq.getSequence(self.song, track)
		pattern = self.libseq.getPattern(sequence, time)
		channel = self.libseq.getChannel(sequence)
		if pattern > 0:
			self.parent.showChild(0, {'pattern':pattern, 'channel':channel})

	# Function to handle pattern click
	#	event: Mouse event
	def onPatternClick(self, event):
		self.populateMenu() # Probably better way but this ensures 'Pattern' is in the menu
		self.parent.showParamEditor('Pattern')

	# Function to toggle note event
	#	col: Column
	#	track: Track number
	def toggleEvent(self, div, track):
		time = div * self.clocksPerDivision
		sequence = self.libseq.getSequence(self.song, track)
		if self.libseq.getPattern(sequence, time) == -1:
			self.addEvent(div, track)
		else:
			self.removeEvent(div, track)
		self.selectCell(div, track)

	# Function to remove an event
	#	div: Time division index (column + columun offset)
	#	track: Track number
	def removeEvent(self, div, track):
		time = div * self.clocksPerDivision
		sequence = self.libseq.getSequence(self.song, track)
		self.libseq.removePattern(sequence, time)
		self.drawTrack(track)

	# Function to add an event
	#	div: Time division index (column + columun offset)
	#	track: Track number
	def addEvent(self, div, track):
		time = div * self.clocksPerDivision
		sequence = self.libseq.getSequence(self.song, track)
		if self.libseq.addPattern(sequence, time, self.pattern, False):
			self.drawTrack(track)

	# Function to draw track
	#	track: Track index
	def drawTrack(self, track):
		self.drawRow(track - self.rowOffset)

	# Function to draw track label
	#	track: Track index
	def drawTrackLabel(self, track):
		row = track - self.rowOffset
		sequence = self.libseq.getSequence(self.song, track)
		channel = self.libseq.getChannel(sequence) + 1
		group = self.libseq.getGroup(sequence)
		mode = self.libseq.getPlayMode(sequence)

		self.trackTitleCanvas.delete('rowtitle:%d'%(row))
		self.trackTitleCanvas.delete('rowicon:%d'%(row))
		self.trackTitleCanvas.delete('rowback:%d'%(row))
		titleBack = self.trackTitleCanvas.create_rectangle(0, self.rowHeight * row, self.trackTitleWidth, (1 + row) * self.rowHeight, tags=('rowback:%d'%(row), 'tracktitle'))
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		title = self.trackTitleCanvas.create_text((0, self.rowHeight * (row + 0.5)), font=font, fill=CELL_FOREGROUND, tags=("rowtitle:%d" % (row),"trackname", 'tracktitle'), anchor="w")
		modeIcon = self.trackTitleCanvas.create_image(self.trackTitleWidth, row * self.rowHeight, anchor='ne', tags=('rowicon:%d'%(row), 'tracktitle'))

		trigger = self.libseq.getTriggerNote(sequence)
		if trigger < 128:
			self.trackTitleCanvas.itemconfig(title, text="%s%d (%d,%s)" % (chr(65+group), track + 1, channel, self.getNote(trigger)))
		else:
			self.trackTitleCanvas.itemconfig(title, text="%s%d (%d)" % (chr(65+group), track + 1, channel))
		self.trackTitleCanvas.itemconfig(modeIcon, image=self.icon[mode])
		if group % 2:
			fill = self.padColourStoppedOdd
		else:
			fill = self.padColourStoppedEven
		self.trackTitleCanvas.itemconfig(titleBack, fill=fill)
		self.trackTitleCanvas.tag_bind('tracktitle', "<Button-1>", self.onTrackClick)

	# Function to draw a grid row
	#	row: Grid row to draw
	#	redrawTrackTitles: True to redraw track titles (Default: True)
	def drawRow(self, row, redrawTrackTitles = True):
		if row + self.rowOffset >= self.libseq.getTracks(self.song):
			return
		track = self.rowOffset + row
		if(redrawTrackTitles):
			self.drawTrackLabel(track)

		for col in range(self.horizontalZoom):
			self.drawCell(col, row)

	# Function to handle track title click
	def onTrackClick(self, event):
		tags = self.trackTitleCanvas.gettags(self.trackTitleCanvas.find_withtag(tkinter.CURRENT))
		if not tags:
			return
		dummy, row = tags[0].split(':')
		track = int(row) + self.rowOffset
		sequence = self.libseq.getSequence(self.song, track)
		print("Song %d, track %d, sequence:%d, trigger:%d, playstate:%d"%(self.song, track, sequence, self.libseq.getTriggerNote(sequence), self.libseq.getPlayState(sequence)))
		self.selectedCell[1] = track
		self.selectCell()

	# Function to get cell coordinates
	#	col: Column index
	#	row: Row index
	#	duration: Duration of cell in time divisions
	#	return: Coordinates required to draw cell
	def getCellCoord(self, col, row, duration):
		x1 = col * self.columnWidth + 1
		y1 = self.rowHeight * row + 1
		x2 = x1 + self.columnWidth * duration - 1 
		y2 = y1 + self.rowHeight - 1
		return [x1, y1, x2, y2]

	# Function to draw a grid cell
	#	col: Column index
	#	row: Row index
	def drawCell(self, col, row):
		cellIndex = row * self.horizontalZoom + col # Cells are stored in array sequentially: 1st row, 2nd row...
		if cellIndex >= len(self.cells):
			return

		track = self.rowOffset + row
		time = (self.colOffset + col) * self.clocksPerDivision # time in clock cycles
		sequence = self.libseq.getSequence(self.song, track)

		pattern = self.libseq.getPattern(sequence, time)
		if pattern == -1:
			fill = CANVAS_BACKGROUND
			duration = 1
			if col == 0:
				for t in range(time, -1, -self.clocksPerDivision):
					pattern = self.libseq.getPattern(sequence, t)
					if pattern != -1:
						duration = int((self.libseq.getPatternLength(pattern) + t) / self.clocksPerDivision) - self.colOffset
						if duration > 0:
							fill = CELL_BACKGROUND
						else:
							pattern = -1
						break
		else:
			duration = int(self.libseq.getPatternLength(pattern) / self.clocksPerDivision)
			fill = CELL_BACKGROUND
			#print("Drawing cell %d,%d for track %d, sequence %d, pattern %d, duration %d"%(col,row,track,sequence,pattern,duration))
		if col + duration > self.colOffset + self.horizontalZoom:
			duration = self.colOffset + self.horizontalZoom - col
		if duration < 1:
			duration = 1

		#print("draw cell time=%d track=%d col=%d row=%d sequence=%d pattern=%d, duration=%d" % (time,track,col, row, sequence, pattern, duration))
		cell = self.cells[cellIndex][0]
		celltext = self.cells[cellIndex][1]
		coord = self.getCellCoord(col, row, duration)
		if not cell:
			# Create new cell
			cell = self.gridCanvas.create_rectangle(coord, fill=fill, width=0, tags=("%d,%d"%(col,row), "gridcell"))
			celltext = self.gridCanvas.create_text(coord[0] + 1, coord[1] + self.rowHeight / 2, fill=CELL_FOREGROUND, tags=("celltext:%d,%d"%(col,row)))
			self.gridCanvas.tag_bind(cell, '<ButtonPress-1>', self.onGridPress)
			self.gridCanvas.tag_bind(cell, '<ButtonRelease-1>', self.onGridRelease)
			self.gridCanvas.tag_bind(cell, '<B1-Motion>', self.onGridMotion)
			self.gridCanvas.tag_lower(cell) # Assume cells are always created left to right
			self.cells[cellIndex][0] = cell
			self.cells[cellIndex][1] = celltext
		# Update existing cell
		else:
			self.gridCanvas.itemconfig(cell, fill=fill)
			self.gridCanvas.coords(cell, coord)
		if pattern == -1:
			self.gridCanvas.itemconfig(celltext, state='hidden')
		else:
			self.gridCanvas.itemconfig(celltext, text=pattern, state='normal', font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize))
			self.gridCanvas.coords(celltext, coord[0] + int(duration * self.columnWidth / 2), int(coord[1] + self.rowHeight / 2))
#		if time + duration > self.horizontalZoom:
#			if duration > 1:
#				self.gridCanvas.itemconfig("lastpatterntext%d" % row, text="+%d" % (duration - self.libseq.getPatternLength() + time), state="normal")

	# Function to draw grid
	def drawGrid(self):
		if self.redraw_pending == 2:
			self.gridCanvas.delete(tkinter.ALL)
			self.trackTitleCanvas.delete(tkinter.ALL)
			self.columnWidth = self.gridWidth / self.horizontalZoom
			self.gridCanvas.create_line(0, 0, 0, self.gridHeight, fill=PLAYHEAD_CURSOR, tags='playheadline')
			self.cells = [[None] * 2 for _ in range(self.verticalZoom * self.horizontalZoom)]
			self.selectCell()
		self.redraw_pending = 0

		# Draw rows of grid
		self.gridCanvas.itemconfig("gridcell", fill=CANVAS_BACKGROUND)
		for row in range(self.verticalZoom):
			if row >= self.libseq.getTracks(self.song):
				break
			self.drawRow(row, True)

		# Vertical (bar / sync) lines
		self.gridCanvas.delete('barlines')
		self.timebasetrackCanvas.delete('barlines')
		font = tkFont.Font(size=self.smallFontSize)
		tempoY = font.metrics('linespace')
		offset = 0 - int(self.colOffset % self.horizontalZoom)
		for bar in range(offset, self.horizontalZoom, int(self.libseq.getBarLength(self.song) / self.clocksPerDivision)):
			self.gridCanvas.create_line(bar * self.columnWidth, 0, bar * self.columnWidth, self.gridHeight, fill='white', tags='barlines')
			if bar:
				self.timebasetrackCanvas.create_text(bar * self.columnWidth, 0, fill='white', text="%d"%(bar+self.colOffset), anchor='n', tags='barlines')
			else:
				self.timebasetrackCanvas.create_text(bar * self.columnWidth, 0, fill='white', text="%d"%(bar+self.colOffset), anchor='nw', tags='barlines')

		# Hide selection if not in view - #TODO: WHEN WOULD THAT BE???
		if self.selectedCell[0] < self.colOffset or self.selectedCell[0] > self.colOffset + self.horizontalZoom or self.selectedCell[1] < self.rowOffset or self.selectedCell[1] > self.rowOffset + self.verticalZoom:
			self.gridCanvas.itemconfig('selection', state='hidden')

		# Timebase track
		self.timebasetrackCanvas.delete('bpm')
		print("Drawing timebase track")
		for event in range(self.libseq.getTimebaseEvents(self.song)):
			time = self.libseq.getTimebaseEventTime(self.song, event) / self.clocksPerDivision
			if time >= self.colOffset and time <= self.colOffset + self.horizontalZoom:
				command = self.libseq.getTimebaseEventCommand(self.song, event)
				if command == 1: # Tempo
					tempoX = (time - self.colOffset) * self.columnWidth
					data = self.libseq.getTimebaseEventData(self.song, event)
					if tempoX:
						self.timebasetrackCanvas.create_text(tempoX, tempoY, fill='red', text=data, anchor='n', tags='bpm')
					else:
						self.timebasetrackCanvas.create_text(tempoX, tempoY, fill='red', text=data, anchor='nw', tags='bpm')

	# Function to select a cell within the grid
	#	time: Time (column) of selected cell (Optional - default to reselect current column)
	#	track: Track number of selected cell (Optional - default to reselect current row)
	#	snap: True to snap to closest pattern (Optional - default True)
	def selectCell(self, time=None, track=None, snap=True):
		if time == None:
			time = self.selectedCell[0]
		if track == None:
			track = self.selectedCell[1]
		duration = int(self.libseq.getPatternLength(self.pattern) / self.clocksPerDivision)
		if not duration:
			duration = 1
		forward = time > self.selectedCell[0]
		backward = None
		if time < self.selectedCell[0]:
			backward = time
		# Skip cells if pattern won't fit
		if snap:
			sequence = self.libseq.getSequence(self.song, track)
			prevStart = 0
			prevEnd = 0
			nextStart = time
			for previous in range(time - 1, -1, -1):
				# Iterate time divs back to start
				prevPattern = self.libseq.getPattern(sequence, previous * self.clocksPerDivision)
				if prevPattern == -1:
					continue
				prevDuration = int(self.libseq.getPatternLength(prevPattern, track) / self.clocksPerDivision)
				prevStart = previous
				prevEnd = prevStart + prevDuration
				break
			for next in range(time + 1, time + duration * 2):
				nextPattern = self.libseq.getPattern(sequence, next * self.clocksPerDivision)
				if nextPattern == -1:
					continue
				nextStart = next
				break
			if nextStart < prevEnd:
				nextStart = prevEnd
			if time >= prevEnd and time < nextStart:
				# Between patterns
				if time + duration > nextStart:
					# Insufficient space for new pattern between pattern
					if forward:
						time = nextStart
					else:
						if nextStart - prevEnd < duration:
							time = prevStart
						else:
							time = nextStart - duration
			elif time == prevStart:
				# At start of previous
				pass
			elif time > prevStart and time < prevEnd:
				# Within pattern
				if forward:
					if prevEnd + duration > nextStart:
						time = nextStart
					else:
						time = prevEnd
				else:
					time = prevStart
			if time == 0 and duration > nextStart:
				time = nextStart

		if track >= self.libseq.getTracks(self.song):
			track = self.libseq.getTracks(self.song) - 1;
		if track < 0:
			track = 0
		if time < 0:
			time = 0
		if time < 0:
			time = 0;
		if time + duration > self.colOffset + self.horizontalZoom:
			# time is off right of display
			self.colOffset = time + duration - self.horizontalZoom
			self.redraw_pending = 1
		if time < self.colOffset:
			# time is off left of display
			self.colOffset = time
			self.redraw_pending = 1
		if track >= self.rowOffset + self.verticalZoom:
			# track is off bottom of display
			self.rowOffset = track - self.verticalZoom + 1
			self.redraw_pending = 1
		elif track < self.rowOffset:
			self.rowOffset = track
			self.redraw_pending = 1
		if backward != None and self.colOffset > 0 and time > backward:
			self.colOffset = self.colOffset - 1
			self.redraw_pending = 1
		self.selectedCell = [time, track]
		coord = self.getCellCoord(time - self.colOffset, track - self.rowOffset, duration)
		coord[0] = coord[0] - 1
		coord[1] = coord[1] - 1
		coord[2] = coord[2]
		coord[3] = coord[3]
		selection_border = self.gridCanvas.find_withtag("selection")
		if not selection_border:
			selection_border = self.gridCanvas.create_rectangle(coord, fill="", outline=SELECT_BORDER, width=self.selectThickness, tags="selection")
		else:
			self.gridCanvas.coords(selection_border, coord)
		self.gridCanvas.itemconfig(selection_border, state='normal')
		self.gridCanvas.tag_raise(selection_border)

#		if self.song > 1000: # Solo will stop playback which may be undesirable
#			self.libseq.solo(self.song, track, True)


	# Function to calculate cell size
	def updateCellSize(self):
		self.rowHeight = (self.gridHeight - 2) / self.verticalZoom
		self.columnWidth = self.gridWidth / self.horizontalZoom
		self.fontsize = int(self.rowHeight * 0.4)
		if self.fontsize > self.trackTitleWidth * 0.15:
			self.fontsize = int(self.trackTitleWidth * 0.15) # Ugly font scale limiting
		self.loadIcons()

	# Function to clear song
	def clearSong(self):
		self.libseq.clearSong(self.song)
		self.redraw_pending = 2
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()
		self.selectCell(0,0)

	# Function to copy song
	def copySong(self):
		if(self.song > 1000):
			self.libseq.copySong(self.copySource + 1000, self.song);
		else:
			self.libseq.copySong(self.copySource, self.song);
		self.selectSong()

	# Function to handle menu editor value change and get display label text
	#	params: Menu item's parameters
	#	returns: String to populate menu editor label
	#	note: params is a dictionary with required fields: min, max, value
	def onMenuChange(self, params):
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		menuItem = self.parent.paramEditorItem
		self.parent.setParam(menuItem, 'value', value)
		if menuItem == 'Clear song':
			return "Clear song %d?" % (self.song)
		elif menuItem =='Copy song':
			self.libseq.selectSong(value) 
			self.selectSong(False)
			return "Copy %d=>%d?" % (self.copySource, value)
		elif menuItem == 'Vertical zoom':
			self.verticalZoom = value
		elif menuItem == 'Horizontal zoom':
			self.horizontalZoom = value
		elif menuItem == 'MIDI channel':
			self.parent.setParam(menuItem, 'value', value)
			track = self.selectedCell[1] + self.rowOffset
			sequence = self.libseq.getSequence(self.song, track)
			self.libseq.setChannel(sequence, value - 1)
			self.drawTrack(self.selectedCell[1])
		elif menuItem == 'Tempo':
			pass
		elif menuItem == 'Bar / sync':
			self.libseq.setBeatsPerBar(self.song, value)
			if self.editorMode:
				self.libseq.setBeatsPerBar(self.song - 1000, value)
			else:
				self.libseq.setBeatsPerBar(self.song + 1000, value)
			self.redraw_pending = 1
		elif menuItem == "Group":
			sequence = self.libseq.getSequence(self.song, self.selectedCell[1])
			self.libseq.setGroup(sequence, value);
			self.drawTrackLabel(self.selectedCell[1])
			return "Group: %s" % (chr(65 + value))
		elif menuItem == "Mode":
			sequence = self.libseq.getSequence(self.song, self.selectedCell[1])
			self.libseq.setPlayMode(sequence, value);
			self.drawTrackLabel(self.selectedCell[1])
			return "Mode: %s" % (self.playModes[value])
		elif menuItem == "Trigger":
			self.trigger = value
			sequence = self.libseq.getSequence(self.song, self.selectedCell[1])
			self.libseq.setTriggerNote(sequence, self.trigger);
			self.drawTrackLabel(self.selectedCell[1])
			if value > 127:
				return "Trigger: None"
			else:
				return "Trigger: %s" % self.getNote(value)
		elif menuItem == "Pattern":
			self.setPattern(value)
#		elif menuItem == "Tracks":
#			self.setTracks(value)
		return "%s: %d" % (menuItem, value)

	# Function to get (note name, octave)
	#	note: MIDI note number
	#	returns: String containing note name and octave number, e.g. "C#4"
	def getNote(self, note):
		notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
		noteName = notes[note % 12]
		octave = int(note / 12) - 1
		return "%s%d" % (noteName, octave)

	# Function to get MIDI channel of selected track
	#	returns: MIDI channel
	def getTrackChannel(self):
		track = self.selectedCell[1]
		sequence = self.libseq.getSequence(self.song, track)
		channel = self.libseq.getChannel(sequence) + 1
		return channel

	# Function to display song
	def selectSong(self, updateCopySource = True):
		song = self.libseq.getSong()
		if song != 0:
			self.song = song
		if self.editorMode:
			self.parent.setTitle("Pad Editor (%d)" % (self.song))
			self.song = self.song + 1000
		else:
			self.parent.setTitle("Song Editor (%d)" % (self.song))
#			self.libseq.solo(self.song + 1000, 0, False) # Clear solo from pad editor when switching to song editor
		if updateCopySource:
			if self.song > 1000:
				self.copySource = self.song - 1000
			else:
				self.copySource = self.song
		self.redraw_pending = 2

	# Function called when new file loaded from disk
	def onLoad(self):
		#TODO: Redraw song
		pass

	# Function to scroll grid to show position in song
	#	pos: Song position in divisions
	def showPos(self, pos):
		if pos >= self.colOffset and pos < self.colOffset + self.horizontalZoom:
			return
		self.colOffset = int(pos)
		self.position = int(pos)
		if self.colOffset < 0:
			self.colOffset = 0
		self.redraw_pending = 1

	# Function to refresh playhead
	def refresh_status(self):
		if self.redraw_pending:
			self.drawGrid()
#		if self.song < 1000:
#			pos = self.libseq.getSongPosition()# / self.clocksPerDivision
#		else:
#			sequence = self.libseq.getSequence(self.song, self.selectedCell[1]) #TODO: Offset?
#			pos = self.libseq.getPlayPosition(sequence)# / self.clocksPerDivision
#		if self.position != pos:
#			self.showPos(pos)
#			self.position = pos
#		self.gridCanvas.coords('playheadline', (pos - self.colOffset) * self.columnWidth, 0, (pos - self.colOffset) * self.columnWidth, self.gridHeight)

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
			time = self.selectedCell[0] + value
			self.selectCell(time, self.selectedCell[1])
		elif encoder == ENC_LAYER:
			self.setPattern(self.pattern + value)

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def onSwitch(self, switch, type):
		if switch == ENC_SELECT and type == 'B':
			self.showPatternEditor()
		elif switch == ENC_SELECT:
			self.toggleEvent(self.selectedCell[0], self.selectedCell[1])
		else:
			return False
		return True
#------------------------------------------------------------------------------
