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

# Define encoder use: 0=Layer, 1=Back, 2=Snapshot, 3=Select
ENC_LAYER           = 0
ENC_BACK            = 1
ENC_SNAPSHOT        = 2
ENC_SELECT          = 3

import inspect
import tkinter
import logging
import tkinter.font as tkFont
from math import sqrt
from PIL import Image, ImageTk
from time import sleep
from threading import Timer

# Zynthian specific modules
from . import zynthian_gui_config
from . import zynthian_gui_stepsequencer
from zyncoder import *

SELECT_BORDER	= zynthian_gui_config.color_on


#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Sequence / Pad Trigger GUI Class
#------------------------------------------------------------------------------

# Class implements step sequencer
class zynthian_gui_zynpad():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent
		self.libseq = parent.zyngui.libseq

		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		self.columns = 4 # Equal quantity of rows and columns
		self.selected_pad = 0 # Index of selected pad
		self.song = 1001 # Index of song used to configure pads
		self.redraw_pending = 0 # What to redraw: 0=nothing, 1=existing elements, 2=recreate grid


		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height
		self.select_thickness = 4#1 + int(self.width / 500) # Scale thickness of select border based on screen
		self.column_width = self.width / self.columns
		self.row_height = self.height / self.columns

		# Main Frame
		self.main_frame = tkinter.Frame(self.parent.main_frame)
		self.main_frame.grid(row=1, column=0, sticky="nsew")

		# Pad grid
		self.grid_canvas = tkinter.Canvas(self.main_frame,
			width=self.width, 
			height=self.height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.grid_canvas.grid(row=0, column=0)
		self.grid_timer = Timer(2, self.on_grid_timer) # Grid press and hold timer

		# Icons
		self.icon = [tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage(),tkinter.PhotoImage()]

		# Selection highlight
		self.selection = self.grid_canvas.create_rectangle(0, 0, self.column_width, self.row_height, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")

	# Function to get name of this view
	def get_name(self):
		return "zynpad"

	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setup_encoders(self):
		self.parent.register_zyncoder(ENC_BACK, self)
		self.parent.register_zyncoder(ENC_SELECT, self)
		self.parent.register_switch(ENC_SELECT, self, 'SB')

	# Function to show GUI
	#   params: Misc parameters
	def show(self, params):
		self.main_frame.tkraise()
		self.setup_encoders()
		self.select_song()

	# Function to populate menu
	def populate_menu(self):
		self.parent.add_menu({'Pad mode':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':len(zynthian_gui_stepsequencer.PLAY_MODES)-1, 'get_value':self.get_selected_pad_mode, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Group':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':25, 'get_value':self.get_group, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'MIDI channel':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':16, 'get_value':self.get_pad_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Trigger channel':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':16, 'get_value':self.get_trigger_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Tally channel':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':15, 'get_value':self.get_tally_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Quantity of pads':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':64, 'get_value':self.get_pads, 'on_change':self.on_menu_change, 'on_assert':self.set_pads}}})

	# Function to hide GUI
	def hide(self):
		self.parent.unregister_zyncoder(ENC_BACK)
		self.parent.unregister_zyncoder(ENC_SELECT)
		self.parent.unregister_switch(ENC_SELECT)

	# Function to get MIDI channel of selected pad
	#	returns: MIDI channel
	def get_pad_channel(self):
		return self.libseq.getChannel(self.get_sequence(self.selected_pad)) + 1

	# Function to get the MIDI trigger channel
	#   returns: MIDI channel
	def get_trigger_channel(self):
		return self.libseq.getTriggerChannel() + 1

	# Function to get the MIDI tally channel
	#   returns: MIDI channel to send tallies (e.g. to light controller pads)
	def get_tally_channel(self):
		channel = self.libseq.getTallyChannel()
		if channel > 15:
			return 0
		else:
			return channel + 1

	# Function to get group of selected track
	def get_group(self):
		return self.libseq.getGroup(self.get_sequence(self.selected_pad))

	# Function to get the mode of the currently selected pad
	#   returns: Mode of selected pad
	def get_selected_pad_mode(self):
		return self.libseq.getPlayMode(self.get_sequence(self.selected_pad))

	# Function to get pad sequence
	#   pad: Pad index
	#   returns: Index of sequence associated with pad
	def get_sequence(self, pad):
		return self.libseq.getSequence(self.song, pad)

	# Function to handle menu editor change
	#   params: Menu item's parameters
	#   returns: String to populate menu editor label
	#   note: params is a dictionary with required fields: min, max, value
	def on_menu_change(self, params):
		menu_item = self.parent.param_editor_item
		value = params['value']
		if value < params['min']:
			value = params['min']
		if value > params['max']:
			value = params['max']
		if menu_item == 'Pad mode':
			self.libseq.setPlayMode(self.get_sequence(self.selected_pad), value)
#			self.draw_pad(self.selected_pad)
			return "Pad mode: %s" % (zynthian_gui_stepsequencer.PLAY_MODES[value])
		elif menu_item == "Group":
			self.libseq.setGroup(self.get_sequence(self.selected_pad), value)
			return "Group: %s" % (chr(65 + value))
		elif menu_item == 'MIDI channel':
			self.libseq.setChannel(self.get_sequence(self.selected_pad), value - 1)
		elif menu_item == 'Trigger channel':
			self.libseq.setTriggerChannel(value - 1)
		elif menu_item == 'Tally channel':
			if value == 0:
				self.set_pad_tallies(255)
				return "None"
			else:
				self.set_pad_tallies(value - 1)
		return "%s: %d" % (menu_item, value)


	# Function to get quantity of pads
	def get_pads(self):
		return self.libseq.getTracks(self.song)


	# Function to set quantity of pads
	#	pads: Quantity of pads
	#	Note: Tracks will be deleted from or added to end of track list as necessary
	def set_pads(self):
		pads = self.parent.get_param('Quantity of pads', 'value')
		# Remove surplus tracks
		while self.get_pads() > pads:
			self.libseq.removeTrack(self.song, pads)
		# Add extra tracks
		while self.get_pads() < pads:
			sequence = self.libseq.addTrack(self.song)
			#TODO: Configure sequences / pads
		pads = self.get_pads()
		self.update_grid()

	# Function to configure pad tallies
	#	channel: MIDI channel to send tallies (255 to disable tallies)
	def set_pad_tallies(self, channel):
		#TODO: Currently only handles Akai APC
		for track in range(self.libseq.getTracks(self.song)):
			sequence = self.libseq.getSequence(self.song, track)
			if sequence:
				note = self.libseq.getTriggerNote(sequence)
				self.libseq.setTallyChannel(sequence, channel)
				if channel < 16:
					if note < 128 and self.libseq.getSequenceLength(sequence):
						self.libseq.playNote(note, 3, channel, 0)
					else:
						self.libseq.playNote(note, 0, channel, 0)

	# Function to load song
	def select_song(self):
		#TODO: Should we stop song and recue?
		song = self.libseq.getSong()
		self.song = song + 1000
#		self.libseq.solo(self.song, 0, False)
		tracks = self.libseq.getTracks(self.song)
		imgWidth = int(self.width / self.columns / 4)
		iconsize = (imgWidth, imgWidth)
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
		self.update_grid()
		self.parent.set_title("ZynPad (%d)"%(song))

	# Function to clear and calculate grid sizes
	# Grid is peridicall refreshed by refresh function which draws cells if required
	def update_grid(self):
		self.grid_canvas.delete(tkinter.ALL)
		pads = self.get_pads()
		if pads < 1:
			self.columns = 1
		else:
			self.columns = int(sqrt(pads - 1) + 1)
		self.column_width = self.width / self.columns
		self.row_height = self.height / self.columns
		self.selection = self.grid_canvas.create_rectangle(0, 0, self.column_width, self.row_height, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")
		# Add pattern to sequence if missing TODO: Need to avoid this if using sequence editor - possibly by creating new sequences with a pattern by default
		for pad in range(self.columns**2):
			sequence = self.get_sequence(pad)
			if sequence == 0:
				continue # This should not occur because all pads are tied to tracks which are sequences
			pattern = self.libseq.getPattern(sequence, 0)
			if pattern == -1:
				pattern = 1001 + (self.song - 1001) * 64 + pad
				logging.warning("Auto add pattern %d to pad %d in song %d", pattern, pad, self.song)
				self.libseq.addPattern(sequence, 0, pattern, True)


	# Function to draw grid cell (pad)
	#   col: Column index
	#   row: Row index
	def draw_cell(self, col, row, clear = False):
		#TODO: Optimisation - pad refresh
		if col < 0 or col >= self.columns or row < 0 or row >= self.columns:
			return
		pad = row + col * self.columns
		sequence = self.get_sequence(pad)
		group = self.libseq.getGroup(sequence)
		pad_x = col * self.column_width
		pad_y = row * self.row_height
		cell = self.grid_canvas.find_withtag("pad:%d"%(pad))
		if cell:
			mode = self.libseq.getPlayMode(sequence)
			if self.libseq.getSequenceLength(sequence) == 0:
				mode = 0
			self.grid_canvas.itemconfig("mode:%d"%pad, image=self.icon[mode], state='normal')
			if not sequence or self.libseq.getPlayMode(sequence) == zynthian_gui_stepsequencer.SEQ_DISABLED:
				fill = zynthian_gui_stepsequencer.PAD_COLOUR_DISABLED
				self.grid_canvas.itemconfig("mode:%d"%pad, state='hidden')
			elif self.libseq.getPlayState(sequence) == zynthian_gui_stepsequencer.SEQ_STOPPED:
				if group % 2:
					fill = zynthian_gui_stepsequencer.PAD_COLOUR_STOPPED_EVEN
				else:
					fill = zynthian_gui_stepsequencer.PAD_COLOUR_STOPPED_ODD
			elif self.libseq.getPlayState(sequence) == zynthian_gui_stepsequencer.SEQ_STARTING:
				fill = zynthian_gui_stepsequencer.PAD_COLOUR_STARTING
			elif self.libseq.getPlayState(sequence) == zynthian_gui_stepsequencer.SEQ_STOPPING:
				fill = zynthian_gui_stepsequencer.PAD_COLOUR_STOPPING
			else:
				fill = zynthian_gui_stepsequencer.PAD_COLOUR_PLAYING
			self.grid_canvas.itemconfig(cell, fill=fill)
			self.grid_canvas.itemconfig("lbl_pad:%d"%(pad), text="%s%d" % (chr(65 + group), pad + 1))
			self.grid_canvas.coords(cell, pad_x, pad_y, pad_x + self.column_width - 2, pad_y + self.row_height - 2)
		else:
			cell = self.grid_canvas.create_rectangle(pad_x, pad_y, pad_x + self.column_width - 2, pad_y + self.row_height - 2,
				fill='grey', width=0, tags=("pad:%d"%(pad), "gridcell"))
			if pad >= self.libseq.getTracks(self.song):
				return
			self.grid_canvas.create_text(pad_x + self.column_width / 2, pad_y + self.row_height / 2,
				font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.row_height * 0.3)),
				fill=zynthian_gui_config.color_panel_tx,
				tags="lbl_pad:%d"%(pad),
				text="%s%d" % (chr(65 + group), pad+1))
			self.grid_canvas.create_image(pad_x + self.column_width - 3, pad_y + self.row_height - 3, tags=("mode:%d"%(pad)), anchor="se")
			self.grid_canvas.tag_bind("pad:%d"%(pad), '<Button-1>', self.on_pad_press)
			self.grid_canvas.tag_bind("lbl_pad:%d"%(pad), '<Button-1>', self.on_pad_press)
			self.grid_canvas.tag_bind("mode:%d"%(pad), '<Button-1>', self.on_pad_press)
			self.grid_canvas.tag_bind("pad:%d"%(pad), '<ButtonRelease-1>', self.on_pad_release)
			self.grid_canvas.tag_bind("lbl_pad:%d"%(pad), '<ButtonRelease-1>', self.on_pad_release)
			self.grid_canvas.tag_bind("mode:%d"%(pad), '<ButtonRelease-1>', self.on_pad_release)

	# Function to draw pad
	#   pad: Pad index
	def draw_pad(self, pad):
		pads = self.columns**2 #TODO: Optimisation - Performing maths for every pad draw which happens for every pad on every refresh (many times a second)
		if pads < 1 or pad < 0:
			return
		col = int(pad / self.columns)
		row = pad % self.columns
		if pad >= pads:
			self.update_grid() #TODO: Optimisation - this will recreate grid for every pad that extends its size
		else:
			self.draw_cell(col, row)
		if self.selected_pad == pad:
			# Move and show seletion cursor
			self.grid_canvas.coords(self.selection, 1 + col * self.column_width, 1 + row * self.row_height, (1 + col) * self.column_width - self.select_thickness, (1 + row) * self.row_height - self.select_thickness)
			self.grid_canvas.tag_raise(self.selection)
			self.grid_canvas.itemconfig(self.selection, state="normal")

	# Function to handle pad press
	def on_pad_press(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hideMenu()
			return
		tags = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))
		pad = int(tags[0].split(':')[1])
		self.selected_pad = pad
		self.toggle_pad()
		self.grid_timer = Timer(2, self.on_grid_timer)
		self.grid_timer.start()
		
	# Function to toggle pad
	def toggle_pad(self):
		sequence = self.get_sequence(self.selected_pad)
		if sequence == 0:
			return
		self.libseq.togglePlayState(sequence)

	# Function to handle pad release
	def on_pad_release(self, event):
		self.grid_timer.cancel()

	# Function to handle grid press and hold
	def on_grid_timer(self):
		self.gridDragStart = None
		self.show_pattern_editor()

	# Function to show pattern editor for first pattern of sequence of selected pad
	def show_pattern_editor(self):
		sequence = self.get_sequence(self.selected_pad)
		if sequence == 0:
			return
		pattern = self.libseq.getPattern(sequence, 0)
		if pattern == -1:
			return
		channel = self.libseq.getChannel(sequence)
		self.parent.show_child("pattern editor", {"pattern":pattern, "channel":channel})
		#TODO: How do we indicate to return to zynpad when closing pattern editor?

	# Function called when new file loaded from disk
	def on_load(self):
		pass

	# Function to refresh status
	def refresh_status(self):
		for pad in range(0, self.columns**2):
			self.draw_pad(pad)

	def refresh_loading(self):
		pass

	# Function to handle zyncoder value change
	#   encoder: Zyncoder index [0..4]
	#   value: Current value of zyncoder
	def on_zyncoder(self, encoder, value):
		column = int(self.selected_pad / self.columns)
		row = self.selected_pad - column * self.columns
		if encoder == ENC_SELECT:
			# SELECT encoder adjusts horizontal pad selection
			column += value
			if column < 0:
				column = 0
			if column >= self.columns:
				column = self.columns - 1
		elif encoder == ENC_BACK:
			# BACK encoder adjusts vertical pad selection
			row += value
			if row < 0:
				row = 0
			if row >= self.columns:
				row = self.columns - 1
		self.selected_pad = row + column * self.columns

	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if switch == ENC_SELECT:
			if type == 'S':
				self.toggle_pad()
			elif type == "B":
				self.show_pattern_editor()
			return True
		return False

#------------------------------------------------------------------------------
