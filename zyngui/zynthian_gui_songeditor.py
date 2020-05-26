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

		self.verticalZoom = 16 # Quantity of rows (tracks) displayed in grid
		self.horizontalZoom = 64 # Quantity of columns (time divisions) displayed in grid
		self.copySource = 1 # Index of song to copy
		self.song = 0 # Index of current song
		self.rowOffset = 0 # Index of track at top row in grid
		self.colOffset = 0 # Index of time division at left column in grid
		self.selectedCell = [0, 0] # Location of selected cell (time div,track)
		self.pattern = 1 # Index of current pattern to add to sequence
		self.duration = 128 #TODO Get duration from song sequences
		self.position = 0 # Current playhead position
		#TODO: Populate tracks from file
		self.trackDragStart = None
		self.timeDragStart = None
		self.clocksPerDivision = 6

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

		# Create pattern entry indicator
		self.patternCanvas = tkinter.Canvas(self.main_frame,
			width=self.trackTitleWidth,
			height=PLAYHEAD_HEIGHT,
			bg=CELL_BACKGROUND,
			bd=0,
			highlightthickness=0,
			)
		self.patternCanvas.create_text(self.trackTitleWidth / 2, PLAYHEAD_HEIGHT / 2, tags="patternIndicator", fill='white', text='%d'%(self.pattern))
		self.patternCanvas.grid(column=0, row=1)

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
		self.playCanvas.grid(column=1, row=1)

		self.selectSong(1)

	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		self.parent.registerZyncoder(ENC_BACK, self)
		self.parent.registerZyncoder(ENC_SELECT, self)
		self.parent.registerZyncoder(ENC_SNAPSHOT, self)
		self.parent.registerZyncoder(ENC_LAYER, self)

	# Function to populate menu
	def populateMenu(self):
		self.parent.addMenu({'Song':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':999, 'value':1, 'onChange':self.onMenuChange}}})
		if self.song:
			# Only show song editor menu entries if we have a song selected
			self.parent.addMenu({'Copy song':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':1, 'onChange':self.onMenuChange,'onAssert':self.copySong}}})
			self.parent.addMenu({'Clear song':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':1, 'value':0, 'onChange':self.onMenuChange, 'onAssert':self.clearSong}}})
			self.parent.addMenu({'Transpose song':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':2, 'value':1, 'onChange':self.onMenuChange}}})
			self.parent.addMenu({'Vertical zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':64, 'value':self.parent.libseq.getTracks(self.song), 'getValue':self.parent.libseq.getTracks, 'onChange':self.onMenuChange}}})
			self.parent.addMenu({'Horizontal zoom':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':128, 'value':64, 'onChange':self.onMenuChange}}})
			self.parent.addMenu({'MIDI channel':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'value':1, 'getValue':self.getTrackChannel, 'onChange':self.onMenuChange}}})
			self.parent.addMenu({'Clocks per division':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':24, 'value':6, 'getValue':self.getClocksPerDivision, 'onChange':self.onMenuChange}}})
			self.parent.addMenu({'Add track':{'method':self.addTrack}})
			self.parent.addMenu({'Remove track':{'method':self.removeTrack}})
			self.parent.addMenu({'Tempo':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':999, 'value':self.zyngui.zyntransport.get_tempo(), 'getValue':self.zyngui.zyntransport.get_tempo, 'onChange':self.onMenuChange}}})
			self.parent.addMenu({'Bar / loop':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':16, 'getValue':self.getBarLength, 'onChange':self.onMenuChange}}})


	# Function to show GUI
	def show(self):
		self.populateMenu()
		self.main_frame.tkraise()
		self.setupEncoders()
		self.parent.setTitle("Song Editor (%d)" % (self.song))
		self.parent.libseq.selectSong(self.song)

	# Function to hide GUI
	def hide(self):
		self.parent.unregisterZyncoder(ENC_BACK)
		self.parent.unregisterZyncoder(ENC_SELECT)
		self.parent.unregisterZyncoder(ENC_SNAPSHOT)
		self.parent.unregisterZyncoder(ENC_LAYER)

	# Function to get bar duration
	def getBarLength(self):
		return int(self.parent.libseq.getBarLength(self.song) / self.clocksPerDivision)

	# Function to add track
	#	params: Dictionary of parameters (not used)
	def addTrack(self, params):
		self.parent.libseq.addTrack(self.song)
		self.drawGrid(True)

	# Function to add track
	#	params: Dictionary of parameters (not used)
	def removeTrack(self, params):
		self.parent.libseq.removeTrack(self.song, self.selectCell[1])
		self.drawGrid(True)

	# Function to handle start of track drag
	def onTrackDragStart(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		if self.parent.libseq.getTracks(self.song) > self.verticalZoom:
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
		if pos + self.verticalZoom >= self.parent.libseq.getTracks(self.song):
			pos = self.parent.libseq.getTracks(self.song) - self.verticalZoom
		if self.rowOffset == pos:
			return
		self.rowOffset = pos
		self.drawGrid()
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
		col, row = tags[0].split(',')
		self.toggleEvent(self.colOffset + int(col), self.rowOffset + int(row))

	# Function to toggle note event
	#	col: Column
	#	track: Track number
	def toggleEvent(self, div, track):
		time = div * self.clocksPerDivision
		sequence = self.parent.libseq.getSequence(self.song, track)
		if self.parent.libseq.getPattern(sequence, time) == -1:
			self.addEvent(div, track)
		else:
			self.removeEvent(div, track)
		self.selectCell(div, track)

	# Function to remove an event
	#	div: Time division index (column + columun offset)
	#	track: Track number
	def removeEvent(self, div, track):
		time = div * self.clocksPerDivision
		sequence = self.parent.libseq.getSequence(self.song, track)
		print("Remove pattern %d from track %d (seq %d) at time %d (clocks)"%(self.parent.libseq.getPattern(sequence, time),track, sequence, time))
		self.parent.libseq.removePattern(sequence, time)
		self.drawTrack(track)

	# Function to add an event
	#	div: Time division index (column + columun offset)
	#	track: Track number
	def addEvent(self, div, track):
		time = div * self.clocksPerDivision
		sequence = self.parent.libseq.getSequence(self.song, track)
		self.parent.libseq.addPattern(sequence, time, self.pattern)
		print("Add pattern %d to sequence %d (track %d) at time %d"%(self.pattern, sequence, track, time))
		self.drawTrack(track)

	# Function to draw track
	#	track: Track index
	def drawTrack(self, track):
		self.drawRow(track - self.rowOffset)

	# Function to draw a grid row
	#	row: Grid row to draw
	def drawRow(self, row):
		if row + self.rowOffset >= self.parent.libseq.getTracks(self.song):
			return
		track = self.rowOffset + row
		sequence = self.parent.libseq.getSequence(self.song, track)
		channel = self.parent.libseq.getChannel(sequence) + 1
		self.trackTitleCanvas.itemconfig("rowtitle%d" % (row), text="Track %d (%d)" % (track + 1, channel))
#		self.gridCanvas.itemconfig("lastpatterntext%d" % (row), state="hidden")
		for col in range(self.horizontalZoom):
			self.drawCell(col, row)
			cell = self.gridCanvas.find_withtag("%d,%d"%(col,row))
			if cell:
				self.gridCanvas.tag_lower(cell)

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
		if col < 0 or col >= self.horizontalZoom or row < 0 or row >= self.verticalZoom:
			return

		track = self.rowOffset + row
		time = (self.colOffset + col) * self.clocksPerDivision # time in clock cycles
		sequence = self.parent.libseq.getSequence(self.song, track)

		pattern = self.parent.libseq.getPattern(sequence, time)
		if pattern == -1:
			fill = CANVAS_BACKGROUND
			duration = 1
			if col == 0:
				for t in range(time, -1, -self.clocksPerDivision):
					pattern = self.parent.libseq.getPattern(sequence, t)
					if pattern != -1:
						duration = int((self.parent.libseq.getPatternLength(pattern) + t) / int(self.getClocksPerDivision())) - self.colOffset
						if duration > 0:
							fill = CELL_BACKGROUND
						else:
							pattern = -1
						break
		else:
			duration = int(self.parent.libseq.getPatternLength(pattern) / int(self.getClocksPerDivision()))
			fill = CELL_BACKGROUND
			#print("Drawing cell %d,%d for track %d, sequence %d, pattern %d, duration %d"%(col,row,track,sequence,pattern,duration))
		if col + duration > self.colOffset + self.horizontalZoom:
			duration = self.colOffset + self.horizontalZoom - col
		if duration < 1:
			duration = 1

		#print("draw cell time=%d track=%d col=%d row=%d sequence=%d pattern=%d, duration=%d" % (time,track,col, row, sequence, pattern, duration))
		cell = self.gridCanvas.find_withtag("%d,%d"%(col,row))
		celltext = self.gridCanvas.find_withtag("celltext:%d,%d"%(col,row))
		coord = self.getCellCoord(col, row, duration)
		if not cell:
			# Create new cell
			cell = self.gridCanvas.create_rectangle(coord, fill=fill, width=0, tags=("%d,%d"%(col,row), "gridcell"))
			celltext = self.gridCanvas.create_text(coord[0] + 1, coord[1] + self.rowHeight / 2, fill=CELL_FOREGROUND, tags=("celltext:%d,%d"%(col,row)))
			self.gridCanvas.tag_bind(cell, '<Button-1>', self.onCanvasClick)
		# Update existing cell
		self.gridCanvas.itemconfig(cell, fill=fill)
		self.gridCanvas.coords(cell, coord)
		if pattern == -1:
			self.gridCanvas.itemconfig(celltext, state='hidden')
		else:
			self.gridCanvas.itemconfig(celltext, text=pattern, state='normal', font=tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize))
			self.gridCanvas.coords(celltext, coord[0] + int(duration * self.columnWidth / 2), int(coord[1] + self.rowHeight / 2))
#		if time + duration > self.horizontalZoom:
#			if duration > 1:
#				self.gridCanvas.itemconfig("lastpatterntext%d" % row, text="+%d" % (duration - self.parent.libseq.getPatternLength() + time), state="normal")

	# Function to draw grid
	#	clearGrid: True to clear grid and create all new elements, False to reuse existing elements if they exist
	def drawGrid(self, clearGrid = False):
		font = tkFont.Font(family=zynthian_gui_config.font_topbar[0], size=self.fontsize)
		if clearGrid:
			self.gridCanvas.delete(tkinter.ALL)
			self.columnWidth = self.gridWidth / self.horizontalZoom
			self.trackTitleCanvas.delete("trackname")
			self.gridCanvas.create_line(0, 0, 0, self.gridHeight, fill='red', tags='playheadline')

		print("drawGrid: A")

		# Draw cells of grid
		self.gridCanvas.itemconfig("gridcell", fill=CANVAS_BACKGROUND)
		for row in range(self.verticalZoom):
			if row >= self.parent.libseq.getTracks(self.song):
				break
			if clearGrid:
				self.trackTitleCanvas.create_text((0, self.rowHeight * (row + 0.5)), text="Track %d" % (self.rowOffset - row + 1), font=font, fill=CELL_FOREGROUND, tags=("rowtitle%d" % (row),"trackname"), anchor="w")
#				self.gridCanvas.create_text(self.gridWidth - self.selectThickness, self.rowHeight * (self.rowHeight * int(row + 0.5)), state="hidden", tags=("lastpatterntext%d" % (row), "lastpatterntext"), font=font, anchor="e")
			self.drawRow(row)
		print("drawGrid: B")
		self.gridCanvas.delete('barlines')
		self.playCanvas.delete('barlines')
		offset = 0 - int(self.colOffset % self.horizontalZoom)
		print("drawGrid: offset:%d horZoom:%d barLen:%d, clk/div:%d"%(offset, self.horizontalZoom, self.parent.libseq.getBarLength(self.song), self.getClocksPerDivision()))
		for bar in range(offset, self.horizontalZoom, int(self.parent.libseq.getBarLength(self.song) / self.getClocksPerDivision())):
			self.gridCanvas.create_line(bar * self.columnWidth, 0, bar * self.columnWidth, self.gridHeight, fill='white', tags='barlines')
			self.playCanvas.create_text(bar * self.columnWidth, PLAYHEAD_HEIGHT / 2, fill='white', text="%d"%(bar+self.colOffset), tags='barlines')

		print("drawGrid: D")
		if self.selectedCell[0] < self.colOffset or self.selectedCell[0] > self.colOffset + self.horizontalZoom or self.selectedCell[1] < self.rowOffset or self.selectedCell[1] > self.rowOffset + self.verticalZoom:
			self.gridCanvas.itemconfig('selection', state='hidden')

#		if clearGrid:
#			for time in range(self.horizontalZoom):
#				self.gridCanvas.tag_lower("time%d"%time)

	# Function to update selectedCell
	#	time: Time (column) of selected cell (Optional - default to reselect current column)
	#	track: Track number of selected cell (Optional - default to reselect current row)
	def selectCell(self, time=None, track=None):
		redraw = False
		if time == None:
			time = self.selectedCell[0]
		if track == None:
			track = self.selectedCell[1]
		if time < 0 or track < 0 or track >= self.parent.libseq.getTracks(self.song):
			return
		# Skip hidden (overlapping) cells
#		for previous in range(time - 1, -1, -1):
#			prevDuration = self.parent.libseq.getSteps(previous, track)
#			if not prevDuration:
#				continue
#			if prevDuration > time - previous:
#				if time > self.selectedCell[0]:
#					time = previous + prevDuration
#				else:
#					time = previous
#				break
#		if time >= self.duration:
#			time = self.duration - 1
#		if time < 0:
#			time = 0;
		if time >= self.colOffset + self.horizontalZoom:
			# time is off right of display
			self.colOffset = time - self.horizontalZoom + 1
			redraw = True
		elif time < self.colOffset:
			# time is off left of display
			self.colOffset = time
			redraw = True
		if track >= self.rowOffset + self.verticalZoom:
			# track is off bottom of display
			self.rowOffset = track - self.verticalZoom + 1
			redraw = True
		elif track < self.rowOffset:
			self.rowOffset = track
			redraw = True
		self.selectedCell = [time, track]
		if redraw:
			self.drawGrid(True)
		duration = int(self.parent.libseq.getPatternLength(self.pattern) / self.clocksPerDivision)
		if not duration:
			duration = 1
		coord = self.getCellCoord(time - self.colOffset, track - self.rowOffset, duration)
		coord[0] = coord[0] - 1
		coord[1] = coord[1] - 1
		coord[2] = coord[2]
		coord[3] = coord[3]
		cell = self.gridCanvas.find_withtag("selection")
		if not cell:
			cell = self.gridCanvas.create_rectangle(coord, fill="", outline=SELECT_BORDER, width=self.selectThickness, tags="selection")
		else:
			self.gridCanvas.coords(cell, coord)
		self.gridCanvas.itemconfig(cell, state='normal')
		self.gridCanvas.tag_raise(cell)

	# Function to calculate cell size
	def updateCellSize(self):
		self.rowHeight = (self.gridHeight - 2) / self.verticalZoom
		self.columnWidth = self.gridWidth / self.horizontalZoom
		self.fontsize = int(self.rowHeight * 0.4)
		if self.fontsize > 16:
			self.fontsize = 16 # Ugly font scale limiting

	# Function to clear a pattern
	def clearSong(self):
		self.parent.libseq.clearSong(self.song)
		self.drawGrid(True)
		if zyncoder.lib_zyncoder:
			zyncoder.lib_zyncoder.zynmidi_send_all_notes_off()
		self.selectCell(0,0)

	# Function to copy pattern
	def copySong(self):
		self.parent.libseq.copySong(self.copySource, self.song);
		self.selectSong(self.song)

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
		if menuItem == 'Song':
			print("Menu change song:", value)
			self.selectSong(value)
			if value == 0:
				return "Song: None"
			self.copySource = value
			self.parent.setParam('Copy song', 'value', value)
		elif menuItem == 'Clear song':
			return "Clear song %d?" % (self.song)
		elif menuItem =='Copy song':
			self.selectSong(value)
			return "Copy %d=>%d?" % (self.copySource, value)
		elif menuItem == 'Transpose song':
			if(value != 1):
				for track in range(self.parent.libseq.getTracks(self.song)):
					self.parent.libseq.transposeSong(self.parent.libseq.getSequence(self.song, track))
				self.parent.setParam(menuItem, 'value', 1)
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
		elif menuItem == 'Clocks per division':
			self.parent.setParam(menuItem, 'value', value)
			self.setClocksPerDivision(value)
			self.drawGrid()
		elif menuItem == 'MIDI channel':
			self.parent.setParam(menuItem, 'value', value)
			track = self.selectedCell[1] + self.rowOffset
			sequence = self.parent.libseq.getSequence(self.song, track)
			self.parent.libseq.setChannel(sequence, value - 1)
			self.drawTrack(self.selectedCell[1])
		elif menuItem == 'Tempo':
			self.zyngui.zyntransport.set_tempo(value)
			self.parent.libseq.setTempo(self.song, value, 0) #TODO: Use selected time
		elif menuItem == 'Bar / loop':
			self.parent.libseq.setBarLength(self.song, value * self.clocksPerDivision) #TODO: Loop point (bar lines) should be song specific
			self.drawGrid(True)
		return "%s: %d" % (menuItem, value)

	# Function to get clocks per division
	#	Returns: Clock cycles per horizontal time division
	def getClocksPerDivision(self):
		return self.clocksPerDivision

	# Function to set clocks per division
	#	clocks: Clock cycles per horizontal time division
	def setClocksPerDivision(self, clocks):
		if clocks:
			self.clocksPerDivision = clocks

	# Function to get MIDI channel of selected track
	#	returns: MIDI channel
	def getTrackChannel(self):
		track = self.selectedCell[1]
		sequence = self.parent.libseq.getSequence(self.song, track)
		channel = self.parent.libseq.getChannel(sequence) + 1
		return channel

	# Function to load new pattern
	#	index: Pattern index
	def selectSong(self, index):
		if self.song == index:
			return
		self.song = index
		self.parent.libseq.selectSong(index)
#		self.parent.setParam('Vertical zoom', 'max', self.parent.libseq.getTracks(self.song))
#		self.parent.setParam('Horizontal zoom', 'max', self.duration)
		self.zyngui.zyntransport.set_tempo(self.parent.libseq.getTempo(self.song))
		self.parent.setParam('Tempo', 'value', self.parent.libseq.getTempo(self.song))
		print("Loaded song %d: tempo=%d, tracks=%d" % (index, self.parent.libseq.getTempo(self.song), self.parent.libseq.getTracks(self.song)))
		self.drawGrid(True)
		print("A")
		self.selectCell(0,0)
		print("B")
		if self.song == 0:
			self.parent.setTitle("Song Editor (None)")
		else:
			self.parent.setTitle("Song Editor (%d)" % (self.song))
		for track in range(0, self.parent.libseq.getTracks(self.song)):
			print("Track %d, sequence %d" % (track, self.parent.libseq.getSequence(self.song, track)))

	# Function called when new file loaded from disk
	def onLoad(self):
		pass

	# Function to handle transport start
	def onTransportStart(self):
		#TODO: Do not change playmode of sequences automatically
		for track in range(self.parent.libseq.getTracks(self.song)):
			sequence = self.parent.libseq.getSequence(self.song, track)
			self.parent.libseq.setPlayMode(sequence, zynthian_gui_config.SEQ_ONESHOT)
			self.parent.libseq.setPlayState(sequence, zynthian_gui_config.SEQ_PLAYING)
		self.drawGrid()

	# Function to handle transport stop
	def onTransportPause(self):
		for track in range(self.parent.libseq.getTracks(self.song)):
			sequence = self.parent.libseq.getSequence(self.song, track)
			self.parent.libseq.setPlayState(sequence, zynthian_gui_config.SEQ_STOPPED)

	# Function to handle transport stop
	def onTransportStop(self):
		for track in range(self.parent.libseq.getTracks(self.song)):
			sequence = self.parent.libseq.getSequence(self.song, track)
			self.parent.libseq.setPlayState(sequence, zynthian_gui_config.SEQ_STOPPED)
			self.parent.libseq.setPlayPosition(sequence, 0)
		self.showPos(0)

	# Function to scroll grid to show position in song
	#	pos: Song position in clocks cycles
	def showPos(self, pos):
		if pos >= self.colOffset and pos < self.colOffset + self.horizontalZoom:
			return
		self.colOffset = int(pos)
		self.position = int(pos)
		if self.colOffset < 0:
			self.colOffset = 0
		self.drawGrid()

	# Function to refresh playhead
	def refresh_status(self):
		pos = self.parent.libseq.getSongPosition(self.song) / self.clocksPerDivision
		if self.position != pos:
			self.showPos(pos)
		self.gridCanvas.coords('playheadline', (pos - self.colOffset) * self.columnWidth, 0, (pos - self.colOffset) * self.columnWidth, self.gridHeight)

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
			pattern = self.pattern + value
			if pattern < 1:
				self.pattern = 1
			else:
				self.pattern = pattern
			self.patternCanvas.itemconfig("patternIndicator", text="%d"%(self.pattern))
			self.selectCell()

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
		elif switch == ENC_SELECT:
			self.toggleEvent(self.selectedCell[0], self.selectedCell[1])
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
