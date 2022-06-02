#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2022 Brian Walton <brian@riban.co.uk>
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
from math import sqrt
from PIL import Image, ImageTk
from time import sleep
from threading import Timer

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui import zynthian_gui_stepsequencer
from zynlibs.zynseq import zynseq
from zynlibs.zynseq.zynseq import libseq


SELECT_BORDER	= zynthian_gui_config.color_on


#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Sequence / Pad Trigger GUI Class
#------------------------------------------------------------------------------

# Class implements step sequencer
class zynthian_gui_zynpad():

	# Function to initialise class
	def __init__(self, parent):
		self.parent = parent

		self.zyngui = zynthian_gui_config.zyngui # Zynthian GUI configuration

		self.columns = 4 # Quantity of columns in grid
		self.selected_pad = 0 # Index of selected pad
		self.refresh_pending = 0 # 0=no refresh pending, 1=update grid

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height
		self.select_thickness = 1 + int(self.width / 400) # Scale thickness of select border based on screen
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
		self.grid_timer = Timer(1.4, self.on_grid_timer) # Grid press and hold timer

		# Icons
		self.mode_icon = [tkinter.PhotoImage() for i in range(7)]
		self.state_icon = [tkinter.PhotoImage() for i in range(4)]
		self.empty_icon = tkinter.PhotoImage()

		# Selection highlight
		self.selection = self.grid_canvas.create_rectangle(0, 0, self.column_width, self.row_height, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")


	# Function to get name of this view
	def get_name(self):
		return "zynpad"


	#Function to set values of encoders
	#	note: Call after other routine uses one or more encoders
	def setup_encoders(self):
		self.parent.register_zyncoder(zynthian_gui_config.ENC_BACK, self)
		self.parent.register_zyncoder(zynthian_gui_config.ENC_SELECT, self)
		self.parent.register_switch(zynthian_gui_config.ENC_SELECT, self, 'SB')


	# Function to show GUI
	#   params: Misc parameters
	def show(self, params):
		libseq.updateSequenceInfo()
		self.main_frame.tkraise()
		self.setup_encoders()
		self.parent.select_bank(self.parent.bank)
		self.parent.set_title("Bank %d" % (self.parent.bank))
		try:
			self.selected_pad = params["sequence"]
		except:
			pass # sequence not passed as parameter


	# Function to populate menu
	def populate_menu(self):
		self.parent.add_menu({'Play mode':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':len(zynthian_gui_stepsequencer.PLAY_MODES)-1, 'get_value':self.get_selected_pad_mode, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'MIDI channel':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':16, 'get_value':self.get_pad_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Trigger channel':{'method':self.parent.show_param_editor, 'params':{'min':0, 'max':16, 'get_value':self.get_trigger_channel, 'on_change':self.on_menu_change}}})
		self.parent.add_menu({'Trigger note':{'method':self.parent.show_param_editor, 'params':{'min':-1, 'max':128, 'get_value':self.get_trigger_note, 'on_change':self.on_menu_change, 'on_reset':self.reset_trigger_note}}})
		self.parent.add_menu({'-------------------':{}})
		self.parent.add_menu({'Grid size':{'method':self.parent.show_param_editor, 'params':{'min':1, 'max':8, 'get_value':self.get_columns, 'on_change':self.on_menu_change, 'on_assert':self.set_grid_size}}})
		self.parent.add_menu({'Name sequence':{'method':self.name_sequence}})


	# Function to hide GUI
	def hide(self):
		self.parent.unregister_zyncoder(zynthian_gui_config.ENC_BACK)
		self.parent.unregister_zyncoder(zynthian_gui_config.ENC_SELECT)
		self.parent.unregister_switch(zynthian_gui_config.ENC_SELECT)


	# Function to set quantity of pads
	def set_grid_size(self):
		if libseq.getSequencesInBank(self.parent.bank) > self.parent.get_param("Grid size", "value") * self.parent.get_param("Grid size", "value"):
			self.zyngui.show_confirm("Reducing the quantity of sequences in bank %d will delete sequences but patterns will still be available. Continue?" % (self.parent.bank), self.do_grid_size)
		else:
			self.do_grid_size()


	# Function to actually set quantity of pad
	def do_grid_size(self, params=None):
		# To avoid odd behaviour we stop all sequences from playing before changing grid size (blunt but effective!)
		bank = self.parent.bank
		for seq in range(libseq.getSequencesInBank(bank)):
			libseq.setPlayState(bank, seq, zynthian_gui_stepsequencer.SEQ_STOPPED)
		channels = []
		groups = []
		for column in range(self.columns):
			channels.append(libseq.getChannel(bank, column * self.columns, 0))
			groups.append(libseq.getGroup(bank, column * self.columns))
		new_size = self.parent.get_param("Grid size", "value")
		delta = new_size - self.columns
		if delta > 0:
			# Growing grid so add extra sequences
			for column in range(self.columns):
				for row in range(self.columns, self.columns + delta):
					pad = row + column * new_size
					libseq.insertSequence(bank, pad)
					libseq.setChannel(bank, pad, channels[column])
					libseq.setGroup(bank, pad, groups[column])
					zynseq.set_sequence_name(bank, pad, "%s"%(pad + 1))
			for column in range(self.columns, new_size):
				for row in range(new_size):
					pad = row + column * new_size
					libseq.insertSequence(bank, pad)
					libseq.setChannel(bank, pad, column)
					libseq.setGroup(bank, pad, column)
					zynseq.set_sequence_name(bank, pad, "%s"%(pad + 1))
		if delta < 0:
			# Shrinking grid so remove excess sequences
			libseq.setSequencesInBank(bank, new_size * self.columns) # Lose excess columns
			for offset in range(new_size, new_size * new_size + 1, new_size):
				for pad in range(-delta):
					libseq.removeSequence(bank, offset)
		self.columns = new_size
		self.refresh_pending = 1


	# Function to name selected sequence
	def name_sequence(self, params=None):
		self.zyngui.show_keyboard(self.do_rename_sequence, zynseq.get_sequence_name(self.parent.bank, self.selected_pad), 16)


	# Function to rename selected sequence
	def do_rename_sequence(self, name):
		zynseq.set_sequence_name(self.parent.bank, self.selected_pad, name)


	# Function to get MIDI channel of selected pad
	#	returns: MIDI channel (1..16)
	def get_pad_channel(self):
		return libseq.getChannel(self.parent.bank, self.selected_pad, 0) + 1
		#TODO: A pad may drive a complex sequence with multiple tracks hence multiple channels - need to go back to using Group


	# Function to get the MIDI trigger note
	#   returns: MIDI note
	def get_trigger_note(self):
		trigger = libseq.getTriggerNote(self.parent.bank, self.selected_pad)
		if trigger > 128:
			trigger = 128
		return trigger


	# Function to reset trigger note to None
	def reset_trigger_note(self):
		self.parent.set_param("Trigger note", 'value', 0xFF)
		self.parent.refreshParamEditor()


	# Function to get group of selected track
	def get_group(self):
		return libseq.getGroup(self.parent.bank, self.selected_pad)


	# Function to get the mode of the currently selected pad
	#   returns: Mode of selected pad
	def get_selected_pad_mode(self):
		return libseq.getPlayMode(self.parent.bank, self.selected_pad)


	# Function to handle menu editor change
	#   params: Menu item's parameters
	#   returns: String to populate menu editor label
	#   note: params is a dictionary with required fields: min, max, value
	def on_menu_change(self, params):
		menu_item = self.parent.param_editor_item
		value = params['value']
		try:
			if value < params['min']:
				value = params['min']
			if value > params['max']:
				value = params['max']
		except:
			pass # min and max values may not be set
		if menu_item == 'Play mode':
			libseq.setPlayMode(self.parent.bank, self.selected_pad, value)
			return "Play mode: %s" % (zynthian_gui_stepsequencer.PLAY_MODES[value])
		elif menu_item == 'MIDI channel':
			libseq.setChannel(self.parent.bank, self.selected_pad, 0, value - 1)
			libseq.setGroup(self.parent.bank, self.selected_pad, value - 1)
			try:
				return "MIDI channel: %d (%s)"%(value, self.parent.layers[value-1].preset_name)
			except:
				pass # No layer so just show MIDI channel
		elif menu_item == 'Trigger channel':
			if value:
				libseq.setTriggerChannel(value - 1)
			else:
				libseq.setTriggerChannel(0xFF)
				return "Trigger channel: None"
		elif menu_item == 'Trigger note':
			if value > 128 or value < 0:
				value = 128
			libseq.setTriggerNote(self.parent.bank, self.selected_pad, value)
			libseq.enableMidiLearn(self.parent.bank, self.selected_pad)
			if value > 127:
				return "Trigger note: None"
			return "Trigger note: %s%d(%d)" % (['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][value%12],int(value/12)-1, value)
		elif menu_item == 'Grid size':
			return "Grid size: %dx%d" % (value, value)
		return "%s: %d" % (menu_item, value)


	# Function to get quantity of columns in grid
	def get_columns(self):
		return self.columns


	# Function to load bank
	#	bank Index of bank to select
	def select_bank(self, bank):
		self.refresh_pending = 1

	# Function called when sequence set loaded from file
	def get_trigger_channel(self):
		if(libseq.getTriggerChannel() > 15):
			return 0
		return libseq.getTriggerChannel() + 1


	# Function to clear and calculate grid sizes
	def update_grid(self):
		self.refresh_pending = 0
		self.grid_canvas.delete(tkinter.ALL)
		pads = libseq.getSequencesInBank(self.parent.bank)
		if pads < 1:
			return
		self.columns = int(sqrt(pads))
		self.column_width = self.width / self.columns
		self.row_height = self.height / self.columns
		self.selection = self.grid_canvas.create_rectangle(0, 0, self.column_width, self.row_height, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")

		iconsize = (int(self.column_width * 0.5), int(self.row_height * 0.2))
		img = (Image.open("/zynthian/zynthian-ui/icons/oneshot.png").resize(iconsize))
		self.mode_icon[1] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loop.png").resize(iconsize))
		self.mode_icon[2] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/oneshotall.png").resize(iconsize))
		self.mode_icon[3] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loopall.png").resize(iconsize))
		self.mode_icon[4] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/oneshotsync.png").resize(iconsize))
		self.mode_icon[5] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/loopsync.png").resize(iconsize))
		self.mode_icon[6] = ImageTk.PhotoImage(img)

		iconsize = (int(self.row_height * 0.2), int(self.row_height * 0.2))
		img = (Image.open("/zynthian/zynthian-ui/icons/stopped.png").resize(iconsize))
		self.state_icon[zynthian_gui_stepsequencer.SEQ_STOPPED] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/starting.png").resize(iconsize))
		self.state_icon[zynthian_gui_stepsequencer.SEQ_STARTING] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/playing.png").resize(iconsize))
		self.state_icon[zynthian_gui_stepsequencer.SEQ_PLAYING] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/stopping.png").resize(iconsize))
		self.state_icon[zynthian_gui_stepsequencer.SEQ_STOPPING] = ImageTk.PhotoImage(img)

		self.text_labels = []

		# Draw pads
		for pad in range(self.columns**2):
			pad_x = int(pad / self.columns) * self.column_width
			pad_y = pad % self.columns * self.row_height
			self.grid_canvas.create_rectangle(pad_x, pad_y, pad_x + self.column_width - 2, pad_y + self.row_height - 2,
				fill='grey', width=0, tags=("pad:%d"%(pad), "gridcell", "trigger_%d"%(pad)))
			self.grid_canvas.create_text(int(pad_x + self.column_width / 2), int(pad_y + 0.01 * self.row_height),
				width=self.column_width,
				anchor="n", justify="center",
				font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.row_height * 0.2)),
				fill=zynthian_gui_config.color_panel_tx,
				tags=("lbl_pad:%d"%(pad),"trigger_%d"%(pad)))
			self.grid_canvas.create_text(pad_x + 1, pad_y + self.row_height - 1,
				anchor="sw",
				font=tkFont.Font(family=zynthian_gui_config.font_topbar[0],
				size=int(self.row_height * 0.2)),
				fill=zynthian_gui_config.color_panel_tx,
				tags=("group:%d"%(pad),"trigger_%d"%(pad)))
			self.grid_canvas.create_image(int(pad_x + self.column_width * 0.2), int(pad_y + 0.9 * self.row_height), tags=("mode:%d"%(pad),"trigger_%d"%(pad)), anchor="sw")
			self.grid_canvas.create_image(int(pad_x + self.column_width * 0.9), int(pad_y + 0.9 * self.row_height), tags=("state:%d"%(pad),"trigger_%d"%(pad)), anchor="se")
			self.grid_canvas.tag_bind("trigger_%d"%(pad), '<Button-1>', self.on_pad_press)
			self.grid_canvas.tag_bind("trigger_%d"%(pad), '<ButtonRelease-1>', self.on_pad_release)
			self.refresh_pad(pad, True)
		self.update_selection_cursor()


	# Function to refresh pad if it has changed
	#   pad: Pad index
	#	force: True to froce refresh
	def refresh_pad(self, pad, force=False):
		if pad >= libseq.getSequencesInBank(self.parent.bank):
			return
		cell = self.grid_canvas.find_withtag("pad:%d"%(pad))
		if cell:
			if force or libseq.hasSequenceChanged(self.parent.bank, pad):
				mode = libseq.getPlayMode(self.parent.bank, pad)
				state = libseq.getPlayState(self.parent.bank, pad)
				if state == zynthian_gui_stepsequencer.SEQ_RESTARTING:
					state = zynthian_gui_stepsequencer.SEQ_PLAYING
				if state == zynthian_gui_stepsequencer.SEQ_STOPPINGSYNC:
					state = zynthian_gui_stepsequencer.SEQ_STOPPING
				group = libseq.getGroup(self.parent.bank, pad)
				foreground = "white"
				if libseq.getSequenceLength(self.parent.bank, pad) == 0 or mode == zynthian_gui_stepsequencer.SEQ_DISABLED:
					self.grid_canvas.itemconfig(cell, fill=zynthian_gui_stepsequencer.PAD_COLOUR_DISABLED)
				else:
					self.grid_canvas.itemconfig(cell, fill=zynthian_gui_stepsequencer.PAD_COLOUR_STOPPED[group%16])
				pad_x = (pad % self.columns) * self.column_width
				pad_y = int(pad / self.columns) * self.row_height
				if libseq.getSequenceLength(self.parent.bank, pad) == 0:
					mode = 0
				self.grid_canvas.itemconfig("lbl_pad:%d"%(pad), text=zynseq.get_sequence_name(self.parent.bank, pad), fill=foreground)
				self.grid_canvas.itemconfig("group:%s"%(pad), text=chr(65 + libseq.getGroup(self.parent.bank, pad)), fill=foreground)
				self.grid_canvas.itemconfig("mode:%d"%pad, image=self.mode_icon[mode])
				if state == 0 and libseq.isEmpty(self.parent.bank, pad):
					self.grid_canvas.itemconfig("state:%d"%pad, image=self.empty_icon)
				else:
					self.grid_canvas.itemconfig("state:%d"%pad, image=self.state_icon[state])


	# Function to move selection cursor
	def update_selection_cursor(self):
		if self.selected_pad >= libseq.getSequencesInBank(self.parent.bank):
			self.selected_pad = libseq.getSequencesInBank(self.parent.bank) - 1
		col = int(self.selected_pad / self.columns)
		row = self.selected_pad % self.columns
		self.grid_canvas.coords(self.selection,
				1 + col * self.column_width, 1 + row * self.row_height,
				(1 + col) * self.column_width - self.select_thickness, (1 + row) * self.row_height - self.select_thickness)
		self.grid_canvas.tag_raise(self.selection)


	# Function to handle pad press
	def on_pad_press(self, event):
		if self.parent.lst_menu.winfo_viewable():
			self.parent.hide_menu()
			return
		tags = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))
		pad = int(tags[0].split(':')[1])
		self.selected_pad = pad
		self.update_selection_cursor()
		if self.parent.param_editor_item:
			self.parent.show_param_editor(self.parent.param_editor_item)
			return
		self.grid_timer = Timer(1.4, self.on_grid_timer)
		self.grid_timer.start()


	# Function to handle pad release
	def on_pad_release(self, event):
		if self.grid_timer.isAlive():
			self.toggle_pad()
		self.grid_timer.cancel()


	# Function to toggle pad
	def toggle_pad(self):
		libseq.togglePlayState(self.parent.bank, self.selected_pad)


	# Function to handle grid press and hold
	def on_grid_timer(self):
		self.gridDragStart = None
		self.show_editor()


	# Function to show the editor (pattern or arranger based on sequence content)
	def show_editor(self):
		tracks_in_sequence = libseq.getTracksInSequence(self.parent.bank, self.selected_pad)
		patterns_in_track = libseq.getPatternsInTrack(self.parent.bank, self.selected_pad, 0)
		pattern = libseq.getPattern(self.parent.bank, self.selected_pad, 0, 0)
		if tracks_in_sequence != 1 or patterns_in_track !=1 or pattern == -1:
			self.parent.show_child(self.parent.arranger)
			return
		channel = libseq.getChannel(self.parent.bank, self.selected_pad, 0)
		self.parent.show_child(self.parent.pattern_editor, {"pattern":pattern, "channel":channel, "name":zynseq.get_sequence_name(self.parent.bank, self.selected_pad)})


	# Function to refresh status
	def refresh_status(self):
		if self.refresh_pending == 1:
			self.update_grid()
		for pad in range(0, self.columns**2):
			self.refresh_pad(pad)
		if self.parent.param_editor_item == "Trigger note":
			old_value = self.parent.get_param("Trigger note", "value")
			value = libseq.getTriggerNote(self.parent.bank, self.selected_pad)
			if old_value != value:
				if value < 128:
					self.parent.set_param("Trigger note", "value", value)
					self.parent.param_title_canvas.itemconfig("lbl_param_editor_value",
						text="Trigger note: %s%d(%d)" % (['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][value%12],int(value/12)-1, value))


	# Function to handle zynpots value change
	#   i: Zynpot index [0..n]
	#   dval: Zynpot value change
	def zynpot_cb(self, i, dval):
		if i == zynthian_gui_config.ENC_SELECT:
			# SELECT encoder adjusts horizontal pad selection
			pad = self.selected_pad + self.columns * dval
			col = int(pad / self.columns)
			row = pad % self.columns
			if col >= self.columns:
				col = 0
				row += 1
				pad = row + self.columns * col
			elif pad < 0:
				col = self.columns -1
				row -= 1
				pad = row + self.columns * col
			if row < 0 or row >= self.columns or col >= self.columns:
				return
			self.selected_pad = pad
			self.update_selection_cursor()
		elif i == zynthian_gui_config.ENC_BACK:
			# BACK encoder adjusts vertical pad selection
			pad = self.selected_pad + dval
			if pad < 0 or pad >= libseq.getSequencesInBank(self.parent.bank):
				return
			self.selected_pad = pad
			self.update_selection_cursor()


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def on_switch(self, switch, type):
		if self.parent.lst_menu.winfo_viewable():
			return False
		if self.parent.param_editor_item:
			return False
		if switch == zynthian_gui_config.ENC_SELECT:
			if type == 'S':
				self.toggle_pad()
			elif type == "B":
				self.show_editor()
			return True
		return False

#------------------------------------------------------------------------------
