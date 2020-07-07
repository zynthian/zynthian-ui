#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Audio Mixer
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
import logging
import tkinter
from time import monotonic
from tkinter import font as tkFont
from PIL import Image, ImageTk

# Zynthian specific modules
from zyngine import zynthian_controller
from . import zynthian_gui_base
from . import zynthian_gui_config
from . import zynthian_gui_controller
from zynmixer import *
from zyncoder import *

ENC_LAYER			= 0
ENC_BACK			= 1
ENC_SNAPSHOT		= 2
ENC_SELECT			= 3

#------------------------------------------------------------------------------
# Zynthian Mixer Channel Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer_channel():
	# Initialise mixer channel object
	#	canvas: Canvas on which to draw fader
	#	x: Horizontal coordinate of left of fader
	#	y: Vertical coordinate of top of fader
	#	width: Width of fader
	#	height: Height of fader
	#	channel: Index of channel (used for labels)
	#	on_select_cb: Function to call when fader is selected (must accept channel as parameter)
	#	on_edit_cb: Function to call when channel edit is requested
	def __init__(self, canvas, x, y, width, height, channel, on_select_cb, on_edit_cb):
		self.main_canvas = canvas
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.hidden = False
		if channel and channel > 16:
			self.channel = channel
		else:
			self.channel = None
			self.hidden = True
		self.on_select_cb = on_select_cb
		self.on_edit_cb = on_edit_cb


		self.legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1
		self.balance_height = self.edit_height * 0.3
		self.balance_top = self.edit_height - self.balance_height
		self.balance_control_centre = self.width / 2 
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.fader_height = self.height - self.edit_height - self.legend_height - 2
		self.fader_bottom = self.height - self.legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		self.mute_top = 1
		fader_centre = x + width * 0.5

		self.drag_start = None

		# Default style
		self.fader_background = zynthian_gui_config.color_bg
		self.fader_colour = "gray28"
		self.legend_colour = "white"
		self.edit_button_background = zynthian_gui_config.color_bg
		self.mute_colour = "red"
		self.left_colour = "dark red"
		self.right_colour = "dark green"

		# Fader
		self.fader_bg = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_background, width=0)
		self.main_canvas.itemconfig(self.fader_bg, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.fader = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_colour, width=0, tags=("fader:%d"%(self.fader_bg), "mixer"))

		self.legend = self.main_canvas.create_text(int(fader_centre), self.height - self.legend_height - 2, fill=self.legend_colour, text="", tags=("fader:%d"%(self.fader_bg),"mixer"), angle=90, anchor="w")
		self.legend_strip = self.main_canvas.create_text(int(fader_centre), self.height - self.legend_height / 2, fill=self.legend_colour, text="-", tags=("fader:%d"%(self.fader_bg), "mixer"))

		self.main_canvas.tag_bind("fader:%d"%(self.fader_bg), "<ButtonPress-1>", self.on_fader_press)
		self.main_canvas.tag_bind("fader:%d"%(self.fader_bg), "<B1-Motion>", self.on_fader_motion)

		# Mute / Edit button
		self.edit_bg = self.main_canvas.create_rectangle(x, 0, x + self.width, self.edit_height, fill=self.edit_button_background, width=0)
		self.main_canvas.itemconfig(self.edit_bg, tags=("edit_button:%d"%(self.edit_bg), "mixer"))
		self.mute = self.main_canvas.create_text(x + 1, self.mute_top, text="M", state="hidden", fill=self.mute_colour, anchor="nw", tags=("edit_button:%d"%(self.edit_bg), "mixer"))
		self.balance_left = self.main_canvas.create_rectangle(x, self.fader_top, int(fader_centre - 0.5), self.fader_top + self.balance_height, fill=self.left_colour, width=0, tags=("edit_button:%d"%(self.edit_bg), "mixer"))
		self.balance_right = self.main_canvas.create_rectangle(int(fader_centre + 0.5), self.fader_top, self.width, self.fader_top + self.balance_height , fill=self.right_colour, width=0, tags=("edit_button:%d"%(self.edit_bg), "mixer"))

		self.main_canvas.tag_bind("edit_button:%d"%(self.edit_bg), "<ButtonPress-1>", self.on_edit_press)
		self.main_canvas.tag_bind("edit_button:%d"%(self.edit_bg), "<ButtonRelease-1>", self.on_edit_release)

		self.draw(True)


	# Function to hide channel
	def hide(self):
		self.main_canvas.itemconfig("fader:%d"%(self.fader_bg), state="hidden")
		self.main_canvas.itemconfig("edit_button:%d"%(self.edit_bg), state="hidden")
		self.hidden = True


	# Function to show channel
	def show(self):
		self.main_canvas.itemconfig("fader:%d"%(self.fader_bg), state="normal")
		self.main_canvas.itemconfig("edit_button:%d"%(self.edit_bg), state="normal")
		self.hidden = False
		self.draw(True)


	# Function to draw channel strip
	#	full: True to perform full draw, else just redraw transient elements
	def draw(self, full = False):
		if self.hidden or self.channel == None:
			return
		if full:
			self.main_canvas.itemconfig(self.legend, text="")
			self.main_canvas.coords(self.fader_background, self.x, self.fader_top, self.x + self.width, self.fader_bottom)
			if self.channel == 16:
				self.main_canvas.itemconfig(self.legend_strip, text="Master")
				self.main_canvas.itemconfig(self.legend, text="Master")
			else:
				if zynmixer.is_channel_routed(self.channel):
					self.main_canvas.itemconfig(self.legend_strip, text=self.channel+1)
					layers_list=zynthian_gui_config.zyngui.screens["layer"].layers
					for layer in layers_list:
						if layer.midi_chan == self.channel:
							self.main_canvas.itemconfig(self.legend, text="%s - %s"%(layer.engine.name, layer.preset_name), state="normal")
							break
				else:
					self.hide()
					return

		self.main_canvas.coords(self.fader, self.x, self.fader_top + self.fader_height * (1 - zynmixer.get_level(self.channel)), self.x + self.width, self.fader_bottom)
		mute_state = "hidden"
		if zynmixer.get_mute(self.channel):
			mute_state = "normal"
		self.main_canvas.itemconfig(self.mute, state=mute_state)

		balance = zynmixer.get_balance(self.channel)
		if balance > 0:
			self.main_canvas.coords(self.balance_left,
				self.x + balance * self.width / 2, self.balance_top, 
				self.x + self.width / 2, self.balance_top + self.balance_height)
			self.main_canvas.coords(self.balance_right, 
				self.x + self.width / 2, self.balance_top, 
				self.x + self.width, self.balance_top + self.balance_height)
		else:
			self.main_canvas.coords(self.balance_left, 
				self.x, self.balance_top,
				self.x + self.width / 2, self.balance_top + self. balance_height)
			self.main_canvas.coords(self.balance_right, 
				self.x + self.width / 2, self.balance_top,
				self.x + self.width * balance / 2 + self.width, self.balance_top + self.balance_height)

	# Function to set fader colours
	# fg: Fader foreground colour
	# bg: Fader background colour (optional - Default: Do not change background colour)
	def set_fader_colour(self, fg, bg=None):
		self.main_canvas.itemconfig(self.fader, fill=fg)
		if bg:
			self.main_canvas.itemconfig(self.fader_background, fill=bg)

	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.drag_start = event
		self.on_select_cb(self.channel)


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.channel == None:
			return
		level = zynmixer.get_level(self.channel) + (self.drag_start.y - event.y) / self.fader_height
		if level > 1: level = 1
		if level < 0: level = 0
		self.drag_start = event
		self.set_fader(level)


	# Function to set channel
	#	channel: Index of channel
	def set_channel(self, channel):
		self.channel = channel
		if channel == None:
			self.hide()
		else:
			if channel > 16: channel = 16
			self.show()


	# Function to set fader values
	#	value: Fader value (0..1)
	def set_fader(self, value):
		if self.channel == None:
			return
		zynmixer.set_level(self.channel, value)
		self.draw()


	# Function to handle edit button press
	#	event: Mouse event
	def on_edit_press(self, event):
		self.press_time = monotonic()
		self.on_select_cb(self.channel)


	# Function to handle edit button release
	#	event: Mouse event
	def on_edit_release(self, event):
		if self.press_time:
			delta = monotonic() - self.press_time
			self.press_time = None
			if delta > 0.4:
				self.on_edit_cb()
				return
		if self.channel != None:
			zynmixer.toggle_mute(self.channel)


#------------------------------------------------------------------------------
# Zynthian Mixer GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):
		super().__init__()

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height


		self.number_layers = 0 # Quantity of layers
		self.max_channels = 16 # Maximum quantiy of faders to display (Defines fader width. Master always displayed.) #TODO: Get from config and estimate initial value if not in config
		if self.width < 600: self.max_channels = 8
		if self.width < 400: self.max_channels = 4
		self.fader_width = (self.width - 6 ) / (self.max_channels + 1)
		self.legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1
		self.selection_border_width = 2

		self.fader_height = self.height - self.edit_height - self.legend_height - 2
		self.fader_bottom = self.height - self.legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		self.balance_control_height = self.fader_height * 0.2
		self.balance_top = self.fader_top
		self.balance_control_centre = self.width / 2 
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.mute_top = 1

		# Arrays of GUI elements for channel strips - Channels + Master
		self.channels = [None] * self.max_channels
		self.selected_channel = 0
		self.channel_offset = 0 # Index of first channel displayed on far left
		self.selected_layer = None

		self.press_time = None

		self.edit_channel = None
		self.mode = 1 # 1:Mixer, 0:Edit

		# Topbar title
		self.title_canvas = tkinter.Canvas(self.tb_frame,
			width=zynthian_gui_config.display_width-self.status_l-self.status_lpad-2,
#			width=self.path_canvas_width,
			height=zynthian_gui_config.topbar_height,
			bd=0,
			highlightthickness=0,
			relief="flat",
			bg = zynthian_gui_config.color_bg)
		self.title_canvas.grid(row=0, column=0, sticky="ewns")
		self.title_canvas.create_text(1, zynthian_gui_config.topbar_height / 2,
			font=zynthian_gui_config.font_topbar,
			text="Audio Mixer",
			fill=zynthian_gui_config.color_header_tx,
			anchor="w")

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=self.height,
			width=self.width,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_panel_bg)
		self.main_canvas.grid()

		# Channel strips
		for channel in range(self.max_channels):
			self.channels[channel] = zynthian_gui_mixer_channel(self.main_canvas, 1 + self.fader_width * channel, 0, self.fader_width - 1, self.height, channel, self.select_midi_channel, self.set_edit_mode)

		self.master_channel = zynthian_gui_mixer_channel(self.main_canvas, self.width - self.fader_width - 1, 0, self.fader_width - 1, self.height, 16, self.select_midi_channel, self.set_edit_mode)
		self.master_channel.set_fader_colour("dark blue")

		# 0dB line
		self.main_canvas.create_line(0, self.fader_top + self.fader_height * 0.2, self.width, self.fader_top + self.fader_height * 0.2, fill="white", tags=("mixer"))

		# Edit widgets
		balance_control_bg = self.main_canvas.create_rectangle(self.balance_control_centre - self.balance_control_width, self.fader_top, self.balance_control_centre + self.balance_control_width, self.fader_top + self.balance_control_height, fill=zynthian_gui_config.color_bg, width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_left = self.main_canvas.create_rectangle(int(self.balance_control_centre - self.balance_control_width), self.fader_top, self.balance_control_centre, self.fader_top + self.balance_control_height, fill="dark red", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_right = self.main_canvas.create_rectangle(self.balance_control_centre, self.fader_top, self.balance_control_centre + self.balance_control_width, self.fader_top + self.balance_control_height, fill="dark green", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.main_canvas.tag_bind("balance_control", "<ButtonPress-1>", self.on_balance_press)
		self.main_canvas.tag_bind("balance_control", "<ButtonRelease-1>", self.on_balance_release)
		self.main_canvas.tag_bind("balance_control", "<B1-Motion>", self.on_balance_motion)
		self.main_canvas.create_line(0, self.fader_top + self.fader_height * 0.2, self.fader_width, self.fader_top + self.fader_height * 0.2, fill="white", tags=("edit_control"), state="hidden")

		self.main_canvas.create_rectangle(1 + int(self.fader_width), 0, self.fader_width * 2 - 1, self.edit_height, state="hidden", fill="dark red", tags=("edit_control", "mute_button"))
		self.main_canvas.create_text(1 + int(self.fader_width * 1.5), int(self.edit_height / 2), fill="white", text="MUTE", state="hidden", tags=("edit_control", "mute_button"))
		self.main_canvas.create_rectangle(1 + int(self.fader_width * 2), 0, self.fader_width * 3 - 1, self.edit_height, state="hidden", fill="orange", tags=("edit_control", "layer_button"))
		self.layer_button_text = self.main_canvas.create_text(1 + int(self.fader_width * 2.5), int(self.edit_height / 2), fill="white", text="LAYER", state="hidden", tags=("edit_control", "layer_button"))
		self.main_canvas.create_rectangle(1 + int(self.fader_width * 3), 0, self.fader_width * 4 - 1, self.edit_height, state="hidden", fill=zynthian_gui_config.color_bg, tags=("edit_control", "cancel_button"))
		self.main_canvas.create_text(1 + int(self.fader_width * 3.5), int(self.edit_height / 2), fill="white", text="CANCEL", state="hidden", tags=("edit_control", "cancel_button"))
		self.main_canvas.tag_bind("mute_button", "<ButtonRelease-1>", self.on_mute_release)
		self.main_canvas.tag_bind("layer_button", "<ButtonRelease-1>", self.on_layer_release)
		self.main_canvas.tag_bind("cancel_button", "<ButtonPress-1>", self.on_cancel_press)

		# Selection border
		self.selection_border = self.main_canvas.create_rectangle(1, 1, self.fader_width, self.height - self.selection_border_width, width=self.selection_border_width, outline=zynthian_gui_config.color_on)

		# Init touchbar
		self.init_buttonbar()


	# Function to display selected channel highlight border
	# channel: Index of channel to highlight
	def highlight_channel(self, channel):
		#TODO: Scroll channels
		if channel < self.number_layers and channel < self.max_channels:
			chan_strip = self.channels[channel]
		else:
			chan_strip = self.master_channel
		self.main_canvas.coords(self.selection_border, chan_strip.x, chan_strip.y + self.selection_border_width, chan_strip.x + chan_strip.width, chan_strip.y + chan_strip.height - self.selection_border_width)


	# Function to select channel by MIDI channel
	# channel: MIDI channel
	def select_midi_channel(self, channel):
		if channel == 16:
			self.select_channel(self.number_layers)
			return
		for index, fader in enumerate(self.channels):
			if fader.channel == channel:
				self.select_channel(index)
				return


	# Function to select channel by index
	#	channel: Index of channel to select
	def select_channel(self, channel):
		if self.mode == 0 or channel == None or channel > self.number_layers or channel < 0:# or channel == self.selected_channel:
			return
		self.selected_channel = channel
		self.highlight_channel(self.selected_channel)
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_BACK, self.selected_channel, 0)

		self.selected_layer = None
		if channel == self.number_layers:
			return # Master channel selected
		layers_list=zynthian_gui_config.zyngui.screens["layer"].layers
		for layer in layers_list:
			if layer.midi_chan == self.get_midi_channel(self.selected_channel):
				self.selected_layer = layer
				break


	# Function to get MIDI channel (and hence mixer channel) from gui channel
	#	channel: Index of GUI channel
	#	returns: MIDI channel
	def get_midi_channel(self, channel):
		if channel > self.max_channels:
			return None
		if channel == self.number_layers:
			return 16
		return self.channels[channel].channel


	# Function to handle balance press
	#	event: Mouse event
	def on_balance_press(self, event):
		self.balance_drag_start = event


	# Function to handle balance release
	#	event: Mouse event
	def on_balance_release(self, event):
		pass


	# Function to balance fader drag
	#	event: Mouse event
	def on_balance_motion(self, event):
		balance = zynmixer.get_balance(self.get_midi_channel(self.selected_channel)) + (event.x - self.balance_drag_start.x) / self.balance_control_width
		if balance > 1: balance = 1
		if balance < -1: balance = -1
		self.balance_drag_start = event
		zynmixer.set_balance(self.get_midi_channel(self.selected_channel), balance)

		if balance > 0:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - (1-balance) * self.balance_control_width, self.fader_top, self.balance_control_centre, self.fader_top + self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, self.fader_top, self.balance_control_centre + self.balance_control_width, self.fader_top + self.balance_control_height)
		if balance < 0:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - self.balance_control_width, self.fader_top, self.balance_control_centre, self.fader_top + self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, self.fader_top, self.balance_control_centre + self.balance_control_width + self.balance_control_width * balance, self.fader_top + self.balance_control_height)


	# Function change to edit mode
	def set_edit_mode(self):
		self.mode = 0
		self.edit_channel = self.selected_channel
		for channel in self.channels:
			channel.hide()
		self.main_canvas.itemconfig(self.selection_border, state="hidden")
		self.channels[0].set_channel(self.get_midi_channel(self.selected_channel))
		self.channels[0].show()
		self.main_canvas.itemconfig("edit_control", state="normal")
		self.channels[0].draw(True)
		balance = zynmixer.get_balance(self.get_midi_channel(self.selected_channel))
		if balance > 0:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - (1-balance) * self.balance_control_width, self.fader_top, self.balance_control_centre, self.fader_top + self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, self.fader_top, self.balance_control_centre + self.balance_control_width, self.fader_top + self.balance_control_height)
		else:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - self.balance_control_width, self.fader_top, self.balance_control_centre, self.fader_top + self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, self.fader_top, self.balance_control_centre + self.balance_control_width + self.balance_control_width * balance, self.fader_top + self.balance_control_height)


	# Function change to mixer mode
	def set_mixer_mode(self):
		self.main_canvas.itemconfig("edit_control", state="hidden")
		layers_list=zynthian_gui_config.zyngui.screens["layer"].layers
		for channel in range(self.max_channels):
			self.channels[channel].set_channel(None)
		self.number_layers = 0
		for channel in range(16):
			if zynmixer.is_channel_routed(channel) and self.number_layers < self.max_channels:
				self.channels[self.number_layers].set_channel(channel)
				self.number_layers += 1
#		for layer in layers_list:
#			if layer.midi_chan != None and self.number_layers < self.max_channels:
#				self.channels[self.number_layers].set_channel(layer.midi_chan)
#				self.number_layers += 1
		self.main_canvas.itemconfig(self.selection_border, state="normal")
		self.mode = 1
		self.edit_channel = None


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		zynmixer.toggle_mute(self.get_midi_channel(self.selected_channel))


	# Function to handle layer button release
	#	event: Mouse event
	def on_layer_release(self, event):
#		self.zyngui.show_screen("layer") #TODO: Show relevant layer control screen
		self.zyngui.layer_control(self.selected_layer)


	# Function to handle cancel edit button release
	#	event: Mouse event
	def on_cancel_press(self, event):
		self.set_mixer_mode()


	def show(self):
		self.set_mixer_mode()
		self.master_channel.set_channel(16)
		super().show()
		zyncoder.lib_zyncoder.setup_zyncoder(ENC_BACK, zynthian_gui_config.zyncoder_pin_a[ENC_BACK], zynthian_gui_config.zyncoder_pin_b[ENC_BACK], 0, 0, None, self.selected_channel, self.number_layers, 0)
		zyncoder.lib_zyncoder.setup_zyncoder(ENC_SELECT, zynthian_gui_config.zyncoder_pin_a[ENC_SELECT], zynthian_gui_config.zyncoder_pin_b[ENC_SELECT], 0, 0, None, 64, 127, 0)
		zyncoder.lib_zyncoder.setup_zyncoder(ENC_SNAPSHOT, zynthian_gui_config.zyncoder_pin_a[ENC_SNAPSHOT], zynthian_gui_config.zyncoder_pin_b[ENC_SNAPSHOT], 0, 0, None, 64, 127, 0)
		zyncoder.lib_zyncoder.setup_zyncoder(ENC_LAYER, zynthian_gui_config.zyncoder_pin_a[ENC_LAYER], zynthian_gui_config.zyncoder_pin_b[ENC_LAYER], 0, 0, None, 64, 127, 0)


	# Function to refresh loading animation
	def refresh_loading(self):
		pass


	# Function to handle CUIA SELECT_UP command
	def select_up(self):
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SELECT, 65, 0)


	# Function to handle CUIA SELECT_DOWN command
	def select_down(self):
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SELECT, 63, 0)


	# Function to handle CUIA BACK_UP command
	def back_up(self):
		if self.selected_channel < self.number_layers + 1:
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_BACK, self.selected_channel + 1, 0)


	# Function to handle CUIA BACK_DOWN command
	def back_down(self):
		if self.selected_channel:
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_BACK, self.selected_channel - 1, 0)


	# Function to handle CUIA LAYER_UP command
	def layer_up(self):
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_LAYER, 65, 0)


	# Function to handle CUIA LAYER_DOWN command
	def layer_down(self):
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_LAYER, 63, 0)


	# Function to handle CUIA SNAPSHOT_UP command
	def snapshot_up(self):
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SNAPSHOT, 65, 0)


	# Function to handle CUIA SNAPSHOT_DOWN command
	def snapshot_down(self):
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SNAPSHOT, 63, 0)


	# Function to handle zyncoder polling
	#	Note: Zyncoder provides positive integers. We need +/- 1 so we keep zyncoder at +1 and calculate offset
	def zyncoder_read(self):
		if not self.shown:
			return
		value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_BACK)
		if(self.mode and value != self.selected_channel):
			self.select_channel(value)
		value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_SELECT)
		if(value != 64):
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SELECT, 64, 0)
			midi_ch = self.get_midi_channel(self.selected_channel)
			level = zynmixer.get_level(midi_ch) + (value - 64) * 0.01
			if level > 1: level = 1
			if level < 0: level = 0
			zynmixer.set_level(midi_ch, level)
		value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_SNAPSHOT)
		if(value != 64):
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SNAPSHOT, 64, 0)
			balance = zynmixer.get_balance(self.get_midi_channel(self.selected_channel)) + (value - 64) * 0.01
			if balance > 1: balance = 1
			if balance < -1: balance = -1
			zynmixer.set_balance(self.get_midi_channel(self.selected_channel), balance)
		value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_LAYER)
		if(value != 64):
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_LAYER, 64, 0)
			level = zynmixer.get_level(self.number_layers) + (value - 64) * 0.01
			if level > 1: level = 1
			if level < 0: level = 0
			zynmixer.set_level(self.number_layers, level)
		value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_LAYER)


	# Function to handle SELECT switch
	# mode: Switch mode ("S"|"B"|"L")
	def switch_select(self, mode):
		if mode == "S":
			zynmixer.toggle_mute(self.get_midi_channel(self.selected_channel))
		elif mode == "B":
			self.set_edit_mode()


	# Function to refresh screen
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			self.master_channel.draw()
			if self.edit_channel == None:
				for fader in range(self.max_channels):
					self.channels[fader].draw()
			else:
				self.channels[0].draw()

