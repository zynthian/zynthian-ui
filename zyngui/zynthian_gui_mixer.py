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

#------------------------------------------------------------------------------
# Zynthian Listbox Selector GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):
		super().__init__()

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height
		
		# Channel height = self.height.
		# Edit button, 1, fader, 0, legend
		self.fader_width = (self.width - 6 ) / 17
		legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1
		self.balance_height = self.edit_height * 0.2
		self.balance_top = self.edit_height * 0.9
		self.fader_height = self.height - self.edit_height - legend_height - 1
		self.fader_bottom = self.height - legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		mute_top = 1

		# Arrays of GUI elements for channel strips - 16 channels + Master
		self.faders = [None] * 17
		self.balances_left = [None] * 17
		self.balances_right = [None] * 17
		self.selected_channel = None
		self.mutes = [None] * 17
		self.edit_buttons = [None] * 17

		self.press_time = None

		self.edit_channel = None

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=self.height,
			width=self.width,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_panel_bg)
		self.main_canvas.grid()


		# Draw faders
		offset = 1
		fill = 'gray'
		for fader in range(17):
			label = "Layer %d" % (fader + 1)
			if fader > 15:
				offset = 4
				fill = 'red4'
				label = 'Master'
			left_edge = offset + self.fader_width * fader
			fader_centre = left_edge + self.fader_width * 0.5
			fader_bg = self.main_canvas.create_rectangle(left_edge, self.fader_top, left_edge + self.fader_width - 1, self.fader_bottom, fill=zynthian_gui_config.color_bg, width=0, tags=('Channel:%d'%fader, 'fader_control', 'mixer', 'background'))
			self.faders[fader] = self.main_canvas.create_rectangle(left_edge, self.fader_top, left_edge + self.fader_width - 1, self.fader_bottom, fill=fill, width=0, tags=('Channel:%d'%fader, 'fader_control', 'mixer'))

			self.main_canvas.create_text(int(fader_centre), self.height - legend_height / 2,  fill='white', text=label)


			# Edit button
			self.edit_buttons[fader] = self.main_canvas.create_rectangle(left_edge, 0, left_edge + self.fader_width - 1, self.edit_height, fill=zynthian_gui_config.color_bg, width=0, tags=('Channel:%d'%fader, 'edit_button', 'background'))
			self.mutes[fader] = self.main_canvas.create_text(left_edge + 1, mute_top, text='M', state=tkinter.HIDDEN, fill='red', anchor='nw', tags=('Channel:%d'%fader, 'edit_button', 'mixer'))
			self.balances_left[fader] = self.main_canvas.create_rectangle(left_edge, self.balance_top, int(fader_centre - 0.5), self.balance_top + self.balance_height, fill='dark green', width=0, tags=('Channel:%d'%fader, 'edit_button', 'mixer'))
			self.balances_right[fader] = self.main_canvas.create_rectangle(int(fader_centre + 0.5), self.balance_top, left_edge + self.fader_width - 1, self.balance_top + self.balance_height, fill='dark red', width=0, tags=('Channel:%d'%fader, 'edit_button', 'mixer'))

			self.draw_channel(fader)

		self.main_canvas.tag_bind('edit_button', '<ButtonRelease-1>', self.on_edit_release)
		self.main_canvas.tag_bind('fader_control', "<ButtonPress-1>", self.on_fader_press)
		self.main_canvas.tag_bind('fader_control', "<ButtonRelease-1>", self.on_fader_release)
		self.main_canvas.tag_bind('fader_control', "<B1-Motion>", self.on_fader_motion)

		# 0dB line
		self.main_canvas.create_line(0, self.fader_top + self.fader_height * 0.2, self.width, self.fader_top + self.fader_height * 0.2, fill="white", tags=('mixer'))

		# Edit widgets
		balance_control_bg = self.main_canvas.create_rectangle(self.fader_width + 1, self.fader_top, self.width - self.fader_width - 4, self.fader_top + self.fader_width, fill=zynthian_gui_config.color_bg, width=0, state='hidden', tags='edit_control')
		self.balance_control = self.main_canvas.create_rectangle(self.fader_width + 1, self.fader_top, self.width - self.fader_width - 4, self.fader_top + self.fader_width, fill='dark blue', width=0, state='hidden', tags='edit_control')
		self.main_canvas.tag_bind(balance_control_bg, "<ButtonPress-1>", self.on_balance_press)
		self.main_canvas.tag_bind(self.balance_control, "<ButtonPress-1>", self.on_balance_press)
		self.main_canvas.tag_bind(balance_control_bg, "<ButtonRelease-1>", self.on_balance_release)
		self.main_canvas.tag_bind(self.balance_control, "<ButtonRelease-1>", self.on_balance_release)
		self.main_canvas.tag_bind(balance_control_bg, "<B1-Motion>", self.on_balance_motion)
		self.main_canvas.tag_bind(self.balance_control, "<B1-Motion>", self.on_balance_motion)
		self.main_canvas.create_line(0, self.fader_top + self.fader_height * 0.2, self.fader_width, self.fader_top + self.fader_height * 0.2, fill="white", tags=('edit_control'), state='hidden')

	# Function to set fader values
	#	fader: Index of fader
	#	value: Fader value (0..1)
	def set_fader(self, fader, value):
		if fader > len(self.faders) or value < 0 or value > 1:
			return
		zynmixer.set_level(fader, value)
		self.draw_channel(fader)


	# Function to draw channel strip
	#	channel: index of channel
	def draw_channel(self, channel):
		if self.edit_channel == None:
			if channel > 15:
				offset = 4 + channel * self.fader_width
			else:
				offset = 1 + channel * self.fader_width
		else:
			offset = 1
		self.main_canvas.coords(self.faders[channel], offset, self.fader_top + self.fader_height * (1 - zynmixer.get_level(channel)), offset + self.fader_width - 1, self.fader_bottom)
		mute_state = tkinter.HIDDEN
		if zynmixer.get_mute(channel):
			mute_state = tkinter.NORMAL
		self.main_canvas.itemconfig(self.mutes[channel], state=mute_state)

		balance = zynmixer.get_balance(channel)
		centre = (balance + 1) * self.fader_width / 2
		self.main_canvas.coords(self.balances_left[channel], offset, self.balance_top, int(offset + centre - 0.5), self.balance_top + self.balance_height)
		self.main_canvas.coords(self.balances_right[channel], int(offset + centre + 0.5), self.balance_top, offset + self.fader_width - 1, self.balance_top + self.balance_height)


	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.drag_start = event
		self.press_time = monotonic()
		try:
			sel = int(self.main_canvas.find_withtag(tkinter.CURRENT)[0])
			fader = int(self.main_canvas.gettags(sel)[0].split(':')[1])
		except:
			return
		self.selected_channel = fader


	# Function to handle fader release
	#	event: Mouse event
	def on_fader_release(self, event):
		self.press_time = None


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.selected_channel == None:
			return
		if (abs(event.x - self.drag_start.x) + abs(event.y - self.drag_start.y)) > 5:
			self.press_time = None
		level = zynmixer.get_level(self.selected_channel) + (self.drag_start.y - event.y) / self.fader_height
		if level > 1: level = 1
		if level < 0: level = 0
		self.drag_start = event
		self.set_fader(self.selected_channel, level)

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
		if self.selected_channel == None:
			return
		balance = zynmixer.get_balance(self.selected_channel) + (event.x - self.balance_drag_start.x) / self.fader_height
		if balance > 1: balance = 1
		if balance < -1: balance = -1
		self.balance_drag_start = event
		zynmixer.set_balance(self.selected_channel, balance)


	# Function to handle edit button release
	#	event: Mouse event
	def on_edit_release(self, event):
		try:
			sel = int(self.main_canvas.find_withtag(tkinter.CURRENT)[0])
			channel = int(self.main_canvas.gettags(sel)[0].split(':')[1])
		except:
			return
		if self.edit_channel == None:
			# Change to edit mode
			self.edit_channel = channel
			self.main_canvas.itemconfig('mixer', state='hidden')
			self.main_canvas.coords('Channel:%d'%(channel), 1, self.fader_top, self.fader_width, self.fader_bottom)
			self.draw_channel(channel)
			self.main_canvas.itemconfig('Channel:%d'%(channel), state='normal')
			self.main_canvas.itemconfig('edit_control', state='normal')
		else:
			# Change to mixer mode
			self.edit_channel = None
			self.main_canvas.itemconfig('edit_control', state='hidden')
			self.main_canvas.coords('Channel:%d'%(self.selected_channel), 1 + self.fader_width * self.selected_channel, self.fader_top, 1 + self.fader_width * self.selected_channel + self.fader_width - 1, self.fader_bottom)
			self.draw_channel(channel)
			self.main_canvas.itemconfig('mixer', state='normal')
			self.main_canvas.tag_lower('background')
		self.selected_channel = channel

	# Function to refresh loading animation
	def refresh_loading(self):
		pass


	# Function to handle zyncoder polling
	def zyncoder_read(self):
		pass

	# Function to refresh screen
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			if self.edit_channel == None:
				for fader in range(17):
					self.draw_channel(fader)
			else:
				self.draw_channel(self.selected_channel)
			if self.press_time and (monotonic() - self.press_time) > 0.4:
				self.press_time = None
				zynmixer.toggle_mute(self.selected_channel)

