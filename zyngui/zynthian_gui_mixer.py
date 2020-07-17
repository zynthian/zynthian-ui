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
import liblo

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

	mute_colour = "yellow4"
	solo_colour = "DodgerBlue4"

	def __init__(self, canvas, x, y, width, height, channel, on_select_cb, on_edit_cb):
		self.main_canvas = canvas
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.hidden = False
		if channel and channel <= 16:
			self.channel = channel
		else:
			self.channel = None
			self.hidden = True
		self.on_select_cb = on_select_cb
		self.on_edit_cb = on_edit_cb

		self.legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1
		self.balance_height = self.edit_height * 0.2
		self.balance_top = self.edit_height - self.balance_height
		self.balance_control_centre = self.width / 2 
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.fader_height = self.height - self.edit_height - self.legend_height
		self.fader_bottom = self.height - self.legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		fader_centre = x + width * 0.5

		#Digital Peak Meter (DPM) parameters
		self.dpm_rangedB = 50 # Lowest meter reading in -dBFS
		self.dpm_highdB = 10 # Start of yellow zone in -dBFS
		self.dpm_overdB = 3  # Start of red zone in -dBFS
		self.dpm_high = 1 - self.dpm_highdB / self.dpm_rangedB
		self.dpm_over = 1 - self.dpm_overdB / self.dpm_rangedB
		self.dpm_scale_lm = int(self.dpm_high * self.fader_height)
		self.dpm_scale_lh = int(self.dpm_over * self.fader_height)

		self.dpm_width = int(self.width / 10)
		self.dpm_a_x = x + self.width - self.dpm_width * 2 - 2
		self.dpm_a_y = self.fader_bottom
		self.dpm_b_x = x + self.width - self.dpm_width - 1
		self.dpm_b_y = self.fader_bottom
		self.dpm_zero_y = self.fader_bottom - self.fader_height * self.dpm_high
		self.fader_width = self.width - self.dpm_width * 2 - 2

		self.drag_start = None

		# Default style
		self.fader_background = zynthian_gui_config.color_bg
		self.fader_colour = "gray30"
		self.legend_colour = "gray70"
		self.edit_button_background = zynthian_gui_config.color_bg
		self.left_colour = "dark red"
		self.right_colour = "dark green"
		self.low_colour = "dark green"
		self.medium_colour = "#AAAA00" # yellow
		self.high_colour = "dark red"
		font=(zynthian_gui_config.font_family, int(self.legend_height / 2))

		# Fader
		self.fader_bg = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_background, width=0)
		self.main_canvas.itemconfig(self.fader_bg, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.fader = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_colour, width=0, tags=("fader:%d"%(self.fader_bg), "mixer"))

		self.legend = self.main_canvas.create_text(x + 1, self.height - self.legend_height - 2, fill=self.legend_colour, text="", tags=("fader:%d"%(self.fader_bg),"mixer"), angle=90, anchor="nw", font=font)
		self.legend_strip = self.main_canvas.create_text(int(fader_centre), self.height - self.legend_height / 2, fill=self.legend_colour, text="-", tags=("fader:%d"%(self.fader_bg), "mixer"), font=font)


		# DPM
		self.dpm_h_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.high_colour, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.dpm_m_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.medium_colour, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.dpm_l_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.low_colour, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.dpm_h_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.high_colour, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.dpm_m_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.medium_colour, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.dpm_l_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.low_colour, tags=("fader:%d"%(self.fader_bg), "mixer"))
		self.dpm_hold_a = self.main_canvas.create_rectangle(self.dpm_a_x, self.fader_bottom, self.dpm_a_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_colour, tags=("fader:%d"%(self.fader_bg), "mixer"), state="hidden")
		self.dpm_hold_b = self.main_canvas.create_rectangle(self.dpm_b_x, self.fader_bottom, self.dpm_b_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_colour, tags=("fader:%d"%(self.fader_bg), "mixer"), state="hidden")

		# 0dB line
		self.main_canvas.create_line(self.dpm_a_x, self.dpm_zero_y, x + self.width, self.dpm_zero_y, fill="white", tags=("fader:%d"%(self.fader_bg), "mixer"))

		# Mute / Edit button
		self.edit_bg = self.main_canvas.create_rectangle(x, 0, x + self.width, self.edit_height, fill=self.edit_button_background, width=0)
		self.main_canvas.itemconfig(self.edit_bg, tags=("mute_button:%d"%(self.edit_bg),"edit_button:%d"%(self.edit_bg), "mixer"))

		self.solo = self.main_canvas.create_rectangle(x, 0, x + self.width, self.edit_height * 0.4 - 1, fill="gray30", width=0, tags=("solo_button:%d"%(self.edit_bg),"edit_button:%d"%(self.edit_bg), "mixer"))
		self.main_canvas.create_text(x + self.width / 2, self.edit_height * 0.2 - 1, text="Solo", fill="gray70", tags=("solo_button:%d"%(self.edit_bg),"edit_button:%d"%(self.edit_bg), "mixer"), font=font)

		self.mute = self.main_canvas.create_rectangle(x, self.edit_height * 0.4, x + self.width, self.edit_height * 0.8, fill="gray30", width=0, tags=("mute_button:%d"%(self.edit_bg),"edit_button:%d"%(self.edit_bg), "mixer"))
		self.main_canvas.create_text(x + self.width / 2, self.edit_height * 0.6, text="Mute", fill="gray70", tags=("mute_button:%d"%(self.edit_bg),"edit_button:%d"%(self.edit_bg), "mixer"), font=font)

		# Balance indicator
		self.balance_left = self.main_canvas.create_rectangle(x, self.fader_top, int(fader_centre - 0.5), self.fader_top + self.balance_height, fill=self.left_colour, width=0, tags=("mute_button:%d"%(self.edit_bg),"edit_button:%d"%(self.edit_bg), "mixer"))
		self.balance_right = self.main_canvas.create_rectangle(int(fader_centre + 0.5), self.fader_top, self.width, self.fader_top + self.balance_height , fill=self.right_colour, width=0, tags=("mute_button:%d"%(self.edit_bg),"edit_button:%d"%(self.edit_bg), "mixer"))

		self.main_canvas.tag_bind("fader:%d"%(self.fader_bg), "<ButtonPress-1>", self.on_fader_press)
		self.main_canvas.tag_bind("fader:%d"%(self.fader_bg), "<B1-Motion>", self.on_fader_motion)
		self.main_canvas.tag_bind("mute_button:%d"%(self.edit_bg), "<ButtonPress-1>", self.on_edit_press)
		self.main_canvas.tag_bind("mute_button:%d"%(self.edit_bg), "<ButtonRelease-1>", self.on_edit_release)
		self.main_canvas.tag_bind("solo_button:%d"%(self.edit_bg), "<ButtonRelease-1>", self.on_solo_release)

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
				self.main_canvas.itemconfig(self.legend_strip, text="Main")
				self.main_canvas.itemconfig(self.legend, text="Main")
			else:
				if zynmixer.is_channel_routed(self.channel):
					self.main_canvas.itemconfig(self.legend_strip, text=self.channel+1)
					layers_list=zynthian_gui_config.zyngui.screens["layer"].layers
					for layer in layers_list:
						if layer.midi_chan == self.channel:
							self.main_canvas.itemconfig(self.legend, text="%s\n%s"%(layer.engine.name, layer.preset_name), state="normal")
							break
				else:
					self.hide()
					return


		# DPM
		# Display audio peak
		signal = max(0, 1 + zynmixer.get_dpm(self.channel,0) / self.dpm_rangedB)
		llA = int(min(signal, self.dpm_high) * self.fader_height)
		lmA = int(min(signal, self.dpm_over) * self.fader_height)
		lhA = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm(self.channel,1) / self.dpm_rangedB)
		llB = int(min(signal, self.dpm_high) * self.fader_height)
		lmB = int(min(signal, self.dpm_over) * self.fader_height)
		lhB = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm_hold(self.channel,0) / self.dpm_rangedB)
		lholdA = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm_hold(self.channel,1) / self.dpm_rangedB)
		lholdB = int(min(signal, 1) * self.fader_height)

		# Channel A (left)
		self.main_canvas.coords(self.dpm_l_a,(self.dpm_a_x, self.dpm_a_y, self.dpm_a_x + self.dpm_width, self.dpm_a_y - llA))
		self.main_canvas.itemconfig(self.dpm_l_a, state='normal')

		if lmA >= self.dpm_scale_lm:
			self.main_canvas.coords(self.dpm_m_a,(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lm, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lmA))
			self.main_canvas.itemconfig(self.dpm_m_a, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_m_a, state="hidden")

		if lhA >= self.dpm_scale_lh:
			self.main_canvas.coords(self.dpm_h_a,(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lh, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lhA))
			self.main_canvas.itemconfig(self.dpm_h_a, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_h_a, state="hidden")

		self.main_canvas.coords(self.dpm_hold_a,(self.dpm_a_x, self.dpm_a_y - lholdA, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lholdA - 1))
		if lholdA >= self.dpm_scale_lh:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#FF0000")
		elif lholdA >= self.dpm_scale_lm:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#FFFF00")
		elif lholdA > 0:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#00FF00")
		else:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="hidden")

		# Channel B (right)
		self.main_canvas.coords(self.dpm_l_b,(self.dpm_b_x, self.dpm_b_y, self.dpm_b_x + self.dpm_width, self.dpm_b_y - llB))
		self.main_canvas.itemconfig(self.dpm_l_b, state='normal')

		if lmB >= self.dpm_scale_lm:
			self.main_canvas.coords(self.dpm_m_b,(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lm, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lmB))
			self.main_canvas.itemconfig(self.dpm_m_b, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_m_b, state="hidden")

		if lhB >= self.dpm_scale_lh:
			self.main_canvas.coords(self.dpm_h_b,(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lh, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lhB))
			self.main_canvas.itemconfig(self.dpm_h_b, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_h_b, state="hidden")

		self.main_canvas.coords(self.dpm_hold_b,(self.dpm_b_x, self.dpm_b_y - lholdB, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lholdB - 1))
		if lholdB >= self.dpm_scale_lh:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#FF0000")
		elif lholdB >= self.dpm_scale_lm:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#FFFF00")
		elif lholdB > 0:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#00FF00")
		else:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="hidden")

		self.main_canvas.coords(self.fader, self.x, self.fader_top + self.fader_height * (1 - zynmixer.get_level(self.channel)), self.x + self.fader_width, self.fader_bottom)

		colour = "gray30"
		if zynmixer.get_mute(self.channel):
			colour = self.mute_colour
		self.main_canvas.itemconfig(self.mute, fill=colour)
		colour = "gray30"
		if zynmixer.get_solo(self.channel):
			colour = self.solo_colour
		self.main_canvas.itemconfig(self.solo, fill=colour)

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


	# Function to handle solo button release
	#	event: Mouse event
	def on_solo_release(self, event):
		if self.channel != None:
			zynmixer.toggle_solo(self.channel)
			self.on_select_cb(self.channel)


#------------------------------------------------------------------------------
# Zynthian Mixer GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):
		super().__init__()

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height

		self.number_layers = 0 # Quantity of layers (routed channels)
		self.max_channels = 16 # Maximum quantiy of faders to display (Defines fader width. Main always displayed.) #TODO: Get from config and estimate initial value if not in config
		if self.width < 600: self.max_channels = 8
		if self.width < 400: self.max_channels = 4
		self.fader_width = (self.width - 6 ) / (self.max_channels + 1)
		self.legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1
		self.selection_border_width = int(self.height / 200)

		self.fader_height = self.height - self.edit_height - self.legend_height - 2
		self.fader_bottom = self.height - self.legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		self.balance_control_height = self.fader_height * 0.1
		self.balance_top = self.fader_top
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.balance_control_centre = self.fader_width + self.balance_control_width

		# Arrays of GUI elements for channel strips - Channels + Main
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

		self.main_channel = zynthian_gui_mixer_channel(self.main_canvas, self.width - self.fader_width - 1, 0, self.fader_width - 1, self.height, 16, self.select_midi_channel, self.set_edit_mode)
		self.main_channel.set_fader_colour("gray32")


		# Edit widgets
		font=(zynthian_gui_config.font_family, int(self.edit_height / 4))
		f=tkFont.Font(family=zynthian_gui_config.font_family, size=int(self.edit_height / 4))
		button_width = f.measure(" BALANCE ") # Width of widest text on edit buttons
		balance_control_bg = self.main_canvas.create_rectangle(self.balance_control_centre - self.balance_control_width, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height, fill=zynthian_gui_config.color_bg, width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_left = self.main_canvas.create_rectangle(int(self.balance_control_centre - self.balance_control_width), 0, self.balance_control_centre, self.balance_control_height, fill="dark red", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_right = self.main_canvas.create_rectangle(self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height, fill="dark green", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.main_canvas.tag_bind("balance_control", "<ButtonPress-1>", self.on_balance_press)
		self.main_canvas.tag_bind("balance_control", "<ButtonRelease-1>", self.on_balance_release)
		self.main_canvas.tag_bind("balance_control", "<B1-Motion>", self.on_balance_motion)

		edit_button_x = 1 + int(self.fader_width)
		edit_button_y = self.balance_control_height + 1
		# Solo button
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_channel.solo_colour, tags=("edit_control", "solo_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="SOLO", state="hidden", tags=("edit_control", "solo_button"), font=font, justify='center')
		# Mute button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_channel.mute_colour, tags=("edit_control", "mono_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="MONO", state="hidden", tags=("edit_control", "mono_button"), font=font, justify='center')
		# Mute button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_channel.mute_colour, tags=("edit_control", "mute_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="MUTE", state="hidden", tags=("edit_control", "mute_button"), font=font, justify='center')
		# Layer button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark orange", tags=("edit_control", "layer_button"))
		self.layer_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="LAYER", state="hidden", tags=("edit_control", "layer_button"), font=font, justify='center')
		# Reset gain button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark blue", tags=("edit_control", "reset_gain_button"))
		self.reset_gain_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="RESET\nGAIN", state="hidden", tags=("edit_control", "reset_gain_button"), font=font, justify='center')
		# Reset balance button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark blue", tags=("edit_control", "reset_balance_button"))
		self.reset_balance_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="RESET\nBALANCE", state="hidden", tags=("edit_control", "reset_balance_button"), font=font, justify='center')
		# Cancel button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_config.color_bg, tags=("edit_control", "cancel_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="CANCEL", state="hidden", tags=("edit_control", "cancel_button"), font=font, justify='center')

		self.main_canvas.tag_bind("mute_button", "<ButtonRelease-1>", self.on_mute_release)
		self.main_canvas.tag_bind("solo_button", "<ButtonRelease-1>", self.on_solo_release)
		self.main_canvas.tag_bind("mono_button", "<ButtonRelease-1>", self.on_mono_release)
		self.main_canvas.tag_bind("layer_button", "<ButtonRelease-1>", self.on_layer_release)
		self.main_canvas.tag_bind("reset_gain_button", "<ButtonRelease-1>", self.on_reset_level_release)
		self.main_canvas.tag_bind("reset_balance_button", "<ButtonRelease-1>", self.on_reset_balance_release)
		self.main_canvas.tag_bind("cancel_button", "<ButtonPress-1>", self.on_cancel_press)

		# Selection border
		self.selection_border = self.main_canvas.create_rectangle(0,0,0,0, width=self.selection_border_width, outline=zynthian_gui_config.color_on)

		zynmixer.enable_dpm(False) # Disable DPM by default - they get enabled when mixer is shown

		# Init touchbar
		self.init_buttonbar()


	# Function to display selected channel highlight border
	# channel: Index of channel to highlight
	def highlight_channel(self, channel):
		#TODO: Scroll channels
		if channel < self.number_layers:
			chan_strip = self.channels[channel - self.channel_offset]
		else:
			chan_strip = self.main_channel
		self.main_canvas.coords(self.selection_border, chan_strip.x, chan_strip.y + chan_strip.height * 0.95 + self.selection_border_width, chan_strip.x + chan_strip.width, chan_strip.y + chan_strip.height - self.selection_border_width)


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
		if self.mode == 0 or channel == None or channel < 0 or channel > self.number_layers:
			return
		self.selected_channel = channel

		if self.selected_channel < self.channel_offset:
			self.channel_offset = channel
			self.set_mixer_mode()
		elif self.selected_channel >= self.max_channels and self.selected_channel != self.number_layers:
			self.channel_offset = self.selected_channel - self.max_channels + 1
			self.set_mixer_mode()

		self.highlight_channel(self.selected_channel)
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_BACK, self.selected_channel, 0)

		self.selected_layer = None
		if channel == self.number_layers:
			return # Main channel selected
		layers_list=zynthian_gui_config.zyngui.screens["layer"].layers
		for layer in layers_list:
			if layer.midi_chan == self.get_midi_channel(self.selected_channel):
				self.selected_layer = layer
				break


	# Function to get MIDI channel (and hence mixer channel) from gui channel
	#	channel: Index of GUI channel
	#	returns: MIDI channel
	def get_midi_channel(self, channel):
		if channel == self.number_layers:
			return 16
		if channel > self.number_layers:
			return None
		return self.channels[channel - self.channel_offset].channel


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
		self.draw_balance_edit()


	# Function to refresh (redraw) balance edit control 
	def draw_balance_edit(self):
		balance = zynmixer.get_balance(self.get_midi_channel(self.selected_channel))
		if balance > 0:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - (1-balance) * self.balance_control_width, 0, self.balance_control_centre, self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height)
		else:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - self.balance_control_width, 0, self.balance_control_centre, self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width + self.balance_control_width * balance, self.balance_control_height)


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
		self.draw_balance_edit()


	# Function change to mixer mode
	def set_mixer_mode(self):
		self.main_canvas.itemconfig("edit_control", state="hidden")
		layers_list=zynthian_gui_config.zyngui.screens["layer"].layers
		for channel in range(self.max_channels):
			self.channels[channel].set_channel(None)
		self.number_layers = 0
		count = 0
		for channel in range(16):
			if zynmixer.is_channel_routed(channel):
				if self.number_layers >= self.channel_offset and count < self.max_channels:
					self.channels[count].set_channel(channel)
					count += 1
				self.number_layers += 1
		self.main_canvas.itemconfig(self.selection_border, state="normal")
		self.mode = 1
		self.edit_channel = None


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		zynmixer.toggle_mute(self.get_midi_channel(self.selected_channel))


	# Function to handle solo button release
	#	event: Mouse event
	def on_solo_release(self, event):
		zynmixer.toggle_solo(self.get_midi_channel(self.selected_channel))


	# Function to handle mono button release
	#	event: Mouse event
	def on_mono_release(self, event):
		zynmixer.toggle_mono(self.get_midi_channel(self.selected_channel))


	# Function to handle layer button release
	#	event: Mouse event
	def on_layer_release(self, event):
		self.zyngui.layer_control(self.selected_layer)


	# Function to handle reset gain button release
	#	event: Mouse event
	def on_reset_level_release(self, event):
		if self.selected_channel == self.number_layers:
			zynmixer.set_level(16, 0.8)
		else:
			zynmixer.set_level(self.selected_channel, 0.8)


	# Function to handle reset balance button release
	#	event: Mouse event
	def on_reset_balance_release(self, event):
		if self.selected_channel == self.number_layers:
			zynmixer.set_balance(16, 0)
		else:
			zynmixer.set_balance(self.selected_channel, 0)


	# Function to handle cancel edit button release
	#	event: Mouse event
	def on_cancel_press(self, event):
		self.set_mixer_mode()


	# Function to handle hiding display
	def hide(self):
		zynmixer.enable_dpm(False)
		super().hide()


	# Function to handle showing display
	def show(self):
		self.set_mixer_mode()
		zynmixer.enable_dpm(True)
		self.main_channel.set_channel(16)
		self.highlight_channel(self.selected_channel)
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
		# Main output
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


	# Function to handle switch press
	#	switch: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	type: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, switch, type):
		if type == "S" and switch == ENC_BACK:
			if self.mode == 0:
				self.set_mixer_mode()
				return True
		elif type == "S" and switch == ENC_SNAPSHOT:
			zynmixer.toggle_solo(self.get_midi_channel(self.selected_channel))
			return True
		return False


	# Function to refresh screen
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			self.main_channel.draw()
			if self.edit_channel == None:
				for fader in range(self.max_channels):
					self.channels[fader].draw()
			else:
				self.channels[0].draw()
				self.draw_balance_edit()


	# Function to handle OSC messages
	def osc(self, path, args, types, src):
#		print("zynthian_gui_mixer::osc", path, args, types)
		if path[:5] == "fader":
			try:
				zynmixer.set_level(int(path[5:]), args[0])
			except:
				pass
		elif path[:7] == "balance":
			try:
				zynmixer.set_balance(int(path[7:]), args[0])
			except:
				pass
		elif path[:4] == "mute":
			try:
				zynmixer.set_mute(int(path[4:]), int(args[0]))
			except:
				pass
		elif path[:4] == "solo":
			try:
				zynmixer.set_solo(int(path[4:]), int(args[0]))
			except:
				pass
