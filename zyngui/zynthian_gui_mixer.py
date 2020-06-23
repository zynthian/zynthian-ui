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
from datetime import datetime
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
		self.fader_width = (self.width - 4 ) / 18
		self.fader_height = self.height - 10

		# Faders
		self.channel_faders = [None] * 16
		self.selected_fader = None

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=self.height,
			width=self.width,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_bg)
		self.main_canvas.grid()

		# Draw faders
		for fader in range(16):
			self.channel_faders[fader] = self.main_canvas.create_rectangle(1 + fader * self.fader_width, 1, 1 + (fader + 1) * self.fader_width - 1, self.fader_height, fill='grey')
			self.main_canvas.tag_bind(self.channel_faders[fader], "<ButtonPress-1>", self.on_fader_press)
			self.main_canvas.tag_bind(self.channel_faders[fader], "<ButtonRelease-1>", self.on_fader_release)
			self.main_canvas.tag_bind(self.channel_faders[fader], "<B1-Motion>", self.on_fader_motion)


	# Function to set fader values
	#	fader: Index of fader
	#	value: Fader value (0..1)
	def set_fader(self, fader, value):
		if fader > len(self.channel_faders) or value < 0 or value > 1:
			return
		zynmixer.set_level(fader, value)
		self.main_canvas.coords(self.channel_faders[fader], fader * self.fader_width, self.fader_height * value, (fader + 1) * self.fader_width - 1, self.fader_height)


	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.drag_start = event
		try:
			sel = int(self.main_canvas.find_withtag(tkinter.CURRENT)[0])
		except:
			return
		for fader in range(len(self.channel_faders)):
			if sel == self.channel_faders[fader]:
				self.selected_fader = fader
				return


	# Function to handle fader release
	#	event: Mouse event
	def on_fader_release(self, event):
		pass


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.selected_fader == None:
			return
		if event.y > self.fader_height or event.y < 0:
			return
		level = 1 - ((self.fader_height - event.y) / self.fader_height)
		self.set_fader(self.selected_fader, level)


	# Function to refresh loading animation
	def refresh_loading(self):
		pass


	# Function to handle zyncoder polling
	def zyncoder_read(self):
		pass