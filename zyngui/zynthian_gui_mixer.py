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
# Zynthian Listbox Selector GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):
		super().__init__()

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.display_height - zynthian_gui_config.topbar_height

		self.fader_width = (self.width - 6 ) / 17
		legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1
		self.balance_height = self.edit_height * 0.3
		self.balance_top = self.edit_height - self.balance_height
		self.balance_control_centre = self.width / 2 
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.fader_height = self.height - self.edit_height - legend_height - 2
		self.fader_bottom = self.height - legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		self.mute_top = 1

		# Arrays of GUI elements for channel strips - 16 channels + Master
		self.faders = [None] * 17
		self.legends = [None] * 17
		self.balances_left = [None] * 17
		self.balances_right = [None] * 17
		self.selected_channel = 0
		self.mutes = [None] * 17
		self.edit_buttons = [None] * 17

		self.press_time = None

		self.edit_channel = None
		self.mode = 1 # 1:Mixer, 0:Edit

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=self.height,
			width=self.width,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_panel_bg)
		self.main_canvas.grid()


		# Draw channel strips
		offset = 1
		fill = 'gray'
		for channel in range(17):
			label = "Layer %d" % (channel + 1)
			if channel > 15:
				offset = 4
				fill = 'purple4'
				label = 'Master'
			left_edge = offset + self.fader_width * channel
			fader_centre = left_edge + self.fader_width * 0.5
			fader_bg = self.main_canvas.create_rectangle(left_edge, self.fader_top, left_edge + self.fader_width - 1, self.fader_bottom, fill=zynthian_gui_config.color_bg, width=0, tags=('Channel:%d'%channel, 'fader_control', 'mixer', 'background'))
			self.faders[channel] = self.main_canvas.create_rectangle(left_edge, self.fader_top, left_edge + self.fader_width - 1, self.fader_bottom, fill=fill, width=0, tags=('Channel:%d'%channel, 'fader_control', 'mixer'))

			self.legends[channel] = self.main_canvas.create_text(int(fader_centre), self.height - legend_height / 2,  fill='white', text=label, tags=('Channel:%d'%(channel),'fader_control','mixer'))


			# Edit button
			self.edit_buttons[channel] = self.main_canvas.create_rectangle(left_edge, 1, left_edge + self.fader_width - 1, self.edit_height, fill=zynthian_gui_config.color_bg, width=0, tags=('Channel:%d'%channel, 'edit_button', 'background'))
			self.mutes[channel] = self.main_canvas.create_text(left_edge + 1, self.mute_top, text='M', state='hidden', fill='red', anchor='nw', tags=('Mute:%d'%channel, 'edit_button', 'mutes'))
			self.balances_left[channel] = self.main_canvas.create_rectangle(left_edge, self.fader_top, int(fader_centre - 0.5), self.fader_top + self.balance_height, fill='dark green', width=0, tags=('Channel:%d'%channel, 'edit_button', 'mixer'))
			self.balances_right[channel] = self.main_canvas.create_rectangle(int(fader_centre + 0.5), self.fader_top, left_edge + self.fader_width - 1, self.fader_top + self.balance_height , fill='dark red', width=0, tags=('Channel:%d'%channel, 'edit_button', 'mixer'))

			self.draw_channel(channel)

		self.main_canvas.tag_bind('edit_button', '<ButtonPress-1>', self.on_edit_press)
		self.main_canvas.tag_bind('edit_button', '<ButtonRelease-1>', self.on_edit_release)
		self.main_canvas.tag_bind('fader_control', "<ButtonPress-1>", self.on_fader_press)
		self.main_canvas.tag_bind('fader_control', '<ButtonRelease-1>', self.on_fader_release)
		self.main_canvas.tag_bind('fader_control', '<B1-Motion>', self.on_fader_motion)

		# 0dB line
		self.main_canvas.create_line(0, self.fader_top + self.fader_height * 0.2, self.width, self.fader_top + self.fader_height * 0.2, fill="white", tags=('mixer'))

		# Edit widgets
		balance_control_bg = self.main_canvas.create_rectangle(self.balance_control_centre - self.balance_control_width, self.fader_top, self.balance_control_centre + self.balance_control_width, self.fader_top + self.fader_width, fill=zynthian_gui_config.color_bg, width=0, state='hidden', tags=('edit_control','balance_control'))
		self.balance_control_left = self.main_canvas.create_rectangle(int(self.balance_control_centre - self.balance_control_width), self.fader_top, self.balance_control_centre, self.fader_top + self.fader_width, fill='dark green', width=0, state='hidden', tags=('edit_control','balance_control'))
		self.balance_control_right = self.main_canvas.create_rectangle(self.balance_control_centre, self.fader_top, self.balance_control_centre + self.balance_control_width, self.fader_top + self.fader_width, fill='dark red', width=0, state='hidden', tags=('edit_control','balance_control'))
		self.main_canvas.tag_bind('balance_control', "<ButtonPress-1>", self.on_balance_press)
		self.main_canvas.tag_bind('balance_control', "<ButtonRelease-1>", self.on_balance_release)
		self.main_canvas.tag_bind('balance_control', "<B1-Motion>", self.on_balance_motion)
		self.main_canvas.create_line(0, self.fader_top + self.fader_height * 0.2, self.fader_width, self.fader_top + self.fader_height * 0.2, fill="white", tags=('edit_control'), state='hidden')

		self.mute_button_text = self.main_canvas.create_text(1 + int(self.fader_width * 1.5), int(self.edit_height / 2), fill='white', text="MUTE", state='hidden', tags=('edit_control'))
		self.layer_button_text = self.main_canvas.create_text(1 + int(self.fader_width * 2.5), int(self.edit_height / 2), fill='white', text="LAYER", state='hidden', tags=('edit_control'))
		self.cancel_edit_button_text = self.main_canvas.create_text(1 + int(self.fader_width * 3.5), int(self.edit_height / 2), fill='white', text="CANCEL", state='hidden', tags=('edit_control'))
		self.main_canvas.tag_bind(self.mute_button_text, "<ButtonRelease-1>", self.on_mute_release)
		self.main_canvas.tag_bind(self.layer_button_text, "<ButtonRelease-1>", self.on_layer_release)
		self.main_canvas.tag_bind(self.cancel_edit_button_text, "<ButtonPress-1>", self.on_cancel_press)

		# Selection border
		self.selection_border = self.main_canvas.create_rectangle(1, 1, self.fader_width, self.height, width=2, outline=zynthian_gui_config.color_on)

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
			# Mixer mode so show channel in its mixer position
			if channel > 15:
				offset = 4 + channel * self.fader_width
			else:
				offset = 1 + channel * self.fader_width
		else:
			# Edit mode so show channel in left most position
			offset = 1
		self.main_canvas.coords(self.faders[channel], offset, self.fader_top + self.fader_height * (1 - zynmixer.get_level(channel)), offset + self.fader_width - 1, self.fader_bottom)
		mute_state = 'hidden'
		if zynmixer.get_mute(channel):
			mute_state = 'normal'
		self.main_canvas.itemconfig(self.mutes[channel], state=mute_state)

		balance = zynmixer.get_balance(channel)
		if balance > 0:
			self.main_canvas.coords(self.balances_left[channel],
				int(offset + balance * self.fader_width / 2), self.balance_top, 
				offset + self.fader_width / 2, self.balance_top + self.balance_height)
			self.main_canvas.coords(self.balances_right[channel], 
				int(offset + self.fader_width / 2), self.balance_top, 
				int(offset + self.fader_width), self.balance_top + self.balance_height)
		else:
			self.main_canvas.coords(self.balances_left[channel], 
				offset, self.balance_top,
				int(offset + self.fader_width / 2), self.balance_top + self. balance_height)
			self.main_canvas.coords(self.balances_right[channel], 
				offset + self.fader_width / 2, self.balance_top,
				offset + self.fader_width * balance / 2 + self.fader_width, self.balance_top + self.balance_height)
		if self.mode == 0:
			if balance > 0:
				self.main_canvas.coords(self.balance_control_left,
					int(self.balance_control_centre - (1 - balance) * self.balance_control_width), self.fader_top, 
					self.balance_control_centre, self.fader_top + self.fader_width)
				self.main_canvas.coords(self.balance_control_right, 
					self.balance_control_centre, self.fader_top, 
					self.balance_control_centre + self.balance_control_width, self.fader_top+ self.fader_width)
			else:
				self.main_canvas.coords(self.balance_control_left, 
					self.balance_control_centre - self.balance_control_width, self.fader_top,
					self.balance_control_centre, self.fader_top + self.fader_width)
				self.main_canvas.coords(self.balance_control_right, 
					self.balance_control_centre, self.fader_top,
					self.balance_control_centre + (1 + balance) * self.balance_control_width, self.fader_top + self.fader_width)
		self.main_canvas.coords(self.mutes[channel], offset + 2, self.mute_top)


	# Function to display selected channel highlight border
	# channel: Index of channel to highlight
	def highlight_channel(self, channel):
		self.main_canvas.coords(self.selection_border, 1 + self.fader_width * channel, 1, 2 + self.fader_width * (channel + 1), self.height - 1)


	# Function to select channel
	# channel: Idex of channel to select
	def select_channel(self, channel):
		if channel > 16 or channel < 0:
			return
		self.selected_channel = channel
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_BACK, self.selected_channel, 0)
		self.highlight_channel(channel)

	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.drag_start = event
		try:
			sel = int(self.main_canvas.find_withtag(tkinter.CURRENT)[0])
			channel = int(self.main_canvas.gettags(sel)[0].split(':')[1])
		except:
			return
		self.select_channel(channel)


	# Function to handle fader release
	#	event: Mouse event
	def on_fader_release(self, event):
		pass


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.selected_channel == None:
			return
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
		balance = zynmixer.get_balance(self.selected_channel) + (event.x - self.balance_drag_start.x) / self.balance_control_width
		if balance > 1: balance = 1
		if balance < -1: balance = -1
		self.balance_drag_start = event
		zynmixer.set_balance(self.selected_channel, balance)


	# Function to handle edit button press
	#	event: Mouse event
	def on_edit_press(self, event):
		self.press_time = monotonic()
		try:
			sel = int(self.main_canvas.find_withtag(tkinter.CURRENT)[0])
			channel = int(self.main_canvas.gettags(sel)[0].split(':')[1])
		except:
			return
		self.select_channel(channel)


	# Function to handle edit button release
	#	event: Mouse event
	def on_edit_release(self, event):
		if self.press_time:
			self.press_time = None
		else:
			return
		zynmixer.toggle_mute(self.selected_channel)


	# Function to toggle edit / mixer mode
	#	channel: Index of channel to edit or None to show mixer
	def set_mode(self, channel):
		if channel != None:
			# Change to edit mode
			self.mode = 0
			self.edit_channel = channel
			self.main_canvas.itemconfig('mixer', state='hidden')
			self.main_canvas.itemconfig('mutes', state='hidden')
			self.main_canvas.itemconfig(self.selection_border, state='hidden')
			if channel > 15:
				self.main_canvas.itemconfig(self.legends[0], text='Master', state='normal')
			else:
				self.main_canvas.itemconfig(self.legends[0], text='Layer %d'%(channel + 1), state='normal')
			self.main_canvas.coords('Channel:%d'%(channel), 1, self.fader_top, self.fader_width, self.fader_bottom)
			self.draw_channel(channel)
			self.main_canvas.itemconfig('Channel:%d'%(channel), state='normal')
			self.main_canvas.itemconfig('edit_control', state='normal')
			self.main_canvas.tag_unbind('edit_button', '<ButtonPress-1>')
			self.main_canvas.tag_unbind('edit_button', '<ButtonRelease-1>')
			self.main_canvas.tag_bind(self.edit_buttons[0], '<ButtonPress-1>', self.on_edit_release)
			self.main_canvas.tag_bind(self.edit_buttons[1], '<ButtonPress-1>', self.on_mute_release)
			self.main_canvas.tag_bind(self.edit_buttons[2], '<ButtonPress-1>', self.on_layer_release)
			self.main_canvas.tag_bind(self.edit_buttons[3], '<ButtonPress-1>', self.on_cancel_press)
			self.selected_channel = channel
		else:
			# Change to mixer mode
			self.mode = 1
			self.edit_channel = None
			self.main_canvas.itemconfig('edit_control', state='hidden')
			self.main_canvas.itemconfig(self.legends[0], text='Layer 1')
			self.main_canvas.coords('Channel:%d'%(self.selected_channel), 1 + self.fader_width * self.selected_channel, self.fader_top, 1 + self.fader_width * self.selected_channel + self.fader_width - 1, self.fader_bottom)
			self.draw_channel(self.selected_channel)
			self.main_canvas.itemconfig('mixer', state='normal')
			self.main_canvas.itemconfig(self.selection_border, state='normal')
			self.main_canvas.tag_lower('background')
			for button in self.edit_buttons:
				# Because we bind to the index (not the tag) we must unbind the index for each button
				self.main_canvas.tag_unbind(button, '<ButtonPress-1>')
			self.main_canvas.tag_bind('edit_button', '<ButtonPress-1>', self.on_edit_press)
			self.main_canvas.tag_bind('edit_button', '<ButtonRelease-1>', self.on_edit_release)


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		zynmixer.toggle_mute(self.selected_channel)


	# Function to handle layer button release
	#	event: Mouse event
	def on_layer_release(self, event):
		self.zyngui.show_screen('layer') #TODO: Show relevant layer control screen


	# Function to handle cancel edit button release
	#	event: Mouse event
	def on_cancel_press(self, event):
		self.set_mode(None)


	def show(self):
		super().show()
		self.set_mode(None)
		zyncoder.lib_zyncoder.setup_zyncoder(ENC_BACK, zynthian_gui_config.zyncoder_pin_a[ENC_BACK], zynthian_gui_config.zyncoder_pin_b[ENC_BACK], 0, 0, None, self.selected_channel, 16, 0)
		zyncoder.lib_zyncoder.setup_zyncoder(ENC_SELECT, zynthian_gui_config.zyncoder_pin_a[ENC_SELECT], zynthian_gui_config.zyncoder_pin_b[ENC_SELECT], 0, 0, None, 64, 127, 0)
		zyncoder.lib_zyncoder.setup_zyncoder(ENC_SNAPSHOT, zynthian_gui_config.zyncoder_pin_a[ENC_SNAPSHOT], zynthian_gui_config.zyncoder_pin_b[ENC_SNAPSHOT], 0, 0, None, 64, 127, 0)


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
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_BACK, self.selected_channel - 1, 0)


	# Function to handle CUIA LAYER_UP command
	def layer_up(self):
		zyncoder.lib_zyncoder.set_value_zyncoder(ENC_LAYER, 63, 0)


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
			level = zynmixer.get_level(self.selected_channel) + (value - 64) * 0.01
			if level > 1: level = 1
			if level < 0: level = 0
			zynmixer.set_level(self.selected_channel, level)
		value = zyncoder.lib_zyncoder.get_value_zyncoder(ENC_SNAPSHOT)
		if(value != 64):
			zyncoder.lib_zyncoder.set_value_zyncoder(ENC_SNAPSHOT, 64, 0)
			balance = zynmixer.get_balance(self.selected_channel) + (value - 64) * 0.01
			if balance > 1: balance = 1
			if balance < -1: balance = -1
			zynmixer.set_balance(self.selected_channel, balance)


	# Function to handle SELECT switch
	# mode: Switch mode ('S'|'B'|'L')
	def switch_select(self, mode):
		zynmixer.toggle_mute(self.selected_channel)


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
				self.set_mode(self.selected_channel)

