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
from math import sqrt
from PIL import Image, ImageTk
from threading import Timer
from collections import OrderedDict

# Zynthian specific modules
import zynautoconnect
from zyngui import zynthian_gui_config
from . import zynthian_gui_base
from zyncoder.zyncore import lib_zyncore
from zynlibs.zynseq import zynseq

SELECT_BORDER = zynthian_gui_config.color_on
INPUT_CHANNEL_LABELS = ['OFF', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16']
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

#------------------------------------------------------------------------------
# Zynthian Step-Sequencer Sequence / Pad Trigger GUI Class
#------------------------------------------------------------------------------

# Class implements step sequencer
class zynthian_gui_zynpad(zynthian_gui_base.zynthian_gui_base):

	# Function to initialise class
	def __init__(self):
		logging.getLogger('PIL').setLevel(logging.WARNING)

		super().__init__()

		self.ctrl_order = zynthian_gui_config.layout['ctrl_order']
		self.selected_pad = 0 # Index of selected pad
		self.redraw_pending = 2 # 0=no refresh pending, 1=update grid, 2=rebuild grid
		self.redrawing = False # True to block further redraws until complete
		self.bank = self.zyngui.zynseq.bank # The last successfully selected bank - used to update stale views
		self.columns = self.zyngui.zynseq.col_in_bank # Columns used during last layout - used to update stale views
		self.midi_learn = False
		self.trigger_channel = 0
		self.trigger_device = 0
		self.trigger_device_driver = False

		# Geometry vars
		self.select_thickness = 1 + int(self.width / 400) # Scale thickness of select border based on screen
		self.column_width = self.width / self.zyngui.zynseq.col_in_bank
		self.row_height = self.height / self.zyngui.zynseq.col_in_bank

		# Pad grid
		self.grid_canvas = tkinter.Canvas(self.main_frame,
			width=self.width,
			height=self.height,
			bd=0,
			highlightthickness=0,
			bg = zynthian_gui_config.color_bg)
		self.main_frame.columnconfigure(0, weight=1)
		self.main_frame.rowconfigure(0, weight=1)
		self.grid_canvas.grid()
		self.grid_timer = Timer(1.4, self.on_grid_timer) # Grid press and hold timer

		self.build_grid()
		self.init_trigger_device()


	#Function to set values of encoders
	def setup_zynpots(self):
		lib_zyncore.setup_behaviour_zynpot(0, 0)
		lib_zyncore.setup_behaviour_zynpot(1, 0)
		lib_zyncore.setup_behaviour_zynpot(2, 0)
		lib_zyncore.setup_behaviour_zynpot(3, 0)


	# Function to show GUI
	#   params: Misc parameters
	def build_view(self):
		self.zyngui.zynseq.libseq.updateSequenceInfo()
		self.setup_zynpots()
		self.refresh_status(force=True)
		if self.param_editor_zctrl == None:
			self.set_title("Scene {}".format(self.bank))


	# Function to hide GUI
	def hide(self):
		super().hide()


	# Function to set quantity of pads
	def set_grid_size(self, value):
		columns = value + 1
		if columns > 8:
			columns = 8
		if self.zyngui.zynseq.libseq.getSequencesInBank(self.bank) > columns ** 2:
			self.zyngui.show_confirm("Reducing the quantity of sequences in bank {} will delete sequences but patterns will still be available. Continue?".format(self.bank), self._set_grid_size, columns)
		else:
			self._set_grid_size(columns)


	def _set_grid_size(self, value):
		self.zyngui.zynseq.update_bank_grid(value)
		self.refresh_status(force=True)


	# Function to name selected sequence
	def rename_sequence(self, params=None):
		self.zyngui.show_keyboard(self.do_rename_sequence, self.zyngui.zynseq.get_sequence_name(self.bank, self.selected_pad), 16)


	# Function to rename selected sequence
	def do_rename_sequence(self, name):
		self.zyngui.zynseq.set_sequence_name(self.bank, self.selected_pad, name)
		self.refresh_pad(self.selected_pad, True)


	def update_layout(self):
		super().update_layout()
		self.redraw_pending = 2
		self.update_grid()


	# Function to create 64 pads
	def build_grid(self):
		columns = 8
		column_width = self.width / columns
		row_height = self.height / columns
		fs1 = int(row_height * 0.15)
		fs2 = int(row_height * 0.11)
		self.selection = self.grid_canvas.create_rectangle(0, 0, int(self.column_width), int(self.row_height), fill="", outline=SELECT_BORDER, width=self.select_thickness, tags="selection")

		self.pads = []
		for pad in range(64):
			pad_struct = {}
			pad_x = int(pad / columns) * column_width
			pad_y = pad % columns * row_height
			header_h = int(0.28 * self.row_height)
			pad_struct["header"] = self.grid_canvas.create_rectangle(pad_x, pad_y, pad_x + self.column_width - 2, pad_y + header_h,
				fill='darkgrey',
				width=0,
				tags=(f"padh:{pad}", "gridcell", f"pad:{pad}", "pad"))
			pad_struct["body"] = self.grid_canvas.create_rectangle(pad_x, pad_y + header_h, pad_x + self.column_width - 2, pad_y + self.row_height - 2,
				fill='grey',
				width=0,
				tags=(f"padb:{pad}", "gridcell", f"pad:{pad}", "pad"))
			posx = pad_x + int(0.02 * self.column_width)
			posy = pad_y + int(0.04 * self.row_height)
			pad_struct["mode"] = self.grid_canvas.create_image(posx + int(0.125 * self.column_width), posy,
				anchor="nw",
				tags=(f"mode:{pad}", f"pad:{pad}", "pad"))
			posy = pad_y + int(0.05 * self.row_height)
			pad_struct["group"] = self.grid_canvas.create_text(posx + int(3 * 0.125 * self.column_width), posy,
				anchor="n",
				font=(zynthian_gui_config.font_family, fs2),
				fill=zynthian_gui_config.color_panel_tx,
				tags=(f"group:{pad}", f"pad:{pad}", "pad"))
			pad_struct["num"] = self.grid_canvas.create_text(posx + int(5 * 0.125 * self.column_width), posy,
				anchor="n",
				font=(zynthian_gui_config.font_family, fs2),
				fill=zynthian_gui_config.color_panel_tx,
				tags=(f"num:{pad}", f"pad:{pad}", "pad"))
			pad_struct["state"] = self.grid_canvas.create_image(posx + int(7 * 0.125 * self.column_width), posy,
				anchor="n",
				tags=(f"state:{pad}", f"pad:{pad}", "pad"))
			posx = pad_x + int(0.03 * self.column_width)
			pad_struct["title"] = self.grid_canvas.create_text(posx, posy + 2 * fs1,
				width=self.column_width - 0.06 * self.column_width,
				anchor="nw", justify="left",
				font=(zynthian_gui_config.font_family, fs1),
				fill=zynthian_gui_config.color_panel_tx,
				tags=(f"title:{pad}", f"pad:{pad}", "pad"))
			self.pads.append(pad_struct)
		self.grid_canvas.tag_bind("pad", '<Button-1>', self.on_pad_press)
		self.grid_canvas.tag_bind("pad", '<ButtonRelease-1>', self.on_pad_release)

		# Icons
		self.empty_icon = tkinter.PhotoImage()
		self.mode_icon = [[] for i in range(9)]
		self.state_icon = [[] for i in range(9)]

		for columns in range(1, 9):
			column_width = self.width / columns
			row_height = self.height / columns
			lst = [self.empty_icon] # Not sure this is right - should be a ImageTk.PhotoImage
			iconsize = (int(column_width * 0.22), int(row_height * 0.2))
			for f in ["zynpad_mode_oneshot", "zynpad_mode_loop", "zynpad_mode_oneshotall", "zynpad_mode_loopall", "zynpad_mode_oneshotsync", "zynpad_mode_loopsync"]:
				img = Image.open(f"/zynthian/zynthian-ui/icons/{f}.png")
				lst.append(ImageTk.PhotoImage(img.resize(iconsize)))
			self.mode_icon[columns] = lst.copy()
			iconsize = (int(row_height * 0.18), int(row_height * 0.18))
			lst = []
			for f in ["stopped", "playing", "stopping", "starting"]:
				img = Image.open(f"/zynthian/zynthian-ui/icons/{f}.png")
				lst.append(ImageTk.PhotoImage(img.resize(iconsize)))
			self.state_icon[columns] = lst.copy()


	# Function to clear and calculate grid sizes
	def update_grid(self):
		self.redrawing = True
		self.column_width = self.width / self.zyngui.zynseq.col_in_bank
		self.row_height = self.height / self.zyngui.zynseq.col_in_bank

		# Update pads location / size
		fs1 = int(self.row_height * 0.15)
		fs2 = int(self.row_height * 0.11)
		self.grid_canvas.itemconfig("pad", state=tkinter.HIDDEN)
		self.update_selection_cursor()
		for col in range(self.zyngui.zynseq.col_in_bank):
			pad_x = int(col * self.column_width)
			for row in range(self.zyngui.zynseq.col_in_bank):
				pad_y = int(row * self.row_height)
				pad = row + col * self.zyngui.zynseq.col_in_bank
				header_h = int(0.28 * self.row_height)
				self.grid_canvas.itemconfig(self.pads[pad]["group"], font=(zynthian_gui_config.font_family, fs2))
				self.grid_canvas.itemconfig(self.pads[pad]["num"], font=(zynthian_gui_config.font_family, fs2))
				self.grid_canvas.itemconfig(self.pads[pad]["title"], width=int(0.96 * self.column_width), font=(zynthian_gui_config.font_family, fs1))
				self.grid_canvas.itemconfig(f"pad:{pad}", state=tkinter.NORMAL)
				self.grid_canvas.coords(self.pads[pad]["header"], pad_x, pad_y, pad_x + self.column_width - 2, pad_y + header_h)
				self.grid_canvas.coords(self.pads[pad]["body"], pad_x, pad_y + header_h, pad_x + self.column_width - 2, pad_y + self.row_height - 2)
				posx = pad_x + int(0.02 * self.column_width)
				posy = pad_y + int(0.04 * self.row_height)
				self.grid_canvas.coords(self.pads[pad]["mode"], posx + int(0.125), posy)
				posy = pad_y + int(0.05 * self.row_height)
				self.grid_canvas.coords(self.pads[pad]["group"], posx + int(3 * 0.125 * self.column_width), posy)
				self.grid_canvas.coords(self.pads[pad]["num"], posx + int(5 * 0.125 * self.column_width), posy)
				self.grid_canvas.coords(self.pads[pad]["state"], posx + int(7 * 0.125 * self.column_width), posy)
				posx = pad_x + int(0.03 * self.column_width)
				self.grid_canvas.coords(self.pads[pad]["title"], posx, posy + 2 * fs1)

		self.redrawing = False
		self.columns = self.zyngui.zynseq.col_in_bank


	# Function to refresh pad if it has changed
	#   pad: Pad index
	#	force: True to force refresh
	def refresh_pad(self, pad, force=False):
		if pad > 63:
			return
		cellh = self.pads[pad]["header"]
		# It MUST be called for cleaning the dirty bit
		changed_state = self.zyngui.zynseq.libseq.hasSequenceChanged(self.bank, pad)
		if changed_state or force:
			mode = self.zyngui.zynseq.libseq.getPlayMode(self.bank, pad)
			state = self.get_pad_state(pad)
			group = self.zyngui.zynseq.libseq.getGroup(self.bank, pad)
			foreground = "white"
			cellb = self.pads[pad]["body"]
			if self.zyngui.zynseq.libseq.getSequenceLength(self.bank, pad) == 0 or mode == zynseq.SEQ_DISABLED:
				self.grid_canvas.itemconfig(cellh, fill=zynthian_gui_config.PAD_COLOUR_DISABLED)
				self.grid_canvas.itemconfig(cellb, fill=zynthian_gui_config.PAD_COLOUR_DISABLED_LIGHT)
			else:
				self.grid_canvas.itemconfig(cellh, fill=zynthian_gui_config.PAD_COLOUR_GROUP[group%16])
				self.grid_canvas.itemconfig(cellb, fill=zynthian_gui_config.PAD_COLOUR_GROUP_LIGHT[group % 16])
			if self.zyngui.zynseq.libseq.getSequenceLength(self.bank, pad) == 0:
				mode = 0
			group = chr(65 + self.zyngui.zynseq.libseq.getGroup(self.bank, pad))
			#patnum = self.zyngui.zynseq.libseq.getPatternAt(self.bank, pad, 0, 0)
			chan = self.zyngui.zynseq.libseq.getChannel(self.bank, pad, 0)
			title = self.zyngui.zynseq.get_sequence_name(self.bank, pad)
			try:
				str(int(title))
				layer = self.zyngui.screens['layer'].get_root_layer_by_midi_chan(chan)
				if layer:
					title = layer.preset_name.replace("_", " ")
				else:
					title = ""
			except:
				pass
			self.grid_canvas.itemconfig(self.pads[pad]["title"], text=title, fill=foreground)
			self.grid_canvas.itemconfig(self.pads[pad]["group"], text=f"CH{chan+1}", fill=foreground)
			self.grid_canvas.itemconfig(self.pads[pad]["num"], text=f"{group}{pad+1}", fill=foreground)
			self.grid_canvas.itemconfig(self.pads[pad]["mode"], image=self.mode_icon[self.zyngui.zynseq.col_in_bank][mode])
			if state == 0 and self.zyngui.zynseq.libseq.isEmpty(self.bank, pad):
				self.grid_canvas.itemconfig(self.pads[pad]["state"], image=self.empty_icon)
			else:
				self.grid_canvas.itemconfig(self.pads[pad]["state"], image=self.state_icon[self.zyngui.zynseq.col_in_bank][state])

			if callable(self.update_trigger_device_pad):
				#TODO: This should be sent on change of state of any sequence, not just visible within GUI
				self.update_trigger_device_pad(pad, state, mode)


	#------------------------------------------------------------------------------------------------------------------
	# Some useful functions
	#------------------------------------------------------------------------------------------------------------------

	def set_bank(self, bank):
		self.zyngui.zynseq.select_bank(bank)
		self.refresh_status(force=True)


	def get_pad_state(self, pad):
		state = self.zyngui.zynseq.libseq.getPlayState(self.bank, pad)
		if state == zynseq.SEQ_RESTARTING:
			state = zynseq.SEQ_PLAYING
		elif state == zynseq.SEQ_STOPPINGSYNC:
			state = zynseq.SEQ_STOPPING
		return state


	def get_xy_from_pad(self, pad):
		col = pad // self.zyngui.zynseq.col_in_bank
		row = pad % self.zyngui.zynseq.col_in_bank
		return (col, row)


	def get_pad_from_xy(self, col, row):
		if col < self.zyngui.zynseq.col_in_bank and row < self.zyngui.zynseq.col_in_bank:
			return col * self.zyngui.zynseq.col_in_bank + row
		else:
			return -1


	#------------------------------------------------------------------------------------------------------------------
	# Trigger MIDI device integration
	#------------------------------------------------------------------------------------------------------------------

	def sync_state(self):
		self.set_trigger_device()
		self.set_trigger_channel()


	def set_trigger_channel(self, chan=None):
		if chan is None:
			chan = self.zyngui.zynseq.libseq.getTriggerChannel()
		if chan != self.trigger_channel:
			self.zyngui.zynseq.libseq.setTriggerChannel(chan)
			self.trigger_channel = chan


	def set_trigger_device(self, idev=None):
		if idev is None:
			idev = self.zyngui.zynseq.libseq.getTriggerDevice()
		if idev != self.trigger_device:
			# Currently selected device, if any ...
			if self.trigger_device > 0:
				# Restore routing & remove from feedback list
				lib_zyncore.zmip_set_route_extdev(self.trigger_device-1, 1)
				zynautoconnect.remove_midi_fb_port(self.trigger_device-1)
				# Call end function
				self.end_trigger_device()

			# Set new selected device (idev)
			self.trigger_device = idev
			self.zyngui.zynseq.libseq.setTriggerDevice(idev)

			# New selected device => Unroute & add feedback list
			if self.trigger_device > 0:
				lib_zyncore.zmip_set_route_extdev(self.trigger_device-1, 0)
				zynautoconnect.add_midi_fb_port(self.trigger_device-1)
				zynautoconnect.midi_autoconnect(True)

			# Initialize new selected device
			self.init_trigger_device(idev)
			self.refresh_trigger_device(force=True)


	def init_trigger_device(self, idev=None):
		if idev is None:
			idev = self.trigger_device
		devname = zynautoconnect.get_midi_device_name(idev)
		logging.debug("Initializing Trigger Device {} => {}".format(idev, devname))
		self.trigger_device_driver = True
		if devname.startswith("Launchpad_Mini"):
			self.init_launchpad_mini()
		elif devname.startswith("Launchkey_Mini_MK3_MIDI_2"):
			self.init_launchkey_mini_3()
		else:
			self.trigger_device_driver = False
			self.end_trigger_device = self._do_nothing
			self.update_trigger_device_bank = self._do_nothing
			self.update_trigger_device_pad = self._do_nothing
			self.midi_event_trigger_device = self._do_nothing
			self.light_off_trigger_device = self._do_nothing


	def refresh_trigger_device(self, force=False):
		# When zynpad is shown, this is done by refresh_status, so no need to refresh twice
		if force or not self.shown:
			self.refresh_trigger_device_pads(force)
		if force:
			self.refresh_trigger_device_extra()


	def refresh_trigger_device_extra(self):
		self.update_trigger_device_bank()


	def refresh_trigger_device_pads(self, force=False):
		if self.trigger_device_driver:
			for pad in range(self.zyngui.zynseq.col_in_bank ** 2):
				# It MUST be called for cleaning the dirty bit
				changed_state = self.zyngui.zynseq.libseq.hasSequenceChanged(self.bank, pad)
				if changed_state or force:
					mode = self.zyngui.zynseq.libseq.getPlayMode(self.bank, pad)
					state = self.get_pad_state(pad)
					self.update_trigger_device_pad(pad, state, mode)


	def refresh_trigger_device_pad(self, pad, force=False):
		# It MUST be called for cleaning the dirty bit
		changed_state = self.zyngui.zynseq.libseq.hasSequenceChanged(self.bank, pad)
		if self.trigger_device_driver and (changed_state or force):
			mode = self.zyngui.zynseq.libseq.getPlayMode(self.bank, pad)
			state = self.get_pad_state(pad)
			self.update_trigger_device_pad(pad, state, mode)


	def _do_nothing(self, *args):
		pass

	end_trigger_device = _do_nothing
	update_trigger_device_bank = _do_nothing
	update_trigger_device_pad = _do_nothing
	midi_event_trigger_device = _do_nothing
	light_off_trigger_device = _do_nothing

	#------------------------------------------------------------------------------------------------------------------
	# Launchpad Mini Integration
	#------------------------------------------------------------------------------------------------------------------

	def init_launchpad_mini(self):
		# Light-Off all LEDs
		self.light_off_launchpad_mini()

		# Bind driver functions
		self.end_trigger_device = self.end_launchpad_mini
		self.update_trigger_device_bank = self.update_launchpad_mini_bank
		self.update_trigger_device_pad = self.update_launchpad_mini_pad
		self.midi_event_trigger_device = self.midi_event_launchpad_mini
		self.light_off_trigger_device = self.light_off_launchpad_mini


	def end_launchpad_mini(self):
		self.light_off_launchpad_mini()


	# Scene LED feedback
	def update_launchpad_mini_bank(self):
		#logging.debug("Updating Launchpad MINI bank leds")
		col = 8
		for row in range(0,8):
			note = 16 * row + col
			if row == self.bank - 1:
				lib_zyncore.ctrlfb_send_note_on(0, note, 0x3C)
			else:
				lib_zyncore.ctrlfb_send_note_on(0, note, 0xC)


	def update_launchpad_mini_pad(self, pad, state, mode):
		#logging.debug("Updating Launchpad MINI pad {}".format(pad))
		col, row = self.get_xy_from_pad(pad)
		note = 16 * row + col
		if mode == 0:
			vel = 0xC
		elif state == zynseq.SEQ_PLAYING:
			vel = 0x3C
		elif state == zynseq.SEQ_STARTING:
			# vel = 0x38
			vel = 0x3A
		elif state == zynseq.SEQ_STOPPING:
			vel = 0x0B
		elif state == zynseq.SEQ_STOPPED:
			vel = 0x3F
		else:
			vel = 0xC
		lib_zyncore.ctrlfb_send_note_on(0, note, vel)


	def midi_event_launchpad_mini(self, ev):
		#logging.debug("Launchpad MINI MIDI handler => {}".format(ev))
		evtype = (ev & 0xF00000) >> 20
		if evtype == 9:
			note = (ev >> 8) & 0x7F
			col, row = self._launchpad_mini_get_note_xy(note)
			# scene change
			if col == 8:
				self.set_bank(row+1)
				return True
			# launch/stop pad
			pad = self.get_pad_from_xy(col, row)
			if pad >= 0:
				self.zyngui.zynseq.libseq.togglePlayState(self.bank, pad)
				return True


	# Light-Off all LEDs
	def light_off_launchpad_mini(self):
		for row in range(8):
			for col in range(9):
				note = 16 * row + col
				lib_zyncore.ctrlfb_send_note_on(0, note, 0xC)

	#--------------------------------------------------------------------------

	def _launchpad_mini_get_note_xy(self, note):
		row = note // 16
		col = note % 16
		return col, row

	#------------------------------------------------------------------------------------------------------------------
	# /Launchpad Mini Integration
	# ------------------------------------------------------------------------------------------------------------------

	#------------------------------------------------------------------------------------------------------------------
	# Launchkey Mini Integration
	# ------------------------------------------------------------------------------------------------------------------

	def init_launchkey_mini_3(self):

		# Enable session mode on launchkey
		lib_zyncore.ctrlfb_send_note_on(15, 12, 127)
		self.update_launchkey_mini_3_bank()

		# Bind driver functions
		self.end_trigger_device = self.end_launchkey_mini_3
		self.update_trigger_device_bank = self.update_launchkey_mini_3_bank
		self.update_trigger_device_pad = self.update_launchkey_mini_3_pad
		self.midi_event_trigger_device = self.midi_event_launchkey_mini_3


	def end_launchkey_mini_3(self):
		# Disable session mode on launchkey
		lib_zyncore.ctrlfb_send_note_on(15, 12, 0)


	def update_launchkey_mini_3_bank(self):
		# Update pad status
		for row in range(2):
			too_big = row >= self.zyngui.zynseq.col_in_bank
			for col in range(8):
				too_big |= col >= self.zyngui.zynseq.col_in_bank
				if too_big:
					note = 96 + row * 16 + col
					lib_zyncore.ctrlfb_send_note_on(0, note, 0)
				else:
					pad = self.zyngui.zynseq.col_in_bank * col + row
					state = self.zyngui.zynseq.libseq.getPlayState(self.bank, pad)
					mode = self.zyngui.zynseq.libseq.getPlayMode(self.bank, pad)
					self.update_launchkey_mini_3_pad(pad, state, mode)


	def update_launchkey_mini_3_pad(self, pad, state, mode):

		PAD_COLOURS = [71,104,76,51,104,41,64,12,11,71,4,67,42,9,105,15]
		STARTING_COLOUR = 123
		STOPPING_COLOUR = 120

		col = pad // self.zyngui.zynseq.col_in_bank
		row = pad % self.zyngui.zynseq.col_in_bank
		if row > 1:
			return
		note = 96 + row * 16 + col
		try:
			group = self.zyngui.zynseq.libseq.getGroup(self.bank, pad)
			if mode == 0 or group > 16:
				lib_zyncore.ctrlfb_send_note_on(0, note, 0)
			elif state == zynseq.SEQ_PLAYING:
				lib_zyncore.ctrlfb_send_note_on(2, note, PAD_COLOURS[group])
			elif state == zynseq.SEQ_STARTING:
				lib_zyncore.ctrlfb_send_note_on(1, note, STARTING_COLOUR)
			elif state == zynseq.SEQ_STOPPING:
				lib_zyncore.ctrlfb_send_note_on(1, note, STOPPING_COLOUR)
			elif state == zynseq.SEQ_STOPPED:
				lib_zyncore.ctrlfb_send_note_on(0, note, PAD_COLOURS[group])
		except Exception as e:
			pass
			#logging.warning(e)


	def midi_event_launchkey_mini_3(self, ev):
		evtype = (ev & 0xF00000) >> 20
		cmd = (ev & 0xff0000) >> 16
		val1 = (ev & 0xff00) >> 8
		val2 = (ev & 0xff)
		if evtype == 0x9:
			note = (ev >> 8) & 0x7F
			if ev == 0x90900c7f:
				# Entered session mode so set pad LEDs
				self.update_launchkey_mini_3_bank()
			else:
				# Toggle pad
				try:
					col = (note - 96) // 16
					row = (note - 96) % 16
					pad = row * self.zyngui.zynseq.col_in_bank + col
					self.zyngui.zynseq.libseq.togglePlayState(self.bank, pad)
				except:
					pass
		elif evtype == 0xB:
			cc_name = f"{val1:02x}"
			if val1 == 0x68:
				cc_name = "UP"
			elif val1 == 0x69:
				cc_name = "DOWN"
			elif val1 == 0x73:
				cc_name = "PLAY"
				if val2:
					self.zyngui.cuia_toggle_play()
			elif val1 == 0x75:
				cc_name = "RECORD"
				if val2:
					self.zyngui.cuia_toggle_record()
			elif val1 == 0x75:
				cc_name = "SHIFT"
			elif val1 == 0x67:
				cc_name = "TRACK LEFT"
			elif val1 == 0x67:
				cc_name = "TRACK RIGHT"
			if val1 >= 0x15 and val1 <= 0x1C:
				logging.debug(f"KNOB {val1 - 0x14}: {val2}")
			elif val2:
				logging.debug(f"{cc_name} PRESSED")
			else:
				logging.debug(f"{cc_name} RELEASED")
		elif evtype == 0xC:
			self.set_bank(val1 + 1)

		return True

	#------------------------------------------------------------------------------------------------------------------
	# /Launchkey Mini Integration
	# ------------------------------------------------------------------------------------------------------------------


	# Function to move selection cursor
	def update_selection_cursor(self):
		if self.selected_pad >= self.zyngui.zynseq.libseq.getSequencesInBank(self.bank):
			self.selected_pad = self.zyngui.zynseq.libseq.getSequencesInBank(self.bank) - 1
		col = int(self.selected_pad / self.zyngui.zynseq.col_in_bank)
		row = self.selected_pad % self.zyngui.zynseq.col_in_bank
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
		self.show_pattern_editor()


	# Function to add menus
	def show_menu(self):
		self.disable_param_editor()
		options = OrderedDict()

		# Global Options
		if not zynthian_gui_config.check_wiring_layout(["Z2", "V5"]):
			options['Tempo'] = 'Tempo'
			options[f'Scene ({self.bank})'] = 'Scene'
		if not zynthian_gui_config.check_wiring_layout(["Z2"]):
			options['Arranger'] = 'Arranger'
		options['Beats per bar ({})'.format(self.zyngui.zynseq.libseq.getBeatsPerBar())] = 'Beats per bar'

		if not self.trigger_device:
			options['Trigger device (OFF)'] = 'Trigger device'
		else:
			devname = zynautoconnect.get_midi_device_name(self.trigger_device).replace("_", " ")
			options['Trigger device ({})'.format(devname)] = 'Trigger device'

		if not self.trigger_device:
			if not self.trigger_channel:
				options['Trigger channel (OFF)'] = 'Trigger channel'
			else:
				options['Trigger channel ({})'.format(self.trigger_channel)] = 'Trigger channel'

		options['Grid size ({}x{})'.format(self.zyngui.zynseq.col_in_bank, self.zyngui.zynseq.col_in_bank)] = 'Grid size'

		# Single Pad Options
		options['> PAD OPTIONS'] = None
		options['Play mode ({})'.format(zynseq.PLAY_MODES[self.zyngui.zynseq.libseq.getPlayMode(self.bank, self.selected_pad)])] = 'Play mode'
		options['MIDI channel ({})'.format(1 + self.zyngui.zynseq.libseq.getChannel(self.bank, self.selected_pad, 0))] = 'MIDI channel'

		if not self.trigger_device and self.trigger_channel > 0:
			note = self.zyngui.zynseq.libseq.getTriggerNote(self.bank, self.selected_pad)
			if note < 128:
				trigger_note = "{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1)
			else:
				trigger_note = "None"
			options['Trigger note ({})'.format(trigger_note)] = 'Trigger note'

		options['Rename sequence'] = 'Rename sequence'

		self.zyngui.screens['option'].config("ZynPad Menu", options, self.menu_cb)
		self.zyngui.show_screen('option')


	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen == "option":
			self.close_screen()


	def menu_cb(self, option, params):
		if params == 'Tempo':
			self.zyngui.show_screen('tempo')
		elif params == 'Arranger':
			self.zyngui.show_screen('arranger')
		elif params == 'Beats per bar':
			self.enable_param_editor(self, 'bpb', 'Beats per bar', {'value_min':1, 'value_max':64, 'value_default':4, 'value':self.zyngui.zynseq.libseq.getBeatsPerBar()})
		elif params == 'Scene':
			self.enable_param_editor(self, 'bank', 'Scene', {'value_min':1, 'value_max':64, 'value':self.bank})
		elif params == 'Grid size':
			labels = []
			for i in range(1, 9):
				labels.append("{}x{}".format(i,i))
			self.enable_param_editor(self, 'grid_size', 'Grid size', {'labels': labels, 'value': self.zyngui.zynseq.col_in_bank - 1, 'value_default': 3}, self.set_grid_size)
		elif params == 'Trigger device':
			labels = ['OFF']
			for devname in zynautoconnect.devices_in:
				if devname:
					labels.append(devname.replace('_', ' '))
			self.enable_param_editor(self, 'trigger_device', 'Trigger device', {'labels': labels, 'value': self.trigger_device, 'value_default': 0}, self.set_trigger_device)
		elif params == 'Trigger channel':
			self.enable_param_editor(self, 'trigger_chan', 'Trigger channel', {'labels': INPUT_CHANNEL_LABELS, 'value': self.trigger_channel})
		elif params == 'Trigger note':
			self.zyngui.enter_midi_learn()
		elif params == 'Play mode':
			self.enable_param_editor(self, 'playmode', 'Play mode', {'labels':zynseq.PLAY_MODES, 'value':self.zyngui.zynseq.libseq.getPlayMode(self.bank, self.selected_pad), 'value_default':zynseq.SEQ_LOOPALL}, self.set_play_mode)
		elif params == 'MIDI channel':
			labels = []
			for chan in range(16):
				for layer in self.zyngui.screens['layer'].layers:
					if layer.midi_chan == chan:
						labels.append('{} ({})'.format(chan + 1, layer.preset_name))
						break
				if len(labels) <= chan:
					labels.append('{}'.format(chan + 1))
			self.enable_param_editor(self, 'midi_chan', 'MIDI channel', {'labels': labels, 'value_default': self.zyngui.zynseq.libseq.getChannel(self.bank, self.selected_pad, 0), 'value':self.zyngui.zynseq.libseq.getChannel(self.bank, self.selected_pad, 0)})
		elif params == 'Rename sequence':
			self.rename_sequence()


	def send_controller_value(self, zctrl):
		if zctrl.symbol == 'bank':
			self.zyngui.zynseq.select_bank(zctrl.value)
			self.set_title(f"Scene {self.zyngui.zynseq.bank}")
		elif zctrl.symbol == 'tempo':
			self.zyngui.zynseq.set_tempo(zctrl.value)
		elif zctrl.symbol == 'metro_vol':
			self.zyngui.zynseq.libseq.setMetronomeVolume(zctrl.value / 100.0)
		elif zctrl.symbol == 'bpb':
			self.zyngui.zynseq.libseq.setBeatsPerBar(zctrl.value)
		elif zctrl.symbol == 'playmode':
			self.set_play_mode(zctrl.value)
			self.refresh_trigger_device_pad(self.selected_pad, force=True)
		elif zctrl.symbol == 'midi_chan':
			self.zyngui.zynseq.set_midi_channel(self.bank, self.selected_pad, 0, zctrl.value)
			self.zyngui.zynseq.set_group(self.bank, self.selected_pad, zctrl.value)
		elif zctrl.symbol == 'trigger_device':
			#self.set_trigger_device(zctrl.value)
			pass
		elif zctrl.symbol == 'trigger_chan':
			self.zyngui.zynseq.libseq.setTriggerChannel(zctrl.value)
		elif zctrl.symbol == 'trigger_note':
			if zctrl.value == 0:
				value = 128
			else:
				value = zctrl.value - 1
			self.zyngui.zynseq.libseq.setTriggerNote(self.bank, self.selected_pad, value)


	#	Function to set the playmode of the selected pad
	def set_play_mode(self, mode):
		self.zyngui.zynseq.set_play_mode(self.bank, self.selected_pad, mode)


	# Function to show the editor (pattern or arranger based on sequence content)
	def show_pattern_editor(self):
		tracks_in_sequence = self.zyngui.zynseq.libseq.getTracksInSequence(self.bank, self.selected_pad)
		patterns_in_track = self.zyngui.zynseq.libseq.getPatternsInTrack(self.bank, self.selected_pad, 0)
		pattern = self.zyngui.zynseq.libseq.getPattern(self.bank, self.selected_pad, 0, 0)
		if tracks_in_sequence != 1 or patterns_in_track !=1 or pattern == -1:
			self.zyngui.screens["arranger"].sequence = self.selected_pad
			self.zyngui.toggle_screen("arranger")
			return True
		self.zyngui.screens['pattern_editor'].channel = self.zyngui.zynseq.libseq.getChannel(self.bank, self.selected_pad, 0)
		self.zyngui.screens['pattern_editor'].bank = self.bank
		self.zyngui.screens['pattern_editor'].sequence = self.selected_pad
		self.zyngui.screens['pattern_editor'].load_pattern(pattern)
		self.zyngui.show_screen("pattern_editor")
		return True


	# Function to refresh pads
	def refresh_status(self, status={}, force=False):
		super().refresh_status(status)

		if self.redrawing and not force:
			return

		force |= self.zyngui.zynseq.bank != self.bank
		if force:
			self.bank = self.zyngui.zynseq.bank
			self.set_title("Scene {}".format(self.bank))
			if self.columns != self.zyngui.zynseq.col_in_bank:
				self.update_grid()
			self.refresh_trigger_device_extra()

		for pad in range(self.zyngui.zynseq.col_in_bank ** 2):
			self.refresh_pad(pad, force)


	# Function to handle zynpots value change
	#   encoder: Zynpot index [0..n]
	#   dval: Zynpot value change
	def zynpot_cb(self, encoder, dval):
		if super().zynpot_cb(encoder, dval):
			return
		if encoder == self.ctrl_order[3]:
			pad = self.selected_pad + self.zyngui.zynseq.col_in_bank * dval
			col = int(pad / self.zyngui.zynseq.col_in_bank)
			row = pad % self.zyngui.zynseq.col_in_bank
			if col >= self.zyngui.zynseq.col_in_bank:
				col = 0
				row += 1
				pad = row + self.zyngui.zynseq.col_in_bank * col
			elif pad < 0:
				col = self.zyngui.zynseq.col_in_bank -1
				row -= 1
				pad = row + self.zyngui.zynseq.col_in_bank * col
			if row < 0 or row >= self.zyngui.zynseq.col_in_bank or col >= self.zyngui.zynseq.col_in_bank:
				return
			self.selected_pad = pad
			self.update_selection_cursor()
		elif encoder == self.ctrl_order[2]:
			pad = self.selected_pad + dval
			if pad < 0 or pad >= self.zyngui.zynseq.libseq.getSequencesInBank(self.bank):
				return
			self.selected_pad = pad
			self.update_selection_cursor()
		elif encoder == self.ctrl_order[1]:
			self.zyngui.zynseq.select_bank(self.zyngui.zynseq.bank + dval)
			self.set_title(f"Scene {self.zyngui.zynseq.bank}")
		elif encoder == self.ctrl_order[0] and zynthian_gui_config.transport_clock_source == 0:
			self.zyngui.zynseq.update_tempo()
			self.zyngui.zynseq.nudge_tempo(dval)
			self.set_title("Tempo: {:.1f}".format(self.zyngui.zynseq.get_tempo()), None, None, 2)


	# Function to handle SELECT button press
	#	type: Button press duration ["S"=Short, "B"=Bold, "L"=Long]
	def switch_select(self, type='S'):
		if super().switch_select(type):
			return True
		if type == 'S':
			self.toggle_pad()
		elif type == "B":
			self.show_pattern_editor()


	def back_action(self):
		if self.midi_learn:
			self.zyngui.exit_midi_learn()
			return True
		else:
			return super().back_action()


	#	CUIA Actions
	# Function to handle CUIA ARROW_RIGHT
	def arrow_right(self):
		self.zynpot_cb(self.ctrl_order[3], 1)


	# Function to handle CUIA ARROW_LEFT
	def arrow_left(self):
		self.zynpot_cb(self.ctrl_order[3], -1)


	# Function to handle CUIA ARROW_UP
	def arrow_up(self):
		if self.param_editor_zctrl:
			self.zynpot_cb(self.ctrl_order[3], 1)
		else:
			self.zynpot_cb(self.ctrl_order[2], -1)


	# Function to handle CUIA ARROW_DOWN
	def arrow_down(self):
		if self.param_editor_zctrl:
			self.zynpot_cb(self.ctrl_order[3], -1)
		else:
			self.zynpot_cb(self.ctrl_order[2], 1)

	#**************************************************************************
	# MIDI learning management
	#**************************************************************************

	def enter_midi_learn(self):
		if self.trigger_device_driver:
			return
		self.midi_learn = True
		labels = ['None']
		for note in range(128):
			labels.append("{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1))
		value = self.zyngui.zynseq.libseq.getTriggerNote(self.bank, self.selected_pad) + 1
		if value > 128:
			value = 0
		self.enable_param_editor(self, 'trigger_note', 'Trigger note', {'labels': labels, 'value': value})


	def exit_midi_learn(self):
		self.midi_learn = False
		self.disable_param_editor()


	def midi_event(self, ev):
		idev = ((ev & 0xFF000000) >> 24)
		chan = (ev & 0x0F0000) >> 16

		#if idev>0 and idev<=len(zynautoconnect.devices_in):
		#	logging.debug("MIDI EVENT FROM '{}'".format(zynautoconnect.devices_in[idev - 1]))

		if idev == self.trigger_device or chan == (self.trigger_channel - 1):
			# Trigger-device MIDI handler
			if self.trigger_device_driver:
				return self.midi_event_trigger_device(ev)

			# Zynpad's default midi learn mechanism
			evtype = (ev & 0xF00000) >> 20
			if evtype == 9:
				note = (ev >> 8) & 0x7F
				if self.midi_learn:
					self.zyngui.zynseq.libseq.setTriggerNote(self.bank, self.selected_pad, note)
					self.zyngui.exit_midi_learn()
					return True
				else:
					seq = self.zyngui.zynseq.libseq.getTriggerSequence(note)
					if seq:
						self.zyngui.zynseq.libseq.togglePlayState(seq >> 8, seq & 0xFF)
						return True


#------------------------------------------------------------------------------
