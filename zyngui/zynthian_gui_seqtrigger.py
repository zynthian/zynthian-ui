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

		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		self.columns = 8
		self.rows = 8
		self.selectedPad = 1 # Index of last selected pad - used to edit config

		self.playModes = ['Disabled', 'Oneshot', 'Loop', 'Oneshot all', 'Loop all']
		self.padColoursStopped = ['grey', '#004060', '#008040', '#5794a8', '#57a861']
		self.padColoursPlaying = ['grey', '#0C4080', '#00A040', '#2ba0d4', '#2dd24a']
		self.padColoursStarting = ['grey', '#000070', '#009000', '#585da7', '#52ad86']
		self.padColoursStopping = ['grey', '#000090', '#00B000', '#1358ec', '#21de81']

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height

		# Main Frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
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

		#TODO: Just adding patterns to sequences for test - this should be done by user in sequence editor
		for pattern in range(1, 65):
			self.parent.libseq.addPattern(pattern, 0, pattern)

	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setupEncoders(self):
		pass

	# Function to show GUI
	def show(self):
		self.parent.addMenu({'Pad mode':{'method':self.parent.showParamEditor, 'params':{'min':0, 'max':len(self.playModes)-1, 'value':0, 'getValue':self.getSelectedPadMode, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Grid size':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':8, 'value':8, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'MIDI channel':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':16, 'value':1, 'getValue':self.getSelectedPadChannel, 'onChange':self.onMenuChange}}})
		self.parent.addMenu({'Sync period':{'method':self.parent.showParamEditor, 'params':{'min':1, 'max':999, 'value':96, 'getValue':self.parent.libseq.getSyncPeriod, 'onChange':self.onMenuChange}}})
		self.drawGrid()
		self.main_frame.tkraise()
		self.setupEncoders()
		self.parent.setTitle("ZynGrid")


	# Function to hide GUI
	def hide(self):
		pass

	# Function to get the mode of the currently selected pad
	#	returns: Mode of selected pad
	def getSelectedPadMode(self):
		return self.parent.libseq.getPlayMode(self.selectedPad)

	# Function to get the MIDI channel of the currently selected pad
	#	returns: MIDI channel of selected pad
	def getSelectedPadChannel(self):
		return self.parent.libseq.getChannel(self.selectedPad)

	# Function to handle menu editor change
	#	params: Menu item's parameters
	#	returns: String to populate menu editor label
	#	note: params is a dictionary with required fields: min, max, value
	def onMenuChange(self, params):
		menuItem = self.parent.paramEditorItem
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		if menuItem == 'Tempo':
			self.zyngui.zyntransport.set_tempo(value)
		prefix = "Pad %s%d" % (chr(int((self.selectedPad - 1) / self.rows) + 65), (self.selectedPad - 1) % self.rows + 1)
		if menuItem == 'Pad mode':
			self.parent.libseq.setPlayMode(self.selectedPad, value)
			self.parent.setParam(menuItem, 'value', value)
			self.drawPad(self.selectedPad)
			return "%s: %s" % (prefix, self.playModes[value])
		elif menuItem == 'Grid size':
			if self.rows != value:
				self.rows = value
				self.columns = value
				self.parent.setParam(menuItem, 'value', value)
				self.drawGrid(True)
		elif menuItem == 'MIDI channel':
			self.parent.libseq.setChannel(self.selectedPad, value - 1)
			self.parent.setParam(menuItem, 'value', value)
			return "%s: MIDI channel: %d" % (prefix, value)
		elif menuItem == 'Sync period':
			self.parent.libseq.setSyncPeriod(value)
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
		padWidth = self.width / self.columns - 2 #TODO: Calculate pad size once
		padHeight = self.height / self.rows - 2
		cell = self.gridCanvas.find_withtag("pad:%d"%(pad))
		if cell:
			if self.parent.libseq.getPlayState(pad) == zynthian_gui_config.SEQ_STOPPED:
				playColour = self.padColoursStopped[self.parent.libseq.getPlayMode(pad)]
			elif self.parent.libseq.getPlayState(pad) == zynthian_gui_config.SEQ_STARTING:
				playColour = self.padColoursStarting[self.parent.libseq.getPlayMode(pad)]
			elif self.parent.libseq.getPlayState(pad) == zynthian_gui_config.SEQ_STOPPING:
				playColour = self.padColoursStopping[self.parent.libseq.getPlayMode(pad)]
			else:
				playColour = self.padColoursPlaying[self.parent.libseq.getPlayMode(pad)]
			self.gridCanvas.itemconfig(cell, fill=playColour)
			self.gridCanvas.coords(cell, padX, padY, padX + padWidth, padY + padHeight)
		else:
			cell = self.gridCanvas.create_rectangle(padX, padY, padX + padWidth, padY + padHeight,
				fill='grey', width=0, tags=("pad:%d"%(pad), "gridcell"))
			self.gridCanvas.create_text(padX + padWidth / 2, padY + padHeight / 2,
				font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(padHeight * 0.3)),
				fill=zynthian_gui_config.color_panel_tx,
				tags="lbl_pad:%d"%(pad),
				text="%s%d" % (chr(col + 65), row + 1))
			self.gridCanvas.tag_bind("pad:%d"%(pad), '<Button-1>', self.onPadPress)
			self.gridCanvas.tag_bind("lbl_pad:%d"%(pad), '<Button-1>', self.onPadPress)
			self.gridCanvas.tag_bind("pad:%d"%(pad), '<ButtonRelease-1>', self.onPadRelease)
			self.gridCanvas.tag_bind("lbl_pad:%d"%(pad), '<ButtonRelease-1>', self.onPadRelease)

	# Function to draw pad
	#	pad: Pad index
	#	returns: Pad sequence play state
	def drawPad(self, pad):
		pads = self.rows * self.columns
		if pads < 1 or pad < 1 or pad > pads:
			return 0
		self.drawCell(int((pad - 1) / self.rows), (pad - 1) % self.rows)
		return self.parent.libseq.getPlayState(pad)

	# Function to handle pad press
	def onPadPress(self, event):
		if self.parent.lstMenu.winfo_viewable():
			self.parent.hideMenu()
			return
		tags = self.gridCanvas.gettags(self.gridCanvas.find_withtag(tkinter.CURRENT))
		pad = int(tags[0].split(':')[1])
		self.selectedPad = pad
		menuItem = self.parent.paramEditorItem
		if menuItem == 'Pad mode':
			self.parent.setParam('Pad mode', 'value', self.parent.libseq.getPlayMode(pad))
			self.parent.refreshParamEditor()
		elif menuItem == 'MIDI channel':
			self.parent.setParam('MIDI channel', 'value', self.parent.libseq.getChannel(pad)+1)
			self.parent.refreshParamEditor()
		if self.parent.libseq.getPlayState(pad) == zynthian_gui_config.SEQ_PLAYING:
			self.parent.libseq.setPlayState(pad, zynthian_gui_config.SEQ_STOPPING)
		elif self.parent.libseq.getPlayMode(pad) != zynthian_gui_config.SEQ_DISABLED:
			self.parent.libseq.setPlayState(pad, zynthian_gui_config.SEQ_STARTING)
		playing = self.drawPad(pad)
		if playing and not self.zyngui.zyntransport.get_state():
			self.parent.libseq.setPlayState(pad, zynthian_gui_config.SEQ_PLAYING)
			self.zyngui.zyntransport.locate(0)
			self.zyngui.zyntransport.transport_play()

	# Function to handle transport toggle
	def onTransportToggle(self):
		pass

	# Function to handle pad release
	def onPadRelease(self, event):
		pass

	# Function to refresh status
	def refresh_status(self):
		playing = 0
		for pad in range(1, self.rows * self.columns + 2):
			playing = playing + self.drawPad(pad)

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
