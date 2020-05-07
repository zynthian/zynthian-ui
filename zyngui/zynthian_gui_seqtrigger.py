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
import tkinter.font as tkFont

# Zynthian specific modules
from . import zynthian_gui_config
from zyncoder import *

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Sequence / Pad Trigger GUI Class
#------------------------------------------------------------------------------

# Class implements step sequencer
class zynthian_gui_seqtrigger():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		parent.setTitle("Pad Trigger")

		self.shown = False # True when GUI in view
		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		self.columns = 8
		self.rows = 8
		self.padConfig = {} # Dictionary of configuration for each pad
		self.selectedPad = 1 # Index of last selected pad - used to edit config

		self.parent.addMenu({'Pad mode':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':2, 'value':2, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Columns':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'value':8, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Rows':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'value':8, 'onChange':self.onMenuChange}}})

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height

		# Main Frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(row=1, column=0, sticky="nsew")

		# Pad grid
		self.gridCanvas = tkinter.Canvas(self.main_frame,
			width=self.width, 
			height=self.height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.gridCanvas.grid(row=0, column=0)

		for pattern in range(1, 65):
			self.parent.libseq.addPattern(pattern, 0, pattern)

	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		pass

	# Function to show GUI
	def show(self):
		self.drawGrid()
		self.main_frame.tkraise()
		self.setupEncoders()
		self.shown=True

	# Function to hide GUI
	def hide(self):
		self.shown=False

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
		if menuItem == 'Pad mode':
			self.padConfig.update({self.selectedPad:{'mode':value}})
			self.parent.setParam(menuItem, 'value', value)
			self.drawPad(self.selectedPad)
			prefix = "Pad %s%d" % (chr(int((self.selectedPad - 1) / self.rows) + 65), (self.selectedPad - 1) % self.rows + 1)
			if value == 2:
				return "%s: Loop" % (prefix)
			else:
				return "%s: One-shot" % (prefix)
		elif menuItem == 'Columns':
			if self.columns != value:
				self.columns = value
				self.parent.setParam(menuItem, 'value', value)
				self.drawGrid(True)
		elif menuItem == 'Rows':
			if self.rows != value:
				self.rows = value
				self.parent.setParam(menuItem, 'value', value)
				self.drawGrid(True)
		return "%s: %d" % (menuItem, value)

	# Function to draw grid
	def drawGrid(self, clear = False):
		if clear:
			self.gridCanvas.delete(tkinter.ALL)
		for col in range(self.columns):
			self.drawColumn(col, clear)

	# Function to draw grid column
	#	col: Column index
	def drawColumn(self, col, clear = False):
		for row in range(self.rows):
			self.drawCell(col, row, clear)

	# Function to draw grid cell (pad)
	#	col: Column index
	#	row: Row index
	def drawCell(self, col, row, clear = False):
		pad = row + col * self.rows + 1 # Index pads from 1 and use index to map sequence (sequence 0 is used by pattern editor)
		if col < 0 or col >= self.columns or row < 0 or row >= self.rows:
			return
		padX = col * self.width / self.columns
		padY = row * self.height / self.rows
		padWidth = self.width / self.columns - 2
		padHeight = self.height / self.rows - 2
		cell = self.gridCanvas.find_withtag("pad:%d"%(pad))
		if cell:
			playMode = self.parent.libseq.getPlayMode(pad)
			playColour = 'grey'
			if playMode == 1:
				playColour = 'blue'
			elif playMode == 2:
				playColour = 'green'
			elif self.parent.libseq.getSequenceLength(pad):
				if self.padConfig[pad]['mode'] == 1:
					playColour = 'dark blue'
				if self.padConfig[pad]['mode'] == 2:
					playColour = 'dark green'
			self.gridCanvas.itemconfig(cell, fill=playColour)
			self.gridCanvas.itemconfig(cell, fill=playColour)
			self.gridCanvas.coords(cell, padX, padY, padX + padWidth, padY + padHeight)
		else:
			cell = self.gridCanvas.create_rectangle(padX, padY, padX + padWidth, padY + padHeight, fill='grey', width=0, tags=("pad:%d"%(pad), "gridcell"))
			self.gridCanvas.create_text(padX + padWidth / 2, padY + padHeight / 2,
			font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(padHeight * 0.3)),
			fill=zynthian_gui_config.color_panel_tx,
			tags="lbl_pad:%d"%(pad),
			text="Pad %s%d" % (chr(col + 65), row + 1))
			self.gridCanvas.tag_bind("pad:%d"%(pad), '<Button-1>', self.onPadPress)
			self.gridCanvas.tag_bind("lbl_pad:%d"%(pad), '<Button-1>', self.onPadPress)
			self.gridCanvas.tag_bind("pad:%d"%(pad), '<ButtonRelease-1>', self.onPadRelease)
			self.gridCanvas.tag_bind("lbl_pad:%d"%(pad), '<ButtonRelease-1>', self.onPadRelease)
			self.padConfig.update({pad:{'mode':2}})

	# Function to draw pad
	#	pad: Pad index
	def drawPad(self, pad):
		pads = self.rows * self.columns
		if pads < 1 or pad < 1 or pad > pads:
			return
		self.drawCell((pad -1) % self.rows, int((pad - 1) / self.rows))

	# Function to handle pad press
	def onPadPress(self, event):
		pass

	# Function to handle pad release
	def onPadRelease(self, event):
		tags = self.gridCanvas.gettags(self.gridCanvas.find_withtag(tkinter.CURRENT))
		pad = int(tags[0].split(':')[1])
		self.selectedPad = pad
		if self.parent.libseq.getSequenceLength(pad):
			if self.parent.libseq.getPlayMode(pad):
				self.parent.libseq.setPlayMode(pad, 0)
			else:
				self.parent.libseq.setPlayMode(pad, self.padConfig[pad]['mode'])
		if(self.parent.paramEditorState):
			params = {'min':1, 'max':2, 'value':2, 'onChange':self.onMenuChange}
			params['value'] = self.padConfig[pad]['mode']
			self.parent.showParamEditor(params) #TODO: Boy this is untidy!!!
		self.drawPad(pad)

	# Function to refresh status
	def refresh_status(self):
		for pad in range(self.rows * self.columns):
			self.drawPad(pad)

	def refresh_loading(self):
		pass

	# Function to handle zyncoder value change
	#	encoder: Zyncoder index [0..4]
	#	value: Current value of zyncoder
	def onZyncoder(self, encoder, value):
		pass

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "L":
			return False # Don't handle any long presses
		return True # Tell parent that we handled all short and bold key presses
#------------------------------------------------------------------------------
