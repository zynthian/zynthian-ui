#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Step-Sequencer Pad Trigger Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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

import tkinter
import logging
import tkinter.font as tkFont
from math import sqrt
from PIL import Image, ImageTk
from time import sleep
from threading import Timer
from collections import OrderedDict

# Zynthian specific modules
from zyngui import zynthian_gui_config
from . import zynthian_gui_base
from zyncoder.zyncore import lib_zyncore

SELECT_BORDER	= zynthian_gui_config.color_on
INPUT_CHANNEL_LABELS = ['OFF','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16']
NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Sequence / Pad Trigger GUI Class
#------------------------------------------------------------------------------

# Class implements step sequencer
class zynthian_gui_zynpad(zynthian_gui_base.zynthian_gui_base):

	# Function to initialise class
	def __init__(self):
		super().__init__()

		self.buttonbar_config = [
			(zynthian_gui_config.ENC_LAYER, 'MENU'),
			(zynthian_gui_config.ENC_BACK, 'BACK'),
			(zynthian_gui_config.ENC_SNAPSHOT, 'SNAPSHOT'),
			(zynthian_gui_config.ENC_SELECT, 'TRIGGER')
		]

		self.columns = 4 # Quantity of columns in grid
		self.selected_pad = 0 # Index of selected pad
		self.refresh_pending = 0 # 0=no refresh pending, 1=update grid
		self.bank = 1

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height
		self.select_thickness = 1 + int(self.width / 400) # Scale thickness of select border based on screen
		self.column_width = self.width / self.columns
		self.row_height = self.height / self.columns


		# Pad grid
		self.grid_canvas = tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height,
			bd=0,
			highlightthickness=0,
			relief='flat',
			bg = zynthian_gui_config.color_bg)
		self.grid_canvas.grid()
		self.grid_timer = Timer(1.4, self.on_grid_timer) # Grid press and hold timer

		# Icons
		self.mode_icon = [tkinter.PhotoImage() for i in range(7)]
		self.state_icon = [tkinter.PhotoImage() for i in range(4)]
		self.empty_icon = tkinter.PhotoImage()

		# Selection highlight
		self.selection = self.grid_canvas.create_rectangle(0, 0, self.column_width, self.row_height, fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")

		# Init touchbar
		self.init_buttonbar()

		self.select_bank(self.bank)


	#Function to set values of encoders
	def setup_zynpots(self):
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_LAYER, 0, 0)
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_BACK, 0, 0)
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_SNAPSHOT, 0, 0)
		lib_zyncore.setup_behaviour_zynpot(zynthian_gui_config.ENC_SELECT, 0, 1)


	# Function to show GUI
	#   params: Misc parameters
	def show(self):
		super().show()
		self.zyngui.zynseq.libseq.updateSequenceInfo()
		self.setup_zynpots()
		if self.param_editor_zctrl == None:
			self.set_title("Bank %d" % (self.bank))


	# Function to hide GUI
	def hide(self):
		super().hide()


	# Function to set quantity of pads
	def set_grid_size(self, value):
		columns = value + 1
		if columns > 8:
			columns = 8
		if self.zyngui.zynseq.libseq.getSequencesInBank(self.bank) > columns ** 2: #self.zyngui.zynseq.grid_size ** 2:
			self.zyngui.show_confirm("Reducing the quantity of sequences in bank {} will delete sequences but patterns will still be available. Continue?".format(self.bank), self.do_grid_size, columns)
		else:
			self.do_grid_size(columns)


	# Function to actually set quantity of pad
	#	columns: Quantity of columns (and rows) in grid
	def do_grid_size(self, columns):
		# To avoid odd behaviour we stop all sequences from playing before changing grid size (blunt but effective!)
		for seq in range(self.zyngui.zynseq.libseq.getSequencesInBank(self.bank)):
			self.zyngui.zynseq.libseq.setPlayState(self.bank, seq, zynthian_gui_config.SEQ_STOPPED)
		channels = []
		groups = []
		for column in range(columns):
			channels.append(self.zyngui.zynseq.libseq.getChannel(self.bank, column * self.columns, 0))
			groups.append(self.zyngui.zynseq.libseq.getGroup(self.bank, column * self.columns))
		delta = columns - self.columns
		if delta > 0:
			# Growing grid so add extra sequences
			for column in range(self.columns):
				for row in range(self.columns, self.columns + delta):
					pad = row + column * columns
					self.zyngui.zynseq.libseq.insertSequence(self.bank, pad)
					self.zyngui.zynseq.libseq.setChannel(self.bank, pad, channels[column])
					self.zyngui.zynseq.libseq.setGroup(self.bank, pad, groups[column])
					self.zyngui.zynseq.set_sequence_name(self.bank, pad, "%s"%(pad + 1))
			for column in range(self.columns, columns):
				for row in range(columns):
					pad = row + column * columns
					self.zyngui.zynseq.libseq.insertSequence(self.bank, pad)
					self.zyngui.zynseq.libseq.setChannel(self.bank, pad, column)
					self.zyngui.zynseq.libseq.setGroup(self.bank, pad, column)
					self.zyngui.zynseq.set_sequence_name(self.bank, pad, "{}".format(pad + 1))
		if delta < 0:
			# Shrinking grid so remove excess sequences
			self.zyngui.zynseq.libseq.setSequencesInBank(self.bank, columns * self.columns) # Lose excess columns
			for offset in range(columns, columns * columns + 1, columns):
				for pad in range(-delta):
					self.zyngui.zynseq.libseq.removeSequence(self.bank, offset)
		self.columns = columns
		self.refresh_pending = 1


	# Function to name selected sequence
	def rename_sequence(self, params=None):
		self.zyngui.show_keyboard(self.do_rename_sequence, self.zyngui.zynseq.get_sequence_name(self.bank, self.selected_pad), 16)


	# Function to rename selected sequence
	def do_rename_sequence(self, name):
		self.zyngui.zynseq.set_sequence_name(self.bank, self.selected_pad, name)


	# Function to get MIDI channel of selected pad
	#	returns: MIDI channel (1..16)
	def get_pad_channel(self):
		return self.zyngui.zynseq.libseq.getChannel(self.bank, self.selected_pad, 0) + 1
		#TODO: A pad may drive a complex sequence with multiple tracks hence multiple channels - need to go back to using Group


	# Function to get the MIDI trigger note
	#   returns: MIDI note
	def get_trigger_note(self):
		trigger = self.zyngui.zynseq.libseq.getTriggerNote(self.bank, self.selected_pad)
		if trigger > 128:
			trigger = 128
		return trigger


	# Function to reset trigger note to None
	def reset_trigger_note(self):
		self.zyngui.zynseq.trigger_note = 0xFF
		self.refreshParamEditor()


	# Function to get group of selected track
	def get_group(self):
		return self.zyngui.zynseq.libseq.getGroup(self.bank, self.selected_pad)


	# Function to get the mode of the currently selected pad
	#   returns: Mode of selected pad
	def get_selected_pad_mode(self):
		return self.zyngui.zynseq.libseq.getPlayMode(self.bank, self.selected_pad)


	# Function to select bank
	#	bank: Index of bank to select
	def select_bank(self, bank):
		if bank > 0:
			self.bank = bank
			if self.zyngui.zynseq.libseq.getSequencesInBank(bank) == 0:
				self.zyngui.zynseq.libseq.setSequencesInBank(bank, 16)
				for column in range(4):
					if column == 3:
						channel = 9
					else:
						channel = column
					for row in range(4):
						pad = row + 4 * column
						self.zyngui.zynseq.set_sequence_name(bank, pad, "{}".format(self.zyngui.zynseq.libseq.getPatternAt(bank, pad, 0, 0)))
						self.zyngui.zynseq.libseq.setGroup(bank, pad, channel)
						self.zyngui.zynseq.libseq.setChannel(bank, pad, 0, channel)
			self.refresh_pending = 1


	# Function called when sequence set loaded from file
	def get_trigger_channel(self):
		if(self.zyngui.zynseq.libseq.getTriggerChannel() > 15):
			return 0
		return self.zyngui.zynseq.libseq.getTriggerChannel() + 1


	# Function to clear and calculate grid sizes
	def update_grid(self):
		self.refresh_pending = 0
		self.grid_canvas.delete(tkinter.ALL)
		pads = self.zyngui.zynseq.libseq.getSequencesInBank(self.bank)
		if pads < 1:
			return
		self.columns = int(sqrt(pads))
		self.column_width = self.width / self.columns
		self.row_height = self.height / self.columns
		self.selection = self.grid_canvas.create_rectangle(0, 0, int(self.column_width), int(self.row_height), fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")

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
		self.state_icon[zynthian_gui_config.SEQ_STOPPED] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/starting.png").resize(iconsize))
		self.state_icon[zynthian_gui_config.SEQ_STARTING] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/playing.png").resize(iconsize))
		self.state_icon[zynthian_gui_config.SEQ_PLAYING] = ImageTk.PhotoImage(img)
		img = (Image.open("/zynthian/zynthian-ui/icons/stopping.png").resize(iconsize))
		self.state_icon[zynthian_gui_config.SEQ_STOPPING] = ImageTk.PhotoImage(img)

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
		if pad >= self.zyngui.zynseq.libseq.getSequencesInBank(self.bank):
			return
		cell = self.grid_canvas.find_withtag("pad:%d"%(pad))
		if cell:
			if force or self.zyngui.zynseq.libseq.hasSequenceChanged(self.bank, pad):
				mode = self.zyngui.zynseq.libseq.getPlayMode(self.bank, pad)
				state = self.zyngui.zynseq.libseq.getPlayState(self.bank, pad)
				if state == zynthian_gui_config.SEQ_RESTARTING:
					state = zynthian_gui_config.SEQ_PLAYING
				if state == zynthian_gui_config.SEQ_STOPPINGSYNC:
					state = zynthian_gui_config.SEQ_STOPPING
				group = self.zyngui.zynseq.libseq.getGroup(self.bank, pad)
				foreground = "white"
				if self.zyngui.zynseq.libseq.getSequenceLength(self.bank, pad) == 0 or mode == zynthian_gui_config.SEQ_DISABLED:
					self.grid_canvas.itemconfig(cell, fill=zynthian_gui_config.PAD_COLOUR_DISABLED)
				else:
					self.grid_canvas.itemconfig(cell, fill=zynthian_gui_config.PAD_COLOUR_STOPPED[group%16])
				pad_x = (pad % self.columns) * self.column_width
				pad_y = int(pad / self.columns) * self.row_height
				if self.zyngui.zynseq.libseq.getSequenceLength(self.bank, pad) == 0:
					mode = 0
				self.grid_canvas.itemconfig("lbl_pad:%d"%(pad), text=self.zyngui.zynseq.get_sequence_name(self.bank, pad), fill=foreground)
				self.grid_canvas.itemconfig("group:%s"%(pad), text=chr(65 + self.zyngui.zynseq.libseq.getGroup(self.bank, pad)), fill=foreground)
				self.grid_canvas.itemconfig("mode:%d"%pad, image=self.mode_icon[mode])
				if state == 0 and self.zyngui.zynseq.libseq.isEmpty(self.bank, pad):
					self.grid_canvas.itemconfig("state:%d"%pad, image=self.empty_icon)
				else:
					self.grid_canvas.itemconfig("state:%d"%pad, image=self.state_icon[state])


	# Function to move selection cursor
	def update_selection_cursor(self):
		if self.selected_pad >= self.zyngui.zynseq.libseq.getSequencesInBank(self.bank):
			self.selected_pad = self.zyngui.zynseq.libseq.getSequencesInBank(self.bank) - 1
		col = int(self.selected_pad / self.columns)
		row = self.selected_pad % self.columns
		self.grid_canvas.coords(self.selection,
				1 + col * self.column_width, 1 + row * self.row_height,
				(1 + col) * self.column_width - self.select_thickness, (1 + row) * self.row_height - self.select_thickness)
		self.grid_canvas.tag_raise(self.selection)


	# Function to handle pad press
	def on_pad_press(self, event):
		tags = self.grid_canvas.gettags(self.grid_canvas.find_withtag(tkinter.CURRENT))
		pad = int(tags[0].split(':')[1])
		self.selected_pad = pad
		self.update_selection_cursor()
		if self.param_editor_zctrl:
			self.disable_param_editor()
		self.grid_timer = Timer(1.4, self.on_grid_timer)
		self.grid_timer.start()


	# Function to handle pad release
	def on_pad_release(self, event):
		if self.grid_timer.isAlive():
			self.toggle_pad()
		self.grid_timer.cancel()


	# Function to toggle pad
	def toggle_pad(self):
		self.zyngui.zynseq.libseq.togglePlayState(self.bank, self.selected_pad)


	# Function to handle grid press and hold
	def on_grid_timer(self):
		self.gridDragStart = None
		self.show_editor()


	# Function to add menus
	def show_menu(self):
		options = OrderedDict()
		options['Arranger'] = 1
		options['Bank'] = 1
		options['Beats per bar'] = 1
		options['-------------------'] = None
		options['Play mode'] = 1
		options['MIDI channel'] = 1
		options['Trigger channel'] = 1
		options['Trigger note'] = 1
		options['--------------------'] = None
		options['Grid size'] = 1
		options['Rename sequence'] = 1
		self.zyngui.screens['option'].config("ZynPad Menu", options, self.menu_cb)
		self.zyngui.show_screen('option')


	def menu_cb(self, option, params):
		if option == 'Arranger':
			self.zyngui.show_screen('arranger')
		elif option == 'Bank':
			self.enable_param_editor(self, 'bank', 'Bank', {'value_min':1, 'value_max':64, 'value':self.bank})
		if option == 'Beats per bar':
			self.enable_param_editor(self, 'bpb', 'Beats per bar', {'value_min':1, 'value_max':64, 'value':self.zyngui.zynseq.libseq.getBeatsPerBar()})
		elif option == 'Play mode':
			self.enable_param_editor(self, 'playmode', 'Play mode', {'labels':zynthian_gui_config.PLAY_MODES, 'value':self.zyngui.zynseq.libseq.getPlayMode(self.bank, self.selected_pad)}, self.set_play_mode)
		elif option == 'MIDI channel':
			self.enable_param_editor(self, 'pad_chan', 'MIDI channel', {'value_max':15, 'value':self.get_pad_channel()})
		elif option == 'Trigger channel':
			self.enable_param_editor(self, 'trigger_chan', 'Trigger channel', {'labels':INPUT_CHANNEL_LABELS, 'value':self.get_trigger_channel()}, self.set_trigger_channel)
		elif option == 'Trigger note':
			labels = ['None']
			for note in range(128):
				labels.append("{}{}".format(NOTE_NAMES[note % 12],int(note // 12)))
			labels.append('None')
			self.enable_param_editor(self, 'trigger_note', 'Trigger note', {'labels':labels, 'value':self.get_trigger_note() + 1})
		elif option == 'Grid size':
			labels = []
			for i in range(1, 9):
				labels.append("{}x{}".format(i,i))
			self.enable_param_editor(self, 'grid_size', 'Grid size', {'labels':labels, 'value':self.columns - 1}, self.set_grid_size)
		elif option == 'Rename sequence':
			self.rename_sequence()


	def send_controller_value(self, zctrl):
		if zctrl.symbol == 'bank':
			self.select_bank(zctrl.value)
		elif zctrl.symbol == 'bpb':
			self.zyngui.zynseq.libseq.setBeatsPerBar(zctrl.value)
		elif zctrl.symbol == 'playmode':
			self.set_play_mode(zctrl.value)
		elif zctrl.symbol == 'pad_chan':
			self.set_pad_channel(zctrl.value)
		elif zctrl.symbol == 'trigger_chan':
			self.set_trigger_channel(zctrl.value)
		elif zctrl.symbol == 'trigger_note':
			self.set_trigger_note(zctrl.value)


	#	Function to set the playmode of the selected pad
	def set_play_mode(self, mode):
		self.zyngui.zynseq.libseq.setPlayMode(self.bank, self.selected_pad, mode)


	#	Function to set pad MIDI channel & group
	def set_pad_channel(self, chan):
		self.zyngui.zynseq.ibseq.setChannel(self.bank, self.selected_pad, 0, chan - 1)
		self.zyngui.zynseq.libseq.setGroup(self.bank, self.selected_pad, chan - 1)
		self.refresh_pending = 1


	#	Function to set trigger channel
	def set_trigger_channel(self, chan):
		if chan:
			self.zyngui.zynseq.libseq.setTriggerChannel(chan - 1)
		else:
			self.zyngui.zynseq.libseq.setTriggerChannel(0xFF)


	#	Function to set trigger note
	def set_trigger_note(self, note):
		if note > 128 or note <= 0:
			note = 128
		else:
			note -= 1
		self.zyngui.zynseq.libseq.setTriggerNote(self.bank, self.selected_pad, note)
		self.zyngui.zynseq.libseq.enableMidiLearn(self.bank, self.selected_pad)



	# Function to show the editor (pattern or arranger based on sequence content)
	def show_editor(self):
		tracks_in_sequence = self.zyngui.zynseq.libseq.getTracksInSequence(self.bank, self.selected_pad)
		patterns_in_track = self.zyngui.zynseq.libseq.getPatternsInTrack(self.bank, self.selected_pad, 0)
		pattern = self.zyngui.zynseq.libseq.getPattern(self.bank, self.selected_pad, 0, 0)
		if tracks_in_sequence != 1 or patterns_in_track !=1 or pattern == -1:
			self.zyngui.toggle_screen("arranger")
			return
		self.zyngui.screens['pattern_editor'].channel = self.zyngui.zynseq.libseq.getChannel(self.bank, self.selected_pad, 0)
		self.zyngui.screens['pattern_editor'].load_pattern(pattern)
		self.zyngui.toggle_screen("pattern_editor")


	# Function to refresh status
	def refresh_status(self, status):
		super().refresh_status(status)
		if self.refresh_pending == 1:
			self.update_grid()
		for pad in range(0, self.columns**2):
			self.refresh_pad(pad)


	# Function to handle zynpots value change
	#   i: Zynpot index [0..n]
	#   dval: Zynpot value change
	def zynpot_cb(self, i, dval):
		if super().zynpot_cb(i, dval):
			return
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
			if pad < 0 or pad >= self.zyngui.zynseq.libseq.getSequencesInBank(self.bank):
				return
			self.selected_pad = pad
			self.update_selection_cursor()
		elif i == zynthian_gui_config.ENC_SNAPSHOT:
			self.zyngui.zynseq.nudge_tempo(dval)
			self.set_title("Tempo: {:.1f}".format(self.zyngui.zynseq.get_tempo()), None, None, 2)


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if super().switch(switch, type):
			return True
		if switch == zynthian_gui_config.ENC_SELECT:
			if type == 'S':
				self.toggle_pad()
			elif type == "B":
				self.show_editor()
			return True
		elif switch == zynthian_gui_config.ENC_LAYER and type == 'S':
			self.show_menu()
			return True
		return False

#------------------------------------------------------------------------------
